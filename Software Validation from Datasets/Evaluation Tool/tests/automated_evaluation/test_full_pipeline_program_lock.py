from __future__ import annotations

from copy import deepcopy
import csv
import hashlib
import io
import itertools
import json
from pathlib import Path
import shutil
from typing import Any
import zipfile

import yaml

from app.full_pipeline_program.validator import (
    EXPECTED_COMMON_DEMO_PROFILE_BACKENDS,
    EXPECTED_COMMON_DEMO_SMOKE_COMPONENTS,
    EXPECTED_COMMON_DEMO_SMOKE_PRESETS,
    EXPECTED_ANCHOR_THRESHOLDS,
    EXPECTED_PIPELINE_IDS,
    EXPECTED_PROMPT_4_CHALLENGERS,
    EXPECTED_TIER_B,
    FROZEN_HYBRID_PROTOCOL_ID,
    FROZEN_HYBRID_SELECTION_SHA256,
    PROMPT_4_CALIBRATION_SOURCE_WORKSPACE,
    PROMPT_4_POLICY_ADOPTION_BINDINGS,
    PROMPT_4_REPORT_ROOT,
    PROMPT_4_WORKSPACE,
    ProgramLockValidationError,
    PUBLIC_CONTRACTS,
    REQUIRED_FULL_PIPELINE_EVALUATION_PACKAGE_PATHS,
    REQUIRED_FULL_PIPELINE_EVALUATION_TEST_PATHS,
    REQUIRED_FULL_PIPELINE_EVALUATION_WRAPPER_PATHS,
    REQUIRED_FULL_PIPELINE_PROTOCOL_PATHS,
    REQUIRED_PROMPT_4_CANONICAL_ARTIFACTS,
    REQUIRED_PROMPT_4_COMBINED_PATHS,
    REQUIRED_PROMPT_4_FROZEN_CONFIG_PATHS,
    REQUIRED_PROMPT_4_ORCHESTRATION_PATHS,
    REQUIRED_PROMPT_4_PACKAGE_PATHS,
    REQUIRED_PROMPT_4_POLICY_PATHS,
    REQUIRED_PROMPT_4_QUALIFICATION_PATHS,
    REQUIRED_PROMPT_4_REPORT_PATHS,
    REQUIRED_PROMPT_4_TEST_PATHS,
    REQUIRED_PROMPT_4_WRAPPER_PATHS,
    _validate_prompt_3_state,
    _validate_prompt_4_state,
    _validate_state,
    validate_program_lock,
)


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
CONTRACT_PATH = (
    EVALUATION_ROOT
    / "configs/automated_evaluation/schemas/full_pipeline_contracts.v1.schema.json"
)
STATE_PATH = EVALUATION_ROOT / "runs/full_pipeline_program/PROGRAM_STATE.json"


def test_prompt_4_v5_release_binding_constants_are_exact() -> None:
    assert PROMPT_4_WORKSPACE.endswith(
        "full_pipeline_development_v1_prompt4_execution_recovery_v5_restart_contract_fix"
    )
    assert PROMPT_4_POLICY_ADOPTION_BINDINGS == {
        "source_development_policy_package_sha256": (
            "1ebb04143362d94f7987f142d3b7f139311ec37704f01d0bc41f30242e6bdde0"
        ),
        "destination_development_policy_package_sha256": (
            "ff3f80fdcc55096366e148b7e8e82b9fcd06d77f0a9fc863a8dbce2e1606469a"
        ),
        "evaluation_package_sha256": (
            "74551484a553edf74cdd3229c0b52cc75b01f26880cf277ece44aa9073799513"
        ),
        "streaming_runtime_package_sha256": (
            "ce8a30253f8191c0ae58a4c0b8f3a30f5cb10416476887cfdd058e9a95fd622d"
        ),
        "source_calibration_campaign_manifest_sha256": (
            "e4a0f7e33f2ec27ba2984f610f59c4f18e424e2d2ebdf3f774ca321bf3f7474e"
        ),
        "decision_policy_registry_file_sha256": (
            "f233a80b8d7dd39407987a1735f08c940cd0fab2591e7f1b1866159ffbbcb4f1"
        ),
        "calibration_freeze_file_sha256": (
            "10e071f9762b38ffd9462a6046e07bd22301e6f3aabbd39d57750ffa676e8c65"
        ),
        "decision_policy_registry_identity_sha256": (
            "3b4f0bc674f0e1a27d7d60327c7c7cbe5532740369dae08c274cdedc3e977dda"
        ),
        "policy_adoption_provenance_file_sha256": (
            "dc1ef272a5f8a7bbf963d4c71c4412cf5000d6e002bd60d053ceac59b87c1094"
        ),
    }
    python_hashes = {
        path: _sha256(EVALUATION_ROOT / path)
        for path in REQUIRED_PROMPT_4_PACKAGE_PATHS
        if path.endswith(".py")
    }
    assert _canonical_hash(python_hashes) == (
        PROMPT_4_POLICY_ADOPTION_BINDINGS[
            "destination_development_policy_package_sha256"
        ]
    )


def test_matrix_is_exact_cartesian_product_with_stable_ids() -> None:
    matrix = yaml.safe_load(MATRIX_PATH.read_text(encoding="utf-8"))
    axes = matrix["axes"]
    expected = set(
        itertools.product(
            axes["asr"], axes["anonymous_diarization"], axes["identity"]
        )
    )
    observed = {
        (row["asr"], row["anonymous_diarization"], row["identity"])
        for row in matrix["pipelines"]
    }
    assert len(matrix["pipelines"]) == 18
    assert observed == expected
    assert len({row["pipeline_id"] for row in matrix["pipelines"]}) == 18
    for row in matrix["pipelines"]:
        assert row["pipeline_id"] == (
            f"fullpipe_v1_{row['asr'].lower()}_"
            f"{row['anonymous_diarization'].lower()}_{row['identity'].lower()}"
        )


def test_public_contracts_preserve_raw_score_semantics() -> None:
    schema = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert PUBLIC_CONTRACTS.issubset(schema["$defs"])
    assert len(schema["oneOf"]) == 15
    serialized = json.dumps(schema, sort_keys=True)
    assert '"probability"' not in serialized
    evidence = json.dumps(schema["$defs"]["IdentityEvidenceEvent"], sort_keys=True)
    for field in (
        "raw_score",
        "score_type",
        "top1_top2_margin",
        "threshold_identity",
        "evidence_duration_sec",
    ):
        assert field in evidence


def test_program_lock_resolves_without_inference() -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    try:
        result = validate_program_lock(evaluation_root=EVALUATION_ROOT)
    except ProgramLockValidationError as exc:
        # During the live Prompt-4 run the last immutable state remains Prompt 3.
        # Result-affecting hardening and this validator update deliberately make
        # its old SHA bindings stale until the final Prompt-4 state is published.
        assert state["status"] == "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE"
        assert exc.errors
        assert all(error.startswith("SHA-256 for ") for error in exc.errors)
    else:
        assert result["status"] == "PASS"
        assert result["matrix_count"] == 18
        assert result["contract_count"] == 15
        assert result["assets_verified"] is False
        assert result["long_inference_run"] is False

    assert state["status"] in {
        "COMPLETE_STREAMING_RUNTIME",
        "COMPLETE_COMMON_DEMO",
        "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
        "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE",
    }
    assert state["completion_state"]["prompt_1"] == "COMPLETE_STREAMING_RUNTIME"
    assert state["completion_state"]["end_to_end_runtime_implemented"] is True
    if state["status"] == "COMPLETE_STREAMING_RUNTIME":
        assert state["current_prompt_index"] == 1
        assert state["remaining_prompt_indices"] == list(range(2, 9))
    elif state["status"] == "COMPLETE_COMMON_DEMO":
        assert state["current_prompt_index"] == 2
        assert state["remaining_prompt_indices"] == list(range(3, 9))
        assert state["completion_state"]["prompt_2"] == "COMPLETE_COMMON_DEMO"
        assert state["completion_state"]["common_demo_implemented"] is True
        assert state["completion_state"]["all_18_demo_presets_available"] is True
        assert state["completion_state"]["six_highlighted_demo_presets_available"] is True
        assert (
            state["completion_state"]["three_required_bounded_demo_presets_passed"]
            is True
        )
    elif state["status"] == "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE":
        assert state["current_prompt_index"] == 3
        assert state["remaining_prompt_indices"] == list(range(4, 9))
        assert state["completion_state"]["prompt_3"] == (
            "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE"
        )
        assert state["completion_state"]["all_18_evaluation_pipelines_planned"] is True
        assert state["bounded_inference_run_by_prompt_3"] is False
    else:
        assert state["current_prompt_index"] == 4
        assert state["remaining_prompt_indices"] == [5, 6, 7, 8]
        assert state["completion_state"]["prompt_4"] == (
            "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE"
        )
        assert state["held_out_evaluation_run_by_prompt_4"] is False


def test_prompt_2_state_accepts_complete_bounded_demo(tmp_path: Path) -> None:
    state, _ = _synthetic_prompt_2_state(tmp_path)
    errors: list[str] = []

    _validate_state(state, MATRIX_PATH, CONTRACT_PATH, errors)

    assert errors == []


def test_prompt_2_state_rejects_completion_and_artifact_mutations(
    tmp_path: Path,
) -> None:
    state, _ = _synthetic_prompt_2_state(tmp_path)
    bad_completion = deepcopy(state)
    bad_completion["completion_state"]["common_demo_export_smoke_passed"] = False
    errors: list[str] = []
    _validate_state(bad_completion, MATRIX_PATH, CONTRACT_PATH, errors)
    assert "Prompt-2 completion records the export smoke PASS" in errors

    missing_artifact = deepcopy(state)
    del missing_artifact["canonical_artifacts"]["common_demo_package"]
    errors = []
    _validate_state(missing_artifact, MATRIX_PATH, CONTRACT_PATH, errors)
    assert "program state binds all Prompt-2 canonical artifacts" in errors

    missing_wrapper = deepcopy(state)
    del missing_wrapper["canonical_artifacts"]["common_demo_package"]["paths"][
        "scripts/run_full_pipeline_demo.ps1"
    ]
    errors = []
    _validate_state(missing_wrapper, MATRIX_PATH, CONTRACT_PATH, errors)
    assert (
        "Prompt-2 package lock binds every demo module, README, and wrapper"
        in errors
    )


def test_prompt_2_state_rejects_campaign_claim_inside_hashed_smoke(
    tmp_path: Path,
) -> None:
    state, smoke_path = _synthetic_prompt_2_state(tmp_path)
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    smoke["scientific_campaign_started"] = True
    smoke_path.write_text(
        json.dumps(smoke, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state["canonical_artifacts"]["prompt_2_common_demo_smoke"]["sha256"] = (
        _sha256(smoke_path)
    )
    errors: list[str] = []

    _validate_state(state, MATRIX_PATH, CONTRACT_PATH, errors)

    assert "Prompt-2 smoke records no scientific campaign" in errors

    smoke["scientific_campaign_started"] = False
    smoke["sessions"][0]["useful_labelled_attribution"]["start_sec"] = None
    smoke_path.write_text(
        json.dumps(smoke, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state["canonical_artifacts"]["prompt_2_common_demo_smoke"]["sha256"] = (
        _sha256(smoke_path)
    )
    errors = []
    _validate_state(state, MATRIX_PATH, CONTRACT_PATH, errors)
    assert "Prompt-2 smoke has timed labelled attribution: AG-H5" in errors


def test_prompt_3_state_accepts_complete_model_free_infrastructure(
    tmp_path: Path,
) -> None:
    state, artifacts, completion, evaluation_root, _ = _synthetic_prompt_3_state(
        tmp_path
    )
    errors: list[str] = []

    _validate_prompt_3_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
    )

    assert errors == []


def test_prompt_3_state_rejects_completion_path_and_protocol_mutations(
    tmp_path: Path,
) -> None:
    state, artifacts, completion, evaluation_root, _ = _synthetic_prompt_3_state(
        tmp_path
    )
    bad_completion = deepcopy(completion)
    bad_completion["all_required_scorers_implemented"] = False
    errors: list[str] = []
    _validate_prompt_3_state(
        state,
        bad_completion,
        artifacts,
        evaluation_root,
        errors,
    )
    assert "Prompt-3 completion records all required scorers implemented" in errors

    missing_controller = deepcopy(artifacts)
    del missing_controller["full_pipeline_evaluation_package"]["paths"][
        "app/full_pipeline_evaluation/controller.py"
    ]
    errors = []
    _validate_prompt_3_state(
        state,
        completion,
        missing_controller,
        evaluation_root,
        errors,
    )
    assert "Prompt-3 package lock binds every evaluation module and README" in errors

    manifest_path = (
        evaluation_root
        / "benchmarks/full_pipeline/full_speech_pipeline_v1/"
        "development/case_manifest.jsonl"
    )
    manifest_path.write_text(
        manifest_path.read_text(encoding="utf-8")
        + json.dumps(
            {
                "protocol_case_id": "case_dev_2",
                "partition": "development",
                "protocol_id": "full_speech_pipeline_v1_123456789abc",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    errors = []
    _validate_prompt_3_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
    )
    assert "Prompt-3 protocol development case count matches its manifest" in errors
    assert "Prompt-3 protocol checksum map covers every generated file exactly" in errors


def test_prompt_3_state_rejects_untruthful_smoke_semantics(tmp_path: Path) -> None:
    state, artifacts, completion, evaluation_root, smoke_path = (
        _synthetic_prompt_3_state(tmp_path)
    )
    smoke = json.loads(smoke_path.read_text(encoding="utf-8"))
    smoke["model_inference_performed"] = True
    smoke["failure_result_reusable"] = True
    smoke["restart_state"]["retry_attempt_count"] = 1
    smoke_path.write_text(
        json.dumps(smoke, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    errors: list[str] = []

    _validate_prompt_3_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
    )

    assert (
        "Prompt-3 smoke validates a non-reusable intentional failure result" in errors
    )
    assert (
        "Prompt-3 smoke exercises restart-safe retry and checksum reuse identity"
        in errors
    )
    assert (
        "Prompt-3 smoke records no inference, downloads, or scientific campaign"
        in errors
    )


def test_prompt_4_state_accepts_complete_development_freeze(tmp_path: Path) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert errors == []


def test_prompt_4_state_rejects_unsafe_or_unbound_policy_adoption(
    tmp_path: Path,
) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    adoption_path = (
        evaluation_root
        / PROMPT_4_WORKSPACE
        / "frozen/policy_adoption_provenance.json"
    )
    adoption = json.loads(adoption_path.read_text(encoding="utf-8"))
    adoption["policy_retuned"] = True
    adoption["source_calibration_campaign_manifest_sha256"] = "f" * 64
    _write_json(adoption_path, adoption)
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert (
        "Prompt-4 policy adoption permits only the qualification comparator "
        "and restart-contract correction"
        in errors
    )
    assert "Prompt-4 v5 adoption matches exact frozen release bindings" in errors
    assert (
        "Prompt-4 policy adoption binds immutable source and copied policy bytes"
        in errors
    )


def test_prompt_4_state_rejects_retroactive_registry_in_raw_calibration(
    tmp_path: Path,
) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    source_manifest_path = (
        evaluation_root
        / PROMPT_4_CALIBRATION_SOURCE_WORKSPACE
        / "calibration/campaign_manifest.json"
    )
    adoption_path = (
        evaluation_root
        / PROMPT_4_WORKSPACE
        / "frozen/policy_adoption_provenance.json"
    )
    adoption = json.loads(adoption_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    registry_sha256 = adoption["decision_policy_registry_file_sha256"]
    source_manifest["decision_policy_registry_sha256"] = registry_sha256
    source_manifest["decision_policy_registry"] = {
        "logical_path": "decision_policy_registry.json",
        "sha256": registry_sha256,
    }
    _write_json(source_manifest_path, source_manifest)
    adoption["source_calibration_campaign_manifest_sha256"] = _sha256(
        source_manifest_path
    )
    _write_json(adoption_path, adoption)
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert "Prompt-4 inherited calibration exact development scope" in errors


def test_prompt_4_state_rejects_v5_manifest_identity_mismatch(
    tmp_path: Path,
) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    manifest_path = (
        evaluation_root
        / PROMPT_4_WORKSPACE
        / "qualification_shared/campaign_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["implementation_identity"][
        "development_policy_package_sha256"
    ] = "f" * 64
    manifest["decision_policy_registry_sha256"] = "e" * 64
    _write_json(manifest_path, manifest)
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert (
        "Prompt-4 v5 qualification_shared manifest binds destination "
        "implementation identity"
        in errors
    )
    assert (
        "Prompt-4 v5 qualification_shared manifest binds adopted policy registry"
        in errors
    )


def test_prompt_4_state_rejects_stale_destination_package_binding(
    tmp_path: Path,
) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    artifacts["full_pipeline_development_package"]["paths"][
        "app/full_pipeline_development/qualification.py"
    ] = "f" * 64
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert (
        "Prompt-4 v5 destination package hash matches canonical source artifacts"
        in errors
    )


def test_prompt_4_state_rejects_missing_policy_adoption(tmp_path: Path) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    adoption_path = (
        evaluation_root
        / PROMPT_4_WORKSPACE
        / "frozen/policy_adoption_provenance.json"
    )
    adoption_path.unlink()
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert any(
        "missing JSON file" in error
        and "policy_adoption_provenance.json" in error
        for error in errors
    )


def test_prompt_4_state_rejects_heldout_winner_and_registry_mutations(
    tmp_path: Path,
) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    state["held_out_evaluation_audio_processed"] = True
    completion["production_winner_selected"] = True
    registry_path = (
        evaluation_root
        / PROMPT_4_WORKSPACE
        / "frozen/decision_policy_registry.json"
    )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["entries"][0]["threshold_shared_with_another_pipeline"] = True
    _write_json(registry_path, registry)
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert "Prompt-4 state records no held-out audio processed" in errors
    assert "Prompt-4 completion records no production winner" in errors
    assert any("challenger policy is frozen independently" in error for error in errors)


def test_prompt_4_state_rejects_anchor_report_and_zip_mutations(
    tmp_path: Path,
) -> None:
    state, completion, artifacts, evaluation_root, bindings = (
        _synthetic_prompt_4_state(tmp_path)
    )
    anchor_path = (
        evaluation_root
        / PROMPT_4_WORKSPACE
        / "frozen_pipeline_configs/fullpipe_v1_ao_dr_ir.yaml"
    )
    anchor = yaml.safe_load(anchor_path.read_text(encoding="utf-8"))
    anchor["identity_policy"]["decision_policy_sha256"] = "f" * 64
    anchor["freeze_identity_sha256"] = _canonical_hash(
        {key: value for key, value in anchor.items() if key != "freeze_identity_sha256"}
    )
    anchor_path.write_text(yaml.safe_dump(anchor, sort_keys=True), encoding="utf-8")
    report = evaluation_root / PROMPT_4_REPORT_ROOT
    summary_path = report / "development_summary.csv"
    summary_lines = summary_path.read_text(encoding="utf-8").splitlines()
    summary_path.write_text("\n".join(summary_lines[:-1]) + "\n", encoding="utf-8")
    (report / "full_pipeline_development_compact.zip").write_bytes(b"broken")
    errors: list[str] = []

    _validate_prompt_4_state(
        state,
        completion,
        artifacts,
        evaluation_root,
        errors,
        policy_adoption_bindings=bindings,
    )

    assert any("preserves exact frozen anchor SHA/settings" in error for error in errors)
    assert "Prompt-4 development summary has exactly 18 pipeline rows" in errors
    assert any("invalid Prompt-4 compact ZIP" in error for error in errors)


def _synthetic_prompt_4_state(
    tmp_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    Path,
    dict[str, str],
]:
    evaluation_root = tmp_path / "Evaluation Tool"
    workspace = evaluation_root / PROMPT_4_WORKSPACE
    source_workspace = evaluation_root / PROMPT_4_CALIBRATION_SOURCE_WORKSPACE
    report = evaluation_root / PROMPT_4_REPORT_ROOT
    pipeline_ids = sorted(EXPECTED_PIPELINE_IDS)
    challenger_ids = sorted(EXPECTED_PROMPT_4_CHALLENGERS)
    development_identity = "d" * 64
    evaluation_identity = "e" * 64
    protocol_id = "full_speech_pipeline_v1_fixture"
    source_development_package_sha256 = "1" * 64
    evaluation_package_sha256 = "2" * 64
    streaming_runtime_package_sha256 = "3" * 64
    matrix_sha256 = "4" * 64
    runtime_config_sha256 = "5" * 64
    development_package_paths = {
        path: f"{index + 100:064x}"
        for index, path in enumerate(sorted(REQUIRED_PROMPT_4_PACKAGE_PATHS))
    }
    destination_development_package_sha256 = _canonical_hash(
        {
            path: digest
            for path, digest in development_package_paths.items()
            if path.endswith(".py")
        }
    )
    common_campaign_identity = {
        "full_protocol_id": protocol_id,
        "development_identity": development_identity,
        "evaluation_identity": evaluation_identity,
        "matrix_sha256": matrix_sha256,
        "runtime_config_sha256": runtime_config_sha256,
        "scorer_version": "full-pipeline-evaluation-scorers.v2",
        "result_contract_version": "full-pipeline-evaluation-result.v1",
        "seed": 5107,
    }

    orchestration = {
        "schema_version": "full-pipeline-development-orchestration.v1",
        "status": "PASS",
        "development_only": True,
        "held_out_evaluation_allowed": False,
        "production_winner_selected": False,
        "stages": {
            "calibration": {
                "case_count": 56,
                "pipeline_count": 12,
                "pipeline_ids": challenger_ids,
                "measurement_modes": ["accuracy"],
                "parallel_jobs": 1,
            },
            "qualification": {
                "case_count": 1,
                "pipeline_count": 18,
                "pipeline_ids": pipeline_ids,
                "measurement_modes": ["accuracy"],
                "cold_parallel_jobs": 1,
                "shared_parallel_jobs": 2,
            },
            "development": {
                "case_count": 807,
                "pipeline_count": 18,
                "pipeline_ids": pipeline_ids,
                "measurement_modes": ["accuracy"],
                "parallel_jobs": 2,
            },
            "resources": {
                "case_count": 2,
                "pipeline_count": 18,
                "pipeline_ids": pipeline_ids,
                "measurement_modes": ["resources"],
                "parallel_jobs": 1,
            },
        },
    }
    _write_json(workspace / "orchestration_plan.json", orchestration)
    manifest_specs = {
        "calibration": (
            "prompt4_challenger_calibration",
            challenger_ids,
            56,
            "accuracy",
        ),
        "qualification_shared": (
            "prompt4_qualification_shared",
            pipeline_ids,
            1,
            "accuracy",
        ),
        "qualification_cold": (
            "prompt4_qualification_cold",
            pipeline_ids,
            1,
            "accuracy",
        ),
        "development_accuracy": (
            "prompt4_all18_development_accuracy",
            pipeline_ids,
            807,
            "accuracy",
        ),
        "resource_spots": (
            "prompt4_resource_spots",
            pipeline_ids,
            2,
            "resources",
        ),
    }
    for directory, (stage, ids, case_count, mode) in manifest_specs.items():
        source_count = (
            2
            if directory
            in {"calibration", "development_accuracy", "resource_spots"}
            else 1
        )
        jobs = [
            {
                "job_id": f"{directory}_{pipeline_id}_{source_index}",
                "pipeline_id": pipeline_id,
                "protocol_id": f"source_{source_index}",
                "source_key": f"source_{source_index}",
                "split": "development",
                "measurement_mode": mode,
            }
            for pipeline_id in ids
            for source_index in range(source_count)
        ]
        development_package_sha256 = (
            source_development_package_sha256
            if directory == "calibration"
            else destination_development_package_sha256
        )
        campaign = {
            "schema_version": "full-pipeline-evaluation-campaign-identity.v1",
            "campaign_id": f"fixture_{directory}",
            "campaign_stage": stage,
            "job_count": len(jobs),
            "case_count": case_count,
            "pipeline_count": len(ids),
            "selected_pipeline_ids": ids,
            "measurement_modes": [mode],
            **common_campaign_identity,
            "implementation_identity": {
                "development_policy_package_sha256": (
                    development_package_sha256
                ),
                "evaluation_package_sha256": evaluation_package_sha256,
                "streaming_runtime_package_sha256": (
                    streaming_runtime_package_sha256
                ),
            },
            "case_index": {
                f"case_{index:04d}": {"split": "development"}
                for index in range(case_count)
            },
            "jobs": jobs,
            "parallelism_policy": {"resource_measurement_jobs": 1},
        }
        campaign_workspace = (
            source_workspace if directory == "calibration" else workspace
        )
        _write_json(
            campaign_workspace / directory / "campaign_manifest.json", campaign
        )

    registry_entries = []
    for index, pipeline_id in enumerate(challenger_ids):
        registry_entries.append(
            {
                "pipeline_id": pipeline_id,
                "calibration_identity_sha256": f"{index + 1:064x}",
                "calibration_partition": "development",
                "evaluation_material_inspected": False,
                "threshold_shared_with_another_pipeline": False,
                "calibration_method": "maximum_gallery_score_with_top1_top2_margin",
                "thresholds_by_gallery_request": [{"gallery_requested_size": "10"}],
            }
        )
    registry_core = {
        "schema_version": "full-pipeline-development-policy-registry.v1",
        "status": "FROZEN_DEVELOPMENT_ONLY",
        "protocol_id": protocol_id,
        "development_identity_sha256": development_identity,
        "calibration_partition": "development",
        "evaluation_material_inspected": False,
        "evaluation_recalibration_allowed": False,
        "cross_backend_threshold_sharing": False,
        "entries": registry_entries,
    }
    registry = {
        **registry_core,
        "registry_identity_sha256": _canonical_hash(registry_core),
    }
    registry_path = workspace / "frozen/decision_policy_registry.json"
    _write_json(registry_path, registry)
    source_registry_path = (
        source_workspace / "frozen/decision_policy_registry.json"
    )
    _write_json(source_registry_path, registry)
    registry_file_sha256 = _sha256(registry_path)
    for directory in manifest_specs:
        if directory == "calibration":
            continue
        manifest_path = workspace / directory / "campaign_manifest.json"
        campaign = json.loads(manifest_path.read_text(encoding="utf-8"))
        campaign["decision_policy_registry_sha256"] = registry_file_sha256
        campaign["decision_policy_registry"] = {
            "logical_path": "decision_policy_registry.json",
            "sha256": registry_file_sha256,
        }
        _write_json(manifest_path, campaign)
    source_calibration_manifest_path = (
        source_workspace / "calibration/campaign_manifest.json"
    )
    source_calibration_manifest = json.loads(
        source_calibration_manifest_path.read_text(encoding="utf-8")
    )
    calibration_freeze = {
        "schema_version": "full-pipeline-development-policy-freeze-evidence.v1",
        "status": "PASS",
        "campaign_id": source_calibration_manifest["campaign_id"],
        "campaign_stage": "prompt4_challenger_calibration",
        "calibration_partition": "development",
        "calibration_case_count": 56,
        "challenger_pipeline_count": 12,
        "observation_count": 1234,
        "evaluation_material_inspected": False,
        "policy_registry_file_sha256": registry_file_sha256,
        "policy_registry_identity_sha256": registry["registry_identity_sha256"],
    }
    calibration_freeze_path = workspace / "frozen/calibration_freeze.json"
    source_calibration_freeze_path = (
        source_workspace / "frozen/calibration_freeze.json"
    )
    _write_json(calibration_freeze_path, calibration_freeze)
    _write_json(source_calibration_freeze_path, calibration_freeze)
    policy_adoption = {
        "schema_version": "full-pipeline-development-policy-adoption.v1",
        "status": "PASS",
        "source_workspace": PROMPT_4_CALIBRATION_SOURCE_WORKSPACE,
        "destination_workspace": PROMPT_4_WORKSPACE,
        "reason": "qualification_comparator_and_restart_contract_correction",
        "source_development_policy_package_sha256": (
            source_development_package_sha256
        ),
        "destination_development_policy_package_sha256": (
            destination_development_package_sha256
        ),
        "evaluation_package_sha256": evaluation_package_sha256,
        "streaming_runtime_package_sha256": streaming_runtime_package_sha256,
        "source_calibration_campaign_manifest_sha256": _sha256(
            source_calibration_manifest_path
        ),
        "decision_policy_registry_file_sha256": registry_file_sha256,
        "calibration_freeze_file_sha256": _sha256(calibration_freeze_path),
        "decision_policy_registry_identity_sha256": registry[
            "registry_identity_sha256"
        ],
        "source_calibration_job_count": 24,
        "source_calibration_case_count": 56,
        "source_challenger_pipeline_count": 12,
        "source_observation_count": 1234,
        "source_calibration_complete": True,
        "source_calibration_sqlite_quick_check": "ok",
        "source_calibration_result_checksums_verified": True,
        "qualification_only_code_change": True,
        "calibration_inference_repeated": False,
        "policy_retuned": False,
        "held_out_evaluation_allowed": False,
        "evaluation_material_inspected": False,
    }
    policy_adoption_path = workspace / "frozen/policy_adoption_provenance.json"
    _write_json(policy_adoption_path, policy_adoption)
    policy_adoption_bindings = {
        field: (
            _sha256(policy_adoption_path)
            if field == "policy_adoption_provenance_file_sha256"
            else str(policy_adoption[field])
        )
        for field in PROMPT_4_POLICY_ADOPTION_BINDINGS
    }

    required_checks = (
        "assets",
        "environment",
        "minimum_duration",
        "native_streaming_asr",
        "segmentation",
        "diarization_embedding",
        "clustering",
        "identity_backend",
        "enrollment_profile",
        "known_unknown_decision",
        "labelled_transcript",
        "event_log",
        "restart",
        "clean_shutdown",
        "cold_vs_shared_equivalence",
    )
    plan_records = [
        {"pipeline_id": pipeline_id, "split": "development"}
        for pipeline_id in pipeline_ids
    ]
    plan = {
        "schema_version": "full-pipeline-development-qualification-plan.v1",
        "pipeline_count": 18,
        "records": plan_records,
        "evaluation_material_inspected": False,
    }
    plan_core = dict(plan)
    plan["plan_identity_sha256"] = _canonical_hash(plan_core)
    qualification_records = []
    for pipeline_id in pipeline_ids:
        record_core = {
            "pipeline_id": pipeline_id,
            "split": "development",
            "qualification_status": "PASS",
            "evaluation_material_inspected": False,
            "checks": {key: {"status": "PASS"} for key in required_checks},
        }
        qualification_records.append(
            {
                **record_core,
                "record_identity_sha256": _canonical_hash(record_core),
            }
        )
    qualification_core = {
        "schema_version": "full-pipeline-development-qualification.v1",
        "status": "PASS",
        "pipeline_count": 18,
        "records": qualification_records,
        "plan_identity_sha256": plan["plan_identity_sha256"],
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
    }
    qualification = {
        **qualification_core,
        "qualification_result_sha256": _canonical_hash(qualification_core),
    }
    anchor_qualification = {
        "schema_version": "full-pipeline-anchor-runtime-qualification.v1",
        "status": "PASS",
        "qualification_result_sha256": qualification[
            "qualification_result_sha256"
        ],
        "anchor_pipeline_ids": sorted(EXPECTED_TIER_B),
        "correct_diarization_embedding_provenance": True,
        "predicted_overlap_excluded_from_primary_identity": True,
        "product_v2_probe_consistency_semantics": True,
        "product_v2_hysteresis_semantics": True,
        "decision_policy_hash_is_not_enrollment_hash": True,
        "all_six_anchor_pipelines_integrated_smoke_passed": True,
        "evaluation_material_inspected": False,
    }
    _write_json(workspace / "qualification/qualification_plan.json", plan)
    _write_json(workspace / "qualification/qualification.json", qualification)
    _write_json(
        workspace / "qualification/anchor_runtime_qualification.json",
        anchor_qualification,
    )
    _write_json(workspace / "qualification_execution_plan.json", {"status": "PREPARED"})
    _write_json(
        workspace / "qualification/evidence/restarts/restart_manifest.json",
        {"status": "PASS"},
    )

    combined_jobs = []
    combined_rows = []
    for mode in ("accuracy", "resources"):
        for pipeline_id in pipeline_ids:
            for source_index in range(2):
                job_id = f"combined_{mode}_{pipeline_id}_{source_index}"
                spec = {
                    "job_id": job_id,
                    "pipeline_id": pipeline_id,
                    "protocol_id": f"source_{source_index}",
                    "source_key": f"source_{source_index}",
                    "split": "development",
                    "measurement_mode": mode,
                }
                combined_jobs.append(spec)
                combined_rows.append(
                    {
                        **spec,
                        "evaluation_material_inspected": False,
                        "result_checksums_sha256": _canonical_hash(job_id),
                    }
                )
    result_set = _canonical_hash(
        {
            row["job_id"]: row["result_checksums_sha256"]
            for row in combined_rows
        }
    )
    identity_core = {
        "identity_schema_version": (
            "full-pipeline-development-combined-campaign-identity.v1"
        ),
        "full_protocol_id": protocol_id,
        "development_identity": development_identity,
        "evaluation_identity": evaluation_identity,
        "campaign_stage": "prompt4_combined_development_evidence",
        "selected_pipeline_ids": pipeline_ids,
        "measurement_modes": ["accuracy", "resources"],
        "selected_case_ids": [f"case_{index:04d}" for index in range(807)],
        "case_index": {
            f"case_{index:04d}": {"split": "development"}
            for index in range(807)
        },
        "jobs": combined_jobs,
        "development_result_set_sha256": result_set,
        "development_only": True,
        "evaluation_material_inspected": False,
    }
    combined_identity = _canonical_hash(identity_core)
    combined_manifest = {
        "schema_version": "full-pipeline-development-combined-campaign.v1",
        "campaign_id": f"full_pipeline_development_combined_{combined_identity[:12]}",
        "campaign_identity_sha256": combined_identity,
        **identity_core,
        "pipeline_count": 18,
        "job_count": 72,
        "case_count": 807,
        "parallelism_policy": {
            "accuracy_maximum_jobs": 2,
            "resource_measurement_jobs": 1,
            "resource_results_comparable_only_with_serial_resource_results": True,
        },
        "production_winner_selected": False,
        "held_out_evaluation_allowed": False,
        "model_inference_performed_by_combination": False,
    }
    combined_analysis = {
        "schema_version": "full-pipeline-evaluation-analysis.v1",
        "campaign_id": combined_manifest["campaign_id"],
        "campaign_identity_sha256": combined_identity,
        "complete_result_count": 72,
        "accuracy_result_count": 36,
        "resource_result_count": 36,
        "development_result_set_sha256": result_set,
        "weighted_composite_score_created": False,
        "evaluation_material_inspected": False,
        "rows": combined_rows,
    }
    _write_json(workspace / "combined_evidence/campaign_manifest.json", combined_manifest)
    _write_json(
        workspace / "combined_evidence/analysis/analysis.json", combined_analysis
    )

    frozen_root = workspace / "frozen_pipeline_configs"
    registry_by_id = {row["pipeline_id"]: row for row in registry_entries}
    for pipeline_id in pipeline_ids:
        hybrid = (
            "H2"
            if pipeline_id.endswith("dr_ir")
            else "H4"
            if pipeline_id.endswith("dw_ir")
            else "H5"
            if pipeline_id.endswith("dr_ie")
            else "challenger"
        )
        if pipeline_id in EXPECTED_TIER_B:
            identity_policy = {
                "frozen_anchor": True,
                "calibration_protocol_id": FROZEN_HYBRID_PROTOCOL_ID,
                "decision_policy_sha256": FROZEN_HYBRID_SELECTION_SHA256,
                "calibration_result_sha256": FROZEN_HYBRID_SELECTION_SHA256,
                "score_threshold": EXPECTED_ANCHOR_THRESHOLDS[hybrid],
                "margin_threshold": 0.03,
                "minimum_evidence_sec": 2.0,
            }
        else:
            identity_policy = {
                "decision_policy_sha256": registry_by_id[pipeline_id][
                    "calibration_identity_sha256"
                ],
                "calibration_partition": "development",
            }
        config_core = {
            "schema_version": "full-pipeline-development-config-freeze.v1",
            "status": "IMMUTABLE_DEVELOPMENT_FREEZE",
            "pipeline_id": pipeline_id,
            "development_protocol_sha256": development_identity,
            "development_result_set_sha256": result_set,
            "evaluation_material_inspected": False,
            "evaluation_retuning_allowed": False,
            "production_winner_selected": False,
            "runtime_anchor_qualification": anchor_qualification,
            "aliases": {"hybrid": hybrid},
            "identity_policy": identity_policy,
            "source_hashes": {
                "frozen_hybrid_selection_sha256": FROZEN_HYBRID_SELECTION_SHA256,
                "development_policy_registry_sha256": registry[
                    "registry_identity_sha256"
                ],
            },
        }
        config = {
            **config_core,
            "freeze_identity_sha256": _canonical_hash(config_core),
        }
        config_path = frozen_root / f"{pipeline_id}.yaml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(config, sort_keys=True), encoding="utf-8")
    frozen_checksums = {
        path.name: _sha256(path) for path in sorted(frozen_root.glob("*.yaml"))
    }
    _write_json(
        frozen_root / "checksums.json",
        {
            "schema_version": "full-pipeline-development-config-checksums.v1",
            "pipeline_count": 18,
            "entries": frozen_checksums,
        },
    )

    report.mkdir(parents=True, exist_ok=True)
    matrix_rows = [
        {"pipeline_id": pipeline_id, "qualification_status": "PASS"}
        for pipeline_id in pipeline_ids
    ]
    summary_rows = [
        {
            "pipeline_id": pipeline_id,
            "split": "development",
            "evaluation_material_inspected": False,
        }
        for pipeline_id in pipeline_ids
    ]
    _write_csv(report / "development_matrix.csv", matrix_rows)
    _write_csv(report / "development_summary.csv", summary_rows)
    _write_csv(
        report / "resource_spot_checks.csv",
        [
            {
                "pipeline_id": pipeline_id,
                "comparison_scope": "serial_matched_resource_jobs_only",
            }
            for pipeline_id in pipeline_ids
        ],
    )
    _write_csv(report / "failure_inventory.csv", [])
    mandatory = sorted(EXPECTED_TIER_B)
    challenger_selection = challenger_ids[:2]
    extended_core = {
        "schema_version": "full-pipeline-tier-b-development-set.v1",
        "status": "FROZEN_DEVELOPMENT_ONLY",
        "weighted_composite_score_used": False,
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
        "mandatory_pipeline_ids": mandatory,
        "additional_challenger_pipeline_ids": challenger_selection,
        "extended_pipeline_ids": mandatory + challenger_selection,
    }
    extended = {**extended_core, "identity_sha256": _canonical_hash(extended_core)}
    (report / "extended_set.yaml").write_text(
        yaml.safe_dump(extended, sort_keys=True), encoding="utf-8"
    )
    summaries = [{"pipeline_id": pipeline_id} for pipeline_id in pipeline_ids]
    analysis_core = {
        "schema_version": "full-pipeline-development-analysis.v1",
        "status": "PASS",
        "pipeline_count": 18,
        "pipeline_summaries": summaries,
        "extended_set": extended,
        "development_identity_sha256": development_identity,
        "campaign_identity_sha256": combined_identity,
        "weighted_composite_score_created": False,
        "evaluation_material_inspected": False,
        "production_winner_selected": False,
        "final_winner": None,
    }
    _write_json(
        report / "development_analysis.json",
        {
            **analysis_core,
            "analysis_identity_sha256": _canonical_hash(analysis_core),
        },
    )
    (report / "development_report.md").write_text(
        "# Development\n\nProduction winner: none\n", encoding="utf-8"
    )
    (report / "metric_guide.md").write_text("# Metrics\n", encoding="utf-8")
    report_configs = report / "frozen_pipeline_configs"
    report_configs.mkdir(parents=True, exist_ok=True)
    for path in frozen_root.iterdir():
        if path.is_file():
            shutil.copy2(path, report_configs / path.name)
    report_hashes = {
        path.relative_to(report).as_posix(): _sha256(path)
        for path in sorted(report.rglob("*"))
        if path.is_file()
    }
    _write_json(
        report / "checksums.json",
        {
            "schema_version": "full-pipeline-development-report-checksums.v1",
            "entries": report_hashes,
            "raw_audio_included": False,
            "model_assets_included": False,
            "cache_payloads_included": False,
            "biometric_vectors_included": False,
        },
    )
    _write_test_zip(report)

    artifacts = {
        "full_pipeline_development_package": {
            "paths": development_package_paths
        },
        "full_pipeline_development_wrapper": _artifact(REQUIRED_PROMPT_4_WRAPPER_PATHS),
        "full_pipeline_development_tests": _artifact(REQUIRED_PROMPT_4_TEST_PATHS),
        "full_pipeline_development_orchestration_plan": _artifact(
            REQUIRED_PROMPT_4_ORCHESTRATION_PATHS
        ),
        "full_pipeline_development_policy_freeze": _artifact(
            REQUIRED_PROMPT_4_POLICY_PATHS
        ),
        "full_pipeline_development_qualification": _artifact(
            REQUIRED_PROMPT_4_QUALIFICATION_PATHS
        ),
        "full_pipeline_development_combined_evidence": _artifact(
            REQUIRED_PROMPT_4_COMBINED_PATHS
        ),
        "full_pipeline_development_frozen_configs": _artifact(
            REQUIRED_PROMPT_4_FROZEN_CONFIG_PATHS
        ),
        "full_pipeline_development_report": _artifact(REQUIRED_PROMPT_4_REPORT_PATHS),
    }
    assert set(artifacts) == REQUIRED_PROMPT_4_CANONICAL_ARTIFACTS
    state = {
        "current_prompt_index": 4,
        "remaining_prompt_indices": [5, 6, 7, 8],
        "remaining_prompt_status": "PENDING_UNSPECIFIED",
        "model_inference_run_by_prompt_4": True,
        "physical_microphone_capture_run_by_prompt_4": False,
        "held_out_evaluation_run_by_prompt_4": False,
        "evaluation_material_inspected_by_prompt_4": False,
        "production_winner_selected_by_prompt_4": False,
        "held_out_protocol_metadata_and_reference_contracts_validated_for_protocol_lock": True,
        "held_out_evaluation_identity_bound_to_campaign_identity": True,
        "held_out_evaluation_audio_processed": False,
        "held_out_evaluation_inference_or_scoring_executed": False,
        "held_out_predictions_metrics_or_results_inspected": False,
        "held_out_evaluation_used_for_calibration_metrics_or_selection": False,
        "evaluation_tiers": {
            "tier_a": {
                "pipeline_count": 18,
                "status": "DEVELOPMENT_COMPLETE_HELDOUT_NOT_RUN",
            },
            "tier_b": {
                "required_pipeline_count": 6,
                "maximum_additional_challengers": 2,
                "status": "EXTENDED_SET_PREDECLARED_DEVELOPMENT_ONLY",
            },
            "tier_c": {
                "selected_pipeline_ids": [],
                "status": "UNSELECTED_UNTIL_HELDOUT_AND_EXTENDED_TESTING",
            },
        },
    }
    completion = {
        "prompt_4": "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE",
        "all_18_pipelines_qualified_on_development": True,
        "challenger_policies_frozen": True,
        "frozen_anchor_policies_preserved": True,
        "complete_807_case_development_campaign_passed": True,
        "serial_resource_spot_checks_passed": True,
        "combined_development_evidence_passed": True,
        "all_18_pipeline_configs_frozen": True,
        "development_report_published": True,
        "tier_b_extended_set_predeclared": True,
        "tier_a_development_complete": True,
        "held_out_evaluation_executed_by_prompt_4": False,
        "production_winner_selected": False,
        "tier_a_executed": False,
        "tier_b_executed": False,
        "tier_c_selected": False,
    }
    return (
        state,
        completion,
        artifacts,
        evaluation_root,
        policy_adoption_bindings,
    )


def _artifact(paths: set[str]) -> dict[str, dict[str, str]]:
    return {"paths": {path: "0" * 64 for path in paths}}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["pipeline_id"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8", newline="")


def _write_test_zip(root: Path) -> None:
    destination = root / "full_pipeline_development_compact.zip"
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path == destination:
                continue
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def _synthetic_prompt_2_state(tmp_path: Path) -> tuple[dict[str, Any], Path]:
    """Upgrade a hash-refreshed Prompt-1 state without touching the real lock."""

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    smoke_path = tmp_path / "common_demo_smoke.json"
    shared_speaker_id = "common_demo_smoke_speaker_fixture"
    profile_by_backend = {
        "speechbrain_ecapa": "profile_fixture_ie",
        "redimnet2_b2_speaker_embedding": "profile_fixture_ir",
    }
    sessions: list[dict[str, object]] = []
    previous: dict[str, object] | None = None
    for index, (label, pipeline_id) in enumerate(
        EXPECTED_COMMON_DEMO_SMOKE_PRESETS.items()
    ):
        session_id = f"session-{index + 1}"
        row: dict[str, object] = {
            "label": label,
            "pipeline_id": pipeline_id,
            "pipeline_config_sha256": "3" * 64,
            "component_backend_ids": EXPECTED_COMMON_DEMO_SMOKE_COMPONENTS[label],
            "enrollment_profile_ids": [
                profile_by_backend[EXPECTED_COMMON_DEMO_PROFILE_BACKENDS[label]]
            ],
            "state": "completed",
            "completion_state": "complete",
            "session_id": session_id,
            "previous_session_id": previous.get("session_id") if previous else None,
            "previous_pipeline_id": previous.get("pipeline_id") if previous else None,
            "model_switch_between_sessions": index > 0,
            "event_count": 4,
            "export_manifest_sha256": "1" * 64,
            "labelled_transcript_sha256": "2" * 64,
            "useful_labelled_attribution": {
                "span_index": 1,
                "start_sec": 0.0,
                "end_sec": 1.0,
                "anonymous_speaker_id": "anon_0001",
                "speaker_label": "Unknown_1",
                "alignment_status": "aligned",
            },
            "immutable_transition": None,
        }
        if previous is not None:
            row["immutable_transition"] = {
                "transition_kind": "new_immutable_session_after_join",
                "predecessor_session_id": previous["session_id"],
                "predecessor_pipeline_id": previous["pipeline_id"],
                "predecessor_state": "completed",
                "predecessor_joined": True,
                "current_session_id": session_id,
                "current_pipeline_id": pipeline_id,
                "changed_component_families": ["speaker_embedding"],
                "distinct_session_id": True,
                "distinct_output_root": True,
            }
        sessions.append(row)
        previous = row
    smoke = {
        "schema_version": "full-pipeline-common-demo-smoke.v1",
        "status": "PASS",
        "purpose": "bounded_application_mechanics_only",
        "scientific_campaign_started": False,
        "physical_microphone_capture_performed": False,
        "shared_speaker_id": shared_speaker_id,
        "enrollment": [
            {
                "state": "profile_created",
                "speaker_id": shared_speaker_id,
                "profile_id": profile_by_backend["speechbrain_ecapa"],
                "profile_sha256": "4" * 64,
                "backend": {"backend_id": "speechbrain_ecapa"},
                "biometric_vectors_inline": False,
                "network_transfer_performed": False,
            },
            {
                "state": "profile_created",
                "speaker_id": shared_speaker_id,
                "profile_id": profile_by_backend[
                    "redimnet2_b2_speaker_embedding"
                ],
                "profile_sha256": "5" * 64,
                "backend": {
                    "backend_id": "redimnet2_b2_speaker_embedding"
                },
                "biometric_vectors_inline": False,
                "network_transfer_performed": False,
            },
        ],
        "sessions": sessions,
        "required_presets_exercised": list(EXPECTED_COMMON_DEMO_SMOKE_PRESETS),
        "file_mode_exercised": True,
        "enrollment_exercised": True,
        "labelled_transcript_export_exercised": True,
        "model_switching_between_sessions_exercised": True,
    }
    smoke_path.write_text(
        json.dumps(smoke, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state.update(
        {
            "status": "COMPLETE_COMMON_DEMO",
            "current_prompt_index": 2,
            "remaining_prompt_indices": list(range(3, 9)),
            "bounded_inference_run_by_prompt_2": True,
            "physical_microphone_capture_run_by_prompt_2": False,
        }
    )
    state["completion_state"].update(
        {
            "prompt_2": "COMPLETE_COMMON_DEMO",
            "common_demo_implemented": True,
            "all_18_demo_presets_available": True,
            "six_highlighted_demo_presets_available": True,
            "three_required_bounded_demo_presets_passed": True,
            "common_demo_enrollment_smoke_passed": True,
            "common_demo_file_smoke_passed": True,
            "common_demo_export_smoke_passed": True,
            "common_demo_model_switch_smoke_passed": True,
            "scientific_campaign_executed_by_prompt_2": False,
            "physical_microphone_smoke_executed": False,
        }
    )
    state["validation"].update(
        {
            "status": "PASS",
            "demo_preset_count": 18,
            "demo_highlighted_preset_count": 6,
            "demo_required_bounded_preset_count": 3,
            "common_demo_smoke_status": "PASS",
        }
    )
    state["canonical_artifacts"].update(
        {
            "common_demo_package": {
                "paths": {
                    "app/full_pipeline_demo/__init__.py": "",
                    "app/full_pipeline_demo/__main__.py": "",
                    "app/full_pipeline_demo/README.md": "",
                    "app/full_pipeline_demo/cli.py": "",
                    "app/full_pipeline_demo/devices.py": "",
                    "app/full_pipeline_demo/enrollment.py": "",
                    "app/full_pipeline_demo/exports.py": "",
                    "app/full_pipeline_demo/presets.py": "",
                    "app/full_pipeline_demo/session.py": "",
                    "app/full_pipeline_demo/smoke.py": "",
                    "app/full_pipeline_demo/state.py": "",
                    "app/full_pipeline_demo/ui.py": "",
                    "scripts/run_full_pipeline_demo.ps1": "",
                }
            },
            "common_demo_targeted_tests": {
                "paths": {
                    "tests/full_pipeline/test_demo_runtime_controls.py": "",
                    "tests/full_pipeline_demo/test_cli.py": "",
                    "tests/full_pipeline_demo/test_presets_enrollment.py": "",
                    "tests/full_pipeline_demo/test_session_export.py": "",
                    "tests/full_pipeline_demo/test_smoke_integrity.py": "",
                    "tests/full_pipeline_demo/test_state_devices.py": "",
                    "tests/full_pipeline_demo/test_ui.py": "",
                }
            },
            "prompt_2_common_demo_smoke": {
                "path": str(smoke_path),
                "sha256": "",
            },
        }
    )
    _refresh_canonical_hashes(state)
    return state, smoke_path


def _synthetic_prompt_3_state(
    tmp_path: Path,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    Path,
    Path,
]:
    """Create a tiny prepared-protocol and smoke lock without model inference."""

    evaluation_root = tmp_path / "Evaluation Tool"
    config_path = (
        evaluation_root
        / "configs/automated_evaluation/full_speech_pipeline_v1.yaml"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": "full-speech-pipeline-config.v1",
                "protocol_name": "full_speech_pipeline_v1",
                "protocol_version": 1,
                "selection_seed": 3800,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    protocol_root = (
        evaluation_root / "benchmarks/full_pipeline/full_speech_pipeline_v1"
    )
    protocol_id = "full_speech_pipeline_v1_123456789abc"
    case_ids_by_split = {
        "development": ["case_dev_1"],
        "evaluation": ["case_eval_1"],
    }
    split_identities: dict[str, dict[str, object]] = {}
    for split, case_ids in case_ids_by_split.items():
        split_root = protocol_root / split
        case_path = split_root / "case_manifest.jsonl"
        case_path.parent.mkdir(parents=True, exist_ok=True)
        case_path.write_text(
            "".join(
                json.dumps(
                    {
                        "protocol_case_id": case_id,
                        "partition": split,
                        "protocol_id": protocol_id,
                    },
                    sort_keys=True,
                )
                + "\n"
                for case_id in case_ids
            ),
            encoding="utf-8",
        )
        for relative in (
            "references/speaker_attributed_transcript.jsonl",
            "identity/identity_overlays.jsonl",
            "enrollment/enrollment_registry.jsonl",
        ):
            output = split_root / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text("", encoding="utf-8")
        digest = _canonical_hash(
            {
                "protocol_id": protocol_id,
                "partition": split,
                "case_ids": case_ids,
            }
        )
        split_identities[split] = {
            "partition_id": f"{protocol_id}_{split}_{digest[:12]}",
            "case_count": len(case_ids),
            "case_ids_sha256": hashlib.sha256(
                "\n".join(case_ids).encode("utf-8")
            ).hexdigest(),
            "identity_sha256": digest,
        }

    protocol_root.mkdir(parents=True, exist_ok=True)
    source_audit = {
        "schema_version": "full-speech-pipeline-source-audit.v1",
        "status": "PASS",
        "config_id": protocol_id,
        "sources": [
            {
                "source_key": f"source_{index}",
                "installed": True,
                "errors": [],
            }
            for index in range(6)
        ],
        "downloads_attempted": False,
        "inference_started": False,
    }
    summary = {
        "schema_version": "full-speech-pipeline.v1",
        "protocol_id": protocol_id,
        "protocol_name": "full_speech_pipeline_v1",
        "protocol_version": 1,
        "selection_seed": 3800,
        "config_path": "configs/automated_evaluation/full_speech_pipeline_v1.yaml",
        "config_sha256": _sha256(config_path),
        "development_identity": split_identities["development"],
        "evaluation_identity": split_identities["evaluation"],
        "case_counts": {split: len(rows) for split, rows in case_ids_by_split.items()},
        "primary_development_evaluation_speaker_disjoint": True,
        "development_evaluation_enrollment_gallery_speaker_disjoint": True,
        "evaluation_only": True,
        "training_eligible": False,
        "audio_copied_or_modified": False,
        "downloads_attempted": False,
        "inference_started": False,
    }
    (protocol_root / "source_audit.json").write_text(
        json.dumps(source_audit, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (protocol_root / "protocol_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    checksum_files = {
        path.relative_to(protocol_root).as_posix(): _sha256(path)
        for path in sorted(protocol_root.rglob("*"))
        if path.is_file() and path.name != "checksums.json"
    }
    (protocol_root / "checksums.json").write_text(
        json.dumps(
            {
                "schema_version": "full-speech-pipeline-checksums.v1",
                "protocol_id": protocol_id,
                "files": checksum_files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    smoke_root = evaluation_root / "smoke_fixture"
    for result_name in ("perfect", "failure"):
        result_checksum = smoke_root / f"{result_name}_result/checksums.json"
        result_checksum.parent.mkdir(parents=True, exist_ok=True)
        result_checksum.write_text(
            json.dumps({"result": result_name}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    smoke_path = smoke_root / "infrastructure_smoke.json"
    smoke = {
        "schema_version": "full-pipeline-evaluation-infrastructure-smoke.v1",
        "status": "PASS",
        "purpose": "tiny_synthetic_infrastructure_only",
        "perfect_result_valid": True,
        "perfect_result_reusable": True,
        "failure_result_valid": True,
        "failure_result_reusable": False,
        "perfect_result_checksum_sha256": _sha256(
            smoke_root / "perfect_result/checksums.json"
        ),
        "failure_result_checksum_sha256": _sha256(
            smoke_root / "failure_result/checksums.json"
        ),
        "scorer_checks": {
            "perfect_asr_wer_zero": True,
            "failed_output_counted": True,
            "perfect_diarization_der_zero": True,
        },
        "restart_state": {
            "status": "PASS",
            "job_count": 2,
            "complete_jobs": 2,
            "retry_attempt_count": 2,
            "lease_restart_exercised": True,
            "checksum_reuse_identity_bound": True,
        },
        "model_inference_performed": False,
        "dataset_downloads_performed": False,
        "long_scientific_campaign_started": False,
        "pipelines_evaluated": 0,
        "synthetic_cases": 2,
    }
    smoke_path.write_text(
        json.dumps(smoke, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    artifacts: dict[str, Any] = {
        "full_speech_pipeline_v1_protocol": {
            "paths": {path: "0" * 64 for path in REQUIRED_FULL_PIPELINE_PROTOCOL_PATHS}
        },
        "full_pipeline_evaluation_result_schema": {
            "path": (
                "configs/automated_evaluation/schemas/"
                "full_pipeline_evaluation_result.v1.schema.json"
            ),
            "sha256": "0" * 64,
        },
        "full_pipeline_evaluation_package": {
            "paths": {
                path: "0" * 64
                for path in REQUIRED_FULL_PIPELINE_EVALUATION_PACKAGE_PATHS
            }
        },
        "full_pipeline_evaluation_wrappers": {
            "paths": {
                path: "0" * 64
                for path in REQUIRED_FULL_PIPELINE_EVALUATION_WRAPPER_PATHS
            }
        },
        "full_pipeline_evaluation_targeted_tests": {
            "paths": {
                path: "0" * 64
                for path in REQUIRED_FULL_PIPELINE_EVALUATION_TEST_PATHS
            }
        },
        "prompt_3_synthetic_smoke": {
            "path": str(smoke_path),
            "sha256": _sha256(smoke_path),
        },
    }
    completion = {
        "prompt_3": "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
        "full_pipeline_evaluation_infrastructure_implemented": True,
        "full_speech_pipeline_v1_protocol_prepared": True,
        "full_speech_pipeline_v1_protocol_validated": True,
        "all_18_evaluation_pipelines_planned": True,
        "common_result_tree_schema_implemented": True,
        "all_required_scorers_implemented": True,
        "restart_safe_evaluation_controller_implemented": True,
        "measured_evaluation_monitor_implemented": True,
        "synthetic_perfect_failure_smoke_passed": True,
        "scientific_campaign_executed_by_prompt_3": False,
    }
    state = {
        "status": "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
        "current_prompt_index": 3,
        "remaining_prompt_indices": list(range(4, 9)),
        "bounded_inference_run_by_prompt_3": False,
        "synthetic_evaluation_smoke_run_by_prompt_3": True,
        "physical_microphone_capture_run_by_prompt_3": False,
    }
    return state, artifacts, completion, evaluation_root, smoke_path


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _refresh_canonical_hashes(state: dict[str, Any]) -> None:
    for artifact in state["canonical_artifacts"].values():
        relative_path = artifact.get("path")
        if isinstance(relative_path, str):
            artifact["sha256"] = _sha256(_state_path(relative_path))
        path_hashes = artifact.get("paths")
        if isinstance(path_hashes, dict):
            for relative in tuple(path_hashes):
                path_hashes[relative] = _sha256(_state_path(relative))


def _state_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else EVALUATION_ROOT / path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
