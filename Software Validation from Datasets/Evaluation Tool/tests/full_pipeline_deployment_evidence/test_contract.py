from __future__ import annotations

from pathlib import Path
import json

import pytest

from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    DeploymentEvidenceError,
    FUTURE_LINUX_ARM64_VALIDATION,
    LINUX_ARM64_PORTABILITY_CLASSES,
    TWO_GIB_FEASIBILITY_CLASSES,
    classify_linux_arm64,
    classify_two_gib,
    evidence,
    load_deployment_steering,
    unknown_evidence,
    validate_deployment_attributes,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
STEERING = (
    TOOL_ROOT / "runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json"
)
EXPECTED_SHA256 = "f8a228765b29e3af5cd88dbe0be5b10fd6fbe525ac5806f96ce2f20f0a7af9a4"


def test_authoritative_steering_exact_contract() -> None:
    value = load_deployment_steering(
        STEERING, expected_prompt_index=5, expected_sha256=EXPECTED_SHA256
    )
    assert tuple(value["deployment_attributes"]) == DEPLOYMENT_ATTRIBUTE_NAMES
    assert tuple(value["two_gib_feasibility_classes"]) == TWO_GIB_FEASIBILITY_CLASSES
    assert (
        tuple(value["linux_arm64_portability_classes"])
        == LINUX_ARM64_PORTABILITY_CLASSES
    )
    assert (
        tuple(value["future_linux_arm64_validation"]) == FUTURE_LINUX_ARM64_VALIDATION
    )


def test_desktop_rss_never_becomes_likely_or_arm_measurement() -> None:
    rss = evidence(
        900_000_000,
        unit="bytes",
        evidence_status="MEASURED",
        reason_code="SERIAL_RESOURCE_SAMPLE",
        measurement_context="WINDOWS_X86_64_DESKTOP",
        desktop_measurement=True,
    )
    result = classify_two_gib(rss)
    assert result["class"] == "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION"
    assert result["arm_measurement"] is False
    assert result["used_as_filter"] is False


def test_missing_rss_is_explicit_high_risk_uncertainty() -> None:
    result = classify_two_gib(
        unknown_evidence(unit="bytes", reason_code="NO_RESOURCE_SURFACE")
    )
    assert result["class"] == "HIGH_RISK_FOR_2GB"
    assert result["evidence_status"] == "UNKNOWN"


def test_portability_unknown_requires_work_not_ready() -> None:
    unknown = unknown_evidence(unit="structured", reason_code="NOT_TESTED_ON_ARM64")
    result = classify_linux_arm64(
        windows_specific_assumptions=unknown,
        linux_arm64_dependency_status=unknown,
        required_platform_replacements=unknown,
    )
    assert result["class"] == "PORT_REQUIRES_WORK"
    assert result["actual_arm64_validation_completed"] is False
    assert result["separate_from_desktop_scientific_rank"] is True


def test_arm_measurement_relabel_is_rejected() -> None:
    with pytest.raises(DeploymentEvidenceError, match="must not be relabelled"):
        evidence(
            1,
            unit="count",
            evidence_status="MEASURED",
            reason_code="INVALID",
            measurement_context="WINDOWS_X86_64_DESKTOP",
            desktop_measurement=True,
            arm_measurement=True,
        )


def test_deployment_attributes_survive_sorted_json_roundtrip() -> None:
    steering = load_deployment_steering(
        STEERING, expected_prompt_index=5, expected_sha256=EXPECTED_SHA256
    )
    cell = unknown_evidence(unit="status", reason_code="MODEL_FREE_TEST")
    attributes = {name: dict(cell) for name in DEPLOYMENT_ATTRIBUTE_NAMES}
    round_tripped = json.loads(json.dumps(attributes, sort_keys=True))

    validated = validate_deployment_attributes(round_tripped, steering)

    assert list(validated) == list(DEPLOYMENT_ATTRIBUTE_NAMES)
