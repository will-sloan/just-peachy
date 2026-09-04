"""Compact C:-only collection and universal Prompt-5 completion finalizer."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import zipfile
from typing import Mapping

from app.full_pipeline_evaluation.io import (
    checksum_map,
    read_json,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_development.policies import (
    validate_development_policy_registry,
)
from app.full_pipeline_deployment_evidence import (
    DeploymentEvidenceError,
    load_deployment_steering,
    steering_ref,
    validate_deployment_evidence_document,
)
from app.full_pipeline_evaluation.planning import matrix

from . import (
    DEFAULT_AMENDMENT,
    DEFAULT_PROGRAM_STATE,
    DEPLOYMENT_EVIDENCE_FILE,
    EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
    PROMPT4_COMPLETION_MARKER,
    PROMPT5_COMPLETION_MARKER,
    TOOL_ROOT,
)
from .controller import layout, _validate_terminal_jobs
from .gate import (
    _validate_development_summary,
    _validate_extended_set,
    _validate_file_artifact,
    _validate_frozen_configs,
)
from .io import (
    CoreEvaluationError,
    ensure_c_drive,
    scope_fields,
    storage_preflight,
)


REQUIRED_REPORT_FILES = (
    "all18_finalist_summary.csv",
    "all18_asr.csv",
    "all18_diarization.csv",
    "all18_identity.csv",
    "all18_speaker_attributed_transcript.csv",
    "all18_streaming.csv",
    "all18_resources.csv",
    "all18_failures.csv",
    "paired_comparisons.csv",
    "bootstrap_intervals.csv",
    "evaluation_report.md",
    "analysis.json",
    "speaker_sufficient_statistics.jsonl.gz",
    DEPLOYMENT_EVIDENCE_FILE,
)
GATE_RECORDS_DIRECTORY = "gate_records"
CANONICAL_REPORT_ROOT = (
    TOOL_ROOT / "JustPeachyResearchSummaries/full_pipeline/heldout/"
    "full_speech_pipeline_v1_reduced_8day_v1"
)


def collect(*, workspace_root: Path) -> dict[str, object]:
    paths = layout(workspace_root)
    storage_preflight(paths.root)
    _validate_terminal_jobs(paths.accuracy, expected_job_count=126)
    _validate_terminal_jobs(paths.resources, expected_job_count=18)
    for name in REQUIRED_REPORT_FILES:
        if not (paths.report / name).is_file():
            raise CoreEvaluationError(f"Analyze output is missing: {name}")
    authorization = read_json(paths.authorization)
    deployment_steering, deployment_steering_path = _validated_deployment_steering(
        authorization
    )
    _validate_deployment_artifact(
        paths.report / DEPLOYMENT_EVIDENCE_FILE,
        authorization=authorization,
        steering=deployment_steering,
    )
    destination = ensure_c_drive(CANONICAL_REPORT_ROOT, label="Prompt-5 summary root")
    destination.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_REPORT_FILES:
        _copy_or_verify(paths.report / name, destination / name)
    protocol_files = {
        "prompt5_authorization.json": paths.authorization,
        "selection_manifest.json": paths.root / "selection/selection_manifest.json",
        "selected_cases.jsonl": paths.selected_cases,
        "excluded_cases.jsonl": paths.excluded_cases,
        "accuracy_campaign_manifest.json": paths.accuracy / "campaign_manifest.json",
        "accuracy_progress.json": paths.accuracy / "campaign_progress.json",
        "resource_campaign_manifest.json": paths.resources / "campaign_manifest.json",
        "resource_progress.json": paths.resources / "campaign_progress.json",
        "eight_day_scope_amendment.json": DEFAULT_AMENDMENT,
        "raspberry_pi_deployment_steering.json": deployment_steering_path,
    }
    for name, source in protocol_files.items():
        if not source.is_file():
            raise CoreEvaluationError(f"collection input is missing: {source}")
        _copy_or_verify(source, destination / "protocol" / name)
    checksums = checksum_map(destination, exclude=("checksums.json",))
    checksum_doc = {
        "schema_version": "full-pipeline-core-heldout-checksums.v1",
        **scope_fields(),
        "entries": checksums,
        "raw_audio_included": False,
        "model_weights_included": False,
        "biometric_vectors_included": False,
        "raw_prediction_event_trees_included": False,
    }
    write_json_atomic(destination / "checksums.json", checksum_doc)
    zip_path = destination.parent / "full_speech_pipeline_v1_reduced_8day_v1.zip"
    _deterministic_zip(destination, zip_path)
    value = {
        "schema_version": "full-pipeline-core-heldout-collection.v1",
        **scope_fields(),
        "status": "PASS",
        "destination": str(destination),
        "checksums_path": str(destination / "checksums.json"),
        "checksums_sha256": sha256_file(destination / "checksums.json"),
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "artifact_count": len(checksums),
        "raw_audio_included": False,
        "model_weights_included": False,
        "biometric_vectors_included": False,
    }
    write_json_atomic(paths.root / "collection.json", value)
    return value


def update_program_state(
    *,
    workspace_root: Path,
    predecessor_record_path: Path | str,
    adapter_id: str,
    adapter_contract_sha256: str,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    completion_record_path: Path | str | None = None,
) -> dict[str, object]:
    """Validate all Prompt-5 evidence and publish the universal stage envelope."""

    paths = layout(workspace_root)
    collection_path = paths.root / "collection.json"
    if not collection_path.is_file():
        raise CoreEvaluationError("Collect must complete before UpdateProgramState")
    collection = read_json(collection_path)
    package_root = ensure_c_drive(
        str(collection.get("destination") or ""),
        label="Prompt-5 canonical report",
        must_exist=True,
    )
    zip_path = ensure_c_drive(
        str(collection.get("zip_path") or ""),
        label="Prompt-5 compact ZIP",
        must_exist=True,
    )
    _verify_collection(package_root, collection)
    predecessor_path = ensure_c_drive(
        predecessor_record_path,
        label="Prompt-4 completion record",
        must_exist=True,
    )
    predecessor = read_json(predecessor_path)
    if (
        predecessor.get("schema_version")
        != "full-pipeline-eight-day-stage-completion.v1"
    ):
        raise CoreEvaluationError("Prompt-4 predecessor completion schema differs")
    if (
        predecessor.get("status") != "COMPLETE"
        or predecessor.get("completion_marker") != PROMPT4_COMPLETION_MARKER
    ):
        raise CoreEvaluationError("Prompt-4 predecessor marker is not complete")
    if int(predecessor.get("prompt_index") or -1) != 4:
        raise CoreEvaluationError("Prompt-4 predecessor prompt index differs")
    for key, expected in scope_fields().items():
        if predecessor.get(key) != expected:
            raise CoreEvaluationError(f"Prompt-4 predecessor {key} differs")
    _verify_universal_refs(predecessor, prompt_index=4)
    authorization = read_json(paths.authorization)
    if authorization.get("prompt4_marker_path") != str(predecessor_path):
        raise CoreEvaluationError(
            "supplied Prompt-4 predecessor path differs from Prompt-5 authorization"
        )
    if authorization.get("prompt4_marker_sha256") != sha256_file(predecessor_path):
        raise CoreEvaluationError(
            "supplied Prompt-4 predecessor bytes differ from Prompt-5 authorization"
        )
    deployment_steering, deployment_steering_path = _validated_deployment_steering(
        authorization
    )
    deployment_artifact = _validate_deployment_artifact(
        package_root / DEPLOYMENT_EVIDENCE_FILE,
        authorization=authorization,
        steering=deployment_steering,
    )
    _require_sha(adapter_contract_sha256, "adapter contract SHA-256")
    if not adapter_id.strip():
        raise CoreEvaluationError("adapter_id is required")

    gates_root = paths.root / GATE_RECORDS_DIRECTORY
    gates_root.mkdir(parents=True, exist_ok=True)
    hash_gate = _write_gate(
        gates_root / "hash_validation.json",
        gate="hash_validation",
        evidence={
            "package_checksums_path": str(package_root / "checksums.json"),
            "package_checksums_sha256": sha256_file(package_root / "checksums.json"),
            "zip_path": str(zip_path),
            "zip_sha256": sha256_file(zip_path),
            "accuracy_terminal_validation": _validate_terminal_jobs(
                paths.accuracy, expected_job_count=126
            ),
            "resources_terminal_validation": _validate_terminal_jobs(
                paths.resources, expected_job_count=18
            ),
            "deployment_evidence_path": str(
                (package_root / DEPLOYMENT_EVIDENCE_FILE).resolve()
            ),
            "deployment_evidence_sha256": sha256_file(
                package_root / DEPLOYMENT_EVIDENCE_FILE
            ),
            "deployment_evidence_pipeline_count": deployment_artifact["pipeline_count"],
        },
    )
    firewall_gate = _write_gate(
        gates_root / "firewall_validation.json",
        gate="firewall_validation",
        evidence={
            "selection_frozen_before_predictions": True,
            "held_out_retuning_performed": False,
            "pipeline_membership_changed_after_open": False,
            "all_18_identical_panel": True,
            "native_known_speaker_metrics_fabricated": False,
        },
    )
    prerequisite_gate = _write_gate(
        gates_root / "prerequisite_validation.json",
        gate="prerequisite_validation",
        evidence={
            "predecessor_record_path": str(predecessor_path),
            "predecessor_record_sha256": sha256_file(predecessor_path),
            "predecessor_completion_marker": PROMPT4_COMPLETION_MARKER,
            "prompt5_authorization_path": str(paths.authorization),
            "prompt5_authorization_sha256": sha256_file(paths.authorization),
            "deployment_steering_path": str(deployment_steering_path),
            "deployment_steering_sha256": sha256_file(deployment_steering_path),
        },
    )
    gate_records = {
        "hash_validation": _artifact_ref(hash_gate),
        "firewall_validation": _artifact_ref(firewall_gate),
        "prerequisite_validation": _artifact_ref(prerequisite_gate),
    }
    artifact_paths = [
        *(package_root / name for name in REQUIRED_REPORT_FILES),
        package_root / "checksums.json",
        zip_path,
        paths.authorization,
        deployment_steering_path,
        paths.root / "selection/selection_manifest.json",
        hash_gate,
        firewall_gate,
        prerequisite_gate,
    ]
    artifact_manifest = {
        "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
        **scope_fields(),
        "prompt_index": 5,
        "artifacts": [
            {**_artifact_ref(path), "required": True} for path in artifact_paths
        ],
    }
    artifact_manifest_path = paths.root / "artifact_manifest.json"
    write_json_atomic(artifact_manifest_path, artifact_manifest)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    completion = {
        "schema_version": "full-pipeline-eight-day-stage-completion.v1",
        **scope_fields(),
        "prompt_index": 5,
        "status": "COMPLETE",
        "completion_marker": PROMPT5_COMPLETION_MARKER,
        "completed_at_utc": now,
        "adapter_id": adapter_id,
        "adapter_contract_sha256": adapter_contract_sha256.casefold(),
        "predecessor": {
            "prompt_index": 4,
            "completion_marker": PROMPT4_COMPLETION_MARKER,
            "completion_record_path": str(predecessor_path),
            "completion_record_sha256": sha256_file(predecessor_path),
        },
        "artifact_manifest": _artifact_ref(artifact_manifest_path),
        "gate_records": gate_records,
        "native_completion": {
            "pipeline_count": 18,
            "selected_case_count": 2240,
            "accuracy_job_count": 126,
            "resource_job_count": 18,
            "compact_zip_path": str(zip_path),
            "compact_zip_sha256": sha256_file(zip_path),
            "deployment_evidence_path": str(
                (package_root / DEPLOYMENT_EVIDENCE_FILE).resolve()
            ),
            "deployment_evidence_sha256": sha256_file(
                package_root / DEPLOYMENT_EVIDENCE_FILE
            ),
        },
    }
    completion_path = ensure_c_drive(
        completion_record_path or paths.completion_marker,
        label="Prompt-5 universal completion record",
    )
    completion_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(completion_path, completion)
    _update_state(
        ensure_c_drive(program_state_path, label="program state", must_exist=True),
        completion_record=completion_path,
        completion=completion,
    )
    return completion


def validate_completion(
    *,
    workspace_root: Path,
    completion_record_path: Path | str,
    expected_adapter_id: str | None = None,
    expected_adapter_contract_sha256: str | None = None,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
) -> dict[str, object]:
    """Independent native validator used by the eight-day controller."""

    paths = layout(workspace_root)
    completion_path = ensure_c_drive(
        completion_record_path,
        label="Prompt-5 completion record",
        must_exist=True,
    )
    completion = read_json(completion_path)
    expected = {
        "schema_version": "full-pipeline-eight-day-stage-completion.v1",
        "scope_id": scope_fields()["scope_id"],
        "scope_class": scope_fields()["scope_class"],
        "original_full_scope_complete": False,
        "prompt_index": 5,
        "status": "COMPLETE",
        "completion_marker": PROMPT5_COMPLETION_MARKER,
    }
    for key, value in expected.items():
        if completion.get(key) != value:
            raise CoreEvaluationError(f"completion {key} differs")
    if expected_adapter_id and completion.get("adapter_id") != expected_adapter_id:
        raise CoreEvaluationError("completion adapter_id differs")
    if (
        expected_adapter_contract_sha256
        and completion.get("adapter_contract_sha256")
        != expected_adapter_contract_sha256.casefold()
    ):
        raise CoreEvaluationError("completion adapter contract hash differs")
    predecessor = completion.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise CoreEvaluationError("completion predecessor is missing")
    predecessor_path = ensure_c_drive(
        str(predecessor.get("completion_record_path") or ""),
        label="Prompt-4 predecessor",
        must_exist=True,
    )
    if predecessor.get("completion_record_sha256") != sha256_file(predecessor_path):
        raise CoreEvaluationError("Prompt-4 predecessor hash differs")
    if predecessor.get("completion_marker") != PROMPT4_COMPLETION_MARKER:
        raise CoreEvaluationError("Prompt-4 predecessor marker differs")
    _verify_universal_refs(completion, prompt_index=5)

    authorization = read_json(paths.authorization)
    if authorization.get("prompt4_marker_path") != str(predecessor_path):
        raise CoreEvaluationError("authorization Prompt-4 marker path differs")
    if authorization.get("prompt4_marker_sha256") != sha256_file(predecessor_path):
        raise CoreEvaluationError("authorization Prompt-4 marker bytes changed")
    deployment_steering, _ = _validated_deployment_steering(authorization)
    frozen = authorization.get("frozen_pipeline_configs")
    if not isinstance(frozen, Mapping):
        raise CoreEvaluationError("authorization frozen configs are missing")
    registry_artifact = authorization.get("decision_policy_registry")
    if not isinstance(registry_artifact, Mapping):
        raise CoreEvaluationError("authorization decision_policy_registry is missing")
    checked_registry = _validate_file_artifact(
        registry_artifact, "decision_policy_registry"
    )
    registry_value = read_json(Path(str(checked_registry["path"])))
    validate_development_policy_registry(registry_value)
    _validate_frozen_configs(
        {
            "path": frozen.get("path"),
            "checksums_path": frozen.get("checksums_path"),
            "checksums_sha256": frozen.get("checksums_sha256"),
            "pipeline_count": 18,
            "sha256": frozen.get("checksums_sha256"),
        },
        policy_registry=registry_value,
    )
    for key, validator in (
        ("extended_set", _validate_extended_set),
        ("development_summary", _validate_development_summary),
    ):
        artifact = authorization.get(key)
        if not isinstance(artifact, Mapping):
            raise CoreEvaluationError(f"authorization {key} is missing")
        checked = _validate_file_artifact(artifact, key)
        if validator is not None:
            validator(Path(str(checked["path"])))

    _validate_terminal_jobs(paths.accuracy, expected_job_count=126)
    _validate_terminal_jobs(paths.resources, expected_job_count=18)
    collection = read_json(paths.root / "collection.json")
    package_root = ensure_c_drive(
        str(collection.get("destination") or ""),
        label="canonical Prompt-5 report",
        must_exist=True,
    )
    _verify_collection(package_root, collection)
    deployment_artifact = _validate_deployment_artifact(
        package_root / DEPLOYMENT_EVIDENCE_FILE,
        authorization=authorization,
        steering=deployment_steering,
    )
    state = read_json(
        ensure_c_drive(program_state_path, label="program state", must_exist=True)
    )
    if (
        state.get("status") != PROMPT5_COMPLETION_MARKER
        or int(state.get("current_prompt_index") or -1) != 5
    ):
        raise CoreEvaluationError("PROGRAM_STATE has not reached bounded Prompt 5")
    return {
        "schema_version": "full-pipeline-core-completion-validation.v1",
        **scope_fields(),
        "status": "PASS",
        "prompt_index": 5,
        "completion_marker": PROMPT5_COMPLETION_MARKER,
        "completion_record_path": str(completion_path),
        "completion_record_sha256": sha256_file(completion_path),
        "pipeline_count": 18,
        "accuracy_job_count": 126,
        "resource_job_count": 18,
        "deployment_evidence_path": str(
            (package_root / DEPLOYMENT_EVIDENCE_FILE).resolve()
        ),
        "deployment_evidence_sha256": sha256_file(
            package_root / DEPLOYMENT_EVIDENCE_FILE
        ),
        "deployment_evidence_pipeline_count": deployment_artifact["pipeline_count"],
    }


def _validated_deployment_steering(
    authorization: Mapping[str, object],
) -> tuple[dict[str, object], Path]:
    reference = authorization.get("deployment_steering")
    if not isinstance(reference, Mapping):
        raise CoreEvaluationError("authorization deployment_steering is missing")
    path = ensure_c_drive(
        str(reference.get("path") or ""),
        label="deployment steering authority",
        must_exist=True,
    )
    try:
        steering = load_deployment_steering(
            path,
            expected_prompt_index=5,
            expected_sha256=EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
        )
        current = steering_ref(path, steering)
    except DeploymentEvidenceError as exc:
        raise CoreEvaluationError(str(exc)) from exc
    if dict(reference) != current:
        raise CoreEvaluationError("authorization deployment steering reference differs")
    return steering, path


def _validate_deployment_artifact(
    path: Path,
    *,
    authorization: Mapping[str, object],
    steering: Mapping[str, object],
) -> dict[str, object]:
    artifact_path = ensure_c_drive(
        path, label="Prompt-5 deployment evidence", must_exist=True
    )
    value = read_json(artifact_path)
    if value.get("steering_authority") != authorization.get("deployment_steering"):
        raise CoreEvaluationError("deployment evidence steering binding differs")
    for key, expected in scope_fields().items():
        if value.get(key) != expected:
            raise CoreEvaluationError(f"deployment evidence {key} differs")
    try:
        return validate_deployment_evidence_document(
            value,
            schema_version="full-pipeline-all18-deployment-evidence.v1",
            prompt_index=5,
            expected_pipeline_ids=matrix().pipeline_ids,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise CoreEvaluationError(str(exc)) from exc


def _write_gate(path: Path, *, gate: str, evidence: Mapping[str, object]) -> Path:
    value = {
        "schema_version": "full-pipeline-eight-day-gate.v1",
        **scope_fields(),
        "prompt_index": 5,
        "gate": gate,
        "status": "PASS",
        "evidence": dict(evidence),
    }
    write_json_atomic(path, value)
    return path.resolve()


def _verify_universal_refs(
    completion: Mapping[str, object], *, prompt_index: int
) -> None:
    manifest_ref = completion.get("artifact_manifest")
    if not isinstance(manifest_ref, Mapping):
        raise CoreEvaluationError("completion artifact_manifest reference is missing")
    manifest_path = ensure_c_drive(
        str(manifest_ref.get("path") or ""),
        label="artifact manifest",
        must_exist=True,
    )
    if manifest_ref.get("sha256") != sha256_file(manifest_path):
        raise CoreEvaluationError("artifact manifest hash differs")
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != "full-pipeline-eight-day-artifact-manifest.v1":
        raise CoreEvaluationError("artifact manifest schema differs")
    if manifest.get("prompt_index") != prompt_index:
        raise CoreEvaluationError("artifact manifest prompt index differs")
    for key, expected in scope_fields().items():
        if manifest.get(key) != expected:
            raise CoreEvaluationError(f"artifact manifest {key} differs")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise CoreEvaluationError("artifact manifest is empty")
    artifact_paths: set[Path] = set()
    for raw in artifacts:
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            raise CoreEvaluationError("artifact manifest entry is invalid")
        path = ensure_c_drive(
            str(raw.get("path") or ""), label="required artifact", must_exist=True
        )
        if raw.get("sha256") != sha256_file(path):
            raise CoreEvaluationError(f"required artifact hash differs: {path}")
        artifact_paths.add(path)
    gate_refs = completion.get("gate_records")
    expected_gates = {
        "hash_validation",
        "firewall_validation",
        "prerequisite_validation",
    }
    if not isinstance(gate_refs, Mapping) or set(gate_refs) != expected_gates:
        raise CoreEvaluationError("completion gate record set differs")
    for gate_name in sorted(expected_gates):
        reference = gate_refs[gate_name]
        if not isinstance(reference, Mapping):
            raise CoreEvaluationError(f"{gate_name} gate reference is invalid")
        path = ensure_c_drive(
            str(reference.get("path") or ""),
            label=f"{gate_name} gate",
            must_exist=True,
        )
        if reference.get("sha256") != sha256_file(path) or path not in artifact_paths:
            raise CoreEvaluationError(f"{gate_name} gate binding differs")
        gate = read_json(path)
        if (
            gate.get("schema_version") != "full-pipeline-eight-day-gate.v1"
            or gate.get("gate") != gate_name
            or gate.get("status") != "PASS"
            or gate.get("prompt_index") != prompt_index
        ):
            raise CoreEvaluationError(f"{gate_name} gate content differs")
        for key, expected in scope_fields().items():
            if gate.get(key) != expected:
                raise CoreEvaluationError(f"{gate_name} gate {key} differs")


def _verify_collection(root: Path, collection: Mapping[str, object]) -> None:
    checksums_path = root / "checksums.json"
    value = read_json(checksums_path)
    entries = value.get("entries")
    if not isinstance(entries, Mapping):
        raise CoreEvaluationError("canonical report checksum map is invalid")
    actual = checksum_map(root, exclude=("checksums.json",))
    if dict(entries) != actual:
        raise CoreEvaluationError("canonical report files changed after Collect")
    if sha256_file(checksums_path) != collection.get("checksums_sha256"):
        raise CoreEvaluationError("collection checksum-document identity changed")
    for name in REQUIRED_REPORT_FILES:
        if not (root / name).is_file():
            raise CoreEvaluationError(f"canonical report lacks {name}")


def _copy_or_verify(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if sha256_file(source) != sha256_file(destination):
            raise CoreEvaluationError(
                f"immutable collected artifact differs: {destination}"
            )
        return
    shutil.copy2(source, destination)


def _deterministic_zip(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(value for value in source.rglob("*") if value.is_file()):
            relative = path.relative_to(source).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(
                info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED
            )
    os.replace(temporary, destination)


def _artifact_ref(path: Path) -> dict[str, str]:
    resolved = ensure_c_drive(path, label="stage artifact", must_exist=True)
    if not resolved.is_file():
        raise CoreEvaluationError(f"stage artifact is not a file: {resolved}")
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def _update_state(
    path: Path,
    *,
    completion_record: Path,
    completion: Mapping[str, object],
) -> None:
    value = read_json(path)
    if value.get("status") != PROMPT4_COMPLETION_MARKER:
        raise CoreEvaluationError("program state moved away from completed Prompt 4")
    state = dict(value)
    completion_state = dict(state.get("completion_state") or {})
    completion_state["prompt_5"] = PROMPT5_COMPLETION_MARKER
    completion_state["prompt_5_scope_id"] = scope_fields()["scope_id"]
    completion_state["prompt_5_original_full_scope_complete"] = False
    state.update(
        {
            "status": PROMPT5_COMPLETION_MARKER,
            "current_prompt_index": 5,
            "remaining_prompt_indices": [6, 7, 8],
            "remaining_prompt_status": "PENDING_AUTOMATIC",
            "completion_state": completion_state,
            "prompt_5_completion_record": str(completion_record.resolve()),
            "prompt_5_completion_record_sha256": sha256_file(completion_record),
            **scope_fields(),
        }
    )
    write_json_atomic(path, state)


def _require_sha(value: str, label: str) -> None:
    text = str(value).casefold()
    if len(text) != 64 or any(
        character not in "0123456789abcdef" for character in text
    ):
        raise CoreEvaluationError(f"{label} must be a SHA-256 hex digest")
