from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from app.h2_product_program.contracts import H2Job, H2ProgramError, ProgramPaths
from app.h2_product_program.io import (
    sha256_file,
    write_csv_atomic,
    write_json_atomic,
    write_yaml_atomic,
)
from app.h2_product_program import reporting


def _paths(tmp_path: Path) -> ProgramPaths:
    root = tmp_path / "tool"
    root.mkdir()
    config = root / "config.yaml"
    config.write_text("seed: 3800\n", encoding="utf-8")
    return ProgramPaths(
        evaluation_root=root,
        workspace=tmp_path / "workspace",
        results_root=tmp_path / "results",
        summary_root=tmp_path / "summary",
        config_path=config,
    )


def _job(job_id: str, kind: str, *, optional: bool = False) -> H2Job:
    return H2Job(
        job_id=job_id,
        phase_index=7 if kind in {"analysis", "collection"} else 1,
        phase_name="FREEZE_HELDOUT" if kind in {"analysis", "collection"} else "TEST",
        job_kind=kind,
        split="none" if kind in {"analysis", "collection"} else "development",
        pipeline_id="NOT_APPLICABLE"
        if kind in {"analysis", "collection"}
        else "fullpipe_v1_ag_dr_ir",
        configuration_id=job_id.upper(),
        mode="NOT_APPLICABLE"
        if kind in {"analysis", "collection"}
        else "H2_SESSION_MEMORY_ENHANCED",
        case_ids=(),
        audio_duration_sec=0.0,
        runtime_tuning={},
        optional=optional,
    )


def test_scheduled_analysis_blocks_incomplete_evidence_but_manual_analysis_is_partial(
    tmp_path: Path,
) -> None:
    paths = _paths(tmp_path)
    jobs = (
        _job("required", "runtime_qualification"),
        _job("analysis", "analysis"),
        _job("collection", "collection"),
    )
    state = {
        "status": "RUNNING",
        "protocol_id": "protocol",
        "protocol_sha256": "a" * 64,
        "job_manifest_sha256": "b" * 64,
        "jobs": {
            "required": {"state": "PENDING"},
            "analysis": {"state": "RUNNING"},
            "collection": {"state": "PENDING"},
        },
    }

    with pytest.raises(H2ProgramError, match="requires complete evidence"):
        reporting.execute_analysis(paths, state=state, jobs=jobs, require_complete=True)

    partial = reporting.execute_analysis(
        paths, state=state, jobs=jobs, require_complete=False
    )
    payload = reporting.read_json(Path(str(partial["result_path"])))
    assert partial["status"] == "PARTIAL_NOT_PROMOTABLE"
    assert payload["complete_status_claimed"] is False
    assert payload["blocker_count"] == 1
    assert not (paths.summary_root / "REPORT.md").exists()


def test_result_root_resolution_accepts_file_and_directory(tmp_path: Path) -> None:
    root = tmp_path / "result"
    root.mkdir()
    result = root / "job_result.json"
    write_json_atomic(result, {"status": "COMPLETE"})

    assert reporting.resolve_runtime_result_root(result) == root.resolve()
    assert reporting.resolve_runtime_result_root(root) == root.resolve()


def test_default_mode_comes_only_from_checksum_frozen_development_selection() -> None:
    unsigned = {
        "schema_version": "h2-development-default-mode-selection.v1",
        "status": "COMPLETE",
        "development_only": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
        "common_metric_priority": [
            "wrong_known_time_sec",
            "stranger_false_known_time_sec",
        ],
        "selected_default_mode": "H2_SESSION_ANONYMOUS",
    }
    selection = {
        **unsigned,
        "selection_identity_sha256": reporting.canonical_sha256(unsigned),
    }
    selected, reason = reporting._default_mode_recommendation(
        {
            "default_product_mode": "H2_SESSION_ANONYMOUS",
            "default_product_mode_selection": selection,
        }
    )

    assert selected == "H2_SESSION_ANONYMOUS"
    assert "before held-out evaluation" in reason
    assert "confirmation evidence only" in reason

    invalid = dict(selection)
    invalid["selected_default_mode"] = "H2_SESSION_MEMORY_ENHANCED"
    selected, _reason = reporting._default_mode_recommendation(
        {
            "default_product_mode": "H2_SESSION_MEMORY_ENHANCED",
            "default_product_mode_selection": invalid,
        }
    )
    assert selected is None


def test_fine_tuning_assessment_requires_measured_diagnostics_but_not_error_free_models() -> (
    None
):
    mode_rows = (
        {
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "metric_id": "wer",
            "metric_status": "computed",
            "metric_scope": "END_TO_END",
            "value": 0.21,
        },
        {
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "metric_id": "wrong_known_time_sec",
            "metric_status": "computed",
            "metric_scope": "END_TO_END",
            "value": 1.25,
        },
    )
    segmentation_rows = (
        {
            "configuration_id": "SEG_SELECTED",
            "metric_id": "miss_rate",
            "metric_status": "computed",
            "value": 0.12,
        },
    )

    answer, evidence = reporting._fine_tuning_assessment(
        mode_rows,
        segmentation_rows,
        selected_segmentation_id="SEG_SELECTED",
    )

    assert answer == "NO_FINE_TUNING_CURRENTLY_JUSTIFIED"
    assert "enhanced end-to-end WER=0.21" in evidence
    assert "selected segmentation miss rate=0.12" in evidence
    assert "adapted-vs-frozen causal comparison" in evidence

    answer, evidence = reporting._fine_tuning_assessment(
        (), (), selected_segmentation_id=None
    )
    assert answer == "INSUFFICIENT_EVIDENCE_TO_JUSTIFY_FINE_TUNING"
    assert "no neural adaptation claim" in evidence


def test_current_app_validation_binds_test_and_source_hashes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    paths.workspace.mkdir(parents=True)
    test_path = paths.evaluation_root / "tests/full_pipeline_demo/test_ui.py"
    source_path = paths.evaluation_root / "app/full_pipeline_demo/ui.py"
    handler_path = paths.evaluation_root / "app/h2_product_program/controller.py"
    test_path.parent.mkdir(parents=True)
    source_path.parent.mkdir(parents=True)
    handler_path.parent.mkdir(parents=True)
    test_path.write_text("def test_ui():\n    assert True\n", encoding="utf-8")
    source_path.write_text("UI_READY = True\n", encoding="utf-8")
    handler_path.write_text("APP_VALIDATION = True\n", encoding="utf-8")
    protocol_sha = "a" * 64
    implementation_sha = "b" * 64
    write_json_atomic(
        paths.protocol_path,
        {"protocol_id": "test-protocol", "protocol_sha256": protocol_sha},
    )
    write_json_atomic(
        paths.workspace / "runtime_implementation_identity.json",
        {"identity_sha256": implementation_sha},
    )
    test_logical = "tests/full_pipeline_demo/test_ui.py"
    source_logical = "app/full_pipeline_demo/ui.py"
    job = _job("app_validation", "app_validation")
    document = {
        "schema_version": "h2-app-validation-result.v1",
        "status": "COMPLETE",
        "job_id": job.job_id,
        "job_identity_sha256": job.identity_sha256,
        "protocol_id": "test-protocol",
        "protocol_sha256": protocol_sha,
        "runtime_implementation_identity_sha256": implementation_sha,
        "handler_source_path": "app/h2_product_program/controller.py",
        "handler_source_sha256": sha256_file(handler_path),
        "model_free": True,
        "neural_inference_performed": False,
        "physical_microphone_performance_claimed": False,
        "controlled_or_mocked_device_behavior_only": True,
        "validation": {
            "status": "PASS",
            "passed_count": 1,
            "failed_count": 0,
            "python_compile_passed": True,
            "ruff_check_passed": True,
        },
        "test_hashes": {test_logical: sha256_file(test_path)},
        "source_hashes": {source_logical: sha256_file(source_path)},
        "capabilities": {
            "embedding_inspector": {
                "status": "PASS",
                "test_paths": [test_logical],
                "source_paths": [source_logical],
            }
        },
    }
    result_path = tmp_path / "app_validation.json"
    write_json_atomic(result_path, document)
    artifact = reporting.ResultArtifact(
        job=job,
        state_row={"state": "COMPLETE"},
        path=result_path,
        root=result_path.parent,
        artifact_kind="file",
        sha256=sha256_file(result_path),
        document=document,
        validated=True,
    )
    artifacts = {artifact.job.job_id: artifact}

    complete, _reason = reporting._preserved_targeted_test_evidence(
        paths,
        artifacts,
        capability_id="embedding_inspector",
        required_test_suffixes=(test_logical,),
        required_sources=(source_logical,),
    )
    assert complete is True

    source_path.write_text("UI_READY = False\n", encoding="utf-8")
    complete, reason = reporting._preserved_targeted_test_evidence(
        paths,
        artifacts,
        capability_id="embedding_inspector",
        required_test_suffixes=(test_logical,),
        required_sources=(source_logical,),
    )
    assert complete is False
    assert "source checksum differs" in reason


def test_policy_selection_compares_axis_values_not_json_substrings(
    tmp_path: Path,
) -> None:
    job = _job("policy", "policy_replay")
    root = tmp_path / "policy"
    root.mkdir()
    write_csv_atomic(
        root / "frontier.csv",
        (
            {"hysteresis": 0.01, "confirmations": 1, "risk": 0.2},
            {"hysteresis": 0.02, "confirmations": 2, "risk": 0.1},
        ),
        ("hysteresis", "confirmations", "risk"),
    )
    primary = root / "job_result.json"
    write_json_atomic(primary, {"status": "COMPLETE"})
    artifact = reporting.ResultArtifact(
        job=job,
        state_row={"state": "COMPLETE"},
        path=primary,
        root=root,
        artifact_kind="file",
        sha256=sha256_file(primary),
        document={"status": "COMPLETE"},
        validated=True,
    )

    rows = reporting._policy_rows(
        artifact,
        ("frontier.csv",),
        selected_record={
            "hysteresis": 0.02,
            "confirmations": 2,
            "risk": 0.1,
            "extra_metric": 99,
        },
        evidence_scope="TEST",
        parameter_keys=("hysteresis", "confirmations"),
    )

    assert {row["policy_id"] for row in rows if row["selected"]} == {"POLICY:2"}


def test_reuse_parity_reporting_accepts_measured_scientific_rejection(
    tmp_path: Path,
) -> None:
    required_outputs = {
        "embedding_cosine_agreement": 1.0,
        "maximum_absolute_error": 0.0,
        "score_agreement": True,
        "top1_agreement": True,
        "top2_agreement": True,
        "margin_agreement": True,
        "known_unknown_decision_agreement": True,
        "cluster_assignment_agreement": True,
        "transcript_label_agreement": True,
        "event_sequence_semantic_agreement": True,
    }

    def artifact(
        strategy: str, *, status: str, qualified: bool, parity_passed: bool
    ) -> reporting.ResultArtifact:
        job = H2Job(
            job_id=strategy.casefold(),
            phase_index=2,
            phase_name="REDIM_EXECUTION",
            job_kind="embedding_reuse_parity",
            split="development",
            pipeline_id="fullpipe_v1_ag_dr_ir",
            configuration_id=strategy,
            mode="H2_SESSION_MEMORY_ENHANCED",
            case_ids=(),
            audio_duration_sec=0.0,
            runtime_tuning={},
        )
        document = {
            "status": status,
            "bounded_exact_parity_executed": True,
            "required_parity_outputs_measured": True,
            "candidate_qualified": qualified,
            "parity_passed": parity_passed,
            **required_outputs,
        }
        path = tmp_path / f"{job.job_id}.json"
        write_json_atomic(path, document)
        return reporting.ResultArtifact(
            job=job,
            state_row={"state": "COMPLETE"},
            path=path,
            root=tmp_path,
            artifact_kind="file",
            sha256=sha256_file(path),
            document=document,
            validated=True,
        )

    r3 = artifact(
        "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        status="COMPLETE",
        qualified=True,
        parity_passed=True,
    )
    r4 = artifact(
        "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
        status="GATED_NOT_PROMOTED",
        qualified=False,
        parity_passed=False,
    )

    complete, reason = reporting._embedding_reuse_parity_complete(
        {r3.job.job_id: r3, r4.job.job_id: r4}
    )

    assert complete is True
    assert "only qualified strategies" in reason


def test_successive_halving_base_selection_marks_tier_results() -> None:
    selected = {"SEGMENTATION_FRONTIER_A"}

    assert reporting._configuration_is_selected(
        "SEGMENTATION_FRONTIER_A_FULL", selected
    )
    assert not reporting._configuration_is_selected(
        "SEGMENTATION_FRONTIER_B_FULL", selected
    )


def _write_valid_analysis_summary(summary: Path) -> None:
    summary.mkdir(parents=True, exist_ok=True)
    source_sha = "a" * 64
    for name in reporting.REQUIRED_CSV_FILES:
        fields = reporting._csv_fields_for(name)
        if name == "failure_inventory.csv":
            rows: tuple[dict[str, object], ...] = ()
        else:

            def measured_row() -> dict[str, object]:
                row = {field: "" for field in fields}
                row["schema_version"] = "test.v1"
                if "metric_id" in row:
                    row["metric_id"] = "measured_metric"
                if "metric_status" in row:
                    row["metric_status"] = "computed"
                if "status" in row:
                    row["status"] = "measured"
                if "source_result_sha256" in row:
                    row["source_result_sha256"] = source_sha
                if "selected" in row:
                    row["selected"] = True
                if "policy_id" in row:
                    row["policy_id"] = "selected-policy"
                if "measured" in row:
                    row["measured"] = True
                if "passed" in row:
                    row["passed"] = True
                return row

            if name in {
                "h2_hysteresis_results.csv",
                "h2_session_memory_results.csv",
                "h2_short_turn_results.csv",
            }:
                values = {
                    "h2_hysteresis_results.csv": (
                        "hysteresis_policy",
                        (
                            "H0_ONE_PASS_DIAGNOSTIC",
                            "H1_TWO_CONFIRM_TWO_RELEASE",
                            "H2A_ADAPTIVE_EARLY",
                            "H3_THREE_CONFIRM_SAFE",
                            "H4_DURATION_DEPENDENT",
                        ),
                        "identity_expiry_sec",
                        (15.0, 30.0, 60.0, 120.0, "end_of_session"),
                    ),
                    "h2_session_memory_results.csv": (
                        "memory_level",
                        (
                            "M0_STATELESS",
                            "M1_CLUSTER",
                            "M2_CONFIRMED_NAME",
                            "M3_SHORT_TURN",
                            "M4_ACTIVE_ROSTER_DECAY",
                            "M5_CLUSTER_RECONCILIATION",
                        ),
                        "identity_expiry_sec",
                        (15.0, 30.0, 60.0, 120.0, "end_of_session"),
                    ),
                    "h2_short_turn_results.csv": (
                        "short_turn_policy",
                        (
                            "FRESH_EMBEDDING_REQUIRED",
                            "ANONYMOUS_CLUSTER_INHERITANCE",
                            "CONFIRMED_NAME_INHERITANCE",
                            "INHERITANCE_WITH_CONTRADICTION_CHECKS",
                            "GENERIC_UNTIL_LATER_CORRECTION",
                        ),
                        "duration_bin",
                        ("LT_0P5", "GE_0P5_LT_1P0", "GE_1P0_LE_2P0"),
                    ),
                }[name]
                key, policies, cell_key, cells = values
                expanded: list[dict[str, object]] = []
                for policy in policies:
                    for cell in cells:
                        row = measured_row()
                        row["policy_id"] = f"{policy}:{cell}"
                        row["selected"] = policy == policies[0] and cell == cells[0]
                        row["parameters_json"] = reporting._json_text(
                            {key: policy, cell_key: cell}
                        )
                        expanded.append(row)
                rows = tuple(expanded)
            else:
                row = measured_row()
                if name == "h2_embedding_policy_results.csv":
                    row["metric_view"] = "embedding_clustering_coverage"
                    row["metric_id"] = "coverage_outcome"
                rows = (row,)
        write_csv_atomic(summary / name, rows, fields)
    configurations = []
    for configuration_id in reporting.FINAL_CONFIGURATION_IDS:
        configurations.append(
            {
                "configuration_id": configuration_id,
                "runtime_tuning": {"product_mode": "H2_SESSION_MEMORY_ENHANCED"},
                "runtime_tuning_identity_sha256": "b" * 64,
                "assets": [{"sha256": "c" * 64}],
            }
        )
    write_yaml_atomic(
        summary / "h2_configuration_registry.yaml",
        {
            "schema_version": "h2-configuration-registry.v1",
            "configurations": configurations,
        },
    )
    write_json_atomic(summary / "h2_linux_portability.json", {"status": "PREPARED"})
    write_json_atomic(
        summary / "h2_memory_budget.json", {"classification": "HIGH_RISK_FOR_2GB"}
    )
    write_json_atomic(
        summary / "historical_evidence_reconciliation.json",
        {
            "schema_version": "h2-historical-evidence-reconciliation.v1",
            "status": "COMPLETE",
            "historical_values_verified_against_machine_readable_artifacts": True,
            "historical_values_silently_replaced": False,
            "cross_protocol_deltas_used_for_selection": False,
            "rows": [
                {
                    "evidence_family": family,
                    "metric_id": "test_metric",
                    "historical_value": 0.5,
                    "historical_source_sha256": "d" * 64,
                    "historical_value_verified": True,
                    "comparability": "DESCRIPTIVE_ONLY_PROTOCOL_CHANGED",
                    "difference_explanation": "The protocols differ.",
                }
                for family in (
                    "FROZEN_H2_PRODUCT_V2",
                    "STANDALONE_PYANNOTE_REDIM",
                    "REDIM_ENROLLMENT_LIVE_V2",
                )
            ],
        },
    )
    write_json_atomic(
        summary / "analysis_manifest.json",
        {"schema_version": "h2-analysis-manifest.v1"},
    )
    write_json_atomic(
        summary / "REPRODUCIBILITY_MANIFEST.json",
        {
            "schema_version": "h2-reproducibility-manifest.v1",
            "weighted_composite_used": False,
        },
    )
    (summary / "REPORT.md").write_text(
        "# Report\n\nFinal status: `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`\n\n"
        "## Historical evidence reconciliation\n\n"
        "Why values differ or remain historical-only:\n",
        encoding="utf-8",
    )
    (summary / "METRIC_GUIDE.md").write_text("# Metrics\n", encoding="utf-8")


def test_required_analysis_output_schemas_are_validated(tmp_path: Path) -> None:
    summary = tmp_path / "summary"
    _write_valid_analysis_summary(summary)

    assert reporting.validate_analysis_outputs(summary)["status"] == "PASS"
    path = summary / "h2_mode_comparison.csv"
    path.write_text("wrong,column\n1,2\n", encoding="utf-8")
    with pytest.raises(H2ProgramError, match="schema differs"):
        reporting.validate_analysis_outputs(summary)


def test_package_policy_rejects_traversal_audio_secrets_and_biometric_vectors() -> None:
    with pytest.raises(H2ProgramError, match="unsafe package"):
        reporting._validate_package_member_name("../escape.json")
    with pytest.raises(H2ProgramError, match="forbidden package suffix"):
        reporting._validate_package_payload("raw/input.wav", b"not audio")
    with pytest.raises(H2ProgramError, match="secret"):
        reporting._validate_package_payload(
            "summary/config.json", b'{"api_key":"sk-abcdefghijklmnopqrstuvwxyz1234"}'
        )
    with pytest.raises(H2ProgramError, match="biometric vector"):
        reporting._validate_package_payload(
            "summary/result.json", b'{"speaker_embeddings":[0.1,0.2]}'
        )


def _write_valid_stage(stage: Path) -> tuple[reporting.PackageMember, ...]:
    summary = stage / "summary"
    _write_valid_analysis_summary(summary)
    write_json_atomic(summary / "cache_inventory.json", {"entries": []})
    write_csv_atomic(
        summary / "result_file_inventory.csv",
        (),
        reporting.RESULT_INVENTORY_FIELDS,
    )
    write_json_atomic(
        summary / "evidence_table.json",
        {
            "schema_version": "h2-final-evidence-table.v1",
            "collection_status": "VALID",
            "rows": [
                {
                    "label": label,
                    "status": "VALID",
                    "acceptable": True,
                    "evidence": "test",
                }
                for label in reporting.EVIDENCE_LABELS
            ],
        },
    )
    write_json_atomic(summary / "analysis_receipt.json", {"status": "COMPLETE"})
    frozen = summary / "frozen_configurations"
    for name in (
        "H2_KNOWN_ONLY.json",
        "H2_SESSION_ANONYMOUS.json",
        "H2_SESSION_MEMORY_ENHANCED.json",
    ):
        write_json_atomic(frozen / name, {"status": "FROZEN"})
    deployment = stage / "deployment/h2_arm64"
    deployment.mkdir(parents=True)
    for name in reporting.ARM64_PACKAGE_FILES:
        (deployment / name).write_text(f"safe fixture: {name}\n", encoding="utf-8")
    members = tuple(
        reporting.PackageMember(
            member=path.relative_to(stage).as_posix(),
            source=path,
            category="test",
        )
        for path in sorted(stage.rglob("*"))
        if path.is_file()
    )
    reporting._write_package_metadata(
        stage,
        state={
            "protocol_id": "protocol",
            "protocol_sha256": "a" * 64,
            "job_manifest_sha256": "b" * 64,
            "jobs": {},
        },
        members=members,
    )
    return members


def test_package_manifests_and_zip_are_deterministic_and_self_validating(
    tmp_path: Path,
) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    members = _write_valid_stage(stage)
    first_manifest = (stage / "PACKAGE_MANIFEST.json").read_bytes()
    first_checksums = (stage / "PACKAGE_CHECKSUMS.json").read_bytes()
    reporting._write_package_metadata(
        stage,
        state={
            "protocol_id": "protocol",
            "protocol_sha256": "a" * 64,
            "job_manifest_sha256": "b" * 64,
            "jobs": {},
        },
        members=members,
    )
    assert (stage / "PACKAGE_MANIFEST.json").read_bytes() == first_manifest
    assert (stage / "PACKAGE_CHECKSUMS.json").read_bytes() == first_checksums
    assert reporting.validate_staged_package(stage)["status"] == "PASS"

    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert reporting.create_deterministic_zip(stage, first) == sha256_file(first)
    assert reporting.create_deterministic_zip(stage, second) == sha256_file(second)
    assert first.read_bytes() == second.read_bytes()
    assert reporting.validate_package_zip(first)["status"] == "VALID"

    with zipfile.ZipFile(second, "a") as archive:
        archive.writestr("../escape.json", "{}")
    with pytest.raises(H2ProgramError, match="unsafe package"):
        reporting.validate_package_zip(second)
