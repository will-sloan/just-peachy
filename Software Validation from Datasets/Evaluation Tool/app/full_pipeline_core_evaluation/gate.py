"""Cross-workspace Prompt-4 freeze and eight-day amendment admission gate."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Mapping

import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_deployment_evidence import (
    DeploymentEvidenceError,
    load_deployment_steering,
    steering_ref,
)
from app.full_pipeline_development.freeze import (
    PIPELINE_FREEZE_SCHEMA_VERSION,
    _model_asset_identity,
    _result_affecting_code_identity,
    _validate_anchor_runtime_qualification,
    baseline_alignment_buffering_policy,
)
from app.full_pipeline_development.policies import (
    FROZEN_ANCHOR_LABELS,
    FROZEN_HYBRID_PROTOCOL_ID,
    FROZEN_HYBRID_SELECTION_SHA256,
    resolve_decision_policy_contract,
    validate_development_policy_registry,
)
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
)
from app.full_pipeline_evaluation.planning import (
    EVALUATION_ROOT,
    MATRIX_PATH,
    RUNTIME_CONFIG_PATH,
)

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
    ORIGINAL_FULL_SCOPE_COMPLETE,
    PROMPT4_COMPLETION_MARKER,
    SCOPE_CLASS,
    SCOPE_ID,
)
from .io import (
    CoreEvaluationError,
    ensure_c_drive,
    scope_fields,
    verify_checksum_document,
)


MARKER_SCHEMA = "full-pipeline-eight-day-stage-completion.v1"
REQUIRED_ARTIFACT_KEYS = {
    "frozen_pipeline_configs",
    "decision_policy_registry",
    "extended_set",
    "development_summary",
}
HELDOUT_FALSE_FIELDS = (
    "evaluation_material_inspected",
    "held_out_evaluation_started",
    "held_out_evaluation_audio_processed",
    "held_out_evaluation_inference_or_scoring_executed",
    "held_out_predictions_metrics_or_results_inspected",
    "held_out_evaluation_used_for_calibration_metrics_or_selection",
)
FROZEN_UI_LABEL_POLICY = {
    "unknown_labels": "stable_session_local_Unknown_N",
    "label_states": ["unknown", "tentative", "confirmed"],
    "tentative_visible": True,
    "raw_score_displayed_as_confidence_percentage": False,
    "retroactive_changes_require_causal_revision": True,
}


def validate_prompt4_freeze(
    marker_path: Path | str,
    *,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    """Validate the bounded Prompt-4 marker and every bound artifact byte."""

    marker_file = ensure_c_drive(marker_path, label="Prompt-4 marker", must_exist=True)
    amendment_file = ensure_c_drive(
        amendment_path, label="eight-day scope amendment", must_exist=True
    )
    state_file = ensure_c_drive(
        program_state_path, label="full-pipeline program state", must_exist=True
    )
    try:
        deployment_steering = load_deployment_steering(
            pi_deployment_steering_path,
            expected_prompt_index=5,
            expected_sha256=EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
        )
        deployment_steering_reference = steering_ref(
            pi_deployment_steering_path, deployment_steering
        )
    except DeploymentEvidenceError as exc:
        raise CoreEvaluationError(str(exc)) from exc
    marker = read_json(marker_file)
    _require_equal(marker, "schema_version", MARKER_SCHEMA)
    _require_equal(marker, "status", "COMPLETE")
    _require_equal(marker, "completion_marker", PROMPT4_COMPLETION_MARKER)
    _require_equal(marker, "prompt_index", 4)
    _require_scope(marker, label="Prompt-4 marker")
    if marker.get("development_only") is not True:
        raise CoreEvaluationError("Prompt-4 marker lacks development_only=true")
    for field in HELDOUT_FALSE_FIELDS:
        if field in marker and marker.get(field) is not False:
            raise CoreEvaluationError(f"Prompt-4 firewall field is not false: {field}")
    if marker.get("evaluation_material_inspected") is not False:
        raise CoreEvaluationError("Prompt-4 marker must prove no evaluation inspection")
    if marker.get("held_out_evaluation_started") is not False:
        raise CoreEvaluationError("Prompt-4 marker says held-out evaluation started")

    amendment = read_json(amendment_file)
    _validate_amendment(amendment)
    program_state = read_json(state_file)
    _validate_program_state(program_state)

    artifacts = marker.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise CoreEvaluationError("Prompt-4 marker artifacts must be an object")
    missing = REQUIRED_ARTIFACT_KEYS - set(str(key) for key in artifacts)
    if missing:
        raise CoreEvaluationError(
            "Prompt-4 marker lacks required artifacts: " + ", ".join(sorted(missing))
        )
    normalized: dict[str, dict[str, object]] = {}
    for key in sorted(REQUIRED_ARTIFACT_KEYS):
        raw = artifacts[key]
        if not isinstance(raw, Mapping):
            raise CoreEvaluationError(f"Prompt-4 artifact {key} is not an object")
        normalized[key] = dict(raw)

    registry = _validate_file_artifact(
        normalized["decision_policy_registry"], "decision-policy registry"
    )
    registry_value = read_json(Path(str(registry["path"])))
    validate_development_policy_registry(registry_value)
    frozen = _validate_frozen_configs(
        normalized["frozen_pipeline_configs"], policy_registry=registry_value
    )
    extended = _validate_file_artifact(normalized["extended_set"], "extended set")
    _validate_extended_set(Path(str(extended["path"])))
    summary = _validate_file_artifact(
        normalized["development_summary"], "development summary"
    )
    _validate_development_summary(Path(str(summary["path"])))

    core = {
        "schema_version": "full-pipeline-core-evaluation-authorization.v1",
        **scope_fields(),
        "status": "AUTHORIZED_NOT_STARTED",
        "prompt4_completion_marker": PROMPT4_COMPLETION_MARKER,
        "prompt4_marker_path": str(marker_file),
        "prompt4_marker_sha256": sha256_file(marker_file),
        "amendment_path": str(amendment_file),
        "amendment_sha256": sha256_file(amendment_file),
        "program_state_path": str(state_file),
        "program_state_sha256": sha256_file(state_file),
        "deployment_steering": deployment_steering_reference,
        "frozen_pipeline_configs": frozen,
        "decision_policy_registry": registry,
        "extended_set": extended,
        "development_summary": summary,
        "pipeline_count": 18,
        "held_out_predictions_inspected": False,
        "held_out_inference_started": False,
        "retuning_allowed": False,
    }
    return {
        **core,
        "authorization_identity_sha256": sha256_bytes(canonical_json_bytes(core)),
    }


def validate_authorization(
    value: Mapping[str, object],
    *,
    marker_path: Path | str,
    amendment_path: Path | str = DEFAULT_AMENDMENT,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    pi_deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
) -> dict[str, object]:
    current = validate_prompt4_freeze(
        marker_path,
        amendment_path=amendment_path,
        program_state_path=program_state_path,
        pi_deployment_steering_path=pi_deployment_steering_path,
    )
    if canonical_json_bytes(value) != canonical_json_bytes(current):
        raise CoreEvaluationError(
            "Prompt-5 authorization differs because a bound Prompt-4/program artifact changed"
        )
    return current


def _validate_amendment(value: Mapping[str, object]) -> None:
    _require_equal(value, "amendment_id", SCOPE_ID)
    scope = value.get("scope")
    storage = value.get("storage_policy")
    labels = value.get("required_artifact_labels")
    markers = value.get("completion_markers")
    if not all(isinstance(item, Mapping) for item in (scope, storage, labels, markers)):
        raise CoreEvaluationError("eight-day amendment sections are missing")
    assert isinstance(scope, Mapping)
    assert isinstance(storage, Mapping)
    assert isinstance(labels, Mapping)
    assert isinstance(markers, Mapping)
    if (
        scope.get("scope_class") != SCOPE_CLASS
        or int(scope.get("total_wall_target_hours") or 0) != 192
    ):
        raise CoreEvaluationError("eight-day scope identity/budget differs")
    if (
        storage.get("allowed_drive") != "C:\\"
        or storage.get("other_drives_allowed") is not False
    ):
        raise CoreEvaluationError("amendment no longer enforces C:-only storage")
    if int(storage.get("minimum_free_space_reserve_gib") or 0) != 35:
        raise CoreEvaluationError("amendment 35-GiB reserve differs")
    _require_scope(labels, label="amendment artifact labels")
    if markers.get("prompt_4") != PROMPT4_COMPLETION_MARKER:
        raise CoreEvaluationError("amendment Prompt-4 marker differs")


def _validate_program_state(value: Mapping[str, object]) -> None:
    if value.get("status") != PROMPT4_COMPLETION_MARKER:
        raise CoreEvaluationError(
            "PROGRAM_STATE has not reached the bounded Prompt-4 completion marker"
        )
    if int(value.get("current_prompt_index") or -1) != 4:
        raise CoreEvaluationError("PROGRAM_STATE current_prompt_index is not 4")
    remaining = [int(item) for item in value.get("remaining_prompt_indices", [])]
    if remaining != [5, 6, 7, 8]:
        raise CoreEvaluationError(
            f"PROGRAM_STATE remaining prompts differ: {remaining}"
        )
    completion = value.get("completion_state")
    if (
        not isinstance(completion, Mapping)
        or completion.get("prompt_4") != PROMPT4_COMPLETION_MARKER
    ):
        raise CoreEvaluationError("PROGRAM_STATE completion_state.prompt_4 differs")
    for field in HELDOUT_FALSE_FIELDS:
        if field in value and value.get(field) is not False:
            raise CoreEvaluationError(
                f"PROGRAM_STATE firewall field is not false: {field}"
            )


def _validate_frozen_configs(
    raw: Mapping[str, object],
    *,
    policy_registry: Mapping[str, object],
) -> dict[str, object]:
    """Prove that every frozen Prompt-4 configuration is what P5 will execute.

    Merely validating the YAML checksum is insufficient for an untouched
    held-out gate: a signed YAML could describe code or policies that the live
    worker no longer uses.  This validator therefore recomputes the complete
    live execution contract without opening evaluation material and rejects
    any difference before Prompt 5 prepares its held-out panel.
    """

    validate_development_policy_registry(policy_registry)
    root = ensure_c_drive(
        str(raw.get("path") or ""), label="frozen pipeline configs", must_exist=True
    )
    if not root.is_dir():
        raise CoreEvaluationError(
            f"frozen pipeline config path is not a directory: {root}"
        )
    checksums_path = ensure_c_drive(
        str(raw.get("checksums_path") or root / "checksums.json"),
        label="frozen config checksums",
        must_exist=True,
    )
    if checksums_path.parent != root:
        raise CoreEvaluationError("frozen config checksums must be inside config root")
    expected_checksums_sha = str(raw.get("checksums_sha256") or "").casefold()
    actual_checksums_sha = sha256_file(checksums_path)
    if expected_checksums_sha != actual_checksums_sha:
        raise CoreEvaluationError(
            "Prompt-4 frozen-config checksum-document hash differs"
        )
    entries = verify_checksum_document(root, checksums_path)
    resolved = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    expected_ids = set(resolved.pipeline_ids)
    yaml_paths = sorted(root.glob("*.yaml"))
    if len(yaml_paths) != 18 or {path.stem for path in yaml_paths} != expected_ids:
        raise CoreEvaluationError(
            "frozen config root does not contain exact all-18 YAMLs"
        )
    if int(raw.get("pipeline_count") or 0) != 18:
        raise CoreEvaluationError("Prompt-4 marker frozen pipeline_count is not 18")
    matrix_doc = _yaml_mapping(MATRIX_PATH, label="full-pipeline matrix")
    runtime_doc = _yaml_mapping(RUNTIME_CONFIG_PATH, label="full-pipeline runtime")
    live_code = _result_affecting_code_identity(EVALUATION_ROOT)
    freeze_ids: dict[str, str] = {}
    shared_protocol_id: str | None = None
    shared_development_protocol_sha256: str | None = None
    shared_development_result_sha256: str | None = None
    shared_anchor_qualification: bytes | None = None
    for path in yaml_paths:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(value, Mapping):
            raise CoreEvaluationError(f"frozen pipeline YAML is not an object: {path}")
        if value.get("pipeline_id") != path.stem:
            raise CoreEvaluationError(f"frozen pipeline ID differs: {path}")
        unsigned = dict(value)
        identity = str(unsigned.pop("freeze_identity_sha256", "")).casefold()
        if identity != sha256_bytes(canonical_json_bytes(unsigned)):
            raise CoreEvaluationError(f"frozen pipeline identity differs: {path}")
        selection = resolved.resolve(path.stem)
        if value.get("pipeline_config_sha256_before_development_freeze") != (
            selection.pipeline_config_sha256
        ):
            raise CoreEvaluationError(
                f"matrix/frozen pipeline identity differs: {path}"
            )
        if value.get("evaluation_material_inspected") is not False:
            raise CoreEvaluationError(
                f"frozen config lacks evaluation firewall: {path}"
            )
        _validate_frozen_execution_contract(
            value,
            pipeline_id=path.stem,
            resolved=resolved,
            matrix_doc=matrix_doc,
            runtime_doc=runtime_doc,
            policy_registry=policy_registry,
            live_code=live_code,
        )
        shared_protocol_id = _same_shared_value(
            shared_protocol_id,
            str(value.get("protocol_id") or ""),
            label="protocol_id",
            pipeline_id=path.stem,
        )
        shared_development_protocol_sha256 = _same_shared_value(
            shared_development_protocol_sha256,
            _sha256_text(
                value.get("development_protocol_sha256"),
                f"{path.stem} development protocol SHA-256",
            ),
            label="development_protocol_sha256",
            pipeline_id=path.stem,
        )
        shared_development_result_sha256 = _same_shared_value(
            shared_development_result_sha256,
            _sha256_text(
                value.get("development_result_set_sha256"),
                f"{path.stem} development result-set SHA-256",
            ),
            label="development_result_set_sha256",
            pipeline_id=path.stem,
        )
        qualification = value.get("runtime_anchor_qualification")
        assert isinstance(qualification, Mapping)
        qualification_bytes = canonical_json_bytes(dict(qualification))
        if shared_anchor_qualification is None:
            shared_anchor_qualification = qualification_bytes
        elif shared_anchor_qualification != qualification_bytes:
            raise CoreEvaluationError(
                "frozen runtime-anchor qualification differs across pipelines"
            )
        freeze_ids[path.stem] = identity
    declared_sha = str(raw.get("sha256") or actual_checksums_sha).casefold()
    if declared_sha not in {
        actual_checksums_sha,
        sha256_bytes(canonical_json_bytes(freeze_ids)),
    }:
        raise CoreEvaluationError("frozen config artifact sha256 is unrecognized")
    return {
        "path": str(root),
        "checksums_path": str(checksums_path),
        "checksums_sha256": actual_checksums_sha,
        "pipeline_count": 18,
        "pipeline_freeze_identity_sha256s": freeze_ids,
        "verified_checksum_entry_count": len(entries),
        "live_result_affecting_code_sha256": str(live_code["sha256"]),
        "execution_contract_validation": "EXACT_LIVE_MATCH",
    }


def _validate_frozen_execution_contract(
    value: Mapping[str, object],
    *,
    pipeline_id: str,
    resolved: FullPipelineMatrix,
    matrix_doc: Mapping[str, object],
    runtime_doc: Mapping[str, object],
    policy_registry: Mapping[str, object],
    live_code: Mapping[str, object],
) -> None:
    """Fail closed if a signed freeze differs from the current worker contract."""

    required_scalars = {
        "schema_version": PIPELINE_FREEZE_SCHEMA_VERSION,
        "status": "IMMUTABLE_DEVELOPMENT_FREEZE",
        "pipeline_id": pipeline_id,
        "evaluation_material_inspected": False,
        "evaluation_retuning_allowed": False,
        "production_winner_selected": False,
    }
    for key, expected in required_scalars.items():
        if value.get(key) != expected:
            raise CoreEvaluationError(
                f"frozen execution contract {pipeline_id}.{key} differs"
            )
    if not str(value.get("protocol_id") or "").strip():
        raise CoreEvaluationError(
            f"frozen execution contract {pipeline_id}.protocol_id is empty"
        )

    selection = resolved.resolve(pipeline_id)
    registry_entries = {
        str(row.get("pipeline_id") or ""): dict(row)
        for row in policy_registry.get("entries", [])
        if isinstance(row, Mapping)
    }
    if selection.hybrid_label in FROZEN_ANCHOR_LABELS:
        identity_policy: Mapping[str, object] = resolve_decision_policy_contract(
            pipeline_id, realized_gallery_size=10
        )
    else:
        try:
            registry_entry = registry_entries[pipeline_id]
        except KeyError as exc:
            raise CoreEvaluationError(
                f"frozen challenger policy is missing for {pipeline_id}"
            ) from exc
        identity_policy = {
            **registry_entry,
            "decision_policy_sha256": registry_entry["calibration_identity_sha256"],
            "calibration_protocol_id": policy_registry["protocol_id"],
            "calibration_result_sha256": registry_entry["calibration_identity_sha256"],
            "target_fpir": 0.01,
            "threshold_scope": "exact_pipeline_and_frozen_gallery_request",
        }

    incremental = runtime_doc.get("incremental_diarization")
    if not isinstance(incremental, Mapping):
        raise CoreEvaluationError("live incremental-diarization runtime is missing")
    policies = matrix_doc.get("policies")
    if not isinstance(policies, Mapping) or not isinstance(
        policies.get("streaming"), Mapping
    ):
        raise CoreEvaluationError("live streaming policy is missing")
    shared_segmentation = matrix_doc.get("shared_segmentation_asset")
    if not isinstance(shared_segmentation, Mapping):
        raise CoreEvaluationError("live shared segmentation asset is missing")
    asr_runtime = runtime_doc.get("asr")
    if not isinstance(asr_runtime, Mapping):
        raise CoreEvaluationError("live ASR runtime is missing")

    expected_fields: dict[str, object] = {
        "aliases": {
            "asr": selection.asr_alias,
            "anonymous_diarization": selection.diarization_alias,
            "identity": selection.identity_alias,
            "hybrid": selection.hybrid_label,
        },
        "asr": {
            "component": dict(selection.asr),
            "runtime": dict(asr_runtime),
            "streaming_policy": dict(policies["streaming"]),
        },
        "segmentation": {
            "shared_asset": dict(shared_segmentation),
            "runtime": {
                key: item
                for key, item in incremental.items()
                if key
                in {
                    "policy_id",
                    "rolling_analysis_window_sec",
                    "rolling_step_sec",
                    "history_context_sec",
                    "algorithmic_lookahead_sec",
                    "flush_at_end_of_input",
                    "future_evidence_used",
                }
            },
        },
        "anonymous_diarization_and_clustering": {
            "component": dict(selection.diarization),
            "runtime": dict(incremental),
        },
        "identity_policy": dict(identity_policy),
        "enrollment_policy": {
            **dict(selection.enrollment_policy),
            "clip_materialization": "first_three_full_reserved_clips",
            "audio_padding": False,
            "target_duration_is_selection_guidance_not_trimming": True,
        },
        # The current worker implements the baseline policy in result-affecting
        # code. A development-tuned alternative must be consumed explicitly by
        # the runtime before it may pass this held-out firewall.
        "transcript_alignment_and_buffering": baseline_alignment_buffering_policy(),
        "ui_label_policy": FROZEN_UI_LABEL_POLICY,
        "model_assets": _model_asset_identity(matrix_doc, selection),
        "source_hashes": {
            "matrix_sha256": sha256_file(MATRIX_PATH),
            "runtime_config_sha256": sha256_file(RUNTIME_CONFIG_PATH),
            "development_policy_registry_sha256": policy_registry[
                "registry_identity_sha256"
            ],
            "frozen_hybrid_protocol_id": FROZEN_HYBRID_PROTOCOL_ID,
            "frozen_hybrid_selection_sha256": FROZEN_HYBRID_SELECTION_SHA256,
        },
        "result_affecting_code": dict(live_code),
    }
    for key, expected in expected_fields.items():
        actual = value.get(key)
        if actual != expected:
            raise CoreEvaluationError(
                f"frozen execution contract {pipeline_id}.{key} does not match "
                "the live held-out worker contract"
            )

    qualification = value.get("runtime_anchor_qualification")
    if not isinstance(qualification, Mapping):
        raise CoreEvaluationError(
            f"frozen execution contract {pipeline_id}.runtime_anchor_qualification "
            "is missing"
        )
    try:
        _validate_anchor_runtime_qualification(qualification)
    except Exception as exc:
        raise CoreEvaluationError(
            f"frozen execution contract {pipeline_id} has invalid anchor qualification: {exc}"
        ) from exc


def _yaml_mapping(path: Path, *, label: str) -> dict[str, object]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise CoreEvaluationError(f"{label} root is not an object")
    return value


def _sha256_text(value: object, label: str) -> str:
    text = str(value or "").casefold()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise CoreEvaluationError(f"{label} must be a SHA-256 hex digest")
    return text


def _same_shared_value(
    current: str | None,
    candidate: str,
    *,
    label: str,
    pipeline_id: str,
) -> str:
    if not candidate:
        raise CoreEvaluationError(f"frozen {pipeline_id}.{label} is empty")
    if current is not None and current != candidate:
        raise CoreEvaluationError(f"frozen {label} differs across pipelines")
    return candidate


def _validate_file_artifact(raw: Mapping[str, object], label: str) -> dict[str, object]:
    path = ensure_c_drive(str(raw.get("path") or ""), label=label, must_exist=True)
    if not path.is_file():
        raise CoreEvaluationError(f"{label} is not a file: {path}")
    expected = str(raw.get("sha256") or "").casefold()
    actual = sha256_file(path)
    if expected != actual:
        raise CoreEvaluationError(f"Prompt-4 marker {label} hash differs")
    return {"path": str(path), "sha256": actual}


def _validate_extended_set(path: Path) -> None:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, Mapping):
        raise CoreEvaluationError("extended_set.yaml is not an object")
    mandatory = set(str(item) for item in value.get("mandatory_pipeline_ids", []))
    expected = {
        "fullpipe_v1_ao_dr_ir",
        "fullpipe_v1_ag_dr_ir",
        "fullpipe_v1_ao_dw_ir",
        "fullpipe_v1_ag_dw_ir",
        "fullpipe_v1_ao_dr_ie",
        "fullpipe_v1_ag_dr_ie",
    }
    if mandatory != expected:
        raise CoreEvaluationError("extended set mandatory frozen anchors differ")
    extended = [str(item) for item in value.get("extended_pipeline_ids", [])]
    if not expected.issubset(extended) or len(extended) > 8:
        raise CoreEvaluationError("extended set is outside the six-plus-two contract")
    if value.get("evaluation_material_inspected") is not False:
        raise CoreEvaluationError("extended set lacks development-only firewall")


def _validate_development_summary(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = set(FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH).pipeline_ids)
    observed = {str(row.get("pipeline_id") or "") for row in rows}
    if len(rows) != 18 or observed != expected:
        raise CoreEvaluationError(
            "development summary does not contain exact all-18 rows"
        )


def _require_scope(value: Mapping[str, object], *, label: str) -> None:
    if value.get("scope_id") != SCOPE_ID or value.get("scope_class") != SCOPE_CLASS:
        raise CoreEvaluationError(f"{label} scope identity differs")
    if value.get("original_full_scope_complete") is not ORIGINAL_FULL_SCOPE_COMPLETE:
        raise CoreEvaluationError(f"{label} misstates original full-scope completion")


def _require_equal(value: Mapping[str, object], key: str, expected: object) -> None:
    if value.get(key) != expected:
        raise CoreEvaluationError(
            f"{key} differs: expected {expected!r}, got {value.get(key)!r}"
        )
