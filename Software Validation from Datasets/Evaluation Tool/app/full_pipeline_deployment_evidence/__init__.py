"""Shared, non-scientific deployment-evidence contracts for Prompts 5--8.

This package deliberately lives outside :mod:`app.full_pipeline`.  The active
Prompt-4 freeze hashes that runtime package, while deployment evidence is an
additive interpretation layer that must not change any scientific execution.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence


STEERING_SCHEMA = "full-pipeline-deployment-steering.v1"
STEERING_ID = "raspberry_pi_compute_module_2gb.v1"
STEERING_STATUS = "DECISION_CONTEXT_ONLY"

TWO_GIB_FEASIBILITY_CLASSES = (
    "LIKELY_2GB_FEASIBLE",
    "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION",
    "HIGH_RISK_FOR_2GB",
    "UNLIKELY_2GB_FEASIBLE",
)
LINUX_ARM64_PORTABILITY_CLASSES = (
    "LINUX_ARM64_READY",
    "LIKELY_PORTABLE",
    "PORT_REQUIRES_WORK",
    "PLATFORM_BLOCKER",
)
DEPLOYMENT_ATTRIBUTE_NAMES = (
    "model_file_size_bytes",
    "loaded_model_memory_bytes",
    "peak_process_rss_bytes",
    "total_pipeline_peak_rss_bytes",
    "simultaneously_resident_neural_model_count",
    "worker_process_count",
    "runtime_environment_count",
    "embedding_dimensions",
    "persistent_enrollment_template_memory_bytes",
    "cache_requirements_bytes",
    "initialization_time_sec",
    "warmup_time_sec",
    "native_onnx_availability",
    "pytorch_dependency",
    "arm_compatibility_status",
    "int8_status",
    "fp16_status",
    "export_status",
    "quantization_readiness",
    "executorch_feasibility",
    "onnx_runtime_export_feasibility",
    "model_instance_sharing_opportunities",
    "embedding_reuse_opportunities",
    "duplicated_feature_extraction",
    "dependency_complexity",
)
RASPBERRY_PI_CANDIDATE_FIELDS = (
    "pipeline_id",
    "asr",
    "segmentation",
    "diarization_embedding",
    "identity_embedding",
    "enrollment_policy",
    "current_desktop_accuracy",
    "wer",
    "der",
    "wrong_known",
    "stranger_false_known",
    "latency",
    "rtf",
    "peak_ram",
    "model_footprint",
    "resident_model_count",
    "export_path",
    "quantization_opportunities",
    "model_sharing_opportunities",
    "arm_runtime_risks",
    "reason_retained",
    "two_gib_feasibility_class",
    "linux_arm64_portability_class",
    "windows_specific_assumptions",
    "linux_arm64_dependency_status",
    "required_platform_replacements",
)
FUTURE_TARGET_HARDWARE_TESTS = (
    "exact_export_parity_validation",
    "optimized_arm_execution",
    "approximately_2gb_ram_constraint",
    "frozen_heldout_regression_suite",
    "real_time_streaming",
    "cpu_and_ram",
    "queue_backlog",
    "dropped_frames",
    "p50_p95_latency",
    "thermal_throttling",
    "30_to_60_minute_sustained_operation",
    "model_startup_and_warmup",
    "power_measurement_when_hardware_permits",
    "final_raspberry_pi_pareto_ranking",
)
FUTURE_LINUX_ARM64_VALIDATION = (
    "actual_arm64_linux_build_and_install",
    "model_loading_and_numerical_parity",
    "linux_audio_capture",
    "worker_and_multiprocessing_behavior",
    "gui_and_runtime_behavior",
    "service_startup_restart_and_recovery",
    "sustained_streaming_on_raspberry_pi_os",
)
EVIDENCE_STATUSES = (
    "MEASURED",
    "DERIVED",
    "UNKNOWN",
    "UNSUPPORTED",
)
MEASUREMENT_CONTEXTS = (
    "WINDOWS_X86_64_DESKTOP",
    "FROZEN_CONFIGURATION",
    "NOT_MEASURED",
)
TWO_GIB_BYTES = 2 * 1024**3


class DeploymentEvidenceError(ValueError):
    """Raised when deployment steering or additive evidence is invalid."""


def sha256_file(path: Path | str) -> str:
    """Return a streaming SHA-256 for one file without importing evaluators."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_deployment_steering(
    path: Path | str,
    *,
    expected_prompt_index: int | None = None,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    """Load and strictly validate the checksum-bound deployment authority.

    Validation is intentionally structural as well as checksum based.  This
    prevents a caller from accidentally accepting an older steering revision
    that lacks platform-portability or explicit-unknown requirements.
    """

    resolved = _c_file(path, label="deployment steering authority")
    actual_sha256 = sha256_file(resolved)
    if expected_sha256 is not None and actual_sha256 != _sha256(
        expected_sha256, "expected deployment steering SHA-256"
    ):
        raise DeploymentEvidenceError("deployment steering SHA-256 differs")
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeploymentEvidenceError(
            f"deployment steering is not valid JSON: {resolved}"
        ) from exc
    if not isinstance(value, Mapping):
        raise DeploymentEvidenceError("deployment steering must be an object")
    steering = dict(value)
    _equal(steering, "schema_version", STEERING_SCHEMA)
    _equal(steering, "steering_id", STEERING_ID)
    _equal(steering, "status", STEERING_STATUS)
    _exact_list(steering, "effective_prompts", [4, 5, 6, 7, 8])
    if (
        expected_prompt_index is not None
        and expected_prompt_index not in steering["effective_prompts"]
    ):
        raise DeploymentEvidenceError(
            f"deployment steering does not authorize Prompt {expected_prompt_index}"
        )
    scientific = _mapping(steering, "scientific_contract")
    expected_scientific = {
        "methodology_changed": False,
        "development_evaluation_firewall_changed": False,
        "frozen_protocols_changed": False,
        "heldout_splits_changed": False,
        "metrics_or_statistics_changed": False,
        "results_may_be_changed_to_favor_deployment": False,
        "prompt4_active_execution_may_be_modified": False,
    }
    if scientific != expected_scientific:
        raise DeploymentEvidenceError("deployment steering scientific contract differs")
    _exact_list(
        steering,
        "two_gib_feasibility_classes",
        list(TWO_GIB_FEASIBILITY_CLASSES),
    )
    _exact_list(
        steering,
        "linux_arm64_portability_classes",
        list(LINUX_ARM64_PORTABILITY_CLASSES),
    )
    _exact_list(steering, "deployment_attributes", list(DEPLOYMENT_ATTRIBUTE_NAMES))
    _exact_list(
        steering,
        "raspberry_pi_candidate_fields",
        list(RASPBERRY_PI_CANDIDATE_FIELDS),
    )
    _exact_list(
        steering,
        "future_target_hardware_tests",
        list(FUTURE_TARGET_HARDWARE_TESTS),
    )
    _exact_list(
        steering,
        "future_linux_arm64_validation",
        list(FUTURE_LINUX_ARM64_VALIDATION),
    )
    policy = _mapping(steering, "attribute_evidence_policy")
    expected_policy = {
        "measure_when_existing_prompt_scope_supports_it": True,
        "modify_models_only_to_measure": False,
        "unknown_or_unsupported_must_be_explicit": True,
        "desktop_measurement_must_not_be_relabelled_as_arm_measurement": True,
    }
    if policy != expected_policy:
        raise DeploymentEvidenceError("deployment attribute evidence policy differs")
    platform = _mapping(steering, "platform_context")
    required_platform = {
        "current_evaluation_os": "WINDOWS",
        "current_evaluation_architecture": "X86_64",
        "future_target_os_family": "LINUX_DEBIAN_RASPBERRY_PI_OS",
        "future_target_architecture": "ARM64",
        "platform_portability_is_separate_from_desktop_scientific_rank": True,
        "flag_windows_specific_assumptions": True,
        "record_linux_arm64_dependency_support": True,
        "record_required_export_or_replacement_libraries": True,
    }
    for key, expected in required_platform.items():
        if platform.get(key) != expected:
            raise DeploymentEvidenceError(f"deployment platform_context.{key} differs")
    _exact_list(
        platform,
        "linux_differences_to_audit",
        [
            "multiprocessing",
            "filesystem_paths",
            "permissions",
            "audio_capture",
            "service_startup",
        ],
    )
    interpretation = _mapping(steering, "interpretation")
    for key in (
        "desktop_rtf_equals_pi_rtf",
        "desktop_winner_equals_pi_winner",
        "universal_within_one_percent_equivalence_rule",
    ):
        if interpretation.get(key) is not False:
            raise DeploymentEvidenceError(f"deployment interpretation.{key} differs")
    if (
        interpretation.get(
            "two_gib_is_a_design_constraint_not_a_prompts_4_to_6_hard_filter"
        )
        is not True
    ):
        raise DeploymentEvidenceError("deployment design-constraint boundary differs")
    matrix_policy = _mapping(steering, "matrix_and_extended_set_policy")
    for key in (
        "prompt4_all18_unchanged",
        "prompt5_all18_unchanged",
        "prompt6_predeclared_membership_unchanged_after_heldout",
        "mandatory_h2_h4_h5_anchors_unchanged",
    ):
        if matrix_policy.get(key) is not True:
            raise DeploymentEvidenceError(f"deployment matrix policy {key} differs")
    return steering


def steering_ref(path: Path | str, steering: Mapping[str, object]) -> dict[str, object]:
    """Build the immutable reference embedded in stage authorization/results."""

    resolved = _c_file(path, label="deployment steering authority")
    if (
        steering.get("schema_version") != STEERING_SCHEMA
        or steering.get("steering_id") != STEERING_ID
    ):
        raise DeploymentEvidenceError(
            "cannot reference unvalidated deployment steering"
        )
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "schema_version": STEERING_SCHEMA,
        "steering_id": STEERING_ID,
        "status": STEERING_STATUS,
    }


def evidence(
    value: object,
    *,
    unit: str,
    evidence_status: str,
    reason_code: str,
    measurement_context: str,
    source_path: Path | str | None = None,
    source_sha256: str | None = None,
    source_field: str | None = None,
    desktop_measurement: bool = False,
    arm_measurement: bool = False,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create one explicit evidence cell shared by P5/P6/P7/P8 artifacts."""

    if evidence_status not in EVIDENCE_STATUSES:
        raise DeploymentEvidenceError(f"invalid evidence_status: {evidence_status}")
    if measurement_context not in MEASUREMENT_CONTEXTS:
        raise DeploymentEvidenceError(
            f"invalid measurement_context: {measurement_context}"
        )
    if not str(unit).strip() or not str(reason_code).strip():
        raise DeploymentEvidenceError("evidence unit and reason_code are required")
    if evidence_status in {"UNKNOWN", "UNSUPPORTED"} and value is not None:
        raise DeploymentEvidenceError(
            f"{evidence_status} evidence must use an explicit null value"
        )
    if evidence_status in {"MEASURED", "DERIVED"} and value is None:
        raise DeploymentEvidenceError(f"{evidence_status} evidence requires a value")
    if arm_measurement:
        raise DeploymentEvidenceError(
            "Prompts 5--8 desktop evidence must not be relabelled as ARM measurement"
        )
    if desktop_measurement and measurement_context != "WINDOWS_X86_64_DESKTOP":
        raise DeploymentEvidenceError(
            "desktop_measurement requires WINDOWS_X86_64_DESKTOP context"
        )
    resolved_source: str | None = None
    if source_path is not None:
        resolved = _c_file(source_path, label="deployment evidence source")
        resolved_source = str(resolved)
        actual = sha256_file(resolved)
        if source_sha256 is not None and actual != _sha256(
            source_sha256, "deployment evidence source SHA-256"
        ):
            raise DeploymentEvidenceError("deployment evidence source SHA-256 differs")
        source_sha256 = actual
    elif source_sha256 is not None:
        source_sha256 = _sha256(source_sha256, "deployment evidence source SHA-256")
    result: dict[str, object] = {
        "value": value,
        "unit": str(unit),
        "evidence_status": evidence_status,
        "reason_code": str(reason_code),
        "measurement_context": measurement_context,
        "desktop_measurement": bool(desktop_measurement),
        "arm_measurement": False,
        "source_path": resolved_source,
        "source_sha256": source_sha256,
        "source_field": str(source_field) if source_field is not None else None,
    }
    if details is not None:
        result["details"] = dict(details)
    validate_evidence(result)
    return result


def unknown_evidence(
    *,
    unit: str,
    reason_code: str,
    source_path: Path | str | None = None,
    source_sha256: str | None = None,
    source_field: str | None = None,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a structured UNKNOWN cell rather than guessing a value."""

    return evidence(
        None,
        unit=unit,
        evidence_status="UNKNOWN",
        reason_code=reason_code,
        measurement_context="NOT_MEASURED",
        source_path=source_path,
        source_sha256=source_sha256,
        source_field=source_field,
        details=details,
    )


def unsupported_evidence(
    *,
    unit: str,
    reason_code: str,
    source_path: Path | str | None = None,
    source_sha256: str | None = None,
    source_field: str | None = None,
    details: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Create a structured UNSUPPORTED cell for an absent measurement surface."""

    return evidence(
        None,
        unit=unit,
        evidence_status="UNSUPPORTED",
        reason_code=reason_code,
        measurement_context="NOT_MEASURED",
        source_path=source_path,
        source_sha256=source_sha256,
        source_field=source_field,
        details=details,
    )


def validate_evidence(value: Mapping[str, object]) -> dict[str, object]:
    """Validate and return a normalized structured evidence cell."""

    required = {
        "value",
        "unit",
        "evidence_status",
        "reason_code",
        "measurement_context",
        "desktop_measurement",
        "arm_measurement",
        "source_path",
        "source_sha256",
        "source_field",
    }
    missing = required - set(value)
    if missing:
        raise DeploymentEvidenceError(
            "evidence cell lacks fields: " + ", ".join(sorted(missing))
        )
    status = str(value.get("evidence_status") or "")
    if status not in EVIDENCE_STATUSES:
        raise DeploymentEvidenceError(f"invalid evidence status: {status}")
    context = str(value.get("measurement_context") or "")
    if context not in MEASUREMENT_CONTEXTS:
        raise DeploymentEvidenceError(f"invalid evidence context: {context}")
    if status in {"UNKNOWN", "UNSUPPORTED"} and value.get("value") is not None:
        raise DeploymentEvidenceError(f"{status} evidence value must be null")
    if status in {"MEASURED", "DERIVED"} and value.get("value") is None:
        raise DeploymentEvidenceError(f"{status} evidence value is missing")
    if value.get("arm_measurement") is not False:
        raise DeploymentEvidenceError("desktop evidence is incorrectly labelled as ARM")
    if value.get("desktop_measurement") is True and context != "WINDOWS_X86_64_DESKTOP":
        raise DeploymentEvidenceError("desktop evidence context differs")
    source_path = value.get("source_path")
    source_sha256 = value.get("source_sha256")
    if source_path is not None and not str(source_path).strip():
        raise DeploymentEvidenceError("evidence source_path is empty")
    if source_sha256 is not None:
        _sha256(str(source_sha256), "evidence source SHA-256")
    if source_path is not None:
        resolved_source = _c_file(source_path, label="deployment evidence source")
        if (
            source_sha256 is None
            or sha256_file(resolved_source) != str(source_sha256).casefold()
        ):
            raise DeploymentEvidenceError("deployment evidence source SHA-256 differs")
    return dict(value)


def classify_two_gib(
    total_pipeline_peak_rss_bytes: Mapping[str, object] | int | float | None,
    *,
    mandatory_resident_lower_bound_bytes: Mapping[str, object]
    | int
    | float
    | None = None,
    target_hardware_validated: bool = False,
) -> dict[str, object]:
    """Conservatively classify 2-GiB feasibility without predicting Pi behavior."""

    rss = _numeric_evidence(total_pipeline_peak_rss_bytes)
    mandatory = _numeric_evidence(mandatory_resident_lower_bound_bytes)
    if target_hardware_validated:
        raise DeploymentEvidenceError(
            "target_hardware_validated cannot be asserted by this desktop program"
        )
    evidence_status = "DERIVED"
    if mandatory is not None and mandatory >= TWO_GIB_BYTES:
        class_name = "UNLIKELY_2GB_FEASIBLE"
        rationale = "MANDATORY_RESIDENT_LOWER_BOUND_AT_OR_ABOVE_2GIB"
    elif rss is None:
        class_name = "HIGH_RISK_FOR_2GB"
        rationale = "TOTAL_PIPELINE_PEAK_RSS_UNKNOWN"
        evidence_status = "UNKNOWN"
    elif rss >= TWO_GIB_BYTES:
        class_name = "HIGH_RISK_FOR_2GB"
        rationale = "DESKTOP_TOTAL_PIPELINE_PEAK_RSS_AT_OR_ABOVE_2GIB"
    else:
        class_name = "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION"
        rationale = "DESKTOP_RSS_BELOW_2GIB_ARM_VALIDATION_STILL_REQUIRED"
    return {
        "class": class_name,
        "evidence_status": evidence_status,
        "rationale_code": rationale,
        "input_evidence": [
            "total_pipeline_peak_rss_bytes",
            "mandatory_resident_lower_bound_bytes",
        ],
        "desktop_only": True,
        "arm_measurement": False,
        "used_as_filter": False,
        "final_target_hardware_determination": False,
    }


def classify_linux_arm64(
    *,
    windows_specific_assumptions: Mapping[str, object],
    linux_arm64_dependency_status: Mapping[str, object],
    required_platform_replacements: Mapping[str, object],
    actual_arm64_validation: bool = False,
    explicit_platform_blocker: bool = False,
) -> dict[str, object]:
    """Classify portability separately from desktop science and resource rank."""

    assumptions = validate_evidence(windows_specific_assumptions)
    dependencies = validate_evidence(linux_arm64_dependency_status)
    replacements = validate_evidence(required_platform_replacements)
    if actual_arm64_validation:
        raise DeploymentEvidenceError(
            "actual ARM64 validation cannot be asserted by this desktop program"
        )
    if explicit_platform_blocker:
        class_name = "PLATFORM_BLOCKER"
        rationale = "EXPLICIT_LINUX_ARM64_PLATFORM_BLOCKER"
        evidence_status = "DERIVED"
    elif dependencies["evidence_status"] in {"UNKNOWN", "UNSUPPORTED"}:
        class_name = "PORT_REQUIRES_WORK"
        rationale = "LINUX_ARM64_DEPENDENCY_SUPPORT_NOT_ESTABLISHED"
        evidence_status = "UNKNOWN"
    elif _nonempty_value(replacements.get("value")) or _nonempty_value(
        assumptions.get("value")
    ):
        class_name = "PORT_REQUIRES_WORK"
        rationale = "WINDOWS_ASSUMPTIONS_OR_PLATFORM_REPLACEMENTS_REMAIN"
        evidence_status = "DERIVED"
    else:
        class_name = "LIKELY_PORTABLE"
        rationale = "DECLARED_DEPENDENCIES_PORTABLE_ARM64_TEST_STILL_REQUIRED"
        evidence_status = "DERIVED"
    return {
        "class": class_name,
        "evidence_status": evidence_status,
        "rationale_code": rationale,
        "input_evidence": [
            "windows_specific_assumptions",
            "linux_arm64_dependency_status",
            "required_platform_replacements",
        ],
        "separate_from_desktop_scientific_rank": True,
        "desktop_only": True,
        "arm_measurement": False,
        "actual_arm64_validation_completed": False,
        "used_as_filter": False,
        "final_target_hardware_determination": False,
    }


def validate_deployment_attributes(
    attributes: Mapping[str, object], steering: Mapping[str, object]
) -> dict[str, object]:
    """Require exactly one structured evidence cell for all 25 attributes."""

    expected = tuple(str(item) for item in steering.get("deployment_attributes", []))
    if expected != DEPLOYMENT_ATTRIBUTE_NAMES:
        raise DeploymentEvidenceError("unvalidated deployment attribute authority")
    if len(attributes) != len(expected) or set(attributes) != set(expected):
        raise DeploymentEvidenceError(
            "deployment attributes must use exact steering membership and count"
        )
    return {
        name: validate_evidence(_as_mapping(attributes[name], name))
        for name in expected
    }


def validate_deployment_evidence_document(
    document: Mapping[str, object],
    *,
    schema_version: str,
    prompt_index: int,
    expected_pipeline_ids: Sequence[str],
    steering: Mapping[str, object],
) -> dict[str, object]:
    """Validate the common all-pipeline deployment-evidence document shape."""

    if document.get("schema_version") != schema_version:
        raise DeploymentEvidenceError("deployment evidence schema differs")
    if int(document.get("prompt_index") or -1) != prompt_index:
        raise DeploymentEvidenceError("deployment evidence prompt index differs")
    if document.get("status") != "PASS":
        raise DeploymentEvidenceError("deployment evidence status is not PASS")
    expected_ids = [str(item) for item in expected_pipeline_ids]
    if document.get("pipeline_ids") != expected_ids:
        raise DeploymentEvidenceError("deployment evidence pipeline order differs")
    if int(document.get("pipeline_count") or -1) != len(expected_ids):
        raise DeploymentEvidenceError("deployment evidence pipeline count differs")
    if document.get("deployment_attribute_names") != list(DEPLOYMENT_ATTRIBUTE_NAMES):
        raise DeploymentEvidenceError("deployment evidence attribute names differ")
    if document.get("two_gib_feasibility_classes") != list(TWO_GIB_FEASIBILITY_CLASSES):
        raise DeploymentEvidenceError("deployment evidence 2-GiB classes differ")
    if document.get("linux_arm64_portability_classes") != list(
        LINUX_ARM64_PORTABILITY_CLASSES
    ):
        raise DeploymentEvidenceError("deployment evidence portability classes differ")
    authority = _mapping(document, "steering_authority")
    if (
        authority.get("schema_version") != STEERING_SCHEMA
        or authority.get("steering_id") != STEERING_ID
        or authority.get("status") != STEERING_STATUS
    ):
        raise DeploymentEvidenceError("deployment evidence steering identity differs")
    authority_path = _c_file(
        str(authority.get("path") or ""), label="deployment steering authority"
    )
    authority_sha256 = _sha256(
        str(authority.get("sha256") or ""), "steering authority SHA-256"
    )
    if sha256_file(authority_path) != authority_sha256:
        raise DeploymentEvidenceError("deployment steering reference is invalid")
    input_binding = _mapping(document, "input_binding")
    expected_binding = {
        "deployment_steering_path": authority.get("path"),
        "deployment_steering_sha256": authority.get("sha256"),
        "deployment_steering_schema_version": authority.get("schema_version"),
        "deployment_steering_id": authority.get("steering_id"),
        "deployment_steering_status": authority.get("status"),
    }
    for key, expected in expected_binding.items():
        if input_binding.get(key) != expected:
            raise DeploymentEvidenceError(
                f"deployment evidence input binding {key} differs"
            )
    if document.get("raspberry_pi_candidate_fields") != list(
        RASPBERRY_PI_CANDIDATE_FIELDS
    ):
        raise DeploymentEvidenceError("deployment evidence candidate fields differ")
    if document.get("future_target_hardware_tests") != list(
        FUTURE_TARGET_HARDWARE_TESTS
    ):
        raise DeploymentEvidenceError(
            "deployment evidence future hardware tests differ"
        )
    if document.get("future_linux_arm64_validation") != list(
        FUTURE_LINUX_ARM64_VALIDATION
    ):
        raise DeploymentEvidenceError("deployment evidence future Linux tests differ")
    rows = document.get("pipelines")
    if not isinstance(rows, list) or len(rows) != len(expected_ids):
        raise DeploymentEvidenceError("deployment evidence rows differ")
    seen: list[str] = []
    for raw in rows:
        row = _as_mapping(raw, "pipeline deployment evidence")
        pipeline_id = str(row.get("pipeline_id") or "")
        seen.append(pipeline_id)
        validate_deployment_attributes(_mapping(row, "deployment_attributes"), steering)
        two_gib = _mapping(row, "two_gib_feasibility")
        if two_gib.get("class") not in TWO_GIB_FEASIBILITY_CLASSES:
            raise DeploymentEvidenceError(f"invalid 2-GiB class for {pipeline_id}")
        if two_gib.get("evidence_status") not in EVIDENCE_STATUSES:
            raise DeploymentEvidenceError(
                f"invalid 2-GiB evidence status for {pipeline_id}"
            )
        portability = _mapping(row, "linux_arm64_portability")
        if portability.get("class") not in LINUX_ARM64_PORTABILITY_CLASSES:
            raise DeploymentEvidenceError(
                f"invalid Linux ARM64 portability class for {pipeline_id}"
            )
        if portability.get("evidence_status") not in EVIDENCE_STATUSES:
            raise DeploymentEvidenceError(
                f"invalid portability evidence status for {pipeline_id}"
            )
        if portability.get("separate_from_desktop_scientific_rank") is not True:
            raise DeploymentEvidenceError(
                f"portability/scientific-rank boundary missing for {pipeline_id}"
            )
        for key in (
            "windows_specific_assumptions",
            "linux_arm64_dependency_status",
            "required_platform_replacements",
        ):
            validate_evidence(_mapping(row, key))
        if row.get("used_to_filter_pipeline") is not False:
            raise DeploymentEvidenceError(
                f"deployment evidence filtered pipeline {pipeline_id}"
            )
        if (
            two_gib.get("used_as_filter") is not False
            or portability.get("used_as_filter") is not False
        ):
            raise DeploymentEvidenceError(
                f"deployment class used as a Prompt-{prompt_index} filter: {pipeline_id}"
            )
        if (
            two_gib.get("arm_measurement") is not False
            or portability.get("arm_measurement") is not False
        ):
            raise DeploymentEvidenceError(
                f"desktop evidence relabelled as ARM for {pipeline_id}"
            )
    if seen != expected_ids:
        raise DeploymentEvidenceError("deployment evidence row order differs")
    if document.get("scientific_firewall") != {
        "scientific_methodology_changed": False,
        "pipeline_membership_changed": False,
        "heldout_selection_or_retuning_performed": False,
        "deployment_evidence_used_as_filter": False,
        "desktop_rank_used_as_final_arm_rank": False,
    }:
        raise DeploymentEvidenceError("deployment evidence scientific firewall differs")
    return dict(document)


def _numeric_evidence(value: Mapping[str, object] | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, Mapping):
        validated = validate_evidence(value)
        raw = validated.get("value")
    else:
        raw = value
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise DeploymentEvidenceError("numeric feasibility input is not numeric")
    if raw < 0:
        raise DeploymentEvidenceError("numeric feasibility input is negative")
    return float(raw)


def _nonempty_value(value: object) -> bool:
    if value is None or value is False or value == "":
        return False
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _mapping(value: Mapping[str, object], key: str) -> dict[str, object]:
    return dict(_as_mapping(value.get(key), key))


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise DeploymentEvidenceError(f"{label} must be an object")
    return value


def _equal(value: Mapping[str, object], key: str, expected: object) -> None:
    if value.get(key) != expected:
        raise DeploymentEvidenceError(f"deployment steering {key} differs")


def _exact_list(value: Mapping[str, object], key: str, expected: list[object]) -> None:
    if value.get(key) != expected:
        raise DeploymentEvidenceError(f"deployment steering {key} differs")


def _sha256(value: str, label: str) -> str:
    normalized = str(value).casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise DeploymentEvidenceError(f"{label} is not a SHA-256 hex digest")
    return normalized


def _c_file(path: Path | str, *, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if resolved.drive.casefold() != "c:":
        raise DeploymentEvidenceError(f"{label} must remain on C: {resolved}")
    if not resolved.is_file():
        raise DeploymentEvidenceError(f"{label} is missing: {resolved}")
    return resolved


__all__ = [
    "DEPLOYMENT_ATTRIBUTE_NAMES",
    "DeploymentEvidenceError",
    "EVIDENCE_STATUSES",
    "FUTURE_LINUX_ARM64_VALIDATION",
    "FUTURE_TARGET_HARDWARE_TESTS",
    "LINUX_ARM64_PORTABILITY_CLASSES",
    "MEASUREMENT_CONTEXTS",
    "RASPBERRY_PI_CANDIDATE_FIELDS",
    "STEERING_ID",
    "STEERING_SCHEMA",
    "STEERING_STATUS",
    "TWO_GIB_FEASIBILITY_CLASSES",
    "classify_linux_arm64",
    "classify_two_gib",
    "evidence",
    "load_deployment_steering",
    "sha256_file",
    "steering_ref",
    "unknown_evidence",
    "unsupported_evidence",
    "validate_deployment_attributes",
    "validate_deployment_evidence_document",
    "validate_evidence",
]
