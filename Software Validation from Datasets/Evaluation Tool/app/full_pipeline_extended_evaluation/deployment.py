"""Additive Raspberry Pi deployment evidence for bounded Prompt 6.

The report produced here never changes the frozen extended-set membership or
scientific results.  It carries the Prompt-5 deployment evidence forward and
adds only checksum-bound serial desktop-resource observations from Prompt 6.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    FUTURE_LINUX_ARM64_VALIDATION,
    FUTURE_TARGET_HARDWARE_TESTS,
    LINUX_ARM64_PORTABILITY_CLASSES,
    RASPBERRY_PI_CANDIDATE_FIELDS,
    TWO_GIB_FEASIBILITY_CLASSES,
    DeploymentEvidenceError,
    classify_linux_arm64,
    classify_two_gib,
    evidence,
    load_deployment_steering,
    steering_ref,
    validate_deployment_attributes,
    validate_deployment_evidence_document,
)
from app.full_pipeline_evaluation.planning import MATRIX_PATH, RUNTIME_CONFIG_PATH

from . import (
    PI_DEPLOYMENT_STEERING_SHA256,
    PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
    PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA,
    scope_fields,
)
from .io import ExtendedEvaluationError, ensure_c_drive, read_json, sha256_file


_RESOURCE_ATTRIBUTE_FIELDS = {
    "model_file_size_bytes": ("model_bytes", "bytes", "DERIVED"),
    "total_pipeline_peak_rss_bytes": (
        "peak_rss_bytes",
        "bytes",
        "MEASURED",
    ),
    "cache_requirements_bytes": ("cache_bytes", "bytes", "MEASURED"),
    "initialization_time_sec": ("model_startup_sec", "seconds", "MEASURED"),
    "warmup_time_sec": ("warmup_duration_sec", "seconds", "DERIVED"),
}


def build_extended_deployment_evidence(
    *,
    plan: Mapping[str, object],
    authorization: Mapping[str, object],
    serial_resource_rows: Sequence[Mapping[str, object]],
    serial_resource_path: Path | str,
) -> dict[str, object]:
    """Build the exact frozen-set Prompt-6 deployment evidence document."""

    steering, steering_reference = _steering(authorization)
    prompt5_reference, prompt5 = _prompt5_document(authorization, steering)
    extended_ids = _pipeline_ids(plan)
    context = _deployment_context(plan)
    prompt4_reference = _prompt4_extended_reference(context, extended_ids)
    serial_path = ensure_c_drive(
        serial_resource_path, label="Prompt-6 serial resource report", must_exist=True
    )
    serial_sha = sha256_file(serial_path)
    serial_index = _serial_index(serial_resource_rows, extended_ids)
    prompt5_index = _pipeline_index(prompt5, expected_ids=None)
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)

    rows: list[dict[str, object]] = []
    serial_statuses: list[dict[str, object]] = []
    for pipeline_id in extended_ids:
        if pipeline_id not in prompt5_index:
            raise ExtendedEvaluationError(
                f"Prompt-5 deployment evidence lacks {pipeline_id}"
            )
        base = prompt5_index[pipeline_id]
        selection = matrix.resolve(pipeline_id)
        _validate_component_identity(base, selection)
        attributes = validate_deployment_attributes(
            _mapping(base, "deployment_attributes"), steering
        )
        serial = serial_index[pipeline_id]
        enriched = _enrich_attributes(
            attributes,
            serial,
            source_path=serial_path,
            source_sha256=serial_sha,
        )
        windows_assumptions = _mapping(base, "windows_specific_assumptions")
        linux_dependencies = _mapping(base, "linux_arm64_dependency_status")
        replacements = _mapping(base, "required_platform_replacements")
        row = {
            **base,
            "deployment_attributes": enriched,
            "desktop_resource_context": _desktop_resource_context(
                serial,
                source_path=serial_path,
                source_sha256=serial_sha,
                prompt5_context=_mapping(base, "desktop_resource_context"),
            ),
            "two_gib_feasibility": classify_two_gib(
                enriched["total_pipeline_peak_rss_bytes"]
            ),
            "linux_arm64_portability": classify_linux_arm64(
                windows_specific_assumptions=windows_assumptions,
                linux_arm64_dependency_status=linux_dependencies,
                required_platform_replacements=replacements,
            ),
            "windows_specific_assumptions": windows_assumptions,
            "linux_arm64_dependency_status": linux_dependencies,
            "required_platform_replacements": replacements,
            "used_to_filter_pipeline": False,
        }
        rows.append(row)
        serial_statuses.append(
            {
                "pipeline_id": pipeline_id,
                "job_id": serial.get("job_id"),
                "job_state": serial.get("job_state"),
                "explicit_failure": bool(serial.get("explicit_failure")),
                "resource_evidence_available": _resource_evidence_available(serial),
                "used_as_filter": False,
            }
        )

    document = {
        "schema_version": PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA,
        **scope_fields(),
        "prompt_index": 6,
        "status": "PASS",
        "pipeline_ids": list(extended_ids),
        "pipeline_count": len(extended_ids),
        "extended_pipeline_ids": list(extended_ids),
        "extended_pipeline_count": len(extended_ids),
        "deployment_attribute_names": list(DEPLOYMENT_ATTRIBUTE_NAMES),
        "two_gib_feasibility_classes": list(TWO_GIB_FEASIBILITY_CLASSES),
        "linux_arm64_portability_classes": list(LINUX_ARM64_PORTABILITY_CLASSES),
        "raspberry_pi_candidate_fields": list(RASPBERRY_PI_CANDIDATE_FIELDS),
        "future_target_hardware_tests": list(FUTURE_TARGET_HARDWARE_TESTS),
        "future_linux_arm64_validation": list(FUTURE_LINUX_ARM64_VALIDATION),
        "steering_authority": steering_reference,
        "input_binding": {
            "deployment_steering_path": steering_reference["path"],
            "deployment_steering_sha256": steering_reference["sha256"],
            "deployment_steering_schema_version": steering_reference["schema_version"],
            "deployment_steering_id": steering_reference["steering_id"],
            "deployment_steering_status": steering_reference["status"],
            "prompt4_extended_set_path": prompt4_reference["path"],
            "prompt4_extended_set_sha256": prompt4_reference["sha256"],
            "prompt5_deployment_evidence_path": prompt5_reference["path"],
            "prompt5_deployment_evidence_sha256": prompt5_reference["sha256"],
            "serial_resource_evidence_path": str(serial_path),
            "serial_resource_evidence_sha256": serial_sha,
        },
        "predeclared_membership": {
            "source_prompt_index": 4,
            "extended_set": prompt4_reference,
            "mandatory_pipeline_ids": prompt4_reference["mandatory_pipeline_ids"],
            "additional_challenger_pipeline_ids": prompt4_reference[
                "additional_challenger_pipeline_ids"
            ],
            "pipeline_ids": list(extended_ids),
            "pipeline_count": len(extended_ids),
            "frozen_before_prompt5_heldout_opened": True,
            "membership_changed_after_heldout": False,
            "deployment_evidence_used_as_filter": False,
        },
        "prompt5_deployment_evidence": prompt5_reference,
        "serial_resource_evidence": {
            "path": str(serial_path),
            "sha256": serial_sha,
            "schema_version": "full-pipeline-extended-serial-resources.csv.v1",
            "status": "PASS",
            "pipeline_count": len(extended_ids),
            "packaged_copy_relative_path": "serial_resources.csv",
            "measurement_context": "WINDOWS_X86_64_DESKTOP",
            "arm_measurement": False,
            "resource_concurrency": 1,
            "cold_start_included": True,
            "warmup_sec": 60,
            "measured_sec": 300,
            "pipeline_statuses": serial_statuses,
            "explicit_failures_retained": True,
            "used_as_filter": False,
        },
        "pipelines": rows,
        "scientific_firewall": {
            "scientific_methodology_changed": False,
            "pipeline_membership_changed": False,
            "heldout_selection_or_retuning_performed": False,
            "deployment_evidence_used_as_filter": False,
            "desktop_rank_used_as_final_arm_rank": False,
        },
    }
    return validate_extended_deployment_evidence(
        document,
        plan=plan,
        authorization=authorization,
        serial_resource_path=serial_path,
    )


def validate_extended_deployment_evidence(
    document: Mapping[str, object],
    *,
    plan: Mapping[str, object],
    authorization: Mapping[str, object],
    serial_resource_path: Path | str,
) -> dict[str, object]:
    """Revalidate scientific firewall, provenance, ordering, and source hashes."""

    try:
        steering, steering_reference = _steering(authorization)
        prompt5_reference, prompt5_document = _prompt5_document(authorization, steering)
        pipeline_ids = _pipeline_ids(plan)
        validate_deployment_evidence_document(
            document,
            schema_version=PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA,
            prompt_index=6,
            expected_pipeline_ids=pipeline_ids,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise ExtendedEvaluationError(
            f"Prompt-6 deployment evidence validation failed: {exc}"
        ) from exc
    for key, expected in scope_fields().items():
        if document.get(key) != expected:
            raise ExtendedEvaluationError(f"Prompt-6 deployment evidence {key} differs")
    if document.get("steering_authority") != steering_reference:
        raise ExtendedEvaluationError("Prompt-6 steering authority reference differs")
    if document.get("prompt5_deployment_evidence") != prompt5_reference:
        raise ExtendedEvaluationError("Prompt-5 deployment evidence reference differs")
    if document.get("extended_pipeline_ids") != list(pipeline_ids) or int(
        document.get("extended_pipeline_count") or -1
    ) != len(pipeline_ids):
        raise ExtendedEvaluationError("Prompt-6 extended deployment membership differs")

    context = _deployment_context(plan)
    expected_extended = _prompt4_extended_reference(context, pipeline_ids)
    predeclared = _mapping(document, "predeclared_membership")
    if predeclared != {
        "source_prompt_index": 4,
        "extended_set": expected_extended,
        "mandatory_pipeline_ids": expected_extended["mandatory_pipeline_ids"],
        "additional_challenger_pipeline_ids": expected_extended[
            "additional_challenger_pipeline_ids"
        ],
        "pipeline_ids": list(pipeline_ids),
        "pipeline_count": len(pipeline_ids),
        "frozen_before_prompt5_heldout_opened": True,
        "membership_changed_after_heldout": False,
        "deployment_evidence_used_as_filter": False,
    }:
        raise ExtendedEvaluationError("Prompt-4 predeclared membership binding differs")

    serial_path = ensure_c_drive(
        serial_resource_path, label="Prompt-6 serial resource report", must_exist=True
    )
    serial = _mapping(document, "serial_resource_evidence")
    if (
        serial.get("path") != str(serial_path)
        or serial.get("sha256") != sha256_file(serial_path)
        or serial.get("status") != "PASS"
        or int(serial.get("pipeline_count") or -1) != len(pipeline_ids)
        or serial.get("packaged_copy_relative_path") != "serial_resources.csv"
        or serial.get("measurement_context") != "WINDOWS_X86_64_DESKTOP"
        or serial.get("arm_measurement") is not False
        or serial.get("resource_concurrency") != 1
        or serial.get("used_as_filter") is not False
        or serial.get("explicit_failures_retained") is not True
    ):
        raise ExtendedEvaluationError("Prompt-6 serial resource evidence differs")
    input_binding = _mapping(document, "input_binding")
    expected_input_binding = {
        "deployment_steering_path": steering_reference["path"],
        "deployment_steering_sha256": steering_reference["sha256"],
        "deployment_steering_schema_version": steering_reference["schema_version"],
        "deployment_steering_id": steering_reference["steering_id"],
        "deployment_steering_status": steering_reference["status"],
        "prompt4_extended_set_path": expected_extended["path"],
        "prompt4_extended_set_sha256": expected_extended["sha256"],
        "prompt5_deployment_evidence_path": prompt5_reference["path"],
        "prompt5_deployment_evidence_sha256": prompt5_reference["sha256"],
        "serial_resource_evidence_path": str(serial_path),
        "serial_resource_evidence_sha256": sha256_file(serial_path),
    }
    if input_binding != expected_input_binding:
        raise ExtendedEvaluationError("Prompt-6 deployment input binding differs")
    statuses = serial.get("pipeline_statuses")
    if not isinstance(statuses, list) or [
        str(row.get("pipeline_id")) for row in statuses if isinstance(row, Mapping)
    ] != list(pipeline_ids):
        raise ExtendedEvaluationError("Prompt-6 serial resource status order differs")

    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    rows = _pipeline_index(document, expected_ids=pipeline_ids)
    prompt5_rows = _pipeline_index(prompt5_document, expected_ids=None)
    for pipeline_id in pipeline_ids:
        row = rows[pipeline_id]
        _validate_component_identity(row, matrix.resolve(pipeline_id))
        resource_context = _mapping(row, "desktop_resource_context")
        if (
            resource_context.get("source_path") != str(serial_path)
            or resource_context.get("source_sha256") != sha256_file(serial_path)
            or resource_context.get("measurement_context") != "WINDOWS_X86_64_DESKTOP"
            or resource_context.get("arm_measurement") is not False
            or resource_context.get("used_as_filter") is not False
            or resource_context.get("prompt5_desktop_resource_context")
            != prompt5_rows[pipeline_id].get("desktop_resource_context")
        ):
            raise ExtendedEvaluationError(
                f"Prompt-6 desktop resource context differs for {pipeline_id}"
            )
    return dict(document)


def _enrich_attributes(
    base: Mapping[str, object],
    serial: Mapping[str, object],
    *,
    source_path: Path,
    source_sha256: str,
) -> dict[str, object]:
    enriched = {name: dict(_as_mapping(base[name], name)) for name in base}
    if str(serial.get("job_state") or "") != "complete":
        return enriched
    for attribute, (field, unit, status) in _RESOURCE_ATTRIBUTE_FIELDS.items():
        value = _number(serial.get(field))
        if value is None:
            continue
        normalized: int | float = int(value) if value.is_integer() else value
        frozen = status == "DERIVED"
        enriched[attribute] = evidence(
            normalized,
            unit=unit,
            evidence_status=status,
            reason_code=(
                "PROMPT6_FROZEN_SERIAL_RESOURCE_CONFIGURATION"
                if frozen
                else "PROMPT6_SERIAL_DESKTOP_RESOURCE_MEASUREMENT"
            ),
            measurement_context=(
                "FROZEN_CONFIGURATION" if frozen else "WINDOWS_X86_64_DESKTOP"
            ),
            source_path=source_path,
            source_sha256=source_sha256,
            source_field=field,
            desktop_measurement=not frozen,
            details={
                "job_id": serial.get("job_id"),
                "job_state": serial.get("job_state"),
                "resource_concurrency": 1,
                "arm_target_measurement": False,
            },
        )
    return enriched


def _desktop_resource_context(
    serial: Mapping[str, object],
    *,
    source_path: Path,
    source_sha256: str,
    prompt5_context: Mapping[str, object],
) -> dict[str, object]:
    fields = (
        "model_bytes",
        "peak_rss_bytes",
        "cache_bytes",
        "model_startup_sec",
        "warmup_duration_sec",
        "total_rtf_including_startup_and_warmup",
        "component_rtf_measurement_status",
        "deadline_miss_count",
        "dropped_frames",
    )
    return {
        "measurement_context": "WINDOWS_X86_64_DESKTOP",
        "source_path": str(source_path),
        "source_sha256": source_sha256,
        "job_id": serial.get("job_id"),
        "job_state": serial.get("job_state"),
        "explicit_failure": bool(serial.get("explicit_failure")),
        "values": {field: serial.get(field) for field in fields},
        "prompt5_desktop_resource_context": dict(prompt5_context),
        "arm_measurement": False,
        "desktop_result_is_final_target_hardware_result": False,
        "resource_concurrency": 1,
        "used_as_filter": False,
    }


def _resource_evidence_available(serial: Mapping[str, object]) -> bool:
    return str(serial.get("job_state") or "") == "complete" and any(
        _number(serial.get(field)) is not None
        for field, _unit, _status in _RESOURCE_ATTRIBUTE_FIELDS.values()
    )


def _steering(
    authorization: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    raw = _mapping(authorization, "raspberry_pi_deployment_steering")
    try:
        steering = load_deployment_steering(
            str(raw.get("path") or ""),
            expected_prompt_index=6,
            expected_sha256=PI_DEPLOYMENT_STEERING_SHA256,
        )
        reference = steering_ref(str(raw.get("path") or ""), steering)
    except DeploymentEvidenceError as exc:
        raise ExtendedEvaluationError(f"deployment steering differs: {exc}") from exc
    if reference != raw:
        raise ExtendedEvaluationError("deployment steering authorization differs")
    return steering, reference


def _prompt5_document(
    authorization: Mapping[str, object], steering: Mapping[str, object]
) -> tuple[dict[str, object], dict[str, object]]:
    reference = _mapping(authorization, "prompt5_deployment_evidence")
    path = ensure_c_drive(
        str(reference.get("path") or ""),
        label="Prompt-5 deployment evidence",
        must_exist=True,
    )
    expected = {
        "path": str(path),
        "sha256": sha256_file(path),
        "schema_version": PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
        "status": "PASS",
        "pipeline_count": 18,
    }
    if reference != expected:
        raise ExtendedEvaluationError("Prompt-5 deployment evidence binding differs")
    document = read_json(path)
    steering_authorization = _mapping(authorization, "raspberry_pi_deployment_steering")
    if document.get("steering_authority") != steering_authorization:
        raise ExtendedEvaluationError(
            "Prompt-5 deployment steering authority differs from Prompt-6"
        )
    try:
        validate_deployment_evidence_document(
            document,
            schema_version=PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
            prompt_index=5,
            expected_pipeline_ids=FullPipelineMatrix(
                MATRIX_PATH, RUNTIME_CONFIG_PATH
            ).pipeline_ids,
            steering=steering,
        )
    except DeploymentEvidenceError as exc:
        raise ExtendedEvaluationError(
            f"Prompt-5 deployment evidence differs: {exc}"
        ) from exc
    return expected, document


def _deployment_context(plan: Mapping[str, object]) -> dict[str, object]:
    return _mapping(plan, "deployment_context")


def _prompt4_extended_reference(
    context: Mapping[str, object], pipeline_ids: Sequence[str]
) -> dict[str, object]:
    raw = _mapping(context, "prompt4_extended_set")
    path = ensure_c_drive(
        str(raw.get("path") or ""), label="Prompt-4 extended set", must_exist=True
    )
    expected = {
        "path": str(path),
        "sha256": sha256_file(path),
        "mandatory_pipeline_ids": list(raw.get("mandatory_pipeline_ids", [])),
        "additional_challenger_pipeline_ids": list(
            raw.get("additional_challenger_pipeline_ids", [])
        ),
        "extended_pipeline_ids": list(pipeline_ids),
        "pipeline_count": len(pipeline_ids),
    }
    if (
        expected["mandatory_pipeline_ids"]
        + expected["additional_challenger_pipeline_ids"]
        != list(pipeline_ids)
        or len(expected["mandatory_pipeline_ids"]) != 6
        or len(expected["additional_challenger_pipeline_ids"]) > 2
    ):
        raise ExtendedEvaluationError("Prompt-4 extended-set roles differ")
    if raw != expected:
        raise ExtendedEvaluationError("Prompt-4 extended-set reference differs")
    return expected


def _serial_index(
    rows: Sequence[Mapping[str, object]], expected_ids: Sequence[str]
) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for raw in rows:
        pipeline_id = str(raw.get("pipeline_id") or "")
        if not pipeline_id or pipeline_id in result:
            raise ExtendedEvaluationError("serial resource pipeline inventory differs")
        result[pipeline_id] = dict(raw)
    if list(sorted(result)) != list(sorted(expected_ids)) or len(result) != len(
        expected_ids
    ):
        raise ExtendedEvaluationError(
            "serial resource evidence must contain every extended pipeline exactly once"
        )
    return result


def _pipeline_index(
    document: Mapping[str, object], *, expected_ids: Sequence[str] | None
) -> dict[str, dict[str, object]]:
    raw_rows = document.get("pipelines")
    if not isinstance(raw_rows, list):
        raise ExtendedEvaluationError("deployment evidence pipeline rows are absent")
    result: dict[str, dict[str, object]] = {}
    observed: list[str] = []
    for raw in raw_rows:
        row = dict(_as_mapping(raw, "pipeline deployment evidence"))
        pipeline_id = str(row.get("pipeline_id") or "")
        if not pipeline_id or pipeline_id in result:
            raise ExtendedEvaluationError("deployment evidence pipeline IDs differ")
        observed.append(pipeline_id)
        result[pipeline_id] = row
    if expected_ids is not None and observed != list(expected_ids):
        raise ExtendedEvaluationError("deployment evidence pipeline order differs")
    return result


def _validate_component_identity(row: Mapping[str, object], selection: object) -> None:
    expected = {
        "pipeline_id": selection.pipeline_id,
        "asr_alias": selection.asr_alias,
        "asr_component_id": selection.asr.get("component_id"),
        "segmentation_component_id": selection.diarization.get("segmentation_id"),
        "diarization_alias": selection.diarization_alias,
        "diarization_embedding_backend_id": selection.diarization.get(
            "embedding_backend_id"
        ),
        "identity_alias": selection.identity_alias,
        "identity_embedding_backend_id": selection.identity.get("backend_id"),
        "hybrid_label": selection.hybrid_label,
    }
    for key, value in expected.items():
        if row.get(key) != value:
            raise ExtendedEvaluationError(
                f"deployment component identity {key} differs for {selection.pipeline_id}"
            )


def _pipeline_ids(plan: Mapping[str, object]) -> tuple[str, ...]:
    values = tuple(str(item) for item in plan.get("pipeline_ids", []))
    if not values or len(set(values)) != len(values):
        raise ExtendedEvaluationError("Prompt-6 pipeline inventory is invalid")
    return values


def _mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    return dict(_as_mapping(value.get(key), key))


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ExtendedEvaluationError(f"{label} must be an object")
    return value


def _number(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result >= 0.0 else None


__all__ = [
    "build_extended_deployment_evidence",
    "validate_extended_deployment_evidence",
]
