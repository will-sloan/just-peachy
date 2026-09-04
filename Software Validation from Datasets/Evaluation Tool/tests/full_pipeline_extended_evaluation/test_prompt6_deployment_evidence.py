from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    FUTURE_LINUX_ARM64_VALIDATION,
    FUTURE_TARGET_HARDWARE_TESTS,
    LINUX_ARM64_PORTABILITY_CLASSES,
    RASPBERRY_PI_CANDIDATE_FIELDS,
    TWO_GIB_FEASIBILITY_CLASSES,
    classify_linux_arm64,
    classify_two_gib,
    load_deployment_steering,
    steering_ref,
    unknown_evidence,
)
from app.full_pipeline_evaluation.planning import MATRIX_PATH, RUNTIME_CONFIG_PATH
from app.full_pipeline_extended_evaluation import (
    DEFAULT_PI_DEPLOYMENT_STEERING,
    MANDATORY_ANCHORS,
    PI_DEPLOYMENT_STEERING_SHA256,
    PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
    PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA,
    TOOL_ROOT,
)
from app.full_pipeline_extended_evaluation.deployment import (
    build_extended_deployment_evidence,
    validate_extended_deployment_evidence,
)
from app.full_pipeline_extended_evaluation.gate import (
    _find_prompt5_deployment_evidence,
)
from app.full_pipeline_extended_evaluation.io import sha256_file


def _unknown_attributes() -> dict[str, object]:
    return {
        name: unknown_evidence(
            unit="unspecified",
            reason_code="SYNTHETIC_MODEL_FREE_TEST_NO_MEASUREMENT",
        )
        for name in DEPLOYMENT_ATTRIBUTE_NAMES
    }


def _platform_cells() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return (
        unknown_evidence(
            unit="assumptions",
            reason_code="SYNTHETIC_WINDOWS_ASSUMPTIONS_NOT_AUDITED",
        ),
        unknown_evidence(
            unit="dependency_status",
            reason_code="SYNTHETIC_ARM64_DEPENDENCIES_NOT_AUDITED",
        ),
        unknown_evidence(
            unit="replacements",
            reason_code="SYNTHETIC_PLATFORM_REPLACEMENTS_NOT_AUDITED",
        ),
    )


def _prompt5_document(steering: dict[str, object]) -> dict[str, object]:
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    authority = steering_ref(DEFAULT_PI_DEPLOYMENT_STEERING, steering)
    rows: list[dict[str, object]] = []
    for pipeline_id in matrix.pipeline_ids:
        selection = matrix.resolve(pipeline_id)
        assumptions, dependencies, replacements = _platform_cells()
        rows.append(
            {
                "pipeline_id": pipeline_id,
                "asr_alias": selection.asr_alias,
                "asr_component_id": selection.asr.get("component_id"),
                "segmentation_component_id": selection.diarization.get(
                    "segmentation_id"
                ),
                "diarization_alias": selection.diarization_alias,
                "diarization_embedding_backend_id": selection.diarization.get(
                    "embedding_backend_id"
                ),
                "identity_alias": selection.identity_alias,
                "identity_embedding_backend_id": selection.identity.get("backend_id"),
                "hybrid_label": selection.hybrid_label,
                "deployment_attributes": _unknown_attributes(),
                "desktop_resource_context": {
                    "status": "NOT_MEASURED_IN_SYNTHETIC_TEST"
                },
                "two_gib_feasibility": classify_two_gib(None),
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
    return {
        "schema_version": PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
        "prompt_index": 5,
        "status": "PASS",
        "pipeline_ids": list(matrix.pipeline_ids),
        "pipeline_count": len(matrix.pipeline_ids),
        "deployment_attribute_names": list(DEPLOYMENT_ATTRIBUTE_NAMES),
        "two_gib_feasibility_classes": list(TWO_GIB_FEASIBILITY_CLASSES),
        "linux_arm64_portability_classes": list(LINUX_ARM64_PORTABILITY_CLASSES),
        "raspberry_pi_candidate_fields": list(RASPBERRY_PI_CANDIDATE_FIELDS),
        "future_target_hardware_tests": list(FUTURE_TARGET_HARDWARE_TESTS),
        "future_linux_arm64_validation": list(FUTURE_LINUX_ARM64_VALIDATION),
        "steering_authority": authority,
        "input_binding": {
            "deployment_steering_path": authority["path"],
            "deployment_steering_sha256": authority["sha256"],
            "deployment_steering_schema_version": authority["schema_version"],
            "deployment_steering_id": authority["steering_id"],
            "deployment_steering_status": authority["status"],
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


def _inputs(
    tmp_path: Path,
) -> tuple[dict[str, object], dict[str, object], Path, list[dict[str, object]]]:
    steering = load_deployment_steering(
        DEFAULT_PI_DEPLOYMENT_STEERING,
        expected_prompt_index=6,
        expected_sha256=PI_DEPLOYMENT_STEERING_SHA256,
    )
    prompt5_path = tmp_path / "all18_deployment_evidence.json"
    prompt5_path.write_text(
        json.dumps(_prompt5_document(steering), sort_keys=True), encoding="utf-8"
    )
    extended_path = tmp_path / "extended_set.yaml"
    extended_path.write_text(
        "extended_pipeline_ids:\n"
        + "".join(f"  - {pipeline_id}\n" for pipeline_id in MANDATORY_ANCHORS),
        encoding="utf-8",
    )
    prompt5_ref = {
        "path": str(prompt5_path.resolve()),
        "sha256": sha256_file(prompt5_path),
        "schema_version": PROMPT5_DEPLOYMENT_EVIDENCE_SCHEMA,
        "status": "PASS",
        "pipeline_count": 18,
    }
    steering_authority = steering_ref(DEFAULT_PI_DEPLOYMENT_STEERING, steering)
    extended_ref = {
        "path": str(extended_path.resolve()),
        "sha256": sha256_file(extended_path),
        "mandatory_pipeline_ids": list(MANDATORY_ANCHORS),
        "additional_challenger_pipeline_ids": [],
        "extended_pipeline_ids": list(MANDATORY_ANCHORS),
        "pipeline_count": len(MANDATORY_ANCHORS),
    }
    authorization = {
        "raspberry_pi_deployment_steering": steering_authority,
        "prompt5_deployment_evidence": prompt5_ref,
    }
    plan = {
        "pipeline_ids": list(MANDATORY_ANCHORS),
        "deployment_context": {
            "raspberry_pi_deployment_steering": steering_authority,
            "prompt5_deployment_evidence": prompt5_ref,
            "prompt4_extended_set": extended_ref,
            "predeclared_membership_unchanged_after_heldout": True,
            "deployment_evidence_used_as_filter": False,
        },
    }
    serial_path = tmp_path / "serial_resources.csv"
    serial_path.write_text("pipeline_id,job_state,peak_rss_bytes\n", encoding="utf-8")
    serial_rows = [
        {
            "pipeline_id": pipeline_id,
            "job_id": f"resource-{index}",
            "job_state": "complete",
            "explicit_failure": False,
            "model_bytes": 100_000_000 + index,
            "peak_rss_bytes": 1_000_000_000 + index,
            "cache_bytes": 20_000_000 + index,
            "model_startup_sec": 1.5,
            "warmup_duration_sec": 60.0,
            "total_rtf_including_startup_and_warmup": 0.75,
            "component_rtf_measurement_status": (
                "COMPUTED_FROM_MEASURED_PROCESSING_AUDIO_PAIRS"
            ),
            "deadline_miss_count": 0,
            "dropped_frames": 0,
        }
        for index, pipeline_id in enumerate(MANDATORY_ANCHORS)
    ]
    return plan, authorization, serial_path, serial_rows


def test_extended_deployment_evidence_preserves_frozen_membership_and_desktop_boundary(
    tmp_path: Path,
) -> None:
    plan, authorization, serial_path, serial_rows = _inputs(tmp_path)
    document = build_extended_deployment_evidence(
        plan=plan,
        authorization=authorization,
        serial_resource_rows=serial_rows,
        serial_resource_path=serial_path,
    )

    assert document["schema_version"] == PROMPT6_DEPLOYMENT_EVIDENCE_SCHEMA
    assert document["pipeline_ids"] == list(MANDATORY_ANCHORS)
    assert document["extended_pipeline_ids"] == list(MANDATORY_ANCHORS)
    assert document["scientific_firewall"] == {
        "scientific_methodology_changed": False,
        "pipeline_membership_changed": False,
        "heldout_selection_or_retuning_performed": False,
        "deployment_evidence_used_as_filter": False,
        "desktop_rank_used_as_final_arm_rank": False,
    }
    assert all(row["used_to_filter_pipeline"] is False for row in document["pipelines"])
    assert all(
        row["desktop_resource_context"]["arm_measurement"] is False
        and row["desktop_resource_context"]["resource_concurrency"] == 1
        for row in document["pipelines"]
    )
    assert all(
        set(row["deployment_attributes"]) == set(DEPLOYMENT_ATTRIBUTE_NAMES)
        for row in document["pipelines"]
    )
    assert all(
        row["deployment_attributes"]["total_pipeline_peak_rss_bytes"]["evidence_status"]
        == "MEASURED"
        for row in document["pipelines"]
    )
    assert all(
        row["linux_arm64_portability"]["class"] == "PORT_REQUIRES_WORK"
        for row in document["pipelines"]
    )
    assert document["raspberry_pi_candidate_fields"] == list(
        RASPBERRY_PI_CANDIDATE_FIELDS
    )
    assert document["future_target_hardware_tests"] == list(
        FUTURE_TARGET_HARDWARE_TESTS
    )
    assert document["future_linux_arm64_validation"] == list(
        FUTURE_LINUX_ARM64_VALIDATION
    )


def test_extended_deployment_evidence_rejects_tamper_and_membership_leakage(
    tmp_path: Path,
) -> None:
    plan, authorization, serial_path, serial_rows = _inputs(tmp_path)
    document = build_extended_deployment_evidence(
        plan=plan,
        authorization=authorization,
        serial_resource_rows=serial_rows,
        serial_resource_path=serial_path,
    )

    tampered = copy.deepcopy(document)
    tampered["pipelines"][0]["used_to_filter_pipeline"] = True
    with pytest.raises(Exception, match="filtered pipeline"):
        validate_extended_deployment_evidence(
            tampered,
            plan=plan,
            authorization=authorization,
            serial_resource_path=serial_path,
        )

    changed_plan = copy.deepcopy(plan)
    changed_plan["pipeline_ids"] = list(MANDATORY_ANCHORS[:-1])
    with pytest.raises(Exception, match="pipeline order differs"):
        validate_extended_deployment_evidence(
            document,
            plan=changed_plan,
            authorization=authorization,
            serial_resource_path=serial_path,
        )

    changed_authorization = copy.deepcopy(authorization)
    changed_authorization["raspberry_pi_deployment_steering"]["sha256"] = "0" * 64
    with pytest.raises(Exception, match="steering authorization differs"):
        validate_extended_deployment_evidence(
            document,
            plan=plan,
            authorization=changed_authorization,
            serial_resource_path=serial_path,
        )

    prompt5_path = Path(authorization["prompt5_deployment_evidence"]["path"])
    prompt5_path.write_text(prompt5_path.read_text(encoding="utf-8") + "\n")
    with pytest.raises(Exception, match="binding differs"):
        validate_extended_deployment_evidence(
            document,
            plan=plan,
            authorization=authorization,
            serial_resource_path=serial_path,
        )


def test_prompt5_deployment_artifact_discovery_is_exact_and_direct(
    tmp_path: Path,
) -> None:
    exact = tmp_path / "all18_deployment_evidence.json"
    exact.write_text("{}", encoding="utf-8")
    unrelated = tmp_path / "all18_identity.csv"
    unrelated.write_text("", encoding="utf-8")
    assert _find_prompt5_deployment_evidence((unrelated, exact)) == exact
    duplicate = tmp_path / "nested" / "all18_deployment_evidence.json"
    duplicate.parent.mkdir()
    duplicate.write_text("{}", encoding="utf-8")
    with pytest.raises(Exception, match="exactly one direct"):
        _find_prompt5_deployment_evidence((exact, duplicate))


def test_serial_resource_evidence_is_required_for_every_extended_pipeline(
    tmp_path: Path,
) -> None:
    plan, authorization, serial_path, serial_rows = _inputs(tmp_path)
    with pytest.raises(Exception, match="every extended pipeline"):
        build_extended_deployment_evidence(
            plan=plan,
            authorization=authorization,
            serial_resource_rows=serial_rows[:-1],
            serial_resource_path=serial_path,
        )


def test_wrapper_and_cli_bind_the_exact_steering_authority() -> None:
    wrapper = (
        TOOL_ROOT / "scripts/run_full_pipeline_extended_evaluation.ps1"
    ).read_text(encoding="utf-8")
    assert "PiDeploymentSteeringPath" in wrapper
    assert "PiDeploymentSteeringSha256" in wrapper
    assert "--pi-deployment-steering-path" in wrapper
    assert "--pi-deployment-steering-sha256" in wrapper
    assert PI_DEPLOYMENT_STEERING_SHA256 in wrapper
    assert "Get-FileHash -LiteralPath $PiDeploymentSteeringPath" in wrapper
