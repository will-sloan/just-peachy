"""Compact collection and universal completion for bounded Prompt 6."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Mapping, Sequence

from app.full_pipeline_evaluation.io import checksum_map, write_json_atomic

from . import (
    DEFAULT_PI_DEPLOYMENT_STEERING,
    DEFAULT_PROGRAM_STATE,
    DEFAULT_REPORT_ROOT,
    PI_DEPLOYMENT_STEERING_SHA256,
    PROMPT5_COMPLETION_MARKER,
    PROMPT6_COMPLETION_MARKER,
    scope_fields,
)
from .analysis import REQUIRED_REPORT_FILES
from .controller import layout, validate_terminal
from .deployment import validate_extended_deployment_evidence
from .execution import _validate_hardening_manifest
from .gate import (
    COMPLETION_SCHEMA,
    EXPECTED_GATE_NAMES,
    GATE_SCHEMA,
    MANIFEST_SCHEMA,
    _validate_extended_set,
    _validate_frozen_configs,
    validate_saved_authorization,
)
from .io import (
    ExtendedEvaluationError,
    artifact_ref,
    deterministic_zip,
    ensure_c_drive,
    read_json,
    sha256_file,
    storage_preflight,
    verify_ref,
)


PACKAGE_NAME = "full_speech_pipeline_extended_reduced_8day_v1.zip"


def collect(*, workspace_root: Path) -> dict[str, object]:
    """Copy only compact reports/protocol bindings into the canonical summary."""

    paths = layout(workspace_root)
    storage_preflight(paths.root)
    terminal = validate_terminal(workspace_root=paths.root)
    if terminal.get("status") != "PASS":
        raise ExtendedEvaluationError("Prompt-6 jobs are not terminal")
    for name in REQUIRED_REPORT_FILES:
        if not (paths.report / name).is_file():
            raise ExtendedEvaluationError(f"Analyze output is missing: {name}")
    _validate_analysis_evidence(paths.report / "analysis.json")
    _validate_deployment_evidence(
        paths.report,
        plan=read_json(paths.plan),
        authorization=read_json(paths.authorization),
    )
    destination = ensure_c_drive(DEFAULT_REPORT_ROOT, label="Prompt-6 report root")
    destination.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_REPORT_FILES:
        _copy_or_verify(paths.report / name, destination / name)
    protocol_files = {
        "prompt6_authorization.json": paths.authorization,
        "input_binding.json": paths.input_binding,
        "bounded_plan.json": paths.plan,
        "selection_manifest.json": paths.selection_manifest,
        "excluded_cases.jsonl": paths.excluded_cases,
        "hardening_input_manifest.json": paths.hardening_manifest,
    }
    for name, source in protocol_files.items():
        if not source.is_file():
            raise ExtendedEvaluationError(f"collection input is missing: {source}")
        _copy_or_verify(source, destination / "protocol" / name)
    checksums = {
        "schema_version": "full-pipeline-extended-checksums.v1",
        **scope_fields(),
        "entries": checksum_map(destination, exclude=("checksums.json",)),
        "raw_dataset_audio_included": False,
        "model_weights_included": False,
        "biometric_vectors_included": False,
        "raw_prediction_event_trees_included": False,
    }
    write_json_atomic(destination / "checksums.json", checksums)
    zip_path = destination.parent / PACKAGE_NAME
    deterministic_zip(destination, zip_path)
    value = {
        "schema_version": "full-pipeline-extended-collection.v1",
        **scope_fields(),
        "status": "PASS",
        "destination": str(destination),
        "checksums_path": str(destination / "checksums.json"),
        "checksums_sha256": sha256_file(destination / "checksums.json"),
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
        "artifact_count": len(checksums["entries"]),
        "hardening_wavs_in_compact_zip": False,
        "raw_audio_included": False,
        "model_weights_included": False,
        "biometric_vectors_included": False,
    }
    write_json_atomic(paths.root / "collection.json", value)
    return value


def finalize(
    *,
    workspace_root: Path,
    predecessor_record_path: Path | str,
    predecessor_record_sha256: str,
    adapter_id: str,
    adapter_contract_sha256: str,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    completion_record_path: Path | str | None = None,
    deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    """Revalidate compact evidence and publish the Prompt-6 completion envelope."""

    paths = layout(workspace_root)
    storage_preflight(paths.root)
    terminal = validate_terminal(workspace_root=paths.root)
    if terminal.get("status") != "PASS":
        raise ExtendedEvaluationError("Prompt-6 terminal validation failed")
    collection_path = paths.root / "collection.json"
    if not collection_path.is_file():
        raise ExtendedEvaluationError("Collect must complete before Finalize")
    collection = read_json(collection_path)
    package_root = ensure_c_drive(
        str(collection.get("destination") or ""),
        label="Prompt-6 canonical report",
        must_exist=True,
    )
    zip_path = ensure_c_drive(
        str(collection.get("zip_path") or ""),
        label="Prompt-6 compact ZIP",
        must_exist=True,
    )
    _verify_collection(package_root, collection)
    analysis_evidence = _validate_analysis_evidence(package_root / "analysis.json")
    predecessor_path = _validate_predecessor(
        predecessor_record_path, predecessor_record_sha256
    )
    authorization = read_json(paths.authorization)
    if authorization.get("prompt5_completion_path") != str(predecessor_path):
        raise ExtendedEvaluationError("authorization predecessor path differs")
    if authorization.get("prompt5_completion_sha256") != sha256_file(predecessor_path):
        raise ExtendedEvaluationError("authorization predecessor bytes changed")
    authorization = validate_saved_authorization(
        authorization,
        predecessor_path=predecessor_path,
        expected_sha256=predecessor_record_sha256,
        program_state_path=program_state_path,
        deployment_steering_path=deployment_steering_path,
        deployment_steering_sha256=deployment_steering_sha256,
    )
    _validate_authorized_freeze(authorization)
    deployment_evidence = _validate_deployment_evidence(
        package_root,
        plan=read_json(paths.plan),
        authorization=authorization,
    )
    _validate_hardening_manifest(read_json(paths.hardening_manifest))
    _require_sha(adapter_contract_sha256, "adapter contract SHA-256")
    if not str(adapter_id).strip():
        raise ExtendedEvaluationError("adapter_id is required")
    _require_sha(predecessor_record_sha256, "predecessor SHA-256")

    paths.gates.mkdir(parents=True, exist_ok=True)
    hash_gate = _write_gate(
        paths.gates / "hash_validation.json",
        gate="hash_validation",
        evidence={
            "package_checksums_path": str(package_root / "checksums.json"),
            "package_checksums_sha256": sha256_file(package_root / "checksums.json"),
            "compact_zip_path": str(zip_path),
            "compact_zip_sha256": sha256_file(zip_path),
            "terminal_validation": terminal,
            "hardening_input_manifest_path": str(paths.hardening_manifest),
            "hardening_input_manifest_sha256": sha256_file(paths.hardening_manifest),
            "extended_deployment_evidence_path": str(
                package_root / "extended_deployment_evidence.json"
            ),
            "extended_deployment_evidence_sha256": sha256_file(
                package_root / "extended_deployment_evidence.json"
            ),
        },
    )
    firewall_gate = _write_gate(
        paths.gates / "firewall_validation.json",
        gate="firewall_validation",
        evidence={
            "extended_set_frozen_in_prompt4": True,
            "prompt5_scientific_outcome_tables_opened_for_selection": False,
            "prompt5_deployment_evidence_opened_for_reporting": True,
            "outcome_dependent_selection": False,
            "deployment_evidence_used_as_filter": False,
            "pipeline_membership_changed_after_heldout": False,
            "desktop_evidence_relabelled_as_arm": False,
            "raspberry_pi_deployment_steering": authorization[
                "raspberry_pi_deployment_steering"
            ],
            "prompt5_deployment_evidence": authorization["prompt5_deployment_evidence"],
            "extended_deployment_evidence": artifact_ref(
                package_root / "extended_deployment_evidence.json"
            ),
            "accuracy_maximum_concurrency": 2,
            "resource_concurrency": 1,
            "native_known_speaker_metrics_fabricated": False,
            "unsupported_chime_wer_fabricated": False,
            "native_metric_applicability": analysis_evidence[
                "native_metric_applicability"
            ],
            "reliability_evidence": analysis_evidence["reliability_evidence"],
            "long_stream_evidence": analysis_evidence["long_stream_evidence"],
            "component_rtf_evidence": analysis_evidence["component_rtf_evidence"],
            "energy_or_beaker_power_claim_fabricated": False,
            "bounded_reduced_scope_disclosed": True,
        },
    )
    prerequisite_gate = _write_gate(
        paths.gates / "prerequisite_validation.json",
        gate="prerequisite_validation",
        evidence={
            "predecessor_record_path": str(predecessor_path),
            "predecessor_record_sha256": sha256_file(predecessor_path),
            "predecessor_completion_marker": PROMPT5_COMPLETION_MARKER,
            "prompt6_authorization_path": str(paths.authorization),
            "prompt6_authorization_sha256": sha256_file(paths.authorization),
            "raspberry_pi_deployment_steering": authorization[
                "raspberry_pi_deployment_steering"
            ],
            "prompt5_deployment_evidence": authorization["prompt5_deployment_evidence"],
        },
    )
    gates = {
        "hash_validation": artifact_ref(hash_gate),
        "firewall_validation": artifact_ref(firewall_gate),
        "prerequisite_validation": artifact_ref(prerequisite_gate),
    }
    artifact_paths = _unique_paths(
        [
            *(package_root / name for name in REQUIRED_REPORT_FILES),
            package_root / "checksums.json",
            zip_path,
            paths.authorization,
            paths.input_binding,
            paths.plan,
            paths.selection_manifest,
            paths.excluded_cases,
            paths.hardening_manifest,
            paths.report / "serial_resources.csv",
            Path(str(authorization["raspberry_pi_deployment_steering"]["path"])),
            Path(str(authorization["prompt5_deployment_evidence"]["path"])),
            Path(str(authorization["extended_set"]["path"])),
            collection_path,
            hash_gate,
            firewall_gate,
            prerequisite_gate,
        ]
    )
    binding = read_json(paths.input_binding)
    for artifact_path in artifact_paths:
        _require_material_path(artifact_path, binding)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        **scope_fields(),
        "prompt_index": 6,
        "artifacts": [
            {**artifact_ref(path), "required": True} for path in artifact_paths
        ],
    }
    write_json_atomic(paths.artifact_manifest, manifest)
    completion_path = ensure_c_drive(
        completion_record_path or paths.completion,
        label="Prompt-6 completion record",
    )
    if completion_path != paths.completion.resolve():
        raise ExtendedEvaluationError(
            "Prompt-6 completion record must be the canonical stage workspace path"
        )
    plan = read_json(paths.plan)
    completion = {
        "schema_version": COMPLETION_SCHEMA,
        **scope_fields(),
        "prompt_index": 6,
        "status": "COMPLETE",
        "completion_marker": PROMPT6_COMPLETION_MARKER,
        "completed_at_utc": _utc_now(),
        "adapter_id": str(adapter_id),
        "adapter_contract_sha256": str(adapter_contract_sha256).casefold(),
        "predecessor": {
            "prompt_index": 5,
            "completion_marker": PROMPT5_COMPLETION_MARKER,
            "completion_record_path": str(predecessor_path),
            "completion_record_sha256": sha256_file(predecessor_path),
        },
        "artifact_manifest": artifact_ref(paths.artifact_manifest),
        "gate_records": gates,
        "native_completion": {
            "pipeline_count": plan["pipeline_count"],
            "job_count": terminal["job_count"],
            "complete_job_count": terminal["complete_count"],
            "failed_job_count": terminal["failed_count"],
            "compact_zip_path": str(zip_path),
            "compact_zip_sha256": sha256_file(zip_path),
            "hardening_input_manifest_path": str(paths.hardening_manifest),
            "hardening_input_manifest_sha256": sha256_file(paths.hardening_manifest),
            "native_metric_applicability": analysis_evidence[
                "native_metric_applicability"
            ],
            "reliability_evidence": analysis_evidence["reliability_evidence"],
            "long_stream_evidence": analysis_evidence["long_stream_evidence"],
            "component_rtf_evidence": analysis_evidence["component_rtf_evidence"],
            "raspberry_pi_deployment_steering": authorization[
                "raspberry_pi_deployment_steering"
            ],
            "prompt5_deployment_evidence": authorization["prompt5_deployment_evidence"],
            "extended_deployment_evidence_path": str(
                package_root / "extended_deployment_evidence.json"
            ),
            "extended_deployment_evidence_sha256": sha256_file(
                package_root / "extended_deployment_evidence.json"
            ),
            "two_gib_feasibility_classes": deployment_evidence[
                "two_gib_feasibility_classes"
            ],
            "linux_arm64_portability_classes": deployment_evidence[
                "linux_arm64_portability_classes"
            ],
            "deployment_evidence_used_as_filter": False,
            "pipeline_membership_changed_after_heldout": False,
            "desktop_evidence_relabelled_as_arm": False,
        },
    }
    write_json_atomic(completion_path, completion)
    _update_program_state(
        ensure_c_drive(program_state_path, label="program state", must_exist=True),
        completion_path=completion_path,
    )
    return completion


def validate_completion(
    *,
    workspace_root: Path,
    completion_record_path: Path | str,
    expected_adapter_id: str | None = None,
    expected_adapter_contract_sha256: str | None = None,
    program_state_path: Path | str = DEFAULT_PROGRAM_STATE,
    deployment_steering_path: Path | str = DEFAULT_PI_DEPLOYMENT_STEERING,
    deployment_steering_sha256: str = PI_DEPLOYMENT_STEERING_SHA256,
) -> dict[str, object]:
    """Independently rehash the universal envelope and all required artifacts."""

    paths = layout(workspace_root)
    completion_path = ensure_c_drive(
        completion_record_path,
        label="Prompt-6 completion record",
        must_exist=True,
    )
    completion = read_json(completion_path)
    expected = {
        "schema_version": COMPLETION_SCHEMA,
        **scope_fields(),
        "prompt_index": 6,
        "status": "COMPLETE",
        "completion_marker": PROMPT6_COMPLETION_MARKER,
    }
    for key, value in expected.items():
        if completion.get(key) != value:
            raise ExtendedEvaluationError(f"completion {key} differs")
    if expected_adapter_id and completion.get("adapter_id") != expected_adapter_id:
        raise ExtendedEvaluationError("completion adapter_id differs")
    if (
        expected_adapter_contract_sha256
        and completion.get("adapter_contract_sha256")
        != expected_adapter_contract_sha256.casefold()
    ):
        raise ExtendedEvaluationError("completion adapter contract hash differs")
    predecessor = completion.get("predecessor")
    if not isinstance(predecessor, Mapping):
        raise ExtendedEvaluationError("completion predecessor is absent")
    _validate_predecessor(
        str(predecessor.get("completion_record_path") or ""),
        str(predecessor.get("completion_record_sha256") or ""),
    )
    if (
        predecessor.get("prompt_index") != 5
        or predecessor.get("completion_marker") != PROMPT5_COMPLETION_MARKER
    ):
        raise ExtendedEvaluationError("completion predecessor identity differs")
    manifested_paths = _verify_universal_refs(completion, prompt_index=6)
    authorization = read_json(paths.authorization)
    if authorization.get("prompt5_completion_path") != predecessor.get(
        "completion_record_path"
    ) or authorization.get("prompt5_completion_sha256") != predecessor.get(
        "completion_record_sha256"
    ):
        raise ExtendedEvaluationError("authorization predecessor binding differs")
    _validate_authorized_freeze(authorization)
    steering_reference = authorization.get("raspberry_pi_deployment_steering")
    if not isinstance(steering_reference, Mapping):
        raise ExtendedEvaluationError("completion deployment steering is absent")
    requested_steering = ensure_c_drive(
        deployment_steering_path,
        label="deployment steering authority",
        must_exist=True,
    )
    if (
        steering_reference.get("path") != str(requested_steering)
        or steering_reference.get("sha256")
        != str(deployment_steering_sha256).casefold()
        or sha256_file(requested_steering) != str(deployment_steering_sha256).casefold()
    ):
        raise ExtendedEvaluationError("completion deployment steering binding differs")
    _validate_hardening_manifest(read_json(paths.hardening_manifest))
    terminal = validate_terminal(workspace_root=paths.root)
    if terminal.get("status") != "PASS":
        raise ExtendedEvaluationError("terminal jobs changed after completion")
    collection = read_json(paths.root / "collection.json")
    _verify_collection(
        ensure_c_drive(
            str(collection.get("destination") or ""),
            label="Prompt-6 report root",
            must_exist=True,
        ),
        collection,
    )
    package_root = ensure_c_drive(
        str(collection.get("destination") or ""),
        label="Prompt-6 report root",
        must_exist=True,
    )
    _validate_analysis_evidence(package_root / "analysis.json")
    deployment_document = _validate_deployment_evidence(
        package_root,
        plan=read_json(paths.plan),
        authorization=authorization,
    )
    serial_reference = deployment_document.get("serial_resource_evidence")
    if not isinstance(serial_reference, Mapping):
        raise ExtendedEvaluationError("completion serial resource reference is absent")
    required_manifested = {
        (package_root / "extended_deployment_evidence.json").resolve(),
        ensure_c_drive(
            str(serial_reference.get("path") or ""),
            label="Prompt-6 serial resource evidence",
            must_exist=True,
        ),
        requested_steering,
        ensure_c_drive(
            str(authorization["prompt5_deployment_evidence"]["path"]),
            label="Prompt-5 deployment evidence",
            must_exist=True,
        ),
        ensure_c_drive(
            str(authorization["extended_set"]["path"]),
            label="Prompt-4 extended set",
            must_exist=True,
        ),
    }
    if not required_manifested <= manifested_paths:
        raise ExtendedEvaluationError(
            "completion artifact manifest lacks deployment evidence inputs/outputs"
        )
    native = completion.get("native_completion")
    if (
        not isinstance(native, Mapping)
        or native.get("extended_deployment_evidence_path")
        != str(package_root / "extended_deployment_evidence.json")
        or native.get("extended_deployment_evidence_sha256")
        != sha256_file(package_root / "extended_deployment_evidence.json")
        or native.get("deployment_evidence_used_as_filter") is not False
        or native.get("pipeline_membership_changed_after_heldout") is not False
        or native.get("desktop_evidence_relabelled_as_arm") is not False
    ):
        raise ExtendedEvaluationError("completion deployment evidence claim differs")
    state = read_json(
        ensure_c_drive(program_state_path, label="program state", must_exist=True)
    )
    if (
        state.get("status") != PROMPT6_COMPLETION_MARKER
        or int(state.get("current_prompt_index") or -1) != 6
    ):
        raise ExtendedEvaluationError("PROGRAM_STATE has not reached bounded Prompt 6")
    if state.get("prompt_6_completion_record_sha256") != sha256_file(completion_path):
        raise ExtendedEvaluationError("PROGRAM_STATE completion binding differs")
    return {
        "schema_version": "full-pipeline-extended-completion-validation.v1",
        **scope_fields(),
        "status": "PASS",
        "prompt_index": 6,
        "completion_marker": PROMPT6_COMPLETION_MARKER,
        "completion_record_path": str(completion_path),
        "completion_record_sha256": sha256_file(completion_path),
        "pipeline_count": read_json(paths.plan)["pipeline_count"],
        "job_count": terminal["job_count"],
    }


def _validate_predecessor(path: Path | str, expected_sha256: str) -> Path:
    predecessor_path = ensure_c_drive(
        path, label="Prompt-5 predecessor", must_exist=True
    )
    _require_sha(expected_sha256, "predecessor SHA-256")
    if sha256_file(predecessor_path) != expected_sha256.casefold():
        raise ExtendedEvaluationError("Prompt-5 predecessor hash differs")
    value = read_json(predecessor_path)
    for key, expected in {
        "schema_version": COMPLETION_SCHEMA,
        **scope_fields(),
        "prompt_index": 5,
        "status": "COMPLETE",
        "completion_marker": PROMPT5_COMPLETION_MARKER,
    }.items():
        if value.get(key) != expected:
            raise ExtendedEvaluationError(f"Prompt-5 predecessor {key} differs")
    _verify_universal_refs(value, prompt_index=5)
    return predecessor_path


def _validate_authorized_freeze(authorization: Mapping[str, object]) -> None:
    registry = authorization.get("decision_policy_registry")
    if not isinstance(registry, Mapping):
        raise ExtendedEvaluationError("authorization decision registry is absent")
    registry_path = verify_ref(registry, label="decision-policy registry")
    registry_document = read_json(registry_path)
    frozen = authorization.get("frozen_pipeline_configs")
    if not isinstance(frozen, Mapping):
        raise ExtendedEvaluationError("authorization frozen configs are absent")
    current_proof = _validate_frozen_configs(
        frozen,
        policy_registry=registry_document,
    )
    if current_proof != dict(frozen):
        raise ExtendedEvaluationError(
            "authorization live execution proof changed after admission"
        )
    extended = authorization.get("extended_set")
    if not isinstance(extended, Mapping):
        raise ExtendedEvaluationError("authorization extended set is absent")
    path = ensure_c_drive(
        str(extended.get("path") or ""), label="extended set", must_exist=True
    )
    if extended.get("sha256") != sha256_file(path):
        raise ExtendedEvaluationError("extended set hash differs")
    _validate_extended_set(path)


def _validate_analysis_evidence(path: Path) -> dict[str, object]:
    value = read_json(path)
    if (
        value.get("schema_version") != "full-pipeline-extended-analysis.v1"
        or value.get("status") != "PASS"
    ):
        raise ExtendedEvaluationError("Prompt-6 analysis evidence is invalid")
    required = (
        "native_metric_applicability",
        "reliability_evidence",
        "long_stream_evidence",
        "component_rtf_evidence",
        "deployment_evidence",
    )
    sections: dict[str, Mapping[str, object]] = {}
    for name in required:
        raw = value.get(name)
        if not isinstance(raw, Mapping) or raw.get("status") != "PASS":
            raise ExtendedEvaluationError(f"Prompt-6 {name} audit did not pass")
        sections[name] = raw
    native = sections["native_metric_applicability"]
    if native.get("disallowed_computed_metric_count") != 0:
        raise ExtendedEvaluationError("disallowed native computed metrics remain")
    reliability = sections["reliability_evidence"]
    if reliability.get("all_faults_have_explicit_evidence_status") is not True:
        raise ExtendedEvaluationError("reliability evidence has implicit outcomes")
    component = sections["component_rtf_evidence"]
    if component.get("false_computed_component_rtf_count") != 0:
        raise ExtendedEvaluationError("component RTF lacks measured duration evidence")
    deployment = sections["deployment_evidence"]
    if (
        deployment.get("pipeline_membership_changed") is not False
        or deployment.get("deployment_evidence_used_as_filter") is not False
        or deployment.get("desktop_evidence_relabelled_as_arm") is not False
    ):
        raise ExtendedEvaluationError("deployment evidence scientific firewall differs")
    return value


def _validate_deployment_evidence(
    report_root: Path,
    *,
    plan: Mapping[str, object],
    authorization: Mapping[str, object],
) -> dict[str, object]:
    path = report_root / "extended_deployment_evidence.json"
    document = read_json(path)
    serial = document.get("serial_resource_evidence")
    if not isinstance(serial, Mapping):
        raise ExtendedEvaluationError("Prompt-6 serial deployment evidence is absent")
    return validate_extended_deployment_evidence(
        document,
        plan=plan,
        authorization=authorization,
        serial_resource_path=ensure_c_drive(
            str(serial.get("path") or ""),
            label="Prompt-6 serial resource evidence",
            must_exist=True,
        ),
    )


def _write_gate(path: Path, *, gate: str, evidence: Mapping[str, object]) -> Path:
    if gate not in EXPECTED_GATE_NAMES:
        raise ExtendedEvaluationError(f"unknown universal gate: {gate}")
    write_json_atomic(
        path,
        {
            "schema_version": GATE_SCHEMA,
            **scope_fields(),
            "prompt_index": 6,
            "gate": gate,
            "status": "PASS",
            "evidence": dict(evidence),
        },
    )
    return path.resolve()


def _verify_universal_refs(
    completion: Mapping[str, object], *, prompt_index: int
) -> set[Path]:
    raw_manifest = completion.get("artifact_manifest")
    if not isinstance(raw_manifest, Mapping):
        raise ExtendedEvaluationError(
            "completion artifact manifest reference is absent"
        )
    manifest_path = verify_ref(raw_manifest, label="artifact manifest")
    manifest = read_json(manifest_path)
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA
        or manifest.get("prompt_index") != prompt_index
    ):
        raise ExtendedEvaluationError("artifact manifest identity differs")
    for key, expected in scope_fields().items():
        if manifest.get(key) != expected:
            raise ExtendedEvaluationError(f"artifact manifest {key} differs")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ExtendedEvaluationError("artifact manifest is empty")
    paths: set[Path] = set()
    for index, raw in enumerate(artifacts):
        if not isinstance(raw, Mapping) or raw.get("required") is not True:
            raise ExtendedEvaluationError(f"artifact entry {index} is invalid")
        paths.add(verify_ref(raw, label=f"required artifact {index}"))
    gates = completion.get("gate_records")
    if not isinstance(gates, Mapping) or set(gates) != EXPECTED_GATE_NAMES:
        raise ExtendedEvaluationError("completion gate inventory differs")
    for name in sorted(EXPECTED_GATE_NAMES):
        raw = gates[name]
        if not isinstance(raw, Mapping):
            raise ExtendedEvaluationError(f"{name} gate reference is invalid")
        path = verify_ref(raw, label=f"{name} gate")
        if path not in paths:
            raise ExtendedEvaluationError(f"{name} gate is not manifested")
        gate = read_json(path)
        for key, expected in {
            "schema_version": GATE_SCHEMA,
            **scope_fields(),
            "prompt_index": prompt_index,
            "gate": name,
            "status": "PASS",
        }.items():
            if gate.get(key) != expected:
                raise ExtendedEvaluationError(f"{name} gate {key} differs")
    return paths


def _verify_collection(root: Path, collection: Mapping[str, object]) -> None:
    checksums_path = root / "checksums.json"
    document = read_json(checksums_path)
    entries = document.get("entries")
    if not isinstance(entries, Mapping):
        raise ExtendedEvaluationError("canonical report checksum map is invalid")
    if dict(entries) != checksum_map(root, exclude=("checksums.json",)):
        raise ExtendedEvaluationError("canonical report bytes changed after Collect")
    if collection.get("checksums_sha256") != sha256_file(checksums_path):
        raise ExtendedEvaluationError("collection checksum-document hash differs")
    zip_path = ensure_c_drive(
        str(collection.get("zip_path") or ""), label="compact ZIP", must_exist=True
    )
    if collection.get("zip_sha256") != sha256_file(zip_path):
        raise ExtendedEvaluationError("compact ZIP hash differs")
    for name in REQUIRED_REPORT_FILES:
        if not (root / name).is_file():
            raise ExtendedEvaluationError(f"canonical report lacks {name}")


def _update_program_state(path: Path, *, completion_path: Path) -> None:
    value = read_json(path)
    if value.get("status") == PROMPT6_COMPLETION_MARKER:
        if value.get("prompt_6_completion_record_sha256") != sha256_file(
            completion_path
        ):
            raise ExtendedEvaluationError("existing Prompt-6 program state differs")
        return
    if (
        value.get("status") != PROMPT5_COMPLETION_MARKER
        or int(value.get("current_prompt_index") or -1) != 5
    ):
        raise ExtendedEvaluationError(
            "program state moved away from completed Prompt 5"
        )
    state = dict(value)
    completion_state = dict(state.get("completion_state") or {})
    completion_state["prompt_6"] = PROMPT6_COMPLETION_MARKER
    completion_state["prompt_6_scope_id"] = scope_fields()["scope_id"]
    completion_state["prompt_6_original_full_scope_complete"] = False
    state.update(
        {
            **scope_fields(),
            "status": PROMPT6_COMPLETION_MARKER,
            "current_prompt_index": 6,
            "remaining_prompt_indices": [7, 8],
            "remaining_prompt_status": "PENDING_AUTOMATIC",
            "completion_state": completion_state,
            "prompt_6_completion_record": str(completion_path),
            "prompt_6_completion_record_sha256": sha256_file(completion_path),
        }
    )
    write_json_atomic(path, state)


def _require_material_path(path: Path, binding: Mapping[str, object]) -> None:
    inventory = binding.get("material_paths")
    if not isinstance(inventory, Mapping):
        raise ExtendedEvaluationError("input binding material inventory is absent")
    candidate = path.resolve()
    for values in inventory.values():
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
            continue
        for raw in values:
            declared = Path(str(raw)).resolve()
            if candidate == declared:
                return
            if declared.is_dir():
                try:
                    candidate.relative_to(declared)
                    return
                except ValueError:
                    pass
    raise ExtendedEvaluationError(
        f"artifact lies outside declared material paths: {path}"
    )


def _copy_or_verify(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if sha256_file(source) != sha256_file(destination):
            raise ExtendedEvaluationError(
                f"immutable collected artifact differs: {destination}"
            )
        return
    shutil.copy2(source, destination)


def _unique_paths(paths: Sequence[Path]) -> list[Path]:
    return list(dict.fromkeys(path.resolve() for path in paths))


def _require_sha(value: str, label: str) -> None:
    text = str(value).casefold()
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ExtendedEvaluationError(f"{label} must be a SHA-256 hex digest")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["PACKAGE_NAME", "collect", "finalize", "validate_completion"]
