"""Non-inference validation for the authoritative full-pipeline program lock."""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Iterable, Mapping
import zipfile

import yaml

from . import (
    CONTRACT_SCHEMA_VERSION,
    MATRIX_SCHEMA_VERSION,
    PROGRAM_ID,
    PROTOCOL_VERSION,
)


PUBLIC_CONTRACTS = {
    "AudioFrame",
    "AsrPartialEvent",
    "AsrFinalEvent",
    "SpeechActivityEvent",
    "SpeakerBoundaryEvent",
    "AnonymousSpeakerEvent",
    "IdentityEvidenceEvent",
    "IdentityLabelEvent",
    "TranscriptRevisionEvent",
    "PipelineStatusEvent",
    "ResourceTelemetryEvent",
    "EnrollmentSample",
    "EnrollmentProfile",
    "SessionState",
    "PipelineResult",
}

EXPECTED_TIER_B = {
    "fullpipe_v1_ao_dr_ir",
    "fullpipe_v1_ag_dr_ir",
    "fullpipe_v1_ao_dw_ir",
    "fullpipe_v1_ag_dw_ir",
    "fullpipe_v1_ao_dr_ie",
    "fullpipe_v1_ag_dr_ie",
}

EXPECTED_PIPELINE_IDS = {
    f"fullpipe_v1_{asr}_{diarization}_{identity}"
    for asr, diarization, identity in itertools.product(
        ("ao", "ag"), ("dw", "dr", "de"), ("iw", "ir", "ie")
    )
}
EXPECTED_PROMPT_4_CHALLENGERS = EXPECTED_PIPELINE_IDS - EXPECTED_TIER_B
FROZEN_HYBRID_PROTOCOL_ID = "hybrid_speaker_attribution_product_v2_a68cc1ac26aa"
FROZEN_HYBRID_SELECTION_SHA256 = (
    "2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a"
)
EXPECTED_ANCHOR_THRESHOLDS = {
    "H2": 0.5265351286789879,
    "H4": 0.5331755752703802,
    "H5": 0.4572960706169966,
}

PROMPT_4_WORKSPACE = (
    "automated_runs/"
    "full_pipeline_development_v1_prompt4_execution_recovery_v5_restart_contract_fix"
)
PROMPT_4_CALIBRATION_SOURCE_WORKSPACE = (
    "automated_runs/full_pipeline_development_v1_prompt4_execution_recovery_v3"
)
PROMPT_4_POLICY_ADOPTION_BINDINGS = {
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
PROMPT_4_REPORT_ROOT = (
    "JustPeachyResearchSummaries/full_pipeline/development/full_speech_pipeline_v1"
)
REQUIRED_PROMPT_4_PACKAGE_PATHS = {
    "app/full_pipeline_development/__init__.py",
    "app/full_pipeline_development/README.md",
    "app/full_pipeline_development/cli.py",
    "app/full_pipeline_development/evidence.py",
    "app/full_pipeline_development/freeze.py",
    "app/full_pipeline_development/orchestration.py",
    "app/full_pipeline_development/policies.py",
    "app/full_pipeline_development/qualification.py",
    "app/full_pipeline_development/qualification_execution.py",
    "app/full_pipeline_development/reporting.py",
    "app/full_pipeline_development/shared_execution.py",
}
REQUIRED_PROMPT_4_WRAPPER_PATHS = {
    "scripts/run_full_pipeline_development.ps1",
}
REQUIRED_PROMPT_4_TEST_PATHS = {
    "tests/full_pipeline_development/test_anchor_runtime_semantics.py",
    "tests/full_pipeline_development/test_evidence.py",
    "tests/full_pipeline_development/test_orchestration.py",
    "tests/full_pipeline_development/test_policies_freeze.py",
    "tests/full_pipeline_development/test_qualification_execution.py",
    "tests/full_pipeline_development/test_qualification_reporting.py",
    "tests/full_pipeline_development/test_shared_execution.py",
}
REQUIRED_PROMPT_4_CANONICAL_ARTIFACTS = {
    "full_pipeline_development_package",
    "full_pipeline_development_wrapper",
    "full_pipeline_development_tests",
    "full_pipeline_development_orchestration_plan",
    "full_pipeline_development_policy_freeze",
    "full_pipeline_development_qualification",
    "full_pipeline_development_combined_evidence",
    "full_pipeline_development_frozen_configs",
    "full_pipeline_development_report",
}
REQUIRED_PROMPT_4_ORCHESTRATION_PATHS = {
    f"{PROMPT_4_WORKSPACE}/orchestration_plan.json",
    f"{PROMPT_4_WORKSPACE}/qualification_shared/campaign_manifest.json",
    f"{PROMPT_4_WORKSPACE}/qualification_cold/campaign_manifest.json",
    f"{PROMPT_4_WORKSPACE}/development_accuracy/campaign_manifest.json",
    f"{PROMPT_4_WORKSPACE}/resource_spots/campaign_manifest.json",
}
REQUIRED_PROMPT_4_POLICY_PATHS = {
    f"{PROMPT_4_CALIBRATION_SOURCE_WORKSPACE}/calibration/campaign_manifest.json",
    f"{PROMPT_4_CALIBRATION_SOURCE_WORKSPACE}/frozen/decision_policy_registry.json",
    f"{PROMPT_4_CALIBRATION_SOURCE_WORKSPACE}/frozen/calibration_freeze.json",
    f"{PROMPT_4_WORKSPACE}/frozen/decision_policy_registry.json",
    f"{PROMPT_4_WORKSPACE}/frozen/calibration_freeze.json",
    f"{PROMPT_4_WORKSPACE}/frozen/policy_adoption_provenance.json",
}
REQUIRED_PROMPT_4_QUALIFICATION_PATHS = {
    f"{PROMPT_4_WORKSPACE}/qualification_execution_plan.json",
    f"{PROMPT_4_WORKSPACE}/qualification/qualification_plan.json",
    f"{PROMPT_4_WORKSPACE}/qualification/qualification.json",
    f"{PROMPT_4_WORKSPACE}/qualification/anchor_runtime_qualification.json",
    f"{PROMPT_4_WORKSPACE}/qualification/evidence/restarts/restart_manifest.json",
}
REQUIRED_PROMPT_4_COMBINED_PATHS = {
    f"{PROMPT_4_WORKSPACE}/combined_evidence/campaign_manifest.json",
    f"{PROMPT_4_WORKSPACE}/combined_evidence/analysis/analysis.json",
}
REQUIRED_PROMPT_4_FROZEN_CONFIG_PATHS = {
    f"{PROMPT_4_WORKSPACE}/frozen_pipeline_configs/{pipeline_id}.yaml"
    for pipeline_id in EXPECTED_PIPELINE_IDS
} | {f"{PROMPT_4_WORKSPACE}/frozen_pipeline_configs/checksums.json"}
REQUIRED_PROMPT_4_REPORT_FILES = {
    "development_matrix.csv",
    "development_summary.csv",
    "extended_set.yaml",
    "development_report.md",
    "metric_guide.md",
    "failure_inventory.csv",
    "resource_spot_checks.csv",
    "development_analysis.json",
    "checksums.json",
    "full_pipeline_development_compact.zip",
}
REQUIRED_PROMPT_4_REPORT_PATHS = {
    f"{PROMPT_4_REPORT_ROOT}/{relative}"
    for relative in REQUIRED_PROMPT_4_REPORT_FILES
} | {
    f"{PROMPT_4_REPORT_ROOT}/frozen_pipeline_configs/{pipeline_id}.yaml"
    for pipeline_id in EXPECTED_PIPELINE_IDS
} | {f"{PROMPT_4_REPORT_ROOT}/frozen_pipeline_configs/checksums.json"}

EXPECTED_COMMON_DEMO_SMOKE_PRESETS = {
    "AG-H5": "fullpipe_v1_ag_dr_ie",
    "AG-H2": "fullpipe_v1_ag_dr_ir",
    "AO-H4": "fullpipe_v1_ao_dw_ir",
}

_COMMON_DEMO_COMPONENTS = {
    "capture": "backend_neutral_audio_source",
    "clustering": "online_normalized_centroid_cosine",
    "pipeline": "full_pipeline_coordinator",
    "segmentation": "pyannote_segmentation_3_0",
    "telemetry": "resource_telemetry",
    "transcript": "causal_transcript_speaker_aligner",
}

EXPECTED_COMMON_DEMO_SMOKE_COMPONENTS = {
    "AG-H5": {
        **_COMMON_DEMO_COMPONENTS,
        "asr": "sherpa_onnx_libri_giga_zipformer_2023_06_21",
        "diarization": "modular_pyannote_redimnet2",
        "speaker_embedding": "speechbrain_ecapa",
        "speaker_matching": "open_set_h5",
    },
    "AG-H2": {
        **_COMMON_DEMO_COMPONENTS,
        "asr": "sherpa_onnx_libri_giga_zipformer_2023_06_21",
        "diarization": "modular_pyannote_redimnet2",
        "speaker_embedding": "redimnet2_b2_speaker_embedding",
        "speaker_matching": "open_set_h2",
    },
    "AO-H4": {
        **_COMMON_DEMO_COMPONENTS,
        "asr": "sherpa_onnx",
        "diarization": "modular_pyannote_wespeaker",
        "speaker_embedding": "redimnet2_b2_speaker_embedding",
        "speaker_matching": "open_set_h4",
    },
}

EXPECTED_COMMON_DEMO_PROFILE_BACKENDS = {
    "AG-H5": "speechbrain_ecapa",
    "AG-H2": "redimnet2_b2_speaker_embedding",
    "AO-H4": "redimnet2_b2_speaker_embedding",
}

REQUIRED_PROMPT_1_CANONICAL_ARTIFACTS = {
    "runtime_readme",
    "runtime_config",
    "runtime_wrapper",
    "native_sherpa_adapter",
    "runtime_package",
    "runtime_targeted_tests",
    "prompt_1_component_smoke",
    "prompt_1_enrollment_smoke",
    "prompt_1_file_smoke_result",
    "prompt_1_file_smoke_session_state",
}

REQUIRED_PROMPT_2_CANONICAL_ARTIFACTS = {
    "common_demo_package",
    "common_demo_targeted_tests",
    "prompt_2_common_demo_smoke",
}

REQUIRED_PROMPT_3_CANONICAL_ARTIFACTS = {
    "full_speech_pipeline_v1_protocol",
    "full_pipeline_evaluation_result_schema",
    "full_pipeline_evaluation_package",
    "full_pipeline_evaluation_wrappers",
    "full_pipeline_evaluation_targeted_tests",
    "prompt_3_synthetic_smoke",
}

REQUIRED_FULL_PIPELINE_PROTOCOL_PATHS = {
    "configs/automated_evaluation/full_speech_pipeline_v1.yaml",
    "benchmarks/full_pipeline/full_speech_pipeline_v1/protocol_summary.json",
    "benchmarks/full_pipeline/full_speech_pipeline_v1/source_audit.json",
    "benchmarks/full_pipeline/full_speech_pipeline_v1/checksums.json",
    "benchmarks/full_pipeline/full_speech_pipeline_v1/development/case_manifest.jsonl",
    (
        "benchmarks/full_pipeline/full_speech_pipeline_v1/development/"
        "references/speaker_attributed_transcript.jsonl"
    ),
    (
        "benchmarks/full_pipeline/full_speech_pipeline_v1/development/"
        "identity/identity_overlays.jsonl"
    ),
    (
        "benchmarks/full_pipeline/full_speech_pipeline_v1/development/"
        "enrollment/enrollment_registry.jsonl"
    ),
    "benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/case_manifest.jsonl",
    (
        "benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/"
        "references/speaker_attributed_transcript.jsonl"
    ),
    (
        "benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/"
        "identity/identity_overlays.jsonl"
    ),
    (
        "benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/"
        "enrollment/enrollment_registry.jsonl"
    ),
}

REQUIRED_FULL_PIPELINE_EVALUATION_PACKAGE_PATHS = {
    "app/full_pipeline_evaluation/__init__.py",
    "app/full_pipeline_evaluation/__main__.py",
    "app/full_pipeline_evaluation/README.md",
    "app/full_pipeline_evaluation/cli.py",
    "app/full_pipeline_evaluation/controller.py",
    "app/full_pipeline_evaluation/host_lock.py",
    "app/full_pipeline_evaluation/io.py",
    "app/full_pipeline_evaluation/metrics.py",
    "app/full_pipeline_evaluation/monitor.py",
    "app/full_pipeline_evaluation/planning.py",
    "app/full_pipeline_evaluation/protocol.py",
    "app/full_pipeline_evaluation/results.py",
    "app/full_pipeline_evaluation/schema.py",
    "app/full_pipeline_evaluation/scorers.py",
    "app/full_pipeline_evaluation/smoke.py",
    "app/full_pipeline_evaluation/store.py",
    "app/full_pipeline_evaluation/synthetic.py",
    "app/full_pipeline_evaluation/worker.py",
}

REQUIRED_FULL_PIPELINE_EVALUATION_WRAPPER_PATHS = {
    "scripts/run_full_pipeline_evaluation.ps1",
    "scripts/monitor_full_pipeline_evaluation.ps1",
}

REQUIRED_FULL_PIPELINE_EVALUATION_TEST_PATHS = {
    "tests/full_pipeline_evaluation/test_cli_wrapper.py",
    "tests/full_pipeline_evaluation/test_controller_store.py",
    "tests/full_pipeline_evaluation/test_host_lock.py",
    "tests/full_pipeline_evaluation/test_metrics_scorers.py",
    "tests/full_pipeline_evaluation/test_protocol.py",
    "tests/full_pipeline_evaluation/test_results_tree.py",
    "tests/full_pipeline_evaluation/test_worker_integration.py",
}

REQUIRED_COMMON_DEMO_PACKAGE_PATHS = {
    "app/full_pipeline_demo/__init__.py",
    "app/full_pipeline_demo/__main__.py",
    "app/full_pipeline_demo/README.md",
    "app/full_pipeline_demo/cli.py",
    "app/full_pipeline_demo/devices.py",
    "app/full_pipeline_demo/enrollment.py",
    "app/full_pipeline_demo/exports.py",
    "app/full_pipeline_demo/presets.py",
    "app/full_pipeline_demo/session.py",
    "app/full_pipeline_demo/smoke.py",
    "app/full_pipeline_demo/state.py",
    "app/full_pipeline_demo/ui.py",
    "scripts/run_full_pipeline_demo.ps1",
}

REQUIRED_COMMON_DEMO_TEST_PATHS = {
    "tests/full_pipeline/test_demo_runtime_controls.py",
    "tests/full_pipeline_demo/test_cli.py",
    "tests/full_pipeline_demo/test_presets_enrollment.py",
    "tests/full_pipeline_demo/test_session_export.py",
    "tests/full_pipeline_demo/test_smoke_integrity.py",
    "tests/full_pipeline_demo/test_state_devices.py",
    "tests/full_pipeline_demo/test_ui.py",
}


class ProgramLockValidationError(RuntimeError):
    """Raised when one or more program-lock invariants do not hold."""

    def __init__(self, errors: Iterable[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("Full-pipeline program lock validation failed:\n- " + "\n- ".join(self.errors))


def validate_program_lock(
    *, evaluation_root: Path | None = None, verify_assets: bool = False
) -> dict[str, object]:
    """Validate program artifacts without importing a model or running inference."""

    root = (
        evaluation_root.resolve()
        if evaluation_root is not None
        else Path(__file__).resolve().parents[2]
    )
    repo_root = root.parents[1]
    matrix_path = root / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
    contract_path = (
        root
        / "configs/automated_evaluation/schemas/full_pipeline_contracts.v1.schema.json"
    )
    state_path = root / "runs/full_pipeline_program/PROGRAM_STATE.json"
    errors: list[str] = []
    source_hashes_checked = 0
    assets_checked = 0

    matrix = _load_yaml(matrix_path, errors)
    contracts = _load_json(contract_path, errors)
    state = _load_json(state_path, errors)
    if not matrix or not contracts or not state:
        raise ProgramLockValidationError(errors)

    _expect(matrix.get("schema_version") == MATRIX_SCHEMA_VERSION, "matrix schema version", errors)
    _expect(matrix.get("program_id") == PROGRAM_ID, "matrix program ID", errors)
    _expect(matrix.get("protocol_version") == PROTOCOL_VERSION, "matrix protocol version", errors)

    contract_declaration = (
        matrix.get("common_contracts")
        if isinstance(matrix.get("common_contracts"), dict)
        else {}
    )
    declared_contract_path = _resolve(root, str(contract_declaration.get("path", "")))
    _expect(
        declared_contract_path == contract_path,
        "matrix binds the canonical common-contract path",
        errors,
    )
    _expect(
        contract_declaration.get("schema_id") == CONTRACT_SCHEMA_VERSION,
        "matrix binds the common-contract schema ID",
        errors,
    )
    _expect(
        contract_declaration.get("event_schema_version") == "full-pipeline-contracts.v1",
        "matrix binds the event schema version",
        errors,
    )
    _expect(
        contract_declaration.get("public_contract_count") == len(PUBLIC_CONTRACTS),
        "matrix declares 15 public contracts",
        errors,
    )
    _expect(
        set(contract_declaration.get("public_contracts", [])) == PUBLIC_CONTRACTS,
        "matrix names all public contracts exactly once",
        errors,
    )
    source_hashes_checked += 1
    _check_file_hash(
        declared_contract_path,
        str(contract_declaration.get("sha256", "")),
        errors,
    )

    axes = matrix.get("axes") if isinstance(matrix.get("axes"), dict) else {}
    asr = axes.get("asr") if isinstance(axes.get("asr"), dict) else {}
    diar = (
        axes.get("anonymous_diarization")
        if isinstance(axes.get("anonymous_diarization"), dict)
        else {}
    )
    identity = axes.get("identity") if isinstance(axes.get("identity"), dict) else {}
    _expect(set(asr) == {"AO", "AG"}, "ASR aliases are exactly AO and AG", errors)
    _expect(
        set(diar) == {"DW", "DR", "DE"},
        "diarization aliases are exactly DW, DR, and DE",
        errors,
    )
    _expect(
        set(identity) == {"IW", "IR", "IE"},
        "identity aliases are exactly IW, IR, and IE",
        errors,
    )

    pipelines = matrix.get("pipelines") if isinstance(matrix.get("pipelines"), list) else []
    expected_product = set(itertools.product(asr, diar, identity))
    observed_product: set[tuple[str, str, str]] = set()
    observed_ids: set[str] = set()
    enrollment_policies = (
        matrix.get("policies", {}).get("enrollment", {})
        if isinstance(matrix.get("policies"), dict)
        else {}
    )
    hybrid_map = matrix.get("hybrid_labels") if isinstance(matrix.get("hybrid_labels"), dict) else {}
    for row in pipelines:
        if not isinstance(row, dict):
            errors.append("pipeline row is not an object")
            continue
        triple = (str(row.get("asr")), str(row.get("anonymous_diarization")), str(row.get("identity")))
        observed_product.add(triple)
        expected_id = f"fullpipe_v1_{triple[0].lower()}_{triple[1].lower()}_{triple[2].lower()}"
        pipeline_id = str(row.get("pipeline_id"))
        _expect(pipeline_id == expected_id, f"pipeline ID for {triple} is {expected_id}", errors)
        _expect(pipeline_id not in observed_ids, f"pipeline ID {pipeline_id} is unique", errors)
        observed_ids.add(pipeline_id)
        _expect(row.get("protocol_version") == PROTOCOL_VERSION, f"{pipeline_id} protocol binding", errors)
        _expect(
            row.get("hybrid_decision_policy") == "full_pipeline_open_set_decision.v1",
            f"{pipeline_id} hybrid policy binding",
            errors,
        )
        _expect(
            row.get("streaming_policy") == "full_pipeline_incremental_stream.v1",
            f"{pipeline_id} streaming policy binding",
            errors,
        )
        alias_policy = enrollment_policies.get(triple[2], {}) if isinstance(enrollment_policies, dict) else {}
        _expect(
            row.get("enrollment_policy") == alias_policy.get("policy_id"),
            f"{pipeline_id} enrollment policy binding",
            errors,
        )
        hybrid = hybrid_map.get(str(row.get("hybrid_label")), {}) if isinstance(hybrid_map, dict) else {}
        _expect(
            hybrid.get("anonymous_diarization") == triple[1]
            and hybrid.get("identity") == triple[2],
            f"{pipeline_id} hybrid H/C label mapping",
            errors,
        )
        expected_frozen = row.get("hybrid_label") in {"H2", "H4", "H5"}
        _expect(
            bool(row.get("frozen_anchor_derived")) == expected_frozen,
            f"{pipeline_id} frozen anchor marker",
            errors,
        )
    _expect(observed_product == expected_product, "pipeline rows cover the exact Cartesian product", errors)
    _expect(len(pipelines) == 18, "matrix contains exactly 18 pipeline rows", errors)
    _expect(matrix.get("matrix_cardinality") == 18, "declared matrix cardinality is 18", errors)

    tier_b = matrix.get("evaluation_tiers", {}).get("tier_b", {})
    required_tier_b = set(tier_b.get("required_pipeline_ids", [])) if isinstance(tier_b, dict) else set()
    row_tier_b = {str(row.get("pipeline_id")) for row in pipelines if isinstance(row, dict) and row.get("tier_b") == "required"}
    _expect(required_tier_b == EXPECTED_TIER_B, "Tier B required list is the six AO/AG H2/H4/H5 anchors", errors)
    _expect(row_tier_b == EXPECTED_TIER_B, "Tier B row markers match the required list", errors)
    _expect(tier_b.get("maximum_additional_challengers") == 2, "Tier B allows at most two challengers", errors)
    tier_c = matrix.get("evaluation_tiers", {}).get("tier_c", {})
    _expect(tier_c.get("maximum_pipeline_count") == 3, "Tier C maximum is three", errors)
    _expect(tier_c.get("current_selection") == [], "Tier C remains unselected in Prompt 0", errors)

    selection = matrix.get("selection_policy", {})
    priorities = selection.get("priorities", []) if isinstance(selection, dict) else []
    _expect(selection.get("weighted_score_used") is False, "selection forbids a weighted score", errors)
    _expect([row.get("rank") for row in priorities] == list(range(1, 13)), "selection priorities preserve ranks 1 through 12", errors)
    _expect(
        selection.get("technical_ranking_separate_from_licensing_provenance_ranking") is True,
        "technical and deployment rankings are separate",
        errors,
    )
    _expect(
        selection.get("deployment_rules", {}).get("sherpa_giga_commercially_cleared") is False,
        "Sherpa Giga is not marked commercially cleared",
        errors,
    )

    for anchor in matrix.get("source_anchors", {}).values():
        if not isinstance(anchor, dict):
            errors.append("source anchor is not an object")
            continue
        candidate = _resolve(root, str(anchor.get("path", "")))
        source_hashes_checked += 1
        _check_file_hash(candidate, str(anchor.get("sha256", "")), errors)

    component_registry = _load_yaml(
        _resolve(root, str(matrix["source_anchors"]["component_registry"]["path"])), errors
    )
    model_registry = _load_yaml(
        _resolve(root, str(matrix["source_anchors"]["model_asset_registry"]["path"])), errors
    )
    environment_registry = _load_yaml(
        _resolve(root, str(matrix["source_anchors"]["environment_registry"]["path"])), errors
    )
    component_rows = component_registry.get("components", []) if isinstance(component_registry, dict) else []
    by_registry_id = {row.get("id"): row for row in component_rows if isinstance(row, dict)}
    for alias, definition in {**asr, **identity}.items():
        registry_id = definition.get("registry_id")
        registered = by_registry_id.get(registry_id)
        _expect(registered is not None, f"{alias} resolves in component registry as {registry_id}", errors)
        if registered:
            _expect(
                registered.get("implementation_class")
                == definition.get("implementation_class"),
                f"{alias} implementation class matches component registry",
                errors,
            )
            _expect(
                registered.get("implementation_path")
                == definition.get("implementation_path"),
                f"{alias} implementation path matches component registry",
                errors,
            )
            _expect(
                registered.get("registry_adapter_class")
                == definition.get("registry_adapter_class"),
                f"{alias} adapter class matches component registry",
                errors,
            )
            _expect(
                registered.get("config_path") == definition.get("config_path"),
                f"{alias} config path matches component registry",
                errors,
            )
            _expect(
                str(registered.get("config_sha256", "")).lower()
                == str(definition.get("config_sha256", "")).lower(),
                f"{alias} config hash matches component registry",
                errors,
            )
            _expect(
                definition.get("environment_profile") in registered.get("environment_profiles", []),
                f"{alias} environment resolves in component registry",
                errors,
            )
        config_path = _resolve(root, str(definition.get("config_path", "")))
        source_hashes_checked += 1
        _check_file_hash(config_path, str(definition.get("config_sha256", "")), errors)
        requirements_path = _resolve(root, str(definition.get("requirements_path", "")))
        source_hashes_checked += 1
        _check_file_hash(requirements_path, str(definition.get("requirements_sha256", "")), errors)

    assets = model_registry.get("assets", {}) if isinstance(model_registry, dict) else {}
    shared_segmentation = (
        matrix.get("shared_segmentation_asset")
        if isinstance(matrix.get("shared_segmentation_asset"), dict)
        else {}
    )
    required_asset_ids = {
        asr["AO"]["model_asset"]["asset_id"],
        asr["AG"]["model_asset"]["asset_id"],
        shared_segmentation.get("asset_id"),
        identity["IW"]["model_asset_id"],
        identity["IR"]["model_asset_id"],
        identity["IR"]["official_source_asset_id"],
    }
    _expect(required_asset_ids.issubset(set(assets)), "all registry-backed model assets resolve", errors)
    registered_segmentation = assets.get(shared_segmentation.get("asset_id"), {})
    _expect(
        str(registered_segmentation.get("expected_sha256", "")).lower()
        == str(shared_segmentation.get("installed_tree_sha256", "")).lower(),
        "shared Pyannote segmentation tree hash matches the model registry",
        errors,
    )
    _expect(
        shared_segmentation.get("per_record_cache_key_is_component_or_model_identity")
        is False,
        "per-record segmentation cache keys are not labelled component identities",
        errors,
    )
    segmentation_configs: set[tuple[str, str]] = set()
    for alias, definition in diar.items():
        _expect(
            definition.get("configuration_source_anchor")
            == "frozen_diarization_pipeline_config",
            f"{alias} binds the frozen diarization pipeline configuration",
            errors,
        )
        _expect(
            definition.get("identity_analysis_source_anchor")
            == "diarization_pipeline_identity_analysis",
            f"{alias} binds the diarization identity analysis",
            errors,
        )
        _expect(
            str(definition.get("segmentation_model_asset_sha256", "")).lower()
            == str(shared_segmentation.get("installed_tree_sha256", "")).lower(),
            f"{alias} binds the shared Pyannote segmentation model tree",
            errors,
        )
        segmentation_configs.add(
            (
                str(definition.get("segmentation_source_config", "")),
                str(definition.get("segmentation_source_config_sha256", "")),
            )
        )
    for relative, expected_hash in segmentation_configs:
        source_hashes_checked += 1
        _check_file_hash(_resolve(root, relative), expected_hash, errors)
    profiles = environment_registry.get("profiles", {}) if isinstance(environment_registry, dict) else {}
    required_profiles = {
        "core-cpu",
        "onnx",
        "wespeaker",
        "redimnet2",
        "credential-diarization",
    }
    _expect(required_profiles.issubset(set(profiles)), "all required environment profiles resolve", errors)

    for identity_alias, policy in enrollment_policies.items():
        if not isinstance(policy, dict):
            errors.append("enrollment policy record is not an object")
            continue
        source_hashes_checked += 1
        policy_path = _resolve(root, str(policy.get("path", "")))
        _check_file_hash(policy_path, str(policy.get("sha256", "")), errors)
        payload = _load_yaml(policy_path, errors)
        _expect(payload.get("policy_id") == policy.get("policy_id"), f"policy ID in {policy_path.name}", errors)
        _expect(
            payload.get("identity_backend_id")
            == identity.get(identity_alias, {}).get("backend_id"),
            f"identity backend in {policy_path.name}",
            errors,
        )
        _expect(
            payload.get("aggregation_method") == policy.get("aggregation"),
            f"enrollment aggregation in {policy_path.name}",
            errors,
        )
        _expect(
            payload.get("enrollment_utterance_count") == policy.get("utterance_count"),
            f"enrollment utterance count in {policy_path.name}",
            errors,
        )
        _expect(
            payload.get("enrollment_total_target_sec")
            == policy.get("target_total_duration_sec"),
            f"enrollment target duration in {policy_path.name}",
            errors,
        )

    pipeline_identity_path = _resolve(
        root,
        str(
            matrix["source_anchors"]["diarization_pipeline_identity_analysis"][
                "path"
            ]
        ),
    )
    if pipeline_identity_path.is_file():
        with pipeline_identity_path.open("r", encoding="utf-8-sig", newline="") as stream:
            identities = {row["pipeline_id"]: row for row in csv.DictReader(stream)}
        for alias, definition in diar.items():
            row = identities.get(str(definition.get("pipeline_id")))
            _expect(row is not None, f"{alias} resolves in diarization identity analysis", errors)
            if row:
                _expect(
                    row.get("configuration_sha256") == definition.get("configuration_sha256"),
                    f"{alias} configuration hash matches diarization analysis",
                    errors,
                )
                _expect(
                    row.get("identity_sha256") == definition.get("resolved_identity_sha256"),
                    f"{alias} resolved identity hash matches diarization analysis",
                    errors,
                )
    else:
        errors.append(f"missing diarization identity analysis: {pipeline_identity_path}")

    hybrid_registry_path = _resolve(
        root,
        str(matrix["source_anchors"]["hybrid_combination_registry"]["path"]),
    )
    combination_registry = _load_json(hybrid_registry_path, errors)
    combination_rows = (
        combination_registry.get("combinations", [])
        if isinstance(combination_registry, dict)
        else []
    )
    combinations = {
        str(row.get("combination_id")): row
        for row in combination_rows
        if isinstance(row, dict)
    }
    for label in ("H1", "H2", "H3", "H4", "H5", "H6"):
        mapping = hybrid_map.get(label, {})
        registered = combinations.get(label)
        _expect(registered is not None, f"{label} resolves in the frozen hybrid registry", errors)
        if not registered:
            continue
        diar_alias = str(mapping.get("anonymous_diarization"))
        identity_alias = str(mapping.get("identity"))
        _expect(
            registered.get("diarization_pipeline_id")
            == diar.get(diar_alias, {}).get("pipeline_id"),
            f"{label} diarization mapping matches the hybrid registry",
            errors,
        )
        _expect(
            registered.get("identity_backend_id")
            == identity.get(identity_alias, {}).get("backend_id"),
            f"{label} identity mapping matches the hybrid registry",
            errors,
        )
        _expect(
            str(registered.get("enrollment_policy_sha256", "")).lower()
            == str(enrollment_policies.get(identity_alias, {}).get("sha256", "")).lower(),
            f"{label} enrollment policy hash matches the hybrid registry",
            errors,
        )
    _expect(
        not ({"C7", "C8", "C9"} & set(combinations)),
        "C7-C9 remain prompt-defined challengers rather than fabricated frozen rows",
        errors,
    )

    required_aggregations = {
        str(policy.get("aggregation"))
        for policy in enrollment_policies.values()
        if isinstance(policy, dict) and policy.get("aggregation")
    }
    _validate_contracts(contracts, required_aggregations, errors)
    _validate_state(state, matrix_path, contract_path, errors)
    for relative in (
        "docs/full_pipeline/PIPELINE_MATRIX.md",
        "docs/full_pipeline/LICENSE_AND_ASSET_MANIFEST.md",
        "docs/full_pipeline/PROGRAM_HANDOFF.md",
        "app/full_pipeline_program/README.md",
    ):
        _expect((root / relative).is_file(), f"required documentation exists: {relative}", errors)

    if verify_assets:
        assets_checked = _verify_local_assets(matrix, repo_root, errors)

    if errors:
        raise ProgramLockValidationError(errors)
    return {
        "status": "PASS",
        "program_id": PROGRAM_ID,
        "protocol_version": PROTOCOL_VERSION,
        "matrix_count": len(pipelines),
        "contract_count": len(PUBLIC_CONTRACTS),
        "source_hashes_checked": source_hashes_checked,
        "assets_verified": verify_assets,
        "asset_hashes_checked": assets_checked,
        "long_inference_run": False,
    }


def _validate_contracts(
    contracts: Mapping[str, Any],
    required_aggregations: set[str],
    errors: list[str],
) -> None:
    _expect(
        contracts.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "contracts declare JSON Schema Draft 2020-12",
        errors,
    )
    _expect(contracts.get("$id") == CONTRACT_SCHEMA_VERSION, "contract schema ID", errors)
    definitions = contracts.get("$defs") if isinstance(contracts.get("$defs"), dict) else {}
    _expect(PUBLIC_CONTRACTS.issubset(set(definitions)), "all 15 public contracts are defined", errors)
    root_refs = {
        str(item.get("$ref"))
        for item in contracts.get("oneOf", [])
        if isinstance(item, dict)
    }
    expected_root_refs = {f"#/$defs/{name}" for name in PUBLIC_CONTRACTS}
    _expect(
        root_refs == expected_root_refs and len(contracts.get("oneOf", [])) == 15,
        "root oneOf exposes exactly the 15 public contracts",
        errors,
    )
    local_references = {
        reference
        for reference in _collect_references(contracts)
        if reference.startswith("#/$defs/")
    }
    unresolved_references = {
        reference
        for reference in local_references
        if reference.removeprefix("#/$defs/") not in definitions
    }
    _expect(
        not unresolved_references,
        "all local common-contract references resolve",
        errors,
    )
    text = json.dumps(contracts, sort_keys=True)
    _expect('"probability"' not in text, "contracts never label raw scores as probability", errors)
    raw_score_type = definitions.get("rawScoreType", {})
    _expect(
        "[Pp][Rr][Oo][Bb][Aa][Bb][Ii][Ll]"
        in str(raw_score_type.get("pattern", "")),
        "rawScoreType rejects probability-labelled raw scores case-insensitively",
        errors,
    )
    score_type_fields = _collect_property_schemas(
        definitions, {"score_type", "raw_score_type"}
    )
    allowed_score_type_refs = {
        "#/$defs/rawScoreType",
        "#/$defs/nullableRawScoreType",
    }
    _expect(bool(score_type_fields), "score-bearing contracts declare score types", errors)
    _expect(
        all(field.get("$ref") in allowed_score_type_refs for field in score_type_fields),
        "every raw score type uses the probability-safe rawScoreType contract",
        errors,
    )
    evidence = definitions.get("IdentityEvidenceEvent", {})
    evidence_text = json.dumps(evidence, sort_keys=True)
    for field in ("raw_score", "score_type", "top1_top2_margin", "threshold_identity", "evidence_duration_sec"):
        _expect(field in evidence_text, f"IdentityEvidenceEvent preserves {field}", errors)
    label_text = json.dumps(
        {
            "event": definitions.get("IdentityLabelEvent", {}),
            "speaker_label": definitions.get("speakerLabel", {}),
        },
        sort_keys=True,
    )
    _expect(
        "Unknown_" in label_text,
        "IdentityLabelEvent defines stable Unknown_N labels through speakerLabel",
        errors,
    )
    for contract_name in ("enrollmentBackendIdentity", "EnrollmentProfile"):
        contract = definitions.get(contract_name, {})
        properties = contract.get("properties", {}) if isinstance(contract, dict) else {}
        aggregation = (
            properties.get("aggregation_method", {})
            if isinstance(properties, dict)
            else {}
        )
        allowed = set(aggregation.get("enum", [])) if isinstance(aggregation, dict) else set()
        _expect(
            required_aggregations.issubset(allowed),
            f"{contract_name} supports every matrix enrollment aggregation",
            errors,
        )
        _expect(
            "aggregation_top_k" in properties
            and "aggregation_top_k" in contract.get("required", []),
            f"{contract_name} records an explicit aggregation Top-K parameter",
            errors,
        )
    biometric_reference = definitions.get("biometricArtifactReference", {})
    _expect(
        '"const": "biometric_sensitive"'
        in json.dumps(biometric_reference, sort_keys=True),
        "biometricArtifactReference enforces biometric-sensitive classification",
        errors,
    )
    enrollment_sample_text = json.dumps(
        definitions.get("EnrollmentSample", {}), sort_keys=True
    )
    enrollment_profile_text = json.dumps(
        definitions.get("EnrollmentProfile", {}), sort_keys=True
    )
    _expect(
        enrollment_sample_text.count("#/$defs/biometricArtifactReference") >= 3,
        "EnrollmentSample protects audio and embedding artifact references",
        errors,
    )
    _expect(
        enrollment_profile_text.count("#/$defs/biometricArtifactReference") >= 2,
        "EnrollmentProfile protects sample and template artifact references",
        errors,
    )


def _validate_state(
    state: Mapping[str, Any], matrix_path: Path, contract_path: Path, errors: list[str]
) -> None:
    evaluation_root = matrix_path.parents[2]
    _expect(state.get("schema_version") == "just-peachy-full-pipeline-program-state.v1", "program state schema", errors)
    _expect(state.get("program_id") == PROGRAM_ID, "program state ID", errors)
    _expect(state.get("protocol_version") == PROTOCOL_VERSION, "program state protocol", errors)
    state_status = state.get("status")
    _expect(
        state_status
        in {
            "COMPLETE_FULL_PIPELINE_PROGRAM_LOCK",
            "COMPLETE_STREAMING_RUNTIME",
            "COMPLETE_COMMON_DEMO",
            "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
            "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE",
        },
        "program state records a recognized completed program stage",
        errors,
    )
    _expect(state.get("matrix_count") == 18, "program state matrix count", errors)
    artifacts = state.get("canonical_artifacts", {}) if isinstance(state.get("canonical_artifacts"), dict) else {}
    matrix_record = artifacts.get("matrix", {}) if isinstance(artifacts.get("matrix"), dict) else {}
    contract_record = artifacts.get("contracts", {}) if isinstance(artifacts.get("contracts"), dict) else {}
    _expect(matrix_record.get("sha256") == _sha256(matrix_path), "program state binds matrix SHA-256", errors)
    _expect(contract_record.get("sha256") == _sha256(contract_path), "program state binds contract SHA-256", errors)
    for artifact_name, artifact in artifacts.items():
        if not isinstance(artifact, dict):
            errors.append(f"canonical artifact {artifact_name} is not an object")
            continue
        relative_path = artifact.get("path")
        expected_hash = artifact.get("sha256")
        path_hashes = artifact.get("paths")
        if isinstance(relative_path, str) and isinstance(expected_hash, str):
            _check_file_hash(
                _resolve(evaluation_root, relative_path), expected_hash, errors
            )
        elif isinstance(path_hashes, dict) and path_hashes:
            for child_path, child_hash in path_hashes.items():
                _check_file_hash(
                    _resolve(evaluation_root, str(child_path)),
                    str(child_hash),
                    errors,
                )
        else:
            errors.append(
                f"canonical artifact {artifact_name} lacks a path/SHA-256 binding"
            )
    completion = (
        state.get("completion_state")
        if isinstance(state.get("completion_state"), dict)
        else {}
    )
    _expect(
        completion.get("prompt_0") == "COMPLETE_FULL_PIPELINE_PROGRAM_LOCK",
        "completion state records Prompt 0 complete",
        errors,
    )
    if state_status in {
        "COMPLETE_STREAMING_RUNTIME",
        "COMPLETE_COMMON_DEMO",
        "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
        "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE",
    }:
        _validate_prompt_1_state(state, completion, artifacts, errors)
    if state_status == "COMPLETE_STREAMING_RUNTIME":
        _expect(
            state.get("current_prompt_index") == 1,
            "streaming-runtime state records Prompt 1 as current",
            errors,
        )
        _expect(
            state.get("remaining_prompt_indices") == list(range(2, 9)),
            "streaming-runtime state records Prompts 2-8 remaining",
            errors,
        )
    elif state_status == "COMPLETE_COMMON_DEMO":
        _validate_prompt_2_state(
            state,
            completion,
            artifacts,
            evaluation_root,
            errors,
        )
    elif state_status == "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE":
        _validate_prompt_2_state(
            state,
            completion,
            artifacts,
            evaluation_root,
            errors,
            validate_stage_position=False,
        )
        _validate_prompt_3_state(
            state,
            completion,
            artifacts,
            evaluation_root,
            errors,
        )
    elif state_status == "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE":
        _validate_prompt_2_state(
            state,
            completion,
            artifacts,
            evaluation_root,
            errors,
            validate_stage_position=False,
        )
        _validate_prompt_3_state(
            state,
            completion,
            artifacts,
            evaluation_root,
            errors,
            validate_stage_position=False,
        )
        _validate_prompt_4_state(
            state,
            completion,
            artifacts,
            evaluation_root,
            errors,
        )
    _expect(
        completion.get("matrix_locked") is True
        and completion.get("common_contracts_defined") is True
        and completion.get("handoff_created") is True,
        "completion state records the matrix, contracts, and handoff complete",
        errors,
    )
    validation = state.get("validation") if isinstance(state.get("validation"), dict) else {}
    _expect(validation.get("status") == "PASS", "program state records targeted validation PASS", errors)
    _expect(
        state.get("long_scientific_campaign_started")
        is (state_status == "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE"),
        (
            "program state records the Prompt-4 development campaign"
            if state_status == "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE"
            else "program state records no long campaign"
        ),
        errors,
    )


def _validate_prompt_1_state(
    state: Mapping[str, Any],
    completion: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    errors: list[str],
) -> None:
    """Require every prior Prompt-1 lock when validating Prompt 1 or later."""

    _expect(
        completion.get("prompt_1") == "COMPLETE_STREAMING_RUNTIME",
        "completion state records Prompt 1 complete",
        errors,
    )
    for key, description in (
        ("end_to_end_runtime_implemented", "the end-to-end runtime implemented"),
        ("native_incremental_asr_implemented", "native incremental ASR implemented"),
        ("persistent_isolated_workers_implemented", "persistent isolated workers implemented"),
        (
            "all_eight_cache_contracts_and_producers_implemented",
            "all eight runtime caches implemented",
        ),
        ("bounded_component_smoke_passed", "the bounded component smoke PASS"),
        ("bounded_enrollment_smoke_passed", "the bounded enrollment smoke PASS"),
        ("bounded_file_stream_smoke_passed", "the bounded file-stream smoke PASS"),
    ):
        _expect(
            completion.get(key) is True,
            f"completion state records {description}",
            errors,
        )
    _expect(
        completion.get("physical_microphone_smoke_executed") is False,
        "Prompt 1 records no physical-microphone smoke",
        errors,
    )
    _expect(
        state.get("bounded_inference_run_by_prompt_1") is True,
        "program state records bounded Prompt-1 inference",
        errors,
    )
    _expect(
        state.get("physical_microphone_capture_run_by_prompt_1") is False,
        "program state records no Prompt-1 physical-microphone capture",
        errors,
    )
    _expect(
        state.get("frozen_scientific_results_modified") is False,
        "streaming-runtime work preserved frozen scientific results",
        errors,
    )
    _expect(
        REQUIRED_PROMPT_1_CANONICAL_ARTIFACTS.issubset(artifacts),
        "program state retains all Prompt-1 canonical artifacts",
        errors,
    )


def _validate_prompt_2_state(
    state: Mapping[str, Any],
    completion: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluation_root: Path,
    errors: list[str],
    *,
    validate_stage_position: bool = True,
) -> None:
    """Validate Prompt 2's common-demo completion without claiming a campaign."""

    if validate_stage_position:
        _expect(
            state.get("current_prompt_index") == 2,
            "common-demo state records Prompt 2 as current",
            errors,
        )
        _expect(
            state.get("remaining_prompt_indices") == list(range(3, 9)),
            "common-demo state records Prompts 3-8 remaining",
            errors,
        )
    _expect(
        completion.get("prompt_2") == "COMPLETE_COMMON_DEMO",
        "completion state records Prompt 2 complete",
        errors,
    )
    for key, description in (
        ("common_demo_implemented", "the common demo implemented"),
        ("all_18_demo_presets_available", "all 18 demo presets available"),
        ("six_highlighted_demo_presets_available", "six highlighted presets available"),
        (
            "three_required_bounded_demo_presets_passed",
            "all three required bounded presets PASS",
        ),
        ("common_demo_enrollment_smoke_passed", "the enrollment smoke PASS"),
        ("common_demo_file_smoke_passed", "the file-mode smoke PASS"),
        ("common_demo_export_smoke_passed", "the export smoke PASS"),
        (
            "common_demo_model_switch_smoke_passed",
            "the between-session model-switch smoke PASS",
        ),
    ):
        _expect(
            completion.get(key) is True,
            f"Prompt-2 completion records {description}",
            errors,
        )
    _expect(
        completion.get("scientific_campaign_executed_by_prompt_2") is False,
        "Prompt-2 completion records no scientific campaign",
        errors,
    )
    _expect(
        completion.get("physical_microphone_smoke_executed") is False,
        "Prompt-2 completion records no physical-microphone smoke",
        errors,
    )
    _expect(
        state.get("bounded_inference_run_by_prompt_2") is True,
        "program state records bounded Prompt-2 inference",
        errors,
    )
    _expect(
        state.get("physical_microphone_capture_run_by_prompt_2") is False,
        "program state records no Prompt-2 physical-microphone capture",
        errors,
    )
    _expect(
        REQUIRED_PROMPT_2_CANONICAL_ARTIFACTS.issubset(artifacts),
        "program state binds all Prompt-2 canonical artifacts",
        errors,
    )
    package_record = artifacts.get("common_demo_package")
    package_paths = (
        package_record.get("paths", {})
        if isinstance(package_record, dict)
        else {}
    )
    _expect(
        isinstance(package_paths, dict)
        and REQUIRED_COMMON_DEMO_PACKAGE_PATHS.issubset(package_paths),
        "Prompt-2 package lock binds every demo module, README, and wrapper",
        errors,
    )
    test_record = artifacts.get("common_demo_targeted_tests")
    test_paths = (
        test_record.get("paths", {}) if isinstance(test_record, dict) else {}
    )
    _expect(
        isinstance(test_paths, dict)
        and REQUIRED_COMMON_DEMO_TEST_PATHS.issubset(test_paths),
        "Prompt-2 test lock binds every focused demo/runtime-control test",
        errors,
    )
    validation = state.get("validation") if isinstance(state.get("validation"), dict) else {}
    _expect(
        validation.get("demo_preset_count") == 18,
        "Prompt-2 validation records 18 presets",
        errors,
    )
    _expect(
        validation.get("demo_highlighted_preset_count") == 6,
        "Prompt-2 validation records six highlighted presets",
        errors,
    )
    _expect(
        validation.get("demo_required_bounded_preset_count") == 3,
        "Prompt-2 validation records three required bounded presets",
        errors,
    )
    _expect(
        validation.get("common_demo_smoke_status") == "PASS",
        "Prompt-2 validation records common-demo smoke PASS",
        errors,
    )
    smoke_record = artifacts.get("prompt_2_common_demo_smoke")
    smoke_artifact = smoke_record if isinstance(smoke_record, dict) else {}
    smoke_path = smoke_artifact.get("path")
    if not isinstance(smoke_path, str):
        errors.append("Prompt-2 common-demo smoke artifact has no path")
        return
    smoke = _load_json(_resolve(evaluation_root, smoke_path), errors)
    if smoke:
        _validate_prompt_2_smoke(smoke, errors)


def _validate_prompt_2_smoke(
    smoke: Mapping[str, Any], errors: list[str]
) -> None:
    _expect(
        smoke.get("schema_version") == "full-pipeline-common-demo-smoke.v1",
        "Prompt-2 common-demo smoke schema",
        errors,
    )
    _expect(smoke.get("status") == "PASS", "Prompt-2 common-demo smoke PASS", errors)
    _expect(
        smoke.get("purpose") == "bounded_application_mechanics_only",
        "Prompt-2 smoke is bounded application mechanics only",
        errors,
    )
    _expect(
        smoke.get("scientific_campaign_started") is False,
        "Prompt-2 smoke records no scientific campaign",
        errors,
    )
    _expect(
        smoke.get("physical_microphone_capture_performed") is False,
        "Prompt-2 smoke records no physical-microphone capture",
        errors,
    )
    for key, description in (
        ("file_mode_exercised", "file mode"),
        ("enrollment_exercised", "enrollment"),
        ("labelled_transcript_export_exercised", "labelled transcript export"),
        ("model_switching_between_sessions_exercised", "model switching"),
    ):
        _expect(
            smoke.get(key) is True,
            f"Prompt-2 smoke exercised {description}",
            errors,
        )
    observed_presets = smoke.get("required_presets_exercised")
    _expect(
        isinstance(observed_presets, list)
        and len(observed_presets) == 3
        and set(observed_presets) == set(EXPECTED_COMMON_DEMO_SMOKE_PRESETS),
        "Prompt-2 smoke exercised exactly AG-H5, AG-H2, and AO-H4",
        errors,
    )
    shared_speaker_id = smoke.get("shared_speaker_id")
    _expect(
        isinstance(shared_speaker_id, str) and bool(shared_speaker_id.strip()),
        "Prompt-2 smoke records one explicit shared speaker ID",
        errors,
    )
    enrollment = smoke.get("enrollment")
    enrollment_rows = enrollment if isinstance(enrollment, list) else []
    _expect(
        len(enrollment_rows) == 2
        and all(
            isinstance(row, dict)
            and row.get("state") == "profile_created"
            and row.get("speaker_id") == shared_speaker_id
            and row.get("biometric_vectors_inline") is False
            and row.get("network_transfer_performed") is False
            and isinstance(row.get("profile_id"), str)
            and bool(str(row.get("profile_id")).strip())
            and _is_sha256(row.get("profile_sha256"))
            for row in enrollment_rows
        ),
        "Prompt-2 smoke created IE/IR profiles for one shared local speaker ID",
        errors,
    )
    profile_by_backend = {
        str(dict(row.get("backend") or {}).get("backend_id")): str(
            row.get("profile_id")
        )
        for row in enrollment_rows
        if isinstance(row, dict) and isinstance(row.get("backend"), dict)
    }
    _expect(
        set(profile_by_backend)
        == {"speechbrain_ecapa", "redimnet2_b2_speaker_embedding"},
        "Prompt-2 smoke enrollment identities are exactly IE and IR",
        errors,
    )
    sessions = smoke.get("sessions")
    session_rows = sessions if isinstance(sessions, list) else []
    observed_sessions = {
        str(row.get("label")): str(row.get("pipeline_id"))
        for row in session_rows
        if isinstance(row, dict)
    }
    _expect(
        len(session_rows) == 3
        and [row.get("label") for row in session_rows if isinstance(row, dict)]
        == list(EXPECTED_COMMON_DEMO_SMOKE_PRESETS)
        and observed_sessions == EXPECTED_COMMON_DEMO_SMOKE_PRESETS,
        "Prompt-2 smoke session order and identities are AG-H5, AG-H2, AO-H4",
        errors,
    )
    previous_row: Mapping[str, Any] | None = None
    for index, row in enumerate(session_rows):
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", f"session_{index + 1}"))
        _expect(
            row.get("state") == "completed"
            and row.get("completion_state") == "complete",
            f"Prompt-2 smoke session completed: {label}",
            errors,
        )
        _expect(
            _is_sha256(row.get("export_manifest_sha256"))
            and _is_sha256(row.get("labelled_transcript_sha256")),
            f"Prompt-2 smoke export hashes recorded: {label}",
            errors,
        )
        event_count = row.get("event_count")
        _expect(
            isinstance(event_count, int)
            and not isinstance(event_count, bool)
            and event_count > 0,
            f"Prompt-2 smoke durable event count is positive: {label}",
            errors,
        )
        _expect(
            _is_sha256(row.get("pipeline_config_sha256")),
            f"Prompt-2 smoke pipeline configuration hash recorded: {label}",
            errors,
        )
        _expect(
            row.get("component_backend_ids")
            == EXPECTED_COMMON_DEMO_SMOKE_COMPONENTS.get(label),
            f"Prompt-2 smoke exact component identities recorded: {label}",
            errors,
        )
        expected_profile_id = profile_by_backend.get(
            EXPECTED_COMMON_DEMO_PROFILE_BACKENDS.get(label, "")
        )
        _expect(
            isinstance(expected_profile_id, str)
            and row.get("enrollment_profile_ids") == [expected_profile_id],
            f"Prompt-2 smoke exact enrollment profile recorded: {label}",
            errors,
        )
        attribution = row.get("useful_labelled_attribution")
        _expect(
            _is_useful_labelled_attribution(attribution),
            f"Prompt-2 smoke has timed labelled attribution: {label}",
            errors,
        )
        _expect(
            row.get("model_switch_between_sessions") is (index > 0),
            f"Prompt-2 smoke model-switch marker is truthful: {label}",
            errors,
        )
        transition = row.get("immutable_transition")
        if index == 0:
            _expect(
                transition is None
                and row.get("previous_session_id") is None
                and row.get("previous_pipeline_id") is None,
                "Prompt-2 first smoke session has no predecessor",
                errors,
            )
        else:
            previous = previous_row or {}
            transition_value = transition if isinstance(transition, dict) else {}
            _expect(
                transition_value.get("transition_kind")
                == "new_immutable_session_after_join"
                and transition_value.get("predecessor_session_id")
                == previous.get("session_id")
                and transition_value.get("predecessor_pipeline_id")
                == previous.get("pipeline_id")
                and transition_value.get("predecessor_state") == "completed"
                and transition_value.get("predecessor_joined") is True
                and transition_value.get("current_session_id")
                == row.get("session_id")
                and transition_value.get("current_pipeline_id")
                == row.get("pipeline_id")
                and transition_value.get("distinct_session_id") is True
                and transition_value.get("distinct_output_root") is True
                and isinstance(
                    transition_value.get("changed_component_families"), list
                )
                and bool(transition_value.get("changed_component_families")),
                f"Prompt-2 smoke immutable predecessor transition recorded: {label}",
                errors,
            )
            _expect(
                row.get("previous_session_id") == previous.get("session_id")
                and row.get("previous_pipeline_id") == previous.get("pipeline_id"),
                f"Prompt-2 smoke previous-session identity recorded: {label}",
                errors,
            )
        previous_row = row


def _validate_prompt_3_state(
    state: Mapping[str, Any],
    completion: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluation_root: Path,
    errors: list[str],
    *,
    validate_stage_position: bool = True,
) -> None:
    """Validate Prompt 3's model-free evaluation-infrastructure lock."""

    if validate_stage_position:
        _expect(
            state.get("current_prompt_index") == 3,
            "evaluation-infrastructure state records Prompt 3 as current",
            errors,
        )
        _expect(
            state.get("remaining_prompt_indices") == list(range(4, 9)),
            "evaluation-infrastructure state records Prompts 4-8 remaining",
            errors,
        )
    _expect(
        completion.get("prompt_3")
        == "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
        "completion state records Prompt 3 complete",
        errors,
    )
    for key, description in (
        (
            "full_pipeline_evaluation_infrastructure_implemented",
            "the full-pipeline evaluation infrastructure implemented",
        ),
        (
            "full_speech_pipeline_v1_protocol_prepared",
            "the full_speech_pipeline_v1 protocol prepared",
        ),
        (
            "full_speech_pipeline_v1_protocol_validated",
            "the full_speech_pipeline_v1 protocol validated",
        ),
        (
            "all_18_evaluation_pipelines_planned",
            "all 18 evaluation pipelines planned",
        ),
        (
            "common_result_tree_schema_implemented",
            "the common result-tree schema implemented",
        ),
        ("all_required_scorers_implemented", "all required scorers implemented"),
        (
            "restart_safe_evaluation_controller_implemented",
            "the restart-safe evaluation controller implemented",
        ),
        (
            "measured_evaluation_monitor_implemented",
            "the measured evaluation monitor implemented",
        ),
        (
            "synthetic_perfect_failure_smoke_passed",
            "the synthetic perfect/failure smoke PASS",
        ),
    ):
        _expect(
            completion.get(key) is True,
            f"Prompt-3 completion records {description}",
            errors,
        )
    _expect(
        completion.get("scientific_campaign_executed_by_prompt_3") is False,
        "Prompt-3 completion records no scientific campaign",
        errors,
    )
    _expect(
        state.get("bounded_inference_run_by_prompt_3") is False,
        "program state records no Prompt-3 model inference",
        errors,
    )
    _expect(
        state.get("synthetic_evaluation_smoke_run_by_prompt_3") is True,
        "program state records the Prompt-3 synthetic smoke",
        errors,
    )
    _expect(
        state.get("physical_microphone_capture_run_by_prompt_3") is False,
        "program state records no Prompt-3 physical-microphone capture",
        errors,
    )
    _expect(
        REQUIRED_PROMPT_3_CANONICAL_ARTIFACTS.issubset(artifacts),
        "program state binds all Prompt-3 canonical artifacts",
        errors,
    )

    protocol_paths = _artifact_path_keys(
        artifacts.get("full_speech_pipeline_v1_protocol")
    )
    _expect(
        REQUIRED_FULL_PIPELINE_PROTOCOL_PATHS.issubset(protocol_paths),
        "Prompt-3 protocol lock binds config, summary, checksums, and both splits",
        errors,
    )
    schema_record = artifacts.get("full_pipeline_evaluation_result_schema")
    schema_path = schema_record.get("path") if isinstance(schema_record, dict) else None
    _expect(
        _normalized_path(schema_path)
        == (
            "configs/automated_evaluation/schemas/"
            "full_pipeline_evaluation_result.v1.schema.json"
        ),
        "Prompt-3 result-schema lock binds the canonical schema path",
        errors,
    )
    package_paths = _artifact_path_keys(
        artifacts.get("full_pipeline_evaluation_package")
    )
    _expect(
        REQUIRED_FULL_PIPELINE_EVALUATION_PACKAGE_PATHS.issubset(package_paths),
        "Prompt-3 package lock binds every evaluation module and README",
        errors,
    )
    wrapper_paths = _artifact_path_keys(
        artifacts.get("full_pipeline_evaluation_wrappers")
    )
    _expect(
        REQUIRED_FULL_PIPELINE_EVALUATION_WRAPPER_PATHS.issubset(wrapper_paths),
        "Prompt-3 wrapper lock binds run and monitor wrappers",
        errors,
    )
    test_paths = _artifact_path_keys(
        artifacts.get("full_pipeline_evaluation_targeted_tests")
    )
    _expect(
        REQUIRED_FULL_PIPELINE_EVALUATION_TEST_PATHS.issubset(test_paths),
        "Prompt-3 test lock binds every focused evaluation-infrastructure test",
        errors,
    )

    _validate_prompt_3_protocol(evaluation_root, errors)
    smoke_record = artifacts.get("prompt_3_synthetic_smoke")
    smoke_artifact = smoke_record if isinstance(smoke_record, dict) else {}
    smoke_value = smoke_artifact.get("path")
    if not isinstance(smoke_value, str):
        errors.append("Prompt-3 synthetic smoke artifact has no path")
        return
    smoke_path = _resolve(evaluation_root, smoke_value)
    smoke = _load_json(smoke_path, errors)
    if smoke:
        _validate_prompt_3_smoke(smoke, smoke_path, errors)


def _validate_prompt_3_protocol(
    evaluation_root: Path, errors: list[str]
) -> None:
    """Check prepared protocol counts, split identities, and its checksum map."""

    config_path = (
        evaluation_root / "configs/automated_evaluation/full_speech_pipeline_v1.yaml"
    )
    protocol_root = (
        evaluation_root / "benchmarks/full_pipeline/full_speech_pipeline_v1"
    )
    summary_path = protocol_root / "protocol_summary.json"
    audit_path = protocol_root / "source_audit.json"
    checksums_path = protocol_root / "checksums.json"
    config = _load_yaml(config_path, errors)
    summary = _load_json(summary_path, errors)
    audit = _load_json(audit_path, errors)
    checksums = _load_json(checksums_path, errors)
    if not config or not summary or not audit or not checksums:
        return

    protocol_id = summary.get("protocol_id")
    _expect(
        config.get("schema_version") == "full-speech-pipeline-config.v1"
        and config.get("protocol_name") == "full_speech_pipeline_v1"
        and config.get("protocol_version") == 1,
        "Prompt-3 protocol config identity",
        errors,
    )
    _expect(
        summary.get("schema_version") == "full-speech-pipeline.v1"
        and summary.get("protocol_name") == config.get("protocol_name")
        and summary.get("protocol_version") == config.get("protocol_version")
        and summary.get("selection_seed") == config.get("selection_seed"),
        "Prompt-3 prepared protocol summary identity",
        errors,
    )
    _expect(
        isinstance(protocol_id, str)
        and protocol_id.startswith("full_speech_pipeline_v1_")
        and len(protocol_id.removeprefix("full_speech_pipeline_v1_")) == 12,
        "Prompt-3 prepared protocol ID",
        errors,
    )
    _expect(
        summary.get("config_path")
        == "configs/automated_evaluation/full_speech_pipeline_v1.yaml"
        and str(summary.get("config_sha256", "")).lower()
        == _sha256(config_path).lower(),
        "Prompt-3 protocol summary binds the canonical config SHA-256",
        errors,
    )
    _expect(
        audit.get("schema_version") == "full-speech-pipeline-source-audit.v1"
        and audit.get("status") == "PASS"
        and audit.get("config_id") == protocol_id
        and audit.get("downloads_attempted") is False
        and audit.get("inference_started") is False,
        "Prompt-3 protocol source audit is PASS and model-free",
        errors,
    )
    audit_sources = audit.get("sources")
    _expect(
        isinstance(audit_sources, list)
        and len(audit_sources) == 6
        and all(
            isinstance(row, dict)
            and row.get("installed") is True
            and row.get("errors") == []
            for row in audit_sources
        ),
        "Prompt-3 protocol source audit binds all six installed source identities",
        errors,
    )

    counts = summary.get("case_counts")
    count_map = counts if isinstance(counts, dict) else {}
    split_identity_hashes: list[str] = []
    for split in ("development", "evaluation"):
        case_path = protocol_root / split / "case_manifest.jsonl"
        case_ids = _protocol_case_ids(case_path, split, protocol_id, errors)
        identity_value = summary.get(f"{split}_identity")
        identity = identity_value if isinstance(identity_value, dict) else {}
        expected_digest = _canonical_json_sha256(
            {
                "protocol_id": protocol_id,
                "partition": split,
                "case_ids": case_ids,
            }
        )
        expected_case_ids_sha = hashlib.sha256(
            "\n".join(case_ids).encode("utf-8")
        ).hexdigest()
        _expect(
            isinstance(count_map.get(split), int)
            and not isinstance(count_map.get(split), bool)
            and count_map.get(split) == len(case_ids)
            and len(case_ids) > 0,
            f"Prompt-3 protocol {split} case count matches its manifest",
            errors,
        )
        _expect(
            identity.get("case_count") == len(case_ids)
            and str(identity.get("case_ids_sha256", "")).lower()
            == expected_case_ids_sha.lower()
            and str(identity.get("identity_sha256", "")).lower()
            == expected_digest.lower()
            and identity.get("partition_id")
            == f"{protocol_id}_{split}_{expected_digest[:12]}",
            f"Prompt-3 protocol {split} split identity matches ordered case IDs",
            errors,
        )
        if _is_sha256(identity.get("identity_sha256")):
            split_identity_hashes.append(str(identity["identity_sha256"]).lower())
    _expect(
        len(split_identity_hashes) == 2
        and len(set(split_identity_hashes)) == 2,
        "Prompt-3 development and evaluation identities are distinct SHA-256 values",
        errors,
    )
    _expect(
        summary.get("primary_development_evaluation_speaker_disjoint") is True
        and summary.get(
            "development_evaluation_enrollment_gallery_speaker_disjoint"
        )
        is True,
        "Prompt-3 protocol preserves development/evaluation speaker disjointness",
        errors,
    )
    _expect(
        summary.get("evaluation_only") is True
        and summary.get("training_eligible") is False
        and summary.get("audio_copied_or_modified") is False
        and summary.get("downloads_attempted") is False
        and summary.get("inference_started") is False,
        "Prompt-3 protocol is evaluation-only, non-training, and model-free",
        errors,
    )

    checksum_files = checksums.get("files")
    expected_files = checksum_files if isinstance(checksum_files, dict) else {}
    observed_files = {
        path.relative_to(protocol_root).as_posix(): _sha256(path)
        for path in sorted(protocol_root.rglob("*"))
        if path.is_file() and path.name != "checksums.json"
    }
    _expect(
        checksums.get("schema_version") == "full-speech-pipeline-checksums.v1"
        and checksums.get("protocol_id") == protocol_id,
        "Prompt-3 protocol checksum-document identity",
        errors,
    )
    _expect(
        {str(key): str(value).lower() for key, value in expected_files.items()}
        == {key: value.lower() for key, value in observed_files.items()},
        "Prompt-3 protocol checksum map covers every generated file exactly",
        errors,
    )


def _validate_prompt_3_smoke(
    smoke: Mapping[str, Any], smoke_path: Path, errors: list[str]
) -> None:
    """Require truthful perfect/failure, retry, and no-campaign smoke evidence."""

    _expect(
        smoke.get("schema_version")
        == "full-pipeline-evaluation-infrastructure-smoke.v1",
        "Prompt-3 synthetic smoke schema",
        errors,
    )
    _expect(smoke.get("status") == "PASS", "Prompt-3 synthetic smoke PASS", errors)
    _expect(
        smoke.get("purpose") == "tiny_synthetic_infrastructure_only",
        "Prompt-3 smoke is tiny synthetic infrastructure only",
        errors,
    )
    _expect(
        smoke.get("perfect_result_valid") is True
        and smoke.get("perfect_result_reusable") is True,
        "Prompt-3 smoke validates a reusable perfect result",
        errors,
    )
    _expect(
        smoke.get("failure_result_valid") is True
        and smoke.get("failure_result_reusable") is False,
        "Prompt-3 smoke validates a non-reusable intentional failure result",
        errors,
    )
    scorer_checks = smoke.get("scorer_checks")
    _expect(
        scorer_checks
        == {
            "perfect_asr_wer_zero": True,
            "failed_output_counted": True,
            "perfect_diarization_der_zero": True,
        },
        "Prompt-3 smoke passes perfect/failure scorer checks",
        errors,
    )
    restart_value = smoke.get("restart_state")
    restart = restart_value if isinstance(restart_value, dict) else {}
    _expect(
        restart.get("status") == "PASS"
        and restart.get("job_count") == 2
        and restart.get("complete_jobs") == 2
        and restart.get("retry_attempt_count") == 2
        and restart.get("lease_restart_exercised") is True
        and restart.get("checksum_reuse_identity_bound") is True,
        "Prompt-3 smoke exercises restart-safe retry and checksum reuse identity",
        errors,
    )
    _expect(
        smoke.get("model_inference_performed") is False
        and smoke.get("dataset_downloads_performed") is False
        and smoke.get("long_scientific_campaign_started") is False
        and smoke.get("pipelines_evaluated") == 0
        and smoke.get("synthetic_cases") == 2,
        "Prompt-3 smoke records no inference, downloads, or scientific campaign",
        errors,
    )
    for result_name in ("perfect", "failure"):
        checksum_path = smoke_path.parent / f"{result_name}_result/checksums.json"
        recorded = smoke.get(f"{result_name}_result_checksum_sha256")
        _expect(
            checksum_path.is_file()
            and _is_sha256(recorded)
            and _sha256(checksum_path).lower() == str(recorded).lower(),
            f"Prompt-3 smoke binds the {result_name} result checksum document",
            errors,
        )


def _validate_prompt_4_state(
    state: Mapping[str, Any],
    completion: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluation_root: Path,
    errors: list[str],
    *,
    policy_adoption_bindings: Mapping[str, str] | None = None,
) -> None:
    """Validate Prompt 4's development-only all-18 run and immutable freeze."""

    expected_policy_adoption_bindings = (
        PROMPT_4_POLICY_ADOPTION_BINDINGS
        if policy_adoption_bindings is None
        else policy_adoption_bindings
    )

    _expect(
        state.get("current_prompt_index") == 4,
        "development-freeze state records Prompt 4 as current",
        errors,
    )
    _expect(
        state.get("remaining_prompt_indices") == [5, 6, 7, 8]
        and state.get("remaining_prompt_status") == "PENDING_UNSPECIFIED",
        "development-freeze state records Prompts 5-8 pending",
        errors,
    )
    for key, expected, description in (
        ("model_inference_run_by_prompt_4", True, "development model inference"),
        (
            "physical_microphone_capture_run_by_prompt_4",
            False,
            "no physical microphone capture",
        ),
        (
            "held_out_evaluation_run_by_prompt_4",
            False,
            "no held-out evaluation run",
        ),
        (
            "evaluation_material_inspected_by_prompt_4",
            False,
            "no evaluation-material inspection",
        ),
        (
            "production_winner_selected_by_prompt_4",
            False,
            "no production winner",
        ),
        (
            "held_out_protocol_metadata_and_reference_contracts_validated_for_protocol_lock",
            True,
            "held-out protocol metadata/reference contracts validated for the protocol lock",
        ),
        (
            "held_out_evaluation_identity_bound_to_campaign_identity",
            True,
            "held-out evaluation identity bound to campaign identity",
        ),
        (
            "held_out_evaluation_audio_processed",
            False,
            "no held-out audio processed",
        ),
        (
            "held_out_evaluation_inference_or_scoring_executed",
            False,
            "no held-out inference or scoring",
        ),
        (
            "held_out_predictions_metrics_or_results_inspected",
            False,
            "no held-out predictions, metrics, or results inspected",
        ),
        (
            "held_out_evaluation_used_for_calibration_metrics_or_selection",
            False,
            "no held-out material used for calibration, metrics, or selection",
        ),
    ):
        _expect(
            state.get(key) is expected,
            f"Prompt-4 state records {description}",
            errors,
        )
    _expect(
        completion.get("prompt_4") == "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE",
        "completion state records Prompt 4 complete",
        errors,
    )
    for key, description in (
        ("all_18_pipelines_qualified_on_development", "all 18 pipelines qualified"),
        ("challenger_policies_frozen", "challenger policies frozen"),
        ("frozen_anchor_policies_preserved", "frozen anchors preserved"),
        (
            "complete_807_case_development_campaign_passed",
            "the complete 807-case development campaign PASS",
        ),
        (
            "serial_resource_spot_checks_passed",
            "serial resource spot checks PASS",
        ),
        (
            "combined_development_evidence_passed",
            "combined development evidence PASS",
        ),
        ("all_18_pipeline_configs_frozen", "all 18 configurations frozen"),
        ("development_report_published", "the development report published"),
        ("tier_b_extended_set_predeclared", "the Tier-B set predeclared"),
        ("tier_a_development_complete", "Tier-A development complete"),
    ):
        _expect(
            completion.get(key) is True,
            f"Prompt-4 completion records {description}",
            errors,
        )
    for key, description in (
        ("held_out_evaluation_executed_by_prompt_4", "no held-out evaluation"),
        ("production_winner_selected", "no production winner"),
        ("tier_a_executed", "no held-out Tier-A execution"),
        ("tier_b_executed", "no held-out Tier-B execution"),
        ("tier_c_selected", "no Tier-C selection"),
    ):
        _expect(
            completion.get(key) is False,
            f"Prompt-4 completion records {description}",
            errors,
        )
    tiers = state.get("evaluation_tiers")
    tiers = tiers if isinstance(tiers, Mapping) else {}
    tier_a = tiers.get("tier_a") if isinstance(tiers.get("tier_a"), Mapping) else {}
    tier_b = tiers.get("tier_b") if isinstance(tiers.get("tier_b"), Mapping) else {}
    tier_c = tiers.get("tier_c") if isinstance(tiers.get("tier_c"), Mapping) else {}
    _expect(
        tier_a.get("pipeline_count") == 18
        and tier_a.get("status") == "DEVELOPMENT_COMPLETE_HELDOUT_NOT_RUN",
        "Prompt-4 Tier A is development-complete and held-out-not-run",
        errors,
    )
    _expect(
        tier_b.get("required_pipeline_count") == 6
        and tier_b.get("maximum_additional_challengers") == 2
        and tier_b.get("status") == "EXTENDED_SET_PREDECLARED_DEVELOPMENT_ONLY",
        "Prompt-4 Tier B is predeclared from development only",
        errors,
    )
    _expect(
        tier_c.get("selected_pipeline_ids") == []
        and tier_c.get("status") == "UNSELECTED_UNTIL_HELDOUT_AND_EXTENDED_TESTING",
        "Prompt-4 Tier C remains unselected",
        errors,
    )

    _expect(
        REQUIRED_PROMPT_4_CANONICAL_ARTIFACTS.issubset(artifacts),
        "program state binds all Prompt-4 canonical artifacts",
        errors,
    )
    expected_groups = (
        ("full_pipeline_development_package", REQUIRED_PROMPT_4_PACKAGE_PATHS),
        ("full_pipeline_development_wrapper", REQUIRED_PROMPT_4_WRAPPER_PATHS),
        ("full_pipeline_development_tests", REQUIRED_PROMPT_4_TEST_PATHS),
        (
            "full_pipeline_development_orchestration_plan",
            REQUIRED_PROMPT_4_ORCHESTRATION_PATHS,
        ),
        ("full_pipeline_development_policy_freeze", REQUIRED_PROMPT_4_POLICY_PATHS),
        (
            "full_pipeline_development_qualification",
            REQUIRED_PROMPT_4_QUALIFICATION_PATHS,
        ),
        (
            "full_pipeline_development_combined_evidence",
            REQUIRED_PROMPT_4_COMBINED_PATHS,
        ),
        (
            "full_pipeline_development_frozen_configs",
            REQUIRED_PROMPT_4_FROZEN_CONFIG_PATHS,
        ),
        ("full_pipeline_development_report", REQUIRED_PROMPT_4_REPORT_PATHS),
    )
    for artifact_name, expected_paths in expected_groups:
        _expect(
            _artifact_path_keys(artifacts.get(artifact_name)) == expected_paths,
            f"Prompt-4 artifact group has exact paths: {artifact_name}",
            errors,
        )

    orchestration = _load_json(
        evaluation_root / f"{PROMPT_4_WORKSPACE}/orchestration_plan.json", errors
    )
    registry_path = evaluation_root / (
        f"{PROMPT_4_WORKSPACE}/frozen/decision_policy_registry.json"
    )
    registry = _load_json(registry_path, errors)
    calibration_freeze = _load_json(
        evaluation_root / f"{PROMPT_4_WORKSPACE}/frozen/calibration_freeze.json",
        errors,
    )
    adoption = _load_json(
        evaluation_root
        / f"{PROMPT_4_WORKSPACE}/frozen/policy_adoption_provenance.json",
        errors,
    )
    source_calibration_manifest = _load_json(
        evaluation_root
        / (
            f"{PROMPT_4_CALIBRATION_SOURCE_WORKSPACE}/"
            "calibration/campaign_manifest.json"
        ),
        errors,
    )
    qualification_plan = _load_json(
        evaluation_root / f"{PROMPT_4_WORKSPACE}/qualification/qualification_plan.json",
        errors,
    )
    qualification = _load_json(
        evaluation_root / f"{PROMPT_4_WORKSPACE}/qualification/qualification.json",
        errors,
    )
    anchor_qualification = _load_json(
        evaluation_root
        / f"{PROMPT_4_WORKSPACE}/qualification/anchor_runtime_qualification.json",
        errors,
    )
    combined_manifest = _load_json(
        evaluation_root / f"{PROMPT_4_WORKSPACE}/combined_evidence/campaign_manifest.json",
        errors,
    )
    combined_analysis = _load_json(
        evaluation_root
        / f"{PROMPT_4_WORKSPACE}/combined_evidence/analysis/analysis.json",
        errors,
    )
    if registry:
        _validate_prompt_4_registry(registry, errors)
    if calibration_freeze and registry:
        _validate_prompt_4_calibration_freeze(
            calibration_freeze, registry, registry_path, errors
        )
    if adoption and source_calibration_manifest and registry and calibration_freeze:
        _validate_prompt_4_policy_adoption(
            adoption,
            source_calibration_manifest,
            calibration_freeze,
            registry,
            artifacts,
            evaluation_root,
            expected_policy_adoption_bindings,
            errors,
        )
    if orchestration:
        _validate_prompt_4_orchestration(
            orchestration,
            evaluation_root,
            adoption,
            source_calibration_manifest,
            errors,
        )
    if qualification and qualification_plan and anchor_qualification:
        _validate_prompt_4_qualification(
            qualification_plan, qualification, anchor_qualification, errors
        )
    if combined_manifest and combined_analysis:
        _validate_prompt_4_combined_evidence(
            combined_manifest, combined_analysis, errors
        )
    if registry and anchor_qualification and combined_manifest:
        _validate_prompt_4_frozen_configs(
            evaluation_root,
            registry,
            anchor_qualification,
            combined_manifest,
            errors,
        )
    _validate_prompt_4_report(evaluation_root, combined_manifest, errors)


def _validate_prompt_4_orchestration(
    plan: Mapping[str, Any],
    evaluation_root: Path,
    adoption: Mapping[str, Any],
    source_calibration_manifest: Mapping[str, Any],
    errors: list[str],
) -> None:
    _expect(
        plan.get("schema_version") == "full-pipeline-development-orchestration.v1"
        and plan.get("status") == "PASS",
        "Prompt-4 orchestration plan identity and PASS",
        errors,
    )
    _expect(
        plan.get("development_only") is True
        and plan.get("held_out_evaluation_allowed") is False
        and plan.get("production_winner_selected") is False,
        "Prompt-4 orchestration is development-only with no winner",
        errors,
    )
    stages = plan.get("stages") if isinstance(plan.get("stages"), Mapping) else {}
    expected = {
        "calibration": (56, 12, EXPECTED_PROMPT_4_CHALLENGERS, "accuracy"),
        "qualification": (1, 18, EXPECTED_PIPELINE_IDS, "accuracy"),
        "development": (807, 18, EXPECTED_PIPELINE_IDS, "accuracy"),
        "resources": (2, 18, EXPECTED_PIPELINE_IDS, "resources"),
    }
    for stage_name, (case_count, pipeline_count, pipeline_ids, mode) in expected.items():
        value = stages.get(stage_name)
        stage = value if isinstance(value, Mapping) else {}
        _expect(
            stage.get("case_count") == case_count
            and stage.get("pipeline_count") == pipeline_count
            and set(stage.get("pipeline_ids", [])) == pipeline_ids
            and stage.get("measurement_modes") == [mode],
            f"Prompt-4 orchestration exact {stage_name} scope",
            errors,
        )
    calibration = stages.get("calibration")
    calibration = calibration if isinstance(calibration, Mapping) else {}
    development = stages.get("development")
    development = development if isinstance(development, Mapping) else {}
    resources = stages.get("resources")
    resources = resources if isinstance(resources, Mapping) else {}
    qualification = stages.get("qualification")
    qualification = qualification if isinstance(qualification, Mapping) else {}
    _expect(
        calibration.get("parallel_jobs") in {1, 2}
        and development.get("parallel_jobs") in {1, 2}
        and qualification.get("cold_parallel_jobs") == 1
        and qualification.get("shared_parallel_jobs") in {1, 2}
        and resources.get("parallel_jobs") == 1,
        "Prompt-4 orchestration caps accuracy at two and resources at one",
        errors,
    )
    manifest_specs = {
        "qualification_shared": (
            "prompt4_qualification_shared",
            18,
            1,
            EXPECTED_PIPELINE_IDS,
            "accuracy",
        ),
        "qualification_cold": (
            "prompt4_qualification_cold",
            18,
            1,
            EXPECTED_PIPELINE_IDS,
            "accuracy",
        ),
        "development_accuracy": (
            "prompt4_all18_development_accuracy",
            36,
            807,
            EXPECTED_PIPELINE_IDS,
            "accuracy",
        ),
        "resource_spots": (
            "prompt4_resource_spots",
            36,
            2,
            EXPECTED_PIPELINE_IDS,
            "resources",
        ),
    }
    evaluation_identities: set[str] = set()
    source_evaluation_identity = str(
        source_calibration_manifest.get("evaluation_identity") or ""
    )
    if _is_sha256(source_evaluation_identity):
        evaluation_identities.add(source_evaluation_identity)
    expected_implementation_identity = {
        "development_policy_package_sha256": adoption.get(
            "destination_development_policy_package_sha256"
        ),
        "evaluation_package_sha256": adoption.get("evaluation_package_sha256"),
        "streaming_runtime_package_sha256": adoption.get(
            "streaming_runtime_package_sha256"
        ),
    }
    adopted_registry_sha256 = adoption.get(
        "decision_policy_registry_file_sha256"
    )
    scientific_identity_fields = (
        "full_protocol_id",
        "development_identity",
        "evaluation_identity",
        "matrix_sha256",
        "runtime_config_sha256",
        "scorer_version",
        "result_contract_version",
        "seed",
    )
    for directory, (
        campaign_stage,
        job_count,
        case_count,
        pipeline_ids,
        mode,
    ) in manifest_specs.items():
        manifest = _load_json(
            evaluation_root
            / f"{PROMPT_4_WORKSPACE}/{directory}/campaign_manifest.json",
            errors,
        )
        if not manifest:
            continue
        evaluation_identity = str(manifest.get("evaluation_identity") or "")
        if _is_sha256(evaluation_identity):
            evaluation_identities.add(evaluation_identity)
        jobs = manifest.get("jobs") if isinstance(manifest.get("jobs"), list) else []
        _expect(
            manifest.get("campaign_stage") == campaign_stage
            and manifest.get("job_count") == job_count
            and len(jobs) == job_count
            and manifest.get("case_count") == case_count
            and manifest.get("pipeline_count") == len(pipeline_ids)
            and set(manifest.get("selected_pipeline_ids", [])) == pipeline_ids
            and manifest.get("measurement_modes") == [mode]
            and all(
                isinstance(row, Mapping)
                and row.get("split") == "development"
                and row.get("measurement_mode") == mode
                and row.get("pipeline_id") in pipeline_ids
                for row in jobs
            ),
            f"Prompt-4 immutable {directory} campaign manifest scope",
            errors,
        )
        case_index = manifest.get("case_index")
        case_index = case_index if isinstance(case_index, Mapping) else {}
        _expect(
            len(case_index) == case_count
            and all(
                isinstance(row, Mapping)
                and str(row.get("split") or row.get("partition") or "")
                == "development"
                for row in case_index.values()
            ),
            f"Prompt-4 immutable {directory} manifest is development-only",
            errors,
        )
        parallelism = manifest.get("parallelism_policy")
        parallelism = parallelism if isinstance(parallelism, Mapping) else {}
        if mode == "resources":
            _expect(
                parallelism.get("resource_measurement_jobs") == 1,
                "Prompt-4 resource campaign manifest records serial execution",
                errors,
            )
        _expect(
            manifest.get("implementation_identity")
            == expected_implementation_identity,
            f"Prompt-4 v5 {directory} manifest binds destination implementation identity",
            errors,
        )
        registry_reference = manifest.get("decision_policy_registry")
        registry_reference = (
            registry_reference if isinstance(registry_reference, Mapping) else {}
        )
        _expect(
            _is_sha256(adopted_registry_sha256)
            and manifest.get("decision_policy_registry_sha256")
            == adopted_registry_sha256
            and registry_reference.get("logical_path")
            == "decision_policy_registry.json"
            and registry_reference.get("sha256") == adopted_registry_sha256,
            f"Prompt-4 v5 {directory} manifest binds adopted policy registry",
            errors,
        )
        for field in scientific_identity_fields:
            _expect(
                manifest.get(field) == source_calibration_manifest.get(field),
                (
                    "Prompt-4 inherited/v5 campaign scientific identity matches: "
                    f"{field}"
                ),
                errors,
            )
    _expect(
        len(evaluation_identities) == 1,
        "Prompt-4 campaign manifests bind one held-out protocol identity without running it",
        errors,
    )


def _validate_prompt_4_policy_adoption(
    adoption: Mapping[str, Any],
    source_manifest: Mapping[str, Any],
    destination_freeze: Mapping[str, Any],
    destination_registry: Mapping[str, Any],
    artifacts: Mapping[str, Any],
    evaluation_root: Path,
    expected_bindings: Mapping[str, str],
    errors: list[str],
) -> None:
    """Validate immutable v3 calibration adoption without replaying old code."""

    source_root = evaluation_root / PROMPT_4_CALIBRATION_SOURCE_WORKSPACE
    destination_root = evaluation_root / PROMPT_4_WORKSPACE
    source_manifest_path = source_root / "calibration/campaign_manifest.json"
    source_registry_path = source_root / "frozen/decision_policy_registry.json"
    source_freeze_path = source_root / "frozen/calibration_freeze.json"
    destination_registry_path = (
        destination_root / "frozen/decision_policy_registry.json"
    )
    destination_freeze_path = destination_root / "frozen/calibration_freeze.json"
    source_registry = _load_json(source_registry_path, errors)
    source_freeze = _load_json(source_freeze_path, errors)

    _expect(
        adoption.get("schema_version")
        == "full-pipeline-development-policy-adoption.v1"
        and adoption.get("status") == "PASS"
        and adoption.get("source_workspace")
        == PROMPT_4_CALIBRATION_SOURCE_WORKSPACE
        and adoption.get("destination_workspace") == PROMPT_4_WORKSPACE
        and adoption.get("reason")
        == "qualification_comparator_and_restart_contract_correction",
        "Prompt-4 policy adoption identity and workspace",
        errors,
    )
    hash_fields = (
        "source_development_policy_package_sha256",
        "destination_development_policy_package_sha256",
        "evaluation_package_sha256",
        "streaming_runtime_package_sha256",
        "source_calibration_campaign_manifest_sha256",
        "decision_policy_registry_file_sha256",
        "calibration_freeze_file_sha256",
        "decision_policy_registry_identity_sha256",
    )
    provenance_sha256_field = "policy_adoption_provenance_file_sha256"
    _expect(
        all(_is_sha256(adoption.get(field)) for field in hash_fields),
        "Prompt-4 policy adoption records valid SHA-256 identities",
        errors,
    )
    adoption_path = destination_root / "frozen/policy_adoption_provenance.json"
    _expect(
        all(
            _is_sha256(expected_bindings.get(field))
            for field in (*hash_fields, provenance_sha256_field)
        )
        and all(
            adoption.get(field) == expected_bindings.get(field)
            for field in hash_fields
        )
        and adoption_path.is_file()
        and _sha256(adoption_path).lower()
        == str(expected_bindings.get(provenance_sha256_field)).lower(),
        "Prompt-4 v5 adoption matches exact frozen release bindings",
        errors,
    )

    source_manifest_sha256 = adoption.get(
        "source_calibration_campaign_manifest_sha256"
    )
    registry_file_sha256 = adoption.get("decision_policy_registry_file_sha256")
    freeze_file_sha256 = adoption.get("calibration_freeze_file_sha256")
    file_bindings = (
        (source_manifest_path, source_manifest_sha256),
        (source_registry_path, registry_file_sha256),
        (destination_registry_path, registry_file_sha256),
        (source_freeze_path, freeze_file_sha256),
        (destination_freeze_path, freeze_file_sha256),
    )
    _expect(
        all(
            path.is_file()
            and _is_sha256(expected)
            and _sha256(path).lower() == str(expected).lower()
            for path, expected in file_bindings
        )
        and bool(source_registry)
        and source_registry == destination_registry
        and bool(source_freeze)
        and source_freeze == destination_freeze,
        "Prompt-4 policy adoption binds immutable source and copied policy bytes",
        errors,
    )
    _expect(
        adoption.get("source_calibration_complete") is True
        and adoption.get("source_calibration_sqlite_quick_check") == "ok"
        and adoption.get("source_calibration_result_checksums_verified") is True
        and adoption.get("qualification_only_code_change") is True
        and adoption.get("calibration_inference_repeated") is False
        and adoption.get("policy_retuned") is False
        and adoption.get("held_out_evaluation_allowed") is False
        and adoption.get("evaluation_material_inspected") is False,
        (
            "Prompt-4 policy adoption permits only the qualification comparator "
            "and restart-contract correction"
        ),
        errors,
    )

    jobs = (
        source_manifest.get("jobs")
        if isinstance(source_manifest.get("jobs"), list)
        else []
    )
    selected_pipeline_ids = source_manifest.get("selected_pipeline_ids")
    selected_pipeline_ids = (
        selected_pipeline_ids if isinstance(selected_pipeline_ids, list) else []
    )
    case_index = source_manifest.get("case_index")
    case_index = case_index if isinstance(case_index, Mapping) else {}
    _expect(
        source_manifest.get("schema_version")
        == "full-pipeline-evaluation-campaign-identity.v1"
        and source_manifest.get("campaign_stage")
        == "prompt4_challenger_calibration"
        and source_manifest.get("job_count") == 24
        and len(jobs) == 24
        and source_manifest.get("case_count") == 56
        and len(case_index) == 56
        and source_manifest.get("pipeline_count") == 12
        and set(selected_pipeline_ids) == EXPECTED_PROMPT_4_CHALLENGERS
        and source_manifest.get("measurement_modes") == ["accuracy"]
        and all(
            isinstance(row, Mapping)
            and row.get("split") == "development"
            and row.get("measurement_mode") == "accuracy"
            and row.get("pipeline_id") in EXPECTED_PROMPT_4_CHALLENGERS
            for row in jobs
        )
        and all(
            isinstance(row, Mapping)
            and str(row.get("split") or row.get("partition") or "")
            == "development"
            for row in case_index.values()
        )
        and source_manifest.get("decision_policy_registry_sha256") is None
        and source_manifest.get("decision_policy_registry") is None,
        "Prompt-4 inherited calibration exact development scope",
        errors,
    )
    source_implementation = source_manifest.get("implementation_identity")
    expected_source_implementation = {
        "development_policy_package_sha256": adoption.get(
            "source_development_policy_package_sha256"
        ),
        "evaluation_package_sha256": adoption.get("evaluation_package_sha256"),
        "streaming_runtime_package_sha256": adoption.get(
            "streaming_runtime_package_sha256"
        ),
    }
    _expect(
        source_implementation == expected_source_implementation,
        "Prompt-4 inherited calibration implementation identity",
        errors,
    )
    _expect(
        adoption.get("source_development_policy_package_sha256")
        != adoption.get("destination_development_policy_package_sha256"),
        "Prompt-4 qualification-only correction has a distinct destination package",
        errors,
    )
    _expect(
        adoption.get("source_calibration_job_count") == 24
        and adoption.get("source_calibration_case_count") == 56
        and adoption.get("source_challenger_pipeline_count") == 12
        and adoption.get("source_observation_count")
        == source_freeze.get("observation_count")
        and source_freeze.get("campaign_id") == source_manifest.get("campaign_id")
        and source_freeze.get("policy_registry_file_sha256")
        == registry_file_sha256
        and source_freeze.get("policy_registry_identity_sha256")
        == adoption.get("decision_policy_registry_identity_sha256")
        and destination_registry.get("registry_identity_sha256")
        == adoption.get("decision_policy_registry_identity_sha256"),
        "Prompt-4 policy adoption source counts and registry identity",
        errors,
    )

    package_record = artifacts.get("full_pipeline_development_package")
    package_paths = (
        package_record.get("paths") if isinstance(package_record, Mapping) else {}
    )
    package_paths = package_paths if isinstance(package_paths, Mapping) else {}
    expected_python_paths = {
        path for path in REQUIRED_PROMPT_4_PACKAGE_PATHS if path.endswith(".py")
    }
    current_python_hashes = {
        normalized: str(digest).lower()
        for path, digest in package_paths.items()
        if (normalized := _normalized_path(path)) in expected_python_paths
    }
    _expect(
        set(current_python_hashes) == expected_python_paths
        and all(_is_sha256(value) for value in current_python_hashes.values())
        and _canonical_json_sha256(current_python_hashes)
        == adoption.get("destination_development_policy_package_sha256"),
        "Prompt-4 v5 destination package hash matches canonical source artifacts",
        errors,
    )


def _validate_prompt_4_registry(
    registry: Mapping[str, Any], errors: list[str]
) -> None:
    rows = registry.get("entries") if isinstance(registry.get("entries"), list) else []
    pipeline_ids = [str(row.get("pipeline_id") or "") for row in rows if isinstance(row, Mapping)]
    identities = [
        str(row.get("calibration_identity_sha256") or "")
        for row in rows
        if isinstance(row, Mapping)
    ]
    _expect(
        registry.get("schema_version")
        == "full-pipeline-development-policy-registry.v1"
        and registry.get("status") == "FROZEN_DEVELOPMENT_ONLY",
        "Prompt-4 challenger policy registry identity",
        errors,
    )
    _expect(
        registry.get("calibration_partition") == "development"
        and registry.get("evaluation_material_inspected") is False
        and registry.get("evaluation_recalibration_allowed") is False
        and registry.get("cross_backend_threshold_sharing") is False,
        "Prompt-4 challenger calibration is development-only and backend-specific",
        errors,
    )
    _expect(
        len(rows) == 12
        and len(pipeline_ids) == len(set(pipeline_ids))
        and set(pipeline_ids) == EXPECTED_PROMPT_4_CHALLENGERS,
        "Prompt-4 registry contains exactly the 12 challenger pipelines",
        errors,
    )
    _expect(
        len(identities) == 12
        and len(set(identities)) == 12
        and all(_is_sha256(value) for value in identities),
        "Prompt-4 challenger policies have unique exact-pipeline identities",
        errors,
    )
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pipeline_id = str(row.get("pipeline_id") or "")
        _expect(
            row.get("calibration_partition") == "development"
            and row.get("evaluation_material_inspected") is False
            and row.get("threshold_shared_with_another_pipeline") is False
            and row.get("calibration_method")
            == "maximum_gallery_score_with_top1_top2_margin"
            and isinstance(row.get("thresholds_by_gallery_request"), list)
            and bool(row.get("thresholds_by_gallery_request")),
            f"Prompt-4 challenger policy is frozen independently: {pipeline_id}",
            errors,
        )
    core = {key: value for key, value in registry.items() if key != "registry_identity_sha256"}
    _expect(
        registry.get("registry_identity_sha256") == _canonical_json_sha256(core),
        "Prompt-4 challenger registry identity checksum",
        errors,
    )


def _validate_prompt_4_calibration_freeze(
    freeze: Mapping[str, Any],
    registry: Mapping[str, Any],
    registry_path: Path,
    errors: list[str],
) -> None:
    _expect(
        freeze.get("schema_version")
        == "full-pipeline-development-policy-freeze-evidence.v1"
        and freeze.get("status") == "PASS"
        and freeze.get("campaign_stage") == "prompt4_challenger_calibration",
        "Prompt-4 challenger calibration freeze PASS",
        errors,
    )
    _expect(
        freeze.get("calibration_partition") == "development"
        and freeze.get("calibration_case_count") == 56
        and freeze.get("challenger_pipeline_count") == 12
        and freeze.get("evaluation_material_inspected") is False,
        "Prompt-4 challenger freeze uses the exact development scope",
        errors,
    )
    _expect(
        freeze.get("policy_registry_file_sha256") == _sha256(registry_path)
        and freeze.get("policy_registry_identity_sha256")
        == registry.get("registry_identity_sha256"),
        "Prompt-4 calibration freeze binds the immutable registry",
        errors,
    )


def _validate_prompt_4_qualification(
    plan: Mapping[str, Any],
    bundle: Mapping[str, Any],
    anchor: Mapping[str, Any],
    errors: list[str],
) -> None:
    plan_rows = plan.get("records") if isinstance(plan.get("records"), list) else []
    rows = bundle.get("records") if isinstance(bundle.get("records"), list) else []
    plan_ids = {str(row.get("pipeline_id") or "") for row in plan_rows if isinstance(row, Mapping)}
    ids = [str(row.get("pipeline_id") or "") for row in rows if isinstance(row, Mapping)]
    _expect(
        plan.get("schema_version")
        == "full-pipeline-development-qualification-plan.v1"
        and plan.get("pipeline_count") == 18
        and len(plan_rows) == 18
        and plan_ids == EXPECTED_PIPELINE_IDS
        and plan.get("evaluation_material_inspected") is False,
        "Prompt-4 qualification plan covers exactly all 18 development pipelines",
        errors,
    )
    _expect(
        bundle.get("schema_version") == "full-pipeline-development-qualification.v1"
        and bundle.get("status") == "PASS"
        and bundle.get("pipeline_count") == 18
        and len(rows) == 18
        and len(ids) == len(set(ids))
        and set(ids) == EXPECTED_PIPELINE_IDS,
        "Prompt-4 qualification bundle has exactly 18 PASS records",
        errors,
    )
    _expect(
        bundle.get("evaluation_material_inspected") is False
        and bundle.get("production_winner_selected") is False
        and bundle.get("plan_identity_sha256") == plan.get("plan_identity_sha256"),
        "Prompt-4 qualification is development-only and binds its plan",
        errors,
    )
    required_checks = {
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
    }
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        pipeline_id = str(row.get("pipeline_id") or "")
        checks = row.get("checks") if isinstance(row.get("checks"), Mapping) else {}
        _expect(
            row.get("split") == "development"
            and row.get("qualification_status") == "PASS"
            and row.get("evaluation_material_inspected") is False
            and set(checks) == required_checks
            and all(
                isinstance(check, Mapping) and check.get("status") == "PASS"
                for check in checks.values()
            ),
            f"Prompt-4 qualification record passes every required check: {pipeline_id}",
            errors,
        )
        record_core = {
            key: value for key, value in row.items() if key != "record_identity_sha256"
        }
        _expect(
            row.get("record_identity_sha256") == _canonical_json_sha256(record_core),
            f"Prompt-4 qualification record identity: {pipeline_id}",
            errors,
        )
    bundle_core = {
        key: value for key, value in bundle.items() if key != "qualification_result_sha256"
    }
    _expect(
        bundle.get("qualification_result_sha256")
        == _canonical_json_sha256(bundle_core),
        "Prompt-4 qualification result identity",
        errors,
    )
    anchor_ids = anchor.get("anchor_pipeline_ids")
    _expect(
        anchor.get("schema_version") == "full-pipeline-anchor-runtime-qualification.v1"
        and anchor.get("status") == "PASS"
        and set(anchor_ids if isinstance(anchor_ids, list) else []) == EXPECTED_TIER_B
        and len(anchor_ids if isinstance(anchor_ids, list) else []) == 6
        and anchor.get("qualification_result_sha256")
        == bundle.get("qualification_result_sha256")
        and anchor.get("evaluation_material_inspected") is False,
        "Prompt-4 runtime qualification binds the six frozen anchors",
        errors,
    )
    for key in (
        "correct_diarization_embedding_provenance",
        "predicted_overlap_excluded_from_primary_identity",
        "product_v2_probe_consistency_semantics",
        "product_v2_hysteresis_semantics",
        "decision_policy_hash_is_not_enrollment_hash",
        "all_six_anchor_pipelines_integrated_smoke_passed",
    ):
        _expect(
            anchor.get(key) is True,
            f"Prompt-4 anchor runtime attestation: {key}",
            errors,
        )


def _validate_prompt_4_combined_evidence(
    manifest: Mapping[str, Any],
    analysis: Mapping[str, Any],
    errors: list[str],
) -> None:
    jobs = manifest.get("jobs") if isinstance(manifest.get("jobs"), list) else []
    rows = analysis.get("rows") if isinstance(analysis.get("rows"), list) else []
    _expect(
        manifest.get("schema_version")
        == "full-pipeline-development-combined-campaign.v1"
        and manifest.get("pipeline_count") == 18
        and set(manifest.get("selected_pipeline_ids", [])) == EXPECTED_PIPELINE_IDS
        and manifest.get("measurement_modes") == ["accuracy", "resources"],
        "Prompt-4 combined campaign covers all 18 pipelines and both modes",
        errors,
    )
    _expect(
        _is_sha256(manifest.get("development_identity"))
        and _is_sha256(manifest.get("evaluation_identity")),
        "Prompt-4 combined campaign binds distinct development/evaluation identities",
        errors,
    )
    _expect(
        manifest.get("job_count") == 72
        and len(jobs) == 72
        and manifest.get("case_count") == 807
        and isinstance(manifest.get("case_index"), Mapping)
        and len(manifest.get("case_index", {})) == 807,
        "Prompt-4 combined evidence has 72 jobs over all 807 development cases",
        errors,
    )
    _expect(
        manifest.get("development_only") is True
        and manifest.get("evaluation_material_inspected") is False
        and manifest.get("held_out_evaluation_allowed") is False
        and manifest.get("production_winner_selected") is False,
        "Prompt-4 combined evidence excludes held-out material and winner selection",
        errors,
    )
    cases = manifest.get("case_index")
    case_rows = cases.values() if isinstance(cases, Mapping) else []
    _expect(
        all(
            isinstance(row, Mapping)
            and str(row.get("split") or row.get("partition") or "") == "development"
            for row in case_rows
        ),
        "Prompt-4 combined case index is development-only",
        errors,
    )
    job_ids = [str(row.get("job_id") or "") for row in jobs if isinstance(row, Mapping)]
    _expect(
        len(job_ids) == 72
        and len(set(job_ids)) == 72
        and all(
            isinstance(row, Mapping)
            and row.get("split") == "development"
            and row.get("pipeline_id") in EXPECTED_PIPELINE_IDS
            and row.get("measurement_mode") in {"accuracy", "resources"}
            for row in jobs
        ),
        "Prompt-4 combined manifest jobs are unique development jobs",
        errors,
    )
    for pipeline_id in EXPECTED_PIPELINE_IDS:
        modes = [
            str(row.get("measurement_mode") or "")
            for row in jobs
            if isinstance(row, Mapping) and row.get("pipeline_id") == pipeline_id
        ]
        _expect(
            modes.count("accuracy") == 2 and modes.count("resources") == 2,
            f"Prompt-4 combined evidence has matched jobs: {pipeline_id}",
            errors,
        )
    parallelism = manifest.get("parallelism_policy")
    parallelism = parallelism if isinstance(parallelism, Mapping) else {}
    _expect(
        parallelism.get("accuracy_maximum_jobs") == 2
        and parallelism.get("resource_measurement_jobs") == 1
        and parallelism.get("resource_results_comparable_only_with_serial_resource_results")
        is True,
        "Prompt-4 combined evidence records serial resource measurement",
        errors,
    )
    identity_core = {
        key: value
        for key, value in manifest.items()
        if key
        not in {
            "schema_version",
            "campaign_id",
            "campaign_identity_sha256",
            "pipeline_count",
            "job_count",
            "case_count",
            "parallelism_policy",
            "production_winner_selected",
            "held_out_evaluation_allowed",
            "model_inference_performed_by_combination",
        }
    }
    identity = manifest.get("campaign_identity_sha256")
    _expect(
        identity == _canonical_json_sha256(identity_core)
        and manifest.get("campaign_id")
        == f"full_pipeline_development_combined_{str(identity)[:12]}",
        "Prompt-4 combined campaign identity checksum",
        errors,
    )
    _expect(
        analysis.get("schema_version") == "full-pipeline-evaluation-analysis.v1"
        and analysis.get("campaign_id") == manifest.get("campaign_id")
        and analysis.get("campaign_identity_sha256") == identity
        and analysis.get("complete_result_count") == 72
        and analysis.get("accuracy_result_count") == 36
        and analysis.get("resource_result_count") == 36
        and len(rows) == 72,
        "Prompt-4 combined analysis has all 72 completed results",
        errors,
    )
    analysis_job_ids = [
        str(row.get("job_id") or "") for row in rows if isinstance(row, Mapping)
    ]
    _expect(
        set(analysis_job_ids) == set(job_ids)
        and len(analysis_job_ids) == len(set(analysis_job_ids))
        and all(
            isinstance(row, Mapping)
            and row.get("split") == "development"
            and row.get("evaluation_material_inspected") is False
            and _is_sha256(row.get("result_checksums_sha256"))
            for row in rows
        ),
        "Prompt-4 combined analysis rows are checksum-bound development rows",
        errors,
    )
    result_checksums = {
        str(row.get("job_id")): str(row.get("result_checksums_sha256"))
        for row in rows
        if isinstance(row, Mapping)
    }
    result_identity = _canonical_json_sha256(result_checksums)
    _expect(
        result_identity == manifest.get("development_result_set_sha256")
        and result_identity == analysis.get("development_result_set_sha256")
        and analysis.get("evaluation_material_inspected") is False
        and analysis.get("weighted_composite_score_created") is False,
        "Prompt-4 combined development result identity and firewall",
        errors,
    )


def _validate_prompt_4_frozen_configs(
    evaluation_root: Path,
    registry: Mapping[str, Any],
    anchor_qualification: Mapping[str, Any],
    combined_manifest: Mapping[str, Any],
    errors: list[str],
) -> None:
    root = evaluation_root / f"{PROMPT_4_WORKSPACE}/frozen_pipeline_configs"
    expected_names = {f"{pipeline_id}.yaml" for pipeline_id in EXPECTED_PIPELINE_IDS}
    actual_names = {path.name for path in root.iterdir() if path.is_file()} if root.is_dir() else set()
    _expect(
        actual_names == expected_names | {"checksums.json"},
        "Prompt-4 frozen-config directory contains exactly 18 YAMLs and checksums",
        errors,
    )
    checksums = _load_json(root / "checksums.json", errors)
    actual_hashes = {
        path.name: _sha256(path)
        for path in sorted(root.glob("*.yaml"))
        if path.is_file()
    }
    _expect(
        checksums.get("schema_version")
        == "full-pipeline-development-config-checksums.v1"
        and checksums.get("pipeline_count") == 18
        and checksums.get("entries") == actual_hashes,
        "Prompt-4 frozen-config checksum map covers exactly 18 YAMLs",
        errors,
    )
    registry_rows = registry.get("entries") if isinstance(registry.get("entries"), list) else []
    registry_by_id = {
        str(row.get("pipeline_id")): row
        for row in registry_rows
        if isinstance(row, Mapping)
    }
    observed: set[str] = set()
    for path in sorted(root.glob("*.yaml")):
        document = _load_yaml(path, errors)
        if not document:
            continue
        pipeline_id = str(document.get("pipeline_id") or "")
        observed.add(pipeline_id)
        aliases = document.get("aliases") if isinstance(document.get("aliases"), Mapping) else {}
        identity_policy = (
            document.get("identity_policy")
            if isinstance(document.get("identity_policy"), Mapping)
            else {}
        )
        source_hashes = (
            document.get("source_hashes")
            if isinstance(document.get("source_hashes"), Mapping)
            else {}
        )
        _expect(
            document.get("schema_version")
            == "full-pipeline-development-config-freeze.v1"
            and document.get("status") == "IMMUTABLE_DEVELOPMENT_FREEZE"
            and pipeline_id in EXPECTED_PIPELINE_IDS
            and document.get("development_protocol_sha256")
            == combined_manifest.get("development_identity")
            and document.get("development_result_set_sha256")
            == combined_manifest.get("development_result_set_sha256"),
            f"Prompt-4 immutable config identity: {pipeline_id}",
            errors,
        )
        _expect(
            document.get("evaluation_material_inspected") is False
            and document.get("evaluation_retuning_allowed") is False
            and document.get("production_winner_selected") is False
            and document.get("runtime_anchor_qualification") == anchor_qualification,
            f"Prompt-4 config preserves evaluation firewall: {pipeline_id}",
            errors,
        )
        core = {
            key: value for key, value in document.items() if key != "freeze_identity_sha256"
        }
        _expect(
            document.get("freeze_identity_sha256") == _canonical_json_sha256(core),
            f"Prompt-4 frozen config identity checksum: {pipeline_id}",
            errors,
        )
        hybrid = str(aliases.get("hybrid") or "")
        if pipeline_id in EXPECTED_TIER_B:
            _expect(
                hybrid in EXPECTED_ANCHOR_THRESHOLDS
                and identity_policy.get("frozen_anchor") is True
                and identity_policy.get("calibration_protocol_id")
                == FROZEN_HYBRID_PROTOCOL_ID
                and identity_policy.get("decision_policy_sha256")
                == FROZEN_HYBRID_SELECTION_SHA256
                and identity_policy.get("calibration_result_sha256")
                == FROZEN_HYBRID_SELECTION_SHA256
                and identity_policy.get("score_threshold")
                == EXPECTED_ANCHOR_THRESHOLDS.get(hybrid)
                and identity_policy.get("margin_threshold") == 0.03
                and identity_policy.get("minimum_evidence_sec") == 2.0
                and source_hashes.get("frozen_hybrid_selection_sha256")
                == FROZEN_HYBRID_SELECTION_SHA256,
                f"Prompt-4 config preserves exact frozen anchor SHA/settings: {pipeline_id}",
                errors,
            )
        else:
            registry_row = registry_by_id.get(pipeline_id, {})
            _expect(
                identity_policy.get("decision_policy_sha256")
                == registry_row.get("calibration_identity_sha256")
                and identity_policy.get("calibration_partition") == "development"
                and source_hashes.get("development_policy_registry_sha256")
                == registry.get("registry_identity_sha256"),
                f"Prompt-4 config binds its challenger calibration: {pipeline_id}",
                errors,
            )
    _expect(
        observed == EXPECTED_PIPELINE_IDS,
        "Prompt-4 frozen configs represent exactly all 18 pipelines",
        errors,
    )


def _validate_prompt_4_report(
    evaluation_root: Path,
    combined_manifest: Mapping[str, Any],
    errors: list[str],
) -> None:
    root = evaluation_root / PROMPT_4_REPORT_ROOT
    expected_top = REQUIRED_PROMPT_4_REPORT_FILES | {"frozen_pipeline_configs"}
    actual_top = {path.name for path in root.iterdir()} if root.is_dir() else set()
    _expect(
        actual_top == expected_top,
        "Prompt-4 report directory has the exact requested outputs",
        errors,
    )
    matrix_rows = _load_csv_rows(root / "development_matrix.csv", errors)
    summary_rows = _load_csv_rows(root / "development_summary.csv", errors)
    for name, rows in (("matrix", matrix_rows), ("summary", summary_rows)):
        ids = [row.get("pipeline_id", "") for row in rows]
        _expect(
            len(rows) == 18
            and len(ids) == len(set(ids))
            and set(ids) == EXPECTED_PIPELINE_IDS,
            f"Prompt-4 development {name} has exactly 18 pipeline rows",
            errors,
        )
    _expect(
        all(row.get("split") == "development" for row in summary_rows)
        and all(row.get("evaluation_material_inspected") == "False" for row in summary_rows),
        "Prompt-4 development summary is development-only",
        errors,
    )
    extended = _load_yaml(root / "extended_set.yaml", errors)
    mandatory = extended.get("mandatory_pipeline_ids")
    challengers = extended.get("additional_challenger_pipeline_ids")
    mandatory_ids = mandatory if isinstance(mandatory, list) else []
    challenger_ids = challengers if isinstance(challengers, list) else []
    _expect(
        extended.get("schema_version") == "full-pipeline-tier-b-development-set.v1"
        and extended.get("status") == "FROZEN_DEVELOPMENT_ONLY"
        and set(mandatory_ids) == EXPECTED_TIER_B
        and len(mandatory_ids) == 6
        and len(challenger_ids) <= 2
        and set(challenger_ids).issubset(EXPECTED_PROMPT_4_CHALLENGERS)
        and extended.get("extended_pipeline_ids") == mandatory_ids + challenger_ids,
        "Prompt-4 Tier-B set is six mandatory anchors plus at most two challengers",
        errors,
    )
    extended_core = {
        key: value for key, value in extended.items() if key != "identity_sha256"
    }
    _expect(
        extended.get("weighted_composite_score_used") is False
        and extended.get("evaluation_material_inspected") is False
        and extended.get("production_winner_selected") is False
        and extended.get("identity_sha256") == _canonical_json_sha256(extended_core),
        "Prompt-4 Tier-B selection is unweighted, development-only, and checksum-bound",
        errors,
    )
    analysis = _load_json(root / "development_analysis.json", errors)
    summaries = (
        analysis.get("pipeline_summaries")
        if isinstance(analysis.get("pipeline_summaries"), list)
        else []
    )
    _expect(
        analysis.get("schema_version") == "full-pipeline-development-analysis.v1"
        and analysis.get("status") == "PASS"
        and analysis.get("pipeline_count") == 18
        and len(summaries) == 18
        and {str(row.get("pipeline_id")) for row in summaries if isinstance(row, Mapping)}
        == EXPECTED_PIPELINE_IDS
        and analysis.get("extended_set") == extended,
        "Prompt-4 development analysis has exactly 18 summaries and binds Tier B",
        errors,
    )
    _expect(
        analysis.get("development_identity_sha256")
        == combined_manifest.get("development_identity")
        and analysis.get("campaign_identity_sha256")
        == combined_manifest.get("campaign_identity_sha256")
        and analysis.get("weighted_composite_score_created") is False
        and analysis.get("evaluation_material_inspected") is False
        and analysis.get("production_winner_selected") is False
        and analysis.get("final_winner") is None,
        "Prompt-4 report preserves development identity and selects no winner",
        errors,
    )
    analysis_core = {
        key: value for key, value in analysis.items() if key != "analysis_identity_sha256"
    }
    _expect(
        analysis.get("analysis_identity_sha256") == _canonical_json_sha256(analysis_core),
        "Prompt-4 development analysis identity checksum",
        errors,
    )
    resource_rows = _load_csv_rows(root / "resource_spot_checks.csv", errors)
    _expect(
        {row.get("pipeline_id", "") for row in resource_rows} == EXPECTED_PIPELINE_IDS
        and all(
            row.get("comparison_scope") == "serial_matched_resource_jobs_only"
            for row in resource_rows
        ),
        "Prompt-4 resource report covers all pipelines with serial-only scope",
        errors,
    )
    checksums = _load_json(root / "checksums.json", errors)
    actual_hashes = {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.relative_to(root).as_posix()
        not in {"full_pipeline_development_compact.zip", "checksums.json"}
    }
    _expect(
        checksums.get("schema_version")
        == "full-pipeline-development-report-checksums.v1"
        and checksums.get("entries") == actual_hashes
        and checksums.get("raw_audio_included") is False
        and checksums.get("model_assets_included") is False
        and checksums.get("cache_payloads_included") is False
        and checksums.get("biometric_vectors_included") is False,
        "Prompt-4 report checksum map and privacy exclusions are exact",
        errors,
    )
    source_configs = evaluation_root / f"{PROMPT_4_WORKSPACE}/frozen_pipeline_configs"
    copied_configs = root / "frozen_pipeline_configs"
    _expect(
        source_configs.is_dir()
        and copied_configs.is_dir()
        and {
            path.name: _sha256(path) for path in source_configs.iterdir() if path.is_file()
        }
        == {path.name: _sha256(path) for path in copied_configs.iterdir() if path.is_file()},
        "Prompt-4 report preserves exact frozen-config bytes",
        errors,
    )
    _validate_prompt_4_zip(root, errors)


def _validate_prompt_4_zip(root: Path, errors: list[str]) -> None:
    zip_path = root / "full_pipeline_development_compact.zip"
    expected = {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != zip_path
    }
    if not zip_path.is_file():
        errors.append(f"missing Prompt-4 compact ZIP: {zip_path}")
        return
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            _expect(
                len(names) == len(set(names)) and set(names) == set(expected),
                "Prompt-4 compact ZIP contains every report artifact exactly once",
                errors,
            )
            for info in infos:
                path = expected.get(info.filename)
                if path is None:
                    continue
                _expect(
                    info.date_time == (1980, 1, 1, 0, 0, 0)
                    and info.compress_type == zipfile.ZIP_DEFLATED
                    and archive.read(info) == path.read_bytes(),
                    f"Prompt-4 deterministic ZIP member: {info.filename}",
                    errors,
                )
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        errors.append(f"invalid Prompt-4 compact ZIP {zip_path}: {exc}")


def _load_csv_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        errors.append(f"missing CSV file: {path}")
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))
    except (OSError, UnicodeError, csv.Error) as exc:
        errors.append(f"invalid CSV {path}: {exc}")
        return []


def _artifact_path_keys(value: object) -> set[str]:
    if not isinstance(value, Mapping):
        return set()
    paths = value.get("paths")
    if not isinstance(paths, Mapping):
        return set()
    return {_normalized_path(path) for path in paths}


def _normalized_path(value: object) -> str:
    return str(value).replace("\\", "/") if isinstance(value, str) else ""


def _protocol_case_ids(
    path: Path, split: str, protocol_id: object, errors: list[str]
) -> list[str]:
    if not path.is_file():
        errors.append(f"missing JSONL file: {path}")
        return []
    case_ids: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"row {line_number} is not an object")
                if row.get("partition") != split:
                    errors.append(
                        f"Prompt-3 protocol {split} row has another partition: "
                        f"{path}:{line_number}"
                    )
                if row.get("protocol_id") != protocol_id:
                    errors.append(
                        f"Prompt-3 protocol {split} row has another protocol ID: "
                        f"{path}:{line_number}"
                    )
                case_id = row.get("protocol_case_id")
                if not isinstance(case_id, str) or not case_id:
                    raise ValueError(f"row {line_number} has no protocol_case_id")
                case_ids.append(case_id)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"invalid JSONL {path}: {exc}")
        return []
    _expect(
        case_ids == sorted(case_ids) and len(case_ids) == len(set(case_ids)),
        f"Prompt-3 protocol {split} case IDs are sorted and unique",
        errors,
    )
    return case_ids


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _is_useful_labelled_attribution(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    start = value.get("start_sec")
    end = value.get("end_sec")
    if (
        not isinstance(start, (int, float))
        or isinstance(start, bool)
        or not isinstance(end, (int, float))
        or isinstance(end, bool)
        or float(end) <= float(start)
    ):
        return False
    anonymous = value.get("anonymous_speaker_id")
    label = str(value.get("speaker_label") or "").strip()
    alignment = str(value.get("alignment_status") or "").strip()
    return (
        isinstance(anonymous, str)
        and bool(anonymous.strip())
        and bool(label)
        and label.casefold() != "unassigned"
        and bool(alignment)
        and "insufficient" not in alignment.casefold()
    )


def _verify_local_assets(
    matrix: Mapping[str, Any], repo_root: Path, errors: list[str]
) -> int:
    checked = 0
    axes = matrix["axes"]
    for definition in axes["asr"].values():
        asset = definition["model_asset"]
        root = _asset_path(repo_root, asset["storage_path"])
        checked += _check_tree(root, asset["installed_tree_sha256"], errors)
        checked += _check_relative_files(root, asset["result_affecting_files"], errors)
        checked += _check_file_hash(
            _asset_path(repo_root, asset["source_archive_path"]),
            asset["source_archive_sha256"],
            errors,
        )
    segmentation = matrix["shared_segmentation_asset"]
    segmentation_root = _asset_path(repo_root, segmentation["storage_path"])
    checked += _check_tree(segmentation_root, segmentation["installed_tree_sha256"], errors)
    checked += _check_relative_files(segmentation_root, segmentation["result_affecting_files"], errors)

    iw = axes["identity"]["IW"]
    iw_root = _asset_path(repo_root, iw["model_asset_path"])
    checked += _check_tree(iw_root, iw["model_asset_sha256"], errors)
    checked += _check_relative_files(iw_root, iw["result_affecting_files"], errors)
    checked += _check_file_hash(
        _asset_path(repo_root, iw["source_archive_path"]), iw["source_archive_sha256"], errors
    )

    ir = axes["identity"]["IR"]
    checked += _check_file_hash(
        _asset_path(repo_root, ir["model_asset_path"]), ir["model_asset_sha256"], errors
    )
    checked += _check_tree(
        _asset_path(repo_root, ir["official_source_path"]),
        ir["official_source_tree_sha256"],
        errors,
    )
    checked += _check_file_hash(
        _asset_path(repo_root, ir["official_source_archive_path"]),
        ir["official_source_archive_sha256"],
        errors,
    )

    ie = axes["identity"]["IE"]
    checked += _check_relative_files(
        _asset_path(repo_root, ie["model_asset_path"]), ie["result_affecting_files"], errors
    )
    return checked


def _check_relative_files(root: Path, files: Mapping[str, str], errors: list[str]) -> int:
    checked = 0
    for relative, expected in files.items():
        checked += _check_file_hash(root / relative, expected, errors)
    return checked


def _collect_property_schemas(
    value: Any, property_names: set[str]
) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            for name in property_names:
                schema = properties.get(name)
                if isinstance(schema, dict):
                    found.append(schema)
        for child in value.values():
            found.extend(_collect_property_schemas(child, property_names))
    elif isinstance(value, list):
        for child in value:
            found.extend(_collect_property_schemas(child, property_names))
    return found


def _collect_references(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str):
            references.append(reference)
        for child in value.values():
            references.extend(_collect_references(child))
    elif isinstance(value, list):
        for child in value:
            references.extend(_collect_references(child))
    return references


def _check_tree(path: Path, expected: str, errors: list[str]) -> int:
    if not path.is_dir():
        errors.append(f"missing asset directory: {path}")
        return 0
    rows: list[tuple[str, int, str]] = []
    for candidate in sorted(
        (
            item
            for item in path.rglob("*")
            if item.is_file()
            and "__pycache__" not in item.parts
            and item.suffix.lower() not in {".pyc", ".pyo"}
        ),
        key=lambda item: item.relative_to(path).as_posix(),
    ):
        rows.append((candidate.relative_to(path).as_posix(), candidate.stat().st_size, _sha256(candidate)))
    digest = hashlib.sha256()
    for relative, size, file_hash in rows:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    _expect(digest.hexdigest().lower() == expected.lower(), f"asset tree hash: {path}", errors)
    return 1


def _check_file_hash(path: Path, expected: str, errors: list[str]) -> int:
    if not path.is_file():
        errors.append(f"missing locked file: {path}")
        return 0
    observed = _sha256(path)
    _expect(observed.lower() == expected.lower(), f"SHA-256 for {path}", errors)
    return 1


def _load_yaml(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing YAML file: {path}")
        return {}
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation reports all parse failures.
        errors.append(f"invalid YAML {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"YAML root is not an object: {path}")
        return {}
    return value


def _load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing JSON file: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation reports all parse failures.
        errors.append(f"invalid JSON {path}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"JSON root is not an object: {path}")
        return {}
    return value


def _resolve(evaluation_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (evaluation_root / path).resolve()


def _asset_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _expect(condition: bool, description: str, errors: list[str]) -> None:
    if not condition:
        errors.append(description)
