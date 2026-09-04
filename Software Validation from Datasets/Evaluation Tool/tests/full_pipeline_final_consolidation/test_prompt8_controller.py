from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    FUTURE_LINUX_ARM64_VALIDATION,
    FUTURE_TARGET_HARDWARE_TESTS,
    classify_linux_arm64,
    classify_two_gib,
    evidence,
    load_deployment_steering,
    steering_ref,
    unknown_evidence,
)
from app.full_pipeline_final_consolidation import (
    COMPLETION_MARKERS,
    DEFAULT_ADAPTER_REGISTRY,
    DEFAULT_AMENDMENT,
    DEFAULT_EXECUTION_POLICY_ADDENDUM,
    DEFAULT_LICENSE_DOCUMENT,
    DEFAULT_MATRIX,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_RUNTIME,
    FINAL_OUTPUTS,
    MANDATORY_EXTENDED_ANCHORS,
    PI_CANDIDATE_FIELDS,
    REQUIRED_STAGE_BASENAMES,
    SCOPE_CLASS,
    SCOPE_ID,
)
from app.full_pipeline_final_consolidation.controller import (
    _update_program_state,
    _validate_final_outputs,
    _validate_runtime_material_layout,
    _write_immutable_snapshot,
    layout,
    request_stop,
    run_all,
    status,
    validate_final_completion,
)
from app.full_pipeline_final_consolidation import controller as controller_module
from app.full_pipeline_final_consolidation.analysis import _adaptation_candidate
from app.full_pipeline_final_consolidation.evidence import (
    ArtifactEvidence,
    EvidenceBundle,
    _expand_checksum_inventories,
    _validate_execution_policy,
    validate_completion,
)
from app.full_pipeline_final_consolidation.io import (
    FinalConsolidationError,
    IncompleteEvidenceError,
    ProductionCandidateError,
    blocked_status,
    deterministic_zip,
    read_json,
    sha256_file,
    validate_zip,
)
from app.full_pipeline_final_consolidation.pi_handoff import (
    _scientifically_credible as pi_scientifically_credible,
    build_pi_handoff,
    validate_pi_handoff,
)
from app.full_pipeline_final_consolidation.ranking import (
    _license_component_evidence,
    _needs_review,
    _number,
    build_rankings,
)
from app.full_pipeline_production_hardening.pi_shortlist import (
    build_pi_shortlist as build_prompt7_pi_shortlist,
)


SYNTHETIC_PROMPT8_ADAPTER_ID = "synthetic_prompt8_finalizer"
SYNTHETIC_PROMPT8_ADAPTER_SHA256 = "8" * 64


def test_synthetic_prompt8_end_to_end_is_bounded_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("JP8_ADAPTER_ID", raising=False)
    monkeypatch.delenv("JP8_ADAPTER_CONTRACT_SHA256", raising=False)
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "chain", pipeline_ids)
    state = _program_state(tmp_path / "PROGRAM_STATE.json", chain)
    pre_prompt8_state = _read_json(state)
    _install_synthetic_prerequisites(monkeypatch, chain, state, pipeline_ids)
    workspace = tmp_path / "prompt8_workspace"
    output = tmp_path / "final_reports"
    zip_path = tmp_path / "full_pipeline_program_reduced_8day_v1.zip"

    first = run_all(
        workspace_root=workspace,
        output_root=output,
        zip_path=zip_path,
        prompt7_marker=chain[7],
        amendment_path=DEFAULT_AMENDMENT,
        execution_policy_path=DEFAULT_EXECUTION_POLICY_ADDENDUM,
        adapter_registry_path=DEFAULT_ADAPTER_REGISTRY,
        program_state_path=state,
        matrix_path=DEFAULT_MATRIX,
        runtime_path=DEFAULT_RUNTIME,
        license_document_path=DEFAULT_LICENSE_DOCUMENT,
    )
    assert first["status"] == "PASS"
    assert first["completion_marker"] == COMPLETION_MARKERS[8]
    assert Path(str(first["compact_zip_path"])).is_file()
    assert set(path.name for path in output.iterdir()) == set(FINAL_OUTPUTS)
    assert "COMPLETE_FULL_PIPELINE_PROGRAM`" in (
        output / "FINAL_PIPELINE_REPORT.md"
    ).read_text(encoding="utf-8")
    assert "does not claim" in (output / "FINAL_PIPELINE_REPORT.md").read_text(
        encoding="utf-8"
    )
    ranking_rows = _read_csv(output / "FINAL_PIPELINE_RANKING.csv")
    assert len(ranking_rows) == 18
    assert all(not row["weighted_composite_score"] for row in ranking_rows)
    assert {row["selected_role"] for row in ranking_rows} >= {"PRIMARY", "FALLBACK"}
    reproducibility = _read_json(output / "REPRODUCIBILITY_MANIFEST.json")
    priority_mapping = reproducibility["selection_policy"][
        "technical_priority_metric_mapping"
    ]
    assert [row["rank"] for row in priority_mapping] == list(range(1, 13))
    assert priority_mapping[10]["output_metrics"] == [
        "reliability_failure_count",
        "total_rtf",
    ]
    assert priority_mapping[11]["output_metrics"] == [
        "mean_cpu_percent",
        "peak_rss_bytes",
        "model_bytes",
    ]
    assert first["fine_tuning_decision"] == "POLICY_CHANGE_ONLY"
    assert (
        "CHECKSUM_BOUND_AGGREGATE_HELDOUT_EXPOSURE_POLICY_ONLY_"
        "NOT_NEURAL_ADAPTATION_EVIDENCE"
        in (output / "FINE_TUNING_CANDIDATES.md").read_text(encoding="utf-8")
    )

    completion_sha = sha256_file(workspace / "completion_marker.json")
    zip_sha = sha256_file(zip_path)
    # Simulate the crash window after durable completion but before PROGRAM_STATE
    # advancement, while retaining a stale failure from the interrupted attempt.
    _write_json(state, pre_prompt8_state)
    _write_json(
        workspace / "failure.json",
        {"schema_version": "synthetic-failure.v1", "status": "FAILED"},
    )
    second = run_all(
        workspace_root=workspace,
        output_root=output,
        zip_path=zip_path,
        prompt7_marker=chain[7],
        amendment_path=DEFAULT_AMENDMENT,
        execution_policy_path=DEFAULT_EXECUTION_POLICY_ADDENDUM,
        adapter_registry_path=DEFAULT_ADAPTER_REGISTRY,
        program_state_path=state,
        matrix_path=DEFAULT_MATRIX,
        runtime_path=DEFAULT_RUNTIME,
        license_document_path=DEFAULT_LICENSE_DOCUMENT,
    )
    assert second["status"] == "PASS"
    assert second["recovered_or_reused"] is True
    assert sha256_file(workspace / "completion_marker.json") == completion_sha
    assert sha256_file(zip_path) == zip_sha
    assert not (workspace / "failure.json").exists()
    assert (
        _read_json(workspace / "failure_superseded_by_completion.json")["status"]
        == "SUPERSEDED_BY_VALIDATED_COMPLETION"
    )

    program_state = _read_json(state)
    assert program_state["status"] == COMPLETION_MARKERS[8]
    assert program_state["remaining_prompt_indices"] == []
    assert program_state["original_full_scope_complete"] is False
    assert program_state["prompt_8_completion_record_sha256"] == completion_sha

    validated = validate_final_completion(
        workspace_root=workspace,
        output_root=output,
        zip_path=zip_path,
        prompt7_marker=chain[7],
        program_state_path=state,
    )
    assert validated["status"] == "PASS"
    assert validated["primary"] == MANDATORY_EXTENDED_ANCHORS[0]
    assert validated["fallback"] == MANDATORY_EXTENDED_ANCHORS[1]

    ranking_rows[0]["weighted_composite_score"] = "0.123"
    _write_csv(output / "FINAL_PIPELINE_RANKING.csv", ranking_rows)
    with pytest.raises(FinalConsolidationError, match="ranking policy semantics"):
        _validate_final_outputs(output)
    ranking_rows[0]["weighted_composite_score"] = ""
    _write_csv(output / "FINAL_PIPELINE_RANKING.csv", ranking_rows)
    missing_license_row = next(
        row
        for row in ranking_rows
        if "MISSING_OR_UNSUPPORTED" in row["component_license_evidence"]
    )
    original_review_count = missing_license_row["component_license_review_count"]
    original_review_required = missing_license_row["component_license_review_required"]
    missing_license_row["component_license_review_count"] = 0
    missing_license_row["component_license_review_required"] = False
    _write_csv(output / "FINAL_PIPELINE_RANKING.csv", ranking_rows)
    with pytest.raises(FinalConsolidationError, match="licensing evidence/review"):
        _validate_final_outputs(output)
    missing_license_row["component_license_review_count"] = original_review_count
    missing_license_row["component_license_review_required"] = original_review_required
    _write_csv(output / "FINAL_PIPELINE_RANKING.csv", ranking_rows)
    pi_path = output / "RASPBERRY_PI_DEPLOYMENT_HANDOFF.json"
    pi_handoff = _read_json(pi_path)
    original_portability_class = pi_handoff["candidates"][0][
        "linux_arm64_portability_class"
    ]
    pi_handoff["candidates"][0]["linux_arm64_portability_class"] = (
        "WINDOWS_DESKTOP_IS_ARM_READY"
    )
    _write_json(pi_path, pi_handoff)
    with pytest.raises(ProductionCandidateError, match="Pi handoff identity differs"):
        _validate_final_outputs(output)
    pi_handoff["candidates"][0]["linux_arm64_portability_class"] = (
        original_portability_class
    )
    _write_json(pi_path, pi_handoff)
    manifest = _read_json(output / "REPRODUCIBILITY_MANIFEST.json")
    manifest["execution_time_policy"]["elapsed_time_kill_switch_enabled"] = True
    _write_json(output / "REPRODUCIBILITY_MANIFEST.json", manifest)
    with pytest.raises(FinalConsolidationError, match="reproducibility policy"):
        _validate_final_outputs(output)


def test_checksum_bound_report_tamper_is_rejected(tmp_path: Path) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "tamper_chain", pipeline_ids)
    p4 = validate_completion(
        chain[4],
        prompt_index=4,
        marker=COMPLETION_MARKERS[4],
        required_basenames=REQUIRED_STAGE_BASENAMES[4],
    )
    report = p4.one("development_report.md")
    report.write_text("tampered", encoding="utf-8")
    with pytest.raises(FinalConsolidationError, match="checksum inventory mismatch"):
        validate_completion(
            chain[4],
            prompt_index=4,
            marker=COMPLETION_MARKERS[4],
            required_basenames=REQUIRED_STAGE_BASENAMES[4],
        )


def test_reserved_original_marker_is_never_emitted(tmp_path: Path) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "marker_chain", pipeline_ids)
    record = _read_json(chain[7])
    record["completion_marker"] = "COMPLETE_PRODUCTION_CANDIDATE_HARDENING"
    _write_json(chain[7], record)
    with pytest.raises(FinalConsolidationError, match="completion_marker differs"):
        validate_completion(
            chain[7],
            prompt_index=7,
            marker=COMPLETION_MARKERS[7],
        )


def test_execution_policy_addendum_is_advisory_and_tamper_fails(tmp_path: Path) -> None:
    document = read_json(DEFAULT_EXECUTION_POLICY_ADDENDUM)
    _validate_execution_policy(document, amendment_path=DEFAULT_AMENDMENT)
    tampered = json.loads(json.dumps(document))
    tampered["execution_policy"]["elapsed_time_kill_switch_enabled"] = True
    with pytest.raises(FinalConsolidationError, match="advisory semantics"):
        _validate_execution_policy(tampered, amendment_path=DEFAULT_AMENDMENT)


def test_empty_checksum_inventory_fails_closed(tmp_path: Path) -> None:
    checksum = tmp_path / "checksums.json"
    _write_json(checksum, {"entries": {}})
    evidence = ArtifactEvidence(
        prompt_index=4,
        path=checksum,
        sha256=sha256_file(checksum),
        binding="universal_artifact_manifest",
        binding_path=checksum,
    )
    with pytest.raises(FinalConsolidationError, match="no nonempty entries"):
        _expand_checksum_inventories(4, (evidence,))


def test_duplicate_manifest_artifact_path_is_rejected(tmp_path: Path) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "duplicate_chain", pipeline_ids)
    completion = _read_json(chain[4])
    manifest_path = Path(str(completion["artifact_manifest"]["path"]))
    manifest = _read_json(manifest_path)
    manifest["artifacts"].append(dict(manifest["artifacts"][0]))
    _write_json(manifest_path, manifest)
    completion["artifact_manifest"]["sha256"] = sha256_file(manifest_path)
    _write_json(chain[4], completion)
    with pytest.raises(FinalConsolidationError, match="duplicate paths"):
        validate_completion(
            chain[4],
            prompt_index=4,
            marker=COMPLETION_MARKERS[4],
        )


def test_zero_rtf_remains_a_measured_zero() -> None:
    assert _number(0.0) == 0.0
    assert _number("0") == 0.0


def test_missing_or_unsupported_license_requires_review() -> None:
    assert _needs_review("MISSING_OR_UNSUPPORTED") == 1
    evidence_by_component = _license_component_evidence(
        SimpleNamespace(asr={}, diarization={}, diarization_embedding={}, identity={}),
        pipeline_id="synthetic",
        p6_document={},
        p7_document={},
    )
    assert set(evidence_by_component) == {
        "asr",
        "diarization",
        "diarization_embedding",
        "identity",
    }
    assert all(
        value == ["MISSING_OR_UNSUPPORTED"] for value in evidence_by_component.values()
    )
    assert (
        sum(
            _needs_review(value)
            for values in evidence_by_component.values()
            for value in values
        )
        == 4
    )


def test_pi_credibility_does_not_reuse_desktop_not_worth_label() -> None:
    row = {
        "selected_role": None,
        "pareto_frontier": False,
        "extended_evidence_status": "TESTED_IN_PREDECLARED_EXTENDED_SET",
        "overall_recommendation": "NOT_WORTH_CONTINUING",
        "wrong_known_time_sec": 0.1,
        "stranger_false_known_time_sec": 0.2,
        "reliability_failure_count": 0,
        "total_rtf": 0.8,
    }
    assert pi_scientifically_credible(row) is True
    row["total_rtf"] = 1.01
    assert pi_scientifically_credible(row) is False


def test_prestart_stop_is_durable_and_emits_no_completion(tmp_path: Path) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "stop_chain", pipeline_ids)
    workspace = tmp_path / "stopped_prompt8"
    request_stop(workspace_root=workspace)
    result = run_all(
        workspace_root=workspace,
        output_root=tmp_path / "unused_reports",
        zip_path=tmp_path / "unused.zip",
        prompt7_marker=chain[7],
    )
    paths = layout(
        workspace,
        output_root=tmp_path / "unused_reports",
        zip_path=tmp_path / "unused.zip",
    )
    assert result["status"] == "STOPPED"
    assert not paths.completion.exists()
    assert not paths.stop_request.exists()
    assert read_json(paths.stop_acknowledged)["disposition"] == (
        "STOPPED_BEFORE_COMPLETION"
    )


def test_immutable_prestate_and_mutation_guard_fail_closed(tmp_path: Path) -> None:
    snapshot = tmp_path / "prestate.json"
    original = {"status": COMPLETION_MARKERS[7], "value": 1}
    _write_immutable_snapshot(snapshot, original)
    _write_immutable_snapshot(snapshot, dict(original))
    with pytest.raises(FinalConsolidationError, match="snapshot differs"):
        _write_immutable_snapshot(snapshot, {**original, "value": 2})

    state = tmp_path / "PROGRAM_STATE.json"
    _write_json(state, original)
    with pytest.raises(FinalConsolidationError, match="changed after"):
        _update_program_state(
            state,
            completion_path=tmp_path / "not_needed.json",
            completion={},
            expected_pre_state_sha256="0" * 64,
        )


def test_zip_member_must_match_canonical_output_bytes(tmp_path: Path) -> None:
    root = tmp_path / "zip_root"
    root.mkdir()
    source = root / "only.txt"
    source.write_text("canonical", encoding="utf-8")
    package = tmp_path / "package.zip"
    deterministic_zip(package, root=root, members=("only.txt",))
    validate_zip(package, root=root, expected_members=("only.txt",))
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("only.txt", "tampered but CRC-valid")
    with pytest.raises(FinalConsolidationError, match="member bytes differ"):
        validate_zip(package, root=root, expected_members=("only.txt",))


def test_runtime_material_layout_is_exact_and_rejects_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = layout(
        tmp_path / "runtime_layout",
        output_root=tmp_path / "reports",
        zip_path=tmp_path / "reports.zip",
    )
    completion_inputs: list[Path] = []
    for prompt in (4, 5, 6, 7):
        path = tmp_path / f"prompt{prompt}" / "completion_marker.json"
        _write_json(
            path,
            {
                "schema_version": "full-pipeline-eight-day-stage-completion.v1",
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": False,
                "prompt_index": prompt,
                "completion_marker": COMPLETION_MARKERS[prompt],
            },
        )
        completion_inputs.append(path)
    exact_inputs = (
        DEFAULT_AMENDMENT,
        DEFAULT_EXECUTION_POLICY_ADDENDUM,
        DEFAULT_ADAPTER_REGISTRY,
        DEFAULT_PROGRAM_STATE,
        DEFAULT_MATRIX,
        DEFAULT_RUNTIME,
        DEFAULT_LICENSE_DOCUMENT,
        DEFAULT_PI_DEPLOYMENT_STEERING,
        *completion_inputs,
    )
    material = {
        "inputs": exact_inputs,
        "workspaces": (paths.root,),
        "temporary": (paths.root / "temp",),
        "logs": (paths.root / "controller.log", paths.progress),
        "results": (),
        "reports": (paths.output_root,),
        "packages": (
            paths.zip_path,
            paths.completion,
            paths.artifact_manifest,
            paths.input_binding,
            paths.pre_state_snapshot,
            paths.gates,
        ),
        "caches": (),
        "checkpoints": (),
    }
    adapter = SimpleNamespace(
        readiness="READY",
        material_paths=material,
        stage_workspace=paths.root,
        completion_record=paths.completion,
        progress_record=paths.progress,
        controller_log=paths.root / "controller.log",
    )
    configuration = SimpleNamespace(stages={8: adapter})
    monkeypatch.setattr(
        controller_module,
        "load_adapter_configuration",
        lambda _path: configuration,
    )
    _validate_runtime_material_layout(DEFAULT_ADAPTER_REGISTRY, paths)
    adapter.material_paths = {**material, "caches": (tmp_path / "cache",)}
    with pytest.raises(FinalConsolidationError, match="exact adapter material"):
        _validate_runtime_material_layout(DEFAULT_ADAPTER_REGISTRY, paths)
    adapter.material_paths = {
        **material,
        "inputs": (*exact_inputs, DEFAULT_MATRIX.parents[2]),
    }
    with pytest.raises(FinalConsolidationError, match="exact authorities"):
        _validate_runtime_material_layout(DEFAULT_ADAPTER_REGISTRY, paths)
    adapter.material_paths = {
        **material,
        "inputs": (*exact_inputs, exact_inputs[0]),
    }
    with pytest.raises(FinalConsolidationError, match="exact authorities"):
        _validate_runtime_material_layout(DEFAULT_ADAPTER_REGISTRY, paths)


def test_status_honors_custom_progress_record(tmp_path: Path) -> None:
    progress = tmp_path / "custom_progress.json"
    _write_json(progress, {"status": "RUNNING", "overall_percentage": 42.0})
    value = status(
        workspace_root=tmp_path / "status_workspace",
        output_root=tmp_path / "status_reports",
        zip_path=tmp_path / "status.zip",
        progress_record=progress,
    )
    assert value["status"] == "RUNNING"
    assert value["overall_percentage"] == 42.0


@pytest.mark.parametrize(
    ("tamper", "message", "error_type"),
    (
        ("winner", "final Pi winner", ProductionCandidateError),
        ("fifth_class", "deployment classes", ProductionCandidateError),
        ("missing_linux_test", "Linux ARM64 tests", ProductionCandidateError),
        ("membership", "candidate membership", ProductionCandidateError),
        ("desktop_source", "desktop roles source", IncompleteEvidenceError),
        ("pool_source", "frozen candidate pool", IncompleteEvidenceError),
    ),
)
def test_prompt7_pi_shortlist_tamper_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tamper: str,
    message: str,
    error_type: type[FinalConsolidationError],
) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / f"pi_{tamper}", pipeline_ids)
    state = _program_state(tmp_path / f"state_{tamper}.json", chain)
    bundle = _install_synthetic_prerequisites(monkeypatch, chain, state, pipeline_ids)
    path = bundle.completions[7].one("raspberry_pi_candidate_shortlist.json")
    value = _read_json(path)
    if tamper == "winner":
        value["final_raspberry_pi_winner"] = value["candidates"][0]["pipeline_id"]
        value["final_raspberry_pi_winner_claimed"] = True
    elif tamper == "fifth_class":
        value["candidates"][0]["two_gib_feasibility_class"] = (
            "UNKNOWN_INSUFFICIENT_EVIDENCE"
        )
    elif tamper == "missing_linux_test":
        value["future_linux_arm64_validation"] = value["future_linux_arm64_validation"][
            :-1
        ]
    elif tamper == "membership":
        value["candidates"][0]["pipeline_id"] = pipeline_ids[-1]
    elif tamper == "desktop_source":
        value["desktop_roles_source"]["sha256"] = "0" * 64
    else:
        value["candidate_pool_source"]["sha256"] = "0" * 64
    _write_json(path, value)
    with pytest.raises(error_type, match=message):
        build_pi_handoff(bundle, build_rankings(bundle))


def test_prompt5_deployment_source_hash_tamper_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "pi_source_hash", pipeline_ids)
    state = _program_state(tmp_path / "state_source_hash.json", chain)
    bundle = _install_synthetic_prerequisites(monkeypatch, chain, state, pipeline_ids)
    path = bundle.completions[5].one("all18_deployment_evidence.json")
    value = _read_json(path)
    value["pipelines"][0]["deployment_attributes"]["model_file_size_bytes"][
        "source_sha256"
    ] = "0" * 64
    _write_json(path, value)
    with pytest.raises(IncompleteEvidenceError, match="source SHA-256"):
        build_pi_handoff(bundle, build_rankings(bundle))


def test_actual_prompt7_shortlist_contract_is_consumable_by_prompt8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_ids = tuple(
        FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME).pipeline_ids
    )
    chain = _chain(tmp_path / "actual_prompt7_contract", pipeline_ids)
    state = _program_state(tmp_path / "state_actual_prompt7.json", chain)
    bundle = _install_synthetic_prerequisites(monkeypatch, chain, state, pipeline_ids)
    p5 = bundle.completions[5]
    p6 = bundle.completions[6]
    p7 = bundle.completions[7]
    extended_path = bundle.completions[4].one("extended_set.yaml")
    p5_deployment_path = p5.one("all18_deployment_evidence.json")
    p6_deployment_path = p6.one("extended_deployment_evidence.json")
    authorization = {
        "deployment_steering": steering_ref(
            DEFAULT_PI_DEPLOYMENT_STEERING,
            read_json(DEFAULT_PI_DEPLOYMENT_STEERING),
        ),
        "prompt5_deployment_evidence": {
            "path": str(p5_deployment_path),
            "sha256": sha256_file(p5_deployment_path),
        },
        "prompt6_deployment_evidence": {
            "path": str(p6_deployment_path),
            "sha256": sha256_file(p6_deployment_path),
        },
        "predeclared_extended_set": {
            "path": str(extended_path),
            "sha256": sha256_file(extended_path),
        },
        "predeclared_extended_pipeline_ids": list(MANDATORY_EXTENDED_ANCHORS),
    }
    desktop_selection = {
        "candidate_pool": list(MANDATORY_EXTENDED_ANCHORS),
        "roles": {
            "PRIMARY": MANDATORY_EXTENDED_ANCHORS[0],
            "FALLBACK": MANDATORY_EXTENDED_ANCHORS[1],
            "ALTERNATIVE": None,
        },
        "candidates": [
            {
                "pipeline_id": pipeline_id,
                "reliability_eligible": True,
                "technical_rank": index + 1,
                "pareto_frontier": index < 3,
                "production_role_eligible": index < 2,
            }
            for index, pipeline_id in enumerate(MANDATORY_EXTENDED_ANCHORS)
        ],
    }
    evidence_files = {
        name: p5.one(name)
        for name in (
            "all18_finalist_summary.csv",
            "all18_asr.csv",
            "all18_diarization.csv",
            "all18_identity.csv",
            "all18_speaker_attributed_transcript.csv",
            "all18_streaming.csv",
            "all18_resources.csv",
        )
    }
    actual = build_prompt7_pi_shortlist(
        authorization=authorization,
        desktop_selection=desktop_selection,
        evidence_files=evidence_files,
        desktop_roles_source=p7.one("production_candidate_catalog.yaml"),
    )
    _write_json(p7.one("raspberry_pi_candidate_shortlist.json"), actual)
    handoff = build_pi_handoff(bundle, build_rankings(bundle))
    assert {row["pipeline_id"] for row in handoff["candidates"]} == {
        row["pipeline_id"] for row in actual["candidates"]
    }
    assert (
        handoff["target_hardware_decision_boundary"][
            "final_raspberry_pi_winner_claimed"
        ]
        is False
    )


def test_final_pi_handoff_authority_and_candidate_field_tamper_fail() -> None:
    steering = read_json(DEFAULT_PI_DEPLOYMENT_STEERING)
    # A minimal invalid object is sufficient to prove the authority is checked
    # before any candidate is trusted.
    with pytest.raises(ProductionCandidateError, match="steering authority"):
        validate_pi_handoff({}, {**steering, "raspberry_pi_candidate_fields": []})


def test_exact_blocked_status_mapping() -> None:
    assert blocked_status(IncompleteEvidenceError("missing")) == (
        "BLOCKED_INCOMPLETE_EVIDENCE"
    )
    assert blocked_status(ProductionCandidateError("not ready")) == (
        "BLOCKED_PRODUCTION_CANDIDATE"
    )
    assert blocked_status(RuntimeError("unexpected")) == "BLOCKED_OTHER"


def test_single_failed_job_cannot_trigger_adaptation() -> None:
    row = {
        "pipeline_id": "fullpipe_v1_ao_dr_ir",
        "job_id": "identity_case_42",
        "status": "FAILED",
        "explicit_failure": "true",
        "component": "open_set_policy",
        "last_error": "held-out stranger false-known threshold exposure",
    }
    evidence_record = {
        "source_prompt": 5,
        "source_file": "C:\\synthetic\\all18_failures.csv",
        "source_row_index": 1,
        "pipeline_id": row["pipeline_id"],
        "case_or_job_id": row["job_id"],
        "component": "open_set_policy",
        "explicit_failure": True,
        "failure_reason_sha256": "a" * 64,
    }
    assert _adaptation_candidate(row, evidence_record) is None


def test_source_declared_reproducible_failure_can_trigger_adaptation() -> None:
    row = {
        "pipeline_id": "fullpipe_v1_ao_dr_ir",
        "job_id": "asr_case_42",
        "status": "FAILED",
        "explicit_failure": "true",
        "component": "asr",
        "last_error": "reproduced held-out ASR error",
        "fine_tuning_candidate": "ASR_TARGET_ADAPTATION_CANDIDATE",
        "reproducible_evidence": "true",
        "frozen_tests_to_rerun": "P5_HELDOUT;P6_EXTENDED",
        "expected_training_target": "source-declared ASR target",
        "regression_risk": "clean ASR regression",
    }
    evidence_record = {
        "source_prompt": 5,
        "source_file": "C:\\synthetic\\all18_failures.csv",
        "source_row_index": 1,
        "pipeline_id": row["pipeline_id"],
        "case_or_job_id": row["job_id"],
        "component": "asr",
        "explicit_failure": True,
        "failure_reason_sha256": "a" * 64,
    }
    candidate = _adaptation_candidate(row, evidence_record)
    assert candidate is not None
    assert candidate["decision"] == "ASR_TARGET_ADAPTATION_CANDIDATE"
    assert candidate["admission_basis"] == (
        "SOURCE_DECLARED_REPRODUCIBLE_ADAPTATION_DECISION"
    )


def _install_synthetic_prerequisites(
    monkeypatch: pytest.MonkeyPatch,
    chain: dict[int, Path],
    state: Path,
    pipeline_ids: tuple[str, ...],
) -> EvidenceBundle:
    completions = {
        prompt: validate_completion(
            chain[prompt],
            prompt_index=prompt,
            marker=COMPLETION_MARKERS[prompt],
            required_basenames=REQUIRED_STAGE_BASENAMES[prompt],
        )
        for prompt in (4, 5, 6, 7)
    }
    execution_policy = read_json(DEFAULT_EXECUTION_POLICY_ADDENDUM)
    bundle = EvidenceBundle(
        completions=completions,
        program_state_path=state,
        program_state_sha256=sha256_file(state),
        amendment_path=DEFAULT_AMENDMENT,
        amendment_sha256=sha256_file(DEFAULT_AMENDMENT),
        execution_policy_path=DEFAULT_EXECUTION_POLICY_ADDENDUM,
        execution_policy_sha256=sha256_file(DEFAULT_EXECUTION_POLICY_ADDENDUM),
        execution_policy=execution_policy,
        adapter_registry_path=DEFAULT_ADAPTER_REGISTRY,
        adapter_registry_sha256=sha256_file(DEFAULT_ADAPTER_REGISTRY),
        pi_deployment_steering_path=DEFAULT_PI_DEPLOYMENT_STEERING,
        pi_deployment_steering_sha256=sha256_file(DEFAULT_PI_DEPLOYMENT_STEERING),
        pi_deployment_steering=read_json(DEFAULT_PI_DEPLOYMENT_STEERING),
        program_state_snapshot=read_json(state),
        matrix_path=DEFAULT_MATRIX,
        matrix_sha256=sha256_file(DEFAULT_MATRIX),
        runtime_path=DEFAULT_RUNTIME,
        runtime_sha256=sha256_file(DEFAULT_RUNTIME),
        license_document_path=DEFAULT_LICENSE_DOCUMENT,
        license_document_sha256=sha256_file(DEFAULT_LICENSE_DOCUMENT),
        pipeline_ids=pipeline_ids,
        frozen_policy_refs={
            "extended_set": {
                "path": str(completions[4].one("extended_set.yaml")),
                "sha256": sha256_file(completions[4].one("extended_set.yaml")),
            }
        },
    )

    def prerequisites(**_kwargs: object) -> EvidenceBundle:
        return bundle

    monkeypatch.setattr(controller_module, "validate_prerequisites", prerequisites)
    monkeypatch.setattr(
        controller_module,
        "_validate_runtime_material_layout",
        lambda _registry, _paths: None,
    )
    monkeypatch.setattr(
        controller_module,
        "_adapter_identity",
        lambda _path=DEFAULT_ADAPTER_REGISTRY: (
            SYNTHETIC_PROMPT8_ADAPTER_ID,
            SYNTHETIC_PROMPT8_ADAPTER_SHA256,
        ),
    )
    return bundle


def _chain(root: Path, pipeline_ids: tuple[str, ...]) -> dict[int, Path]:
    root.mkdir(parents=True)
    paths: dict[int, Path] = {}
    predecessor: Path | None = None
    for prompt in (4, 5, 6, 7):
        stage = root / f"prompt{prompt}"
        report = stage / "report"
        report.mkdir(parents=True)
        for name in REQUIRED_STAGE_BASENAMES[prompt]:
            path = report / name
            _required_file(path, prompt=prompt, name=name, pipeline_ids=pipeline_ids)
        checksums = {
            path.relative_to(report).as_posix(): sha256_file(path)
            for path in report.rglob("*")
            if path.is_file() and path.name != "checksums.json"
        }
        _write_json(
            report / "checksums.json",
            {
                "schema_version": f"synthetic-prompt{prompt}-checksums.v1",
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": False,
                "entries": checksums,
            },
        )
        gates = _gates(stage, prompt)
        manifest_path = stage / "artifact_manifest.json"
        manifest_artifacts = [report / "checksums.json", *gates.values()]
        _write_json(
            manifest_path,
            {
                "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": False,
                "prompt_index": prompt,
                "artifacts": [
                    {"path": str(path), "sha256": sha256_file(path), "required": True}
                    for path in manifest_artifacts
                ],
            },
        )
        completion_path = stage / "completion_marker.json"
        completion = {
            "schema_version": "full-pipeline-eight-day-stage-completion.v1",
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "prompt_index": prompt,
            "status": "COMPLETE",
            "completion_marker": COMPLETION_MARKERS[prompt],
            "adapter_id": f"synthetic_prompt{prompt}",
            "adapter_contract_sha256": str(prompt) * 64,
            "predecessor": (
                None
                if predecessor is None
                else {
                    "prompt_index": prompt - 1,
                    "completion_marker": COMPLETION_MARKERS[prompt - 1],
                    "completion_record_path": str(predecessor),
                    "completion_record_sha256": sha256_file(predecessor),
                }
            ),
            "artifact_manifest": {
                "path": str(manifest_path),
                "sha256": sha256_file(manifest_path),
            },
            "gate_records": {
                name: {"path": str(path), "sha256": sha256_file(path)}
                for name, path in gates.items()
            },
        }
        if prompt == 4:
            completion["artifacts"] = _prompt4_native(stage, report, pipeline_ids)
        _write_json(completion_path, completion)
        paths[prompt] = completion_path
        predecessor = completion_path
    return paths


def _prompt4_native(
    stage: Path, report: Path, pipeline_ids: tuple[str, ...]
) -> dict[str, object]:
    frozen = stage / "frozen_pipeline_configs"
    frozen.mkdir()
    for pipeline_id in pipeline_ids:
        (frozen / f"{pipeline_id}.yaml").write_text(
            yaml.safe_dump({"pipeline_id": pipeline_id}), encoding="utf-8"
        )
    entries = {
        path.relative_to(frozen).as_posix(): sha256_file(path)
        for path in frozen.glob("*.yaml")
    }
    _write_json(frozen / "checksums.json", {"entries": entries})
    registry = report / "decision_policy_registry.json"
    _write_json(
        registry,
        {
            "schema_version": "synthetic-policy-registry.v1",
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "pipeline_ids": list(pipeline_ids),
        },
    )
    checksum_sha = sha256_file(frozen / "checksums.json")
    return {
        "frozen_pipeline_configs": {
            "path": str(frozen),
            "sha256": checksum_sha,
            "checksums_path": str(frozen / "checksums.json"),
            "checksums_sha256": checksum_sha,
            "pipeline_count": 18,
        },
        "decision_policy_registry": {
            "path": str(registry),
            "sha256": sha256_file(registry),
        },
        "extended_set": {
            "path": str(report / "extended_set.yaml"),
            "sha256": sha256_file(report / "extended_set.yaml"),
        },
        "development_summary": {
            "path": str(report / "development_summary.csv"),
            "sha256": sha256_file(report / "development_summary.csv"),
        },
    }


def _gates(stage: Path, prompt: int) -> dict[str, Path]:
    root = stage / "gates"
    root.mkdir()
    result: dict[str, Path] = {}
    for name in ("hash_validation", "firewall_validation", "prerequisite_validation"):
        path = root / f"{name}.json"
        _write_json(
            path,
            {
                "schema_version": "full-pipeline-eight-day-gate.v1",
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": False,
                "prompt_index": prompt,
                "gate": name,
                "status": "PASS",
            },
        )
        result[name] = path
    return result


def _required_file(
    path: Path, *, prompt: int, name: str, pipeline_ids: tuple[str, ...]
) -> None:
    if name.endswith(".csv"):
        if name == "all18_finalist_summary.csv":
            rows = [
                {
                    "pipeline_id": pipeline_id,
                    "wrong_known_time_sec": index / 100,
                    "stranger_false_known_time_sec": index / 200,
                    "speaker_attributed_wer": 0.1 + index / 1000,
                    "wer": 0.09 + index / 1000,
                    "correctly_named_known_rate": 0.95 - index / 1000,
                    "der": 0.08 + index / 1000,
                    "first_readable_partial_latency_sec": 0.2 + index / 100,
                    "stable_prefix_latency_sec": 0.4 + index / 100,
                    "stable_name_latency_sec": 0.8 + index / 100,
                    "premature_wrong_name_exposure_sec": index / 300,
                    "speaker_confusion_rate": 0.03 + index / 1000,
                    "transcript_revision_count": index,
                    "identity_revision_count": index,
                    "explicit_failed_job_count": 0,
                    "total_rtf": 0.3 + index / 100,
                    "mean_cpu_percent": 20 + index,
                    "peak_rss_bytes": 100_000_000 + index * 1_000_000,
                    "model_bytes": 50_000_000 + index * 1_000_000,
                }
                for index, pipeline_id in enumerate(pipeline_ids)
            ]
        elif name in {
            "all18_asr.csv",
            "all18_diarization.csv",
            "all18_identity.csv",
            "all18_speaker_attributed_transcript.csv",
            "all18_streaming.csv",
            "all18_resources.csv",
        }:
            rows = [
                {"pipeline_id": pipeline_id, "status": "computed"}
                for pipeline_id in pipeline_ids
            ]
        elif name in {"development_summary.csv", "development_matrix.csv"}:
            rows = [
                {"pipeline_id": pipeline_id, "status": "complete"}
                for pipeline_id in pipeline_ids
            ]
        elif name in {
            "extended_summary.csv",
            "technical_ranking.csv",
            "licensing_ranking.csv",
            "pareto_frontier.csv",
        }:
            rows = [
                {"pipeline_id": pipeline_id, "rank": index + 1, "status": "PASS"}
                for index, pipeline_id in enumerate(MANDATORY_EXTENDED_ANCHORS)
            ]
        elif name == "production_candidate_summary.csv":
            rows = [
                {
                    "pipeline_id": MANDATORY_EXTENDED_ANCHORS[0],
                    "selected_role": "PRIMARY",
                    "software_ready": True,
                },
                {
                    "pipeline_id": MANDATORY_EXTENDED_ANCHORS[1],
                    "selected_role": "FALLBACK",
                    "software_ready": True,
                },
            ]
        elif "failure" in name:
            rows = [
                {
                    "pipeline_id": pipeline_ids[-1],
                    "status": "complete",
                    "explicit_failure": False,
                }
            ]
        else:
            rows = [{"pipeline_id": pipeline_ids[0], "status": "computed"}]
        _write_csv(path, rows)
        return
    if name == "extended_set.yaml":
        path.write_text(
            yaml.safe_dump({"extended_pipeline_ids": list(MANDATORY_EXTENDED_ANCHORS)}),
            encoding="utf-8",
        )
        return
    if name == "production_candidate_catalog.yaml":
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_version": "full-pipeline-production-candidate-catalog.v1",
                    "scope_id": SCOPE_ID,
                    "scope_class": SCOPE_CLASS,
                    "original_full_scope_complete": False,
                    "roles": {
                        "PRIMARY": MANDATORY_EXTENDED_ANCHORS[0],
                        "FALLBACK": MANDATORY_EXTENDED_ANCHORS[1],
                        "ALTERNATIVE": None,
                    },
                    "candidates": [
                        {
                            "pipeline_id": MANDATORY_EXTENDED_ANCHORS[0],
                            "selected_role": "PRIMARY",
                            "software_ready": True,
                        },
                        {
                            "pipeline_id": MANDATORY_EXTENDED_ANCHORS[1],
                            "selected_role": "FALLBACK",
                            "software_ready": True,
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        return
    if name == "all18_deployment_evidence.json":
        _write_deployment_evidence(
            path,
            prompt=5,
            pipeline_ids=pipeline_ids,
            prompt5_path=None,
        )
        return
    if name == "extended_deployment_evidence.json":
        prompt5_path = (
            path.parents[2] / "prompt5" / "report" / ("all18_deployment_evidence.json")
        )
        _write_deployment_evidence(
            path,
            prompt=6,
            pipeline_ids=MANDATORY_EXTENDED_ANCHORS,
            prompt5_path=prompt5_path,
        )
        return
    if name == "raspberry_pi_candidate_shortlist.json":
        _write_pi_shortlist(path, pipeline_ids)
        return
    if name in {"licensing_provenance.json", "hardening_input_manifest.json"}:
        _write_json(
            path,
            {
                "schema_version": f"synthetic-{name}.v1",
                "scope_id": SCOPE_ID,
                "scope_class": SCOPE_CLASS,
                "original_full_scope_complete": False,
            },
        )
        return
    path.write_text(f"# Synthetic {name}\n\nPrompt {prompt}.\n", encoding="utf-8")


def _write_deployment_evidence(
    path: Path,
    *,
    prompt: int,
    pipeline_ids: tuple[str, ...],
    prompt5_path: Path | None,
) -> None:
    prompt5_authorization = path.parent / "prompt5_authorization.json"
    if prompt == 5 and not prompt5_authorization.exists():
        prompt5_authorization.write_text(
            "# Synthetic prompt5_authorization.json\n\nPrompt 5.\n",
            encoding="utf-8",
        )
    steering = load_deployment_steering(
        DEFAULT_PI_DEPLOYMENT_STEERING,
        expected_prompt_index=prompt,
    )
    matrix = FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME)
    summary_path = (
        path.parents[2] / "prompt5" / "report" / ("all18_finalist_summary.csv")
    )
    summary = {row["pipeline_id"]: row for row in _read_csv(summary_path)}
    rows: list[dict[str, object]] = []
    for pipeline_id in pipeline_ids:
        selection = matrix.resolve(pipeline_id)
        metrics = summary[pipeline_id]
        attributes = _deployment_attributes(metrics, summary_path)
        if prompt == 6:
            # Prompt 6 is the standardized serial resource source for the
            # extended set and is allowed to differ from Prompt 5's all-18
            # spot-check values.
            attributes["total_pipeline_peak_rss_bytes"]["value"] += 10_000_000
            attributes["model_file_size_bytes"]["value"] += 1_000_000
        assumptions = unknown_evidence(
            unit="assumption_list",
            reason_code="WINDOWS_SPECIFIC_ASSUMPTIONS_NOT_YET_AUDITED",
        )
        dependencies = unknown_evidence(
            unit="dependency_status",
            reason_code="LINUX_ARM64_DEPENDENCIES_NOT_VALIDATED",
        )
        replacements = unknown_evidence(
            unit="replacement_list",
            reason_code="PLATFORM_REPLACEMENTS_NOT_YET_IDENTIFIED",
        )
        rows.append(
            {
                "pipeline_id": pipeline_id,
                "asr_alias": selection.asr_alias,
                "diarization_alias": selection.diarization_alias,
                "identity_alias": selection.identity_alias,
                "deployment_attributes": attributes,
                "desktop_resource_context": {
                    "measurement_context": "WINDOWS_X86_64_DESKTOP",
                    "arm_measurement": False,
                },
                "two_gib_feasibility": classify_two_gib(
                    attributes["total_pipeline_peak_rss_bytes"]
                ),
                "linux_arm64_portability": classify_linux_arm64(
                    windows_specific_assumptions=assumptions,
                    linux_arm64_dependency_status=dependencies,
                    required_platform_replacements=replacements,
                ),
                "windows_specific_assumptions": assumptions,
                "linux_arm64_dependency_status": dependencies,
                "required_platform_replacements": replacements,
                "used_to_filter_pipeline": False,
            }
        )
    document: dict[str, object] = {
        "schema_version": (
            "full-pipeline-all18-deployment-evidence.v1"
            if prompt == 5
            else "full-pipeline-extended-deployment-evidence.v1"
        ),
        "scope_id": SCOPE_ID,
        "scope_class": SCOPE_CLASS,
        "original_full_scope_complete": False,
        "prompt_index": prompt,
        "status": "PASS",
        "steering_authority": steering_ref(DEFAULT_PI_DEPLOYMENT_STEERING, steering),
        "input_binding": {
            "deployment_steering_path": str(DEFAULT_PI_DEPLOYMENT_STEERING),
            "deployment_steering_sha256": sha256_file(DEFAULT_PI_DEPLOYMENT_STEERING),
            "deployment_steering_schema_version": steering["schema_version"],
            "deployment_steering_id": steering["steering_id"],
            "deployment_steering_status": steering["status"],
            "prompt5_authorization_path": str(
                path.parent / "prompt5_authorization.json"
            ),
            "prompt5_authorization_sha256": (
                sha256_file(path.parent / "prompt5_authorization.json")
                if prompt == 5
                else None
            ),
            "serial_resources_path": str(path.parent / "all18_resources.csv"),
            "serial_resources_sha256": (
                sha256_file(path.parent / "all18_resources.csv")
                if prompt == 5
                else None
            ),
        },
        "evidence_policy": {
            "unknown_or_unsupported_explicit": True,
            "desktop_measurement_relabelled_as_arm": False,
            "model_or_scientific_execution_modified_to_measure": False,
            "uncertainty_separate_from_feasibility_class": True,
        },
        "classification_policy": {
            "two_gib_is_design_constraint_not_prompt5_filter": True,
            "likely_2gb_requires_target_hardware_evidence": True,
            "desktop_rss_below_2gb_is_at_most_possibly_feasible": True,
            "final_raspberry_pi_winner_claimed": False,
        },
        "platform_portability_policy": {
            "current_platform": "WINDOWS_X86_64",
            "future_target_platform": "LINUX_DEBIAN_RASPBERRY_PI_OS_ARM64",
            "portability_separate_from_desktop_scientific_rank": True,
            "linux_arm64_ready_requires_actual_target_validation": True,
            "desktop_rank_used_as_final_arm_rank": False,
        },
        "pipeline_ids": list(pipeline_ids),
        "pipeline_count": len(pipeline_ids),
        "deployment_attribute_names": list(DEPLOYMENT_ATTRIBUTE_NAMES),
        "two_gib_feasibility_classes": list(steering["two_gib_feasibility_classes"]),
        "linux_arm64_portability_classes": list(
            steering["linux_arm64_portability_classes"]
        ),
        "raspberry_pi_candidate_fields": list(PI_CANDIDATE_FIELDS),
        "future_target_hardware_tests": list(FUTURE_TARGET_HARDWARE_TESTS),
        "future_linux_arm64_validation": list(FUTURE_LINUX_ARM64_VALIDATION),
        "pipelines": rows,
        "scientific_firewall": {
            "scientific_methodology_changed": False,
            "pipeline_membership_changed": False,
            "heldout_selection_or_retuning_performed": False,
            "deployment_evidence_used_as_filter": False,
            "desktop_rank_used_as_final_arm_rank": False,
        },
    }
    if prompt5_path is not None:
        document["prompt5_deployment_evidence"] = {
            "path": str(prompt5_path),
            "sha256": sha256_file(prompt5_path),
        }
        extended_path = path.parents[2] / "prompt4" / "report" / "extended_set.yaml"
        serial_path = path.parent / "serial_resources.csv"
        document["predeclared_membership"] = {
            "source_prompt_index": 4,
            "extended_set": {
                "path": str(extended_path),
                "sha256": sha256_file(extended_path),
                "extended_pipeline_ids": list(pipeline_ids),
                "pipeline_count": len(pipeline_ids),
            },
            "pipeline_ids": list(pipeline_ids),
            "pipeline_count": len(pipeline_ids),
            "frozen_before_prompt5_heldout_opened": True,
            "membership_changed_after_heldout": False,
            "deployment_evidence_used_as_filter": False,
        }
        document["serial_resource_evidence"] = {
            "path": str(serial_path),
            "sha256": sha256_file(serial_path),
            "measurement_context": "WINDOWS_X86_64_DESKTOP",
            "arm_measurement": False,
            "resource_concurrency": 1,
            "used_as_filter": False,
            "pipeline_statuses": [
                {"pipeline_id": pipeline_id} for pipeline_id in pipeline_ids
            ],
        }
    _write_json(path, document)


def _deployment_attributes(
    metrics: dict[str, str], source_path: Path
) -> dict[str, object]:
    measured = {
        "model_file_size_bytes": (
            float(metrics["model_bytes"]),
            "bytes",
            "model_bytes",
        ),
        "total_pipeline_peak_rss_bytes": (
            float(metrics["peak_rss_bytes"]),
            "bytes",
            "peak_rss_bytes",
        ),
    }
    result: dict[str, object] = {}
    for attribute in DEPLOYMENT_ATTRIBUTE_NAMES:
        if attribute in measured:
            value, unit, field = measured[attribute]
            result[attribute] = evidence(
                value,
                unit=unit,
                evidence_status="MEASURED",
                reason_code="SYNTHETIC_DESKTOP_RESOURCE_MEASUREMENT",
                measurement_context="WINDOWS_X86_64_DESKTOP",
                source_path=source_path,
                source_field=field,
                desktop_measurement=True,
            )
        elif attribute == "simultaneously_resident_neural_model_count":
            result[attribute] = evidence(
                4,
                unit="models",
                evidence_status="DERIVED",
                reason_code="SYNTHETIC_FROZEN_COMPONENT_COUNT",
                measurement_context="FROZEN_CONFIGURATION",
            )
        else:
            result[attribute] = unknown_evidence(
                unit="not_measured",
                reason_code=f"SYNTHETIC_UNKNOWN_{attribute.upper()}",
            )
    return result


def _write_pi_shortlist(path: Path, pipeline_ids: tuple[str, ...]) -> None:
    steering = load_deployment_steering(
        DEFAULT_PI_DEPLOYMENT_STEERING,
        expected_prompt_index=7,
    )
    root = path.parents[2]
    p5_path = root / "prompt5" / "report" / "all18_deployment_evidence.json"
    p6_path = root / "prompt6" / "report" / "extended_deployment_evidence.json"
    desktop_roles_path = (
        root / "prompt7" / "report" / "production_candidate_catalog.yaml"
    )
    candidate_pool_path = root / "prompt4" / "report" / "extended_set.yaml"
    p5 = _read_json(p5_path)
    p6 = _read_json(p6_path)
    p5_rows = {row["pipeline_id"]: row for row in p5["pipelines"]}
    p6_rows = {row["pipeline_id"]: row for row in p6["pipelines"]}
    summary_path = root / "prompt5" / "report" / "all18_finalist_summary.csv"
    summary = {row["pipeline_id"]: row for row in _read_csv(summary_path)}
    matrix = FullPipelineMatrix(DEFAULT_MATRIX, DEFAULT_RUNTIME)
    candidate_ids = tuple(sorted(MANDATORY_EXTENDED_ANCHORS[:2]))
    candidates: list[dict[str, object]] = []
    attributes: dict[str, object] = {}
    feasibility: dict[str, object] = {}
    for pipeline_id in candidate_ids:
        selection = matrix.resolve(pipeline_id)
        deployment = p6_rows[pipeline_id]
        metrics = summary[pipeline_id]

        def metric(field: str, unit: str) -> dict[str, object]:
            return evidence(
                float(metrics[field]),
                unit=unit,
                evidence_status="MEASURED",
                reason_code="SYNTHETIC_PROMPT5_DESKTOP_METRIC",
                measurement_context="WINDOWS_X86_64_DESKTOP",
                source_path=summary_path,
                source_field=field,
                desktop_measurement=True,
            )

        candidate = {
            "pipeline_id": pipeline_id,
            "asr": {
                "alias": selection.asr_alias,
                "component_id": selection.asr.get("component_id"),
                "registry_id": selection.asr.get("registry_id"),
                "environment_profile": selection.asr.get("environment_profile"),
            },
            "segmentation": {
                "segmentation_id": selection.diarization.get("segmentation_id")
            },
            "diarization_embedding": {
                "alias": selection.diarization_alias,
                "backend_id": selection.diarization_embedding.get("backend_id"),
                "model_id": selection.diarization_embedding.get("model_id"),
                "embedding_dimension": selection.diarization_embedding.get(
                    "embedding_dimension"
                ),
                "environment_profile": selection.diarization_embedding.get(
                    "environment_profile"
                ),
            },
            "identity_embedding": {
                "alias": selection.identity_alias,
                "backend_id": selection.identity.get("backend_id"),
                "model_id": selection.identity.get("model_id"),
                "embedding_dimension": selection.identity.get("embedding_dimension"),
                "environment_profile": selection.identity.get("environment_profile"),
            },
            "enrollment_policy": dict(selection.enrollment_policy),
            "current_desktop_accuracy": {"status": "PROMPT5_HELDOUT_DESKTOP"},
            "wer": metric("wer", "ratio"),
            "der": metric("der", "ratio"),
            "wrong_known": metric("wrong_known_time_sec", "seconds"),
            "stranger_false_known": metric("stranger_false_known_time_sec", "seconds"),
            "latency": {
                "first_readable_partial": metric(
                    "first_readable_partial_latency_sec", "seconds"
                ),
                "stable_transcript": metric("stable_prefix_latency_sec", "seconds"),
                "stable_correct_name": metric("stable_name_latency_sec", "seconds"),
            },
            "rtf": metric("total_rtf", "ratio"),
            "peak_ram": deployment["deployment_attributes"][
                "total_pipeline_peak_rss_bytes"
            ],
            "model_footprint": deployment["deployment_attributes"][
                "model_file_size_bytes"
            ],
            "resident_model_count": deployment["deployment_attributes"][
                "simultaneously_resident_neural_model_count"
            ],
            "export_path": {"status": "UNKNOWN_REQUIRES_ARM_EXPORT"},
            "quantization_opportunities": ["ARM_PARITY_REQUIRED"],
            "model_sharing_opportunities": ["POTENTIAL_ONLY_NOT_MEASURED"],
            "arm_runtime_risks": ["NO_ARM64_MEASUREMENTS"],
            "reason_retained": ["DESKTOP_PRIMARY_OR_EFFICIENCY_REFERENCE"],
            "two_gib_feasibility_class": deployment["two_gib_feasibility"]["class"],
            "linux_arm64_portability_class": deployment["linux_arm64_portability"][
                "class"
            ],
            "windows_specific_assumptions": deployment["windows_specific_assumptions"],
            "linux_arm64_dependency_status": deployment[
                "linux_arm64_dependency_status"
            ],
            "required_platform_replacements": deployment[
                "required_platform_replacements"
            ],
        }
        assert set(candidate) == set(PI_CANDIDATE_FIELDS)
        candidates.append(candidate)
        attributes[pipeline_id] = deployment["deployment_attributes"]
        feasibility[pipeline_id] = deployment["two_gib_feasibility"]
    _write_json(
        path,
        {
            "schema_version": "full-pipeline-raspberry-pi-candidate-shortlist.v1",
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "prompt_index": 7,
            "status": "PASS",
            "steering_authority": steering_ref(
                DEFAULT_PI_DEPLOYMENT_STEERING, steering
            ),
            "prompt5_deployment_evidence": {
                "path": str(p5_path),
                "sha256": sha256_file(p5_path),
            },
            "prompt6_deployment_evidence": {
                "path": str(p6_path),
                "sha256": sha256_file(p6_path),
            },
            "desktop_roles_source": {
                "path": str(desktop_roles_path),
                "sha256": sha256_file(desktop_roles_path),
            },
            "candidate_pool_source": {
                "path": str(candidate_pool_path),
                "sha256": sha256_file(candidate_pool_path),
            },
            "desktop_roles": {
                "PRIMARY": MANDATORY_EXTENDED_ANCHORS[0],
                "FALLBACK": MANDATORY_EXTENDED_ANCHORS[1],
                "ALTERNATIVE": None,
            },
            "desktop_roles_changed_for_pi": False,
            "candidate_pool_pipeline_ids": list(MANDATORY_EXTENDED_ANCHORS),
            "candidate_count": len(candidates),
            "candidates": candidates,
            "deployment_attributes_by_pipeline": attributes,
            "two_gib_classification_evidence_by_pipeline": feasibility,
            "selection_policy": {
                "weighted_composite_used": False,
                "universal_within_one_percent_equivalence_rule_used": False,
                "deployment_evidence_used_to_rewrite_scientific_ranks": False,
                "two_gib_used_as_hard_filter": False,
                "final_pi_winner_selected": False,
            },
            "architecture_tradeoff_audit": {
                "H2_same_model": "POTENTIAL_ONLY_NOT_MEASURED",
                "H5_dual_embedding": "SAFETY_RESOURCE_TRADEOFF",
                "wespeaker_paths": "RETAINED_IF_SUPPORTED",
                "both_asrs_preserved_in_all18_desktop_ranking": True,
                "final_arm_preference_claimed": False,
            },
            "future_target_hardware_tests": list(FUTURE_TARGET_HARDWARE_TESTS),
            "future_linux_arm64_validation": list(FUTURE_LINUX_ARM64_VALIDATION),
            "final_raspberry_pi_winner": None,
            "final_raspberry_pi_winner_claimed": False,
            "p5_pipeline_evidence_sha256s": {
                pipeline_id: sha256_file(p5_path) for pipeline_id in p5_rows
            },
        },
    )


def _program_state(path: Path, chain: dict[int, Path]) -> Path:
    _write_json(
        path,
        {
            "schema_version": "just-peachy-full-pipeline-program-state.v1",
            "status": COMPLETION_MARKERS[7],
            "current_prompt_index": 7,
            "remaining_prompt_indices": [8],
            "completion_state": {
                key: value
                for prompt in (4, 5, 6, 7)
                for key, value in {
                    f"prompt_{prompt}": COMPLETION_MARKERS[prompt],
                    f"prompt_{prompt}_scope_id": SCOPE_ID,
                    f"prompt_{prompt}_original_full_scope_complete": False,
                }.items()
            },
            "prompt_7_completion_record": str(chain[7]),
            "prompt_7_completion_record_sha256": sha256_file(chain[7]),
            "scope_id": SCOPE_ID,
            "scope_class": SCOPE_CLASS,
            "original_full_scope_complete": False,
            "remaining_prompt_status": "PENDING_AUTOMATIC",
        },
    )
    return path


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))
