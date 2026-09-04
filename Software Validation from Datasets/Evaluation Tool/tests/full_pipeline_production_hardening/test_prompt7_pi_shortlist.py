from __future__ import annotations

import csv
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

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
    evidence,
    load_deployment_steering,
    steering_ref,
    unknown_evidence,
)
from app.full_pipeline_production_hardening import (
    ANCHOR_PIPELINES,
    DEFAULT_PI_DEPLOYMENT_STEERING,
    MATRIX_PATH,
    PI_DEPLOYMENT_STEERING_SHA256,
    PI_SHORTLIST_SCHEMA,
    PROMPT5_REQUIRED_FILES,
    PROMPT6_REQUIRED_FILES,
    REQUIRED_PROMPT7_REPORTS,
    RUNTIME_PATH,
    scope_fields,
)
from app.full_pipeline_production_hardening.io import HardeningError, sha256_file
from app.full_pipeline_production_hardening.pi_shortlist import (
    build_pi_shortlist,
    validate_pi_shortlist,
)
from app.full_pipeline_production_hardening.reporting import (
    _validate_report_checksums,
)
from app.full_pipeline_evaluation.io import checksum_map


def test_pi_shortlist_is_additive_exact_and_p8_consumable(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    original_selection = copy.deepcopy(fixture["selection"])
    document = build_pi_shortlist(
        authorization=fixture["authorization"],
        desktop_selection=fixture["selection"],
        evidence_files=fixture["evidence_files"],
        desktop_roles_source=fixture["catalog"],
    )

    assert fixture["selection"] == original_selection
    assert document["schema_version"] == PI_SHORTLIST_SCHEMA
    assert 2 <= document["candidate_count"] <= 4
    candidate_ids = [row["pipeline_id"] for row in document["candidates"]]
    assert candidate_ids == [
        pipeline_id for pipeline_id in ANCHOR_PIPELINES if pipeline_id in candidate_ids
    ]
    assert fixture["selection"]["roles"]["PRIMARY"] in candidate_ids
    assert document["desktop_roles"] == fixture["selection"]["roles"]
    assert document["desktop_roles_changed_for_pi"] is False
    assert document["desktop_roles_source"] == _ref(fixture["catalog"])
    assert document["candidate_pool_source"] == _ref(fixture["extended_set"])
    assert document["candidate_pool_pipeline_ids"] == list(ANCHOR_PIPELINES)
    assert document["future_target_hardware_tests"] == list(
        FUTURE_TARGET_HARDWARE_TESTS
    )
    assert document["future_linux_arm64_validation"] == list(
        FUTURE_LINUX_ARM64_VALIDATION
    )
    assert document["final_raspberry_pi_winner"] is None
    assert document["final_raspberry_pi_winner_claimed"] is False
    assert (
        document["architecture_tradeoff_audit"]["final_arm_preference_claimed"] is False
    )

    policy = document["selection_policy"]
    for key in (
        "weighted_composite_used",
        "universal_within_one_percent_equivalence_rule_used",
        "deployment_evidence_used_to_rewrite_scientific_ranks",
        "two_gib_used_as_hard_filter",
        "final_pi_winner_selected",
    ):
        assert policy[key] is False

    for candidate in document["candidates"]:
        assert set(candidate) == set(RASPBERRY_PI_CANDIDATE_FIELDS)
        resolved = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH).resolve(
            candidate["pipeline_id"]
        )
        assert candidate["asr"] == {
            "alias": resolved.asr_alias,
            "component_id": resolved.asr.get("component_id"),
            "registry_id": resolved.asr.get("registry_id"),
            "environment_profile": resolved.asr.get("environment_profile"),
        }
        assert candidate["segmentation"] == {
            "segmentation_id": resolved.diarization.get("segmentation_id")
        }
        assert set(candidate["latency"]) == {
            "first_readable_partial",
            "stable_transcript",
            "stable_correct_name",
        }
        assert candidate["export_path"]
        assert candidate["quantization_opportunities"]
        assert candidate["model_sharing_opportunities"]
        assert candidate["arm_runtime_risks"]
        assert candidate["reason_retained"]

    # A deployment-only candidate is allowed without changing desktop roles,
    # bundles, or the exact 17-task-per-desktop-candidate acceptance plan.
    assert ANCHOR_PIPELINES[2] in candidate_ids
    assert (
        fixture["selection_rows"][ANCHOR_PIPELINES[2]]["production_role_eligible"]
        is False
    )
    assert document["pi_only_candidate_bundles_or_acceptance_tasks_created"] is False


def test_pi_shortlist_tamper_and_firewall_fail_closed(tmp_path: Path) -> None:
    fixture = _fixture(tmp_path)
    document = build_pi_shortlist(
        authorization=fixture["authorization"],
        desktop_selection=fixture["selection"],
        evidence_files=fixture["evidence_files"],
        desktop_roles_source=fixture["catalog"],
    )

    tampered = copy.deepcopy(document)
    tampered["selection_policy"]["two_gib_used_as_hard_filter"] = True
    with pytest.raises(HardeningError, match="two_gib_used_as_hard_filter"):
        validate_pi_shortlist(
            tampered,
            authorization=fixture["authorization"],
            desktop_selection=fixture["selection"],
            evidence_files=fixture["evidence_files"],
            desktop_roles_source=fixture["catalog"],
        )

    tampered = copy.deepcopy(document)
    tampered["candidates"][0]["identity_embedding"]["model_id"] = "tampered"
    with pytest.raises(HardeningError, match="candidate binding differs"):
        validate_pi_shortlist(
            tampered,
            authorization=fixture["authorization"],
            desktop_selection=fixture["selection"],
            evidence_files=fixture["evidence_files"],
            desktop_roles_source=fixture["catalog"],
        )

    tampered = copy.deepcopy(document)
    tampered["candidates"][0]["windows_specific_assumptions"] = unknown_evidence(
        unit="status", reason_code="TAMPERED"
    )
    with pytest.raises(HardeningError, match="candidate binding differs"):
        validate_pi_shortlist(
            tampered,
            authorization=fixture["authorization"],
            desktop_selection=fixture["selection"],
            evidence_files=fixture["evidence_files"],
            desktop_roles_source=fixture["catalog"],
        )


def test_pi_artifacts_are_direct_completion_requirements() -> None:
    assert "all18_deployment_evidence.json" in PROMPT5_REQUIRED_FILES
    assert "extended_deployment_evidence.json" in PROMPT6_REQUIRED_FILES
    assert "raspberry_pi_candidate_shortlist.json" in REQUIRED_PROMPT7_REPORTS
    assert "report_checksums.json" in REQUIRED_PROMPT7_REPORTS
    assert sha256_file(DEFAULT_PI_DEPLOYMENT_STEERING) == (
        PI_DEPLOYMENT_STEERING_SHA256
    )


def test_report_checksums_bind_shortlist_and_fail_on_tamper(tmp_path: Path) -> None:
    report = tmp_path / "report"
    report.mkdir()
    shortlist = report / "raspberry_pi_candidate_shortlist.json"
    shortlist.write_text("{}\n", encoding="utf-8")
    (report / "other.md").write_text("frozen\n", encoding="utf-8")
    checksum_path = report / "report_checksums.json"
    _json(
        checksum_path,
        {
            "schema_version": "full-pipeline-production-report-checksums.v1",
            "status": "PASS",
            "entries": checksum_map(report, exclude=("report_checksums.json",)),
            "raspberry_pi_candidate_shortlist": _ref(shortlist),
        },
    )
    paths = SimpleNamespace(report=report)
    _validate_report_checksums(paths)
    shortlist.write_text('{"tampered":true}\n', encoding="utf-8")
    with pytest.raises(HardeningError, match="checksum inventory differs"):
        _validate_report_checksums(paths)


def _fixture(tmp_path: Path) -> dict[str, object]:
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    all_ids = matrix.pipeline_ids
    pool = ANCHOR_PIPELINES
    evidence_files: dict[str, Path] = {}
    summary_rows: list[dict[str, object]] = []
    for index, pipeline_id in enumerate(all_ids):
        pool_index = pool.index(pipeline_id) if pipeline_id in pool else index + 10
        summary_rows.append(
            {
                "pipeline_id": pipeline_id,
                "wer": 0.08 + pool_index / 1000,
                "der": 0.07 + pool_index / 1000,
                "wrong_known_time_sec": (
                    0.10
                    if pool_index == 0
                    else 0.09
                    if pool_index == 1
                    else 0.13 + pool_index / 100
                ),
                "stranger_false_known_time_sec": (
                    0.10
                    if pool_index == 0
                    else 0.12
                    if pool_index == 1
                    else 0.13 + pool_index / 100
                ),
                "explicit_failed_job_count": 0,
                "total_rtf": 0.20 + pool_index / 100,
                "first_readable_partial_latency_sec": 0.2 + pool_index / 100,
                "stable_prefix_latency_sec": 0.4 + pool_index / 100,
                "stable_name_latency_sec": 0.8 + pool_index / 100,
            }
        )
    for name in (
        "all18_finalist_summary.csv",
        "all18_asr.csv",
        "all18_diarization.csv",
        "all18_identity.csv",
        "all18_speaker_attributed_transcript.csv",
        "all18_streaming.csv",
        "all18_resources.csv",
    ):
        path = tmp_path / name
        _csv(
            path,
            summary_rows
            if name == "all18_finalist_summary.csv"
            else [
                {"pipeline_id": pipeline_id, "status": "computed"}
                for pipeline_id in all_ids
            ],
        )
        evidence_files[name] = path

    steering = load_deployment_steering(
        DEFAULT_PI_DEPLOYMENT_STEERING,
        expected_prompt_index=7,
        expected_sha256=PI_DEPLOYMENT_STEERING_SHA256,
    )
    authority = steering_ref(DEFAULT_PI_DEPLOYMENT_STEERING, steering)
    summary = evidence_files["all18_finalist_summary.csv"]
    summary_index = {row["pipeline_id"]: row for row in summary_rows}

    p5_path = tmp_path / "all18_deployment_evidence.json"
    p5_rows = [
        _deployment_row(
            pipeline_id,
            matrix=matrix,
            source=summary,
            metrics=summary_index[pipeline_id],
            resource_offset=index,
        )
        for index, pipeline_id in enumerate(all_ids)
    ]
    _json(
        p5_path,
        _deployment_document(
            schema="full-pipeline-all18-deployment-evidence.v1",
            prompt_index=5,
            pipeline_ids=all_ids,
            rows=p5_rows,
            authority=authority,
        ),
    )
    p6_path = tmp_path / "extended_deployment_evidence.json"
    p6_rows = [
        _deployment_row(
            pipeline_id,
            matrix=matrix,
            source=summary,
            metrics=summary_index[pipeline_id],
            resource_offset=index,
        )
        for index, pipeline_id in enumerate(pool)
    ]
    p6_document = _deployment_document(
        schema="full-pipeline-extended-deployment-evidence.v1",
        prompt_index=6,
        pipeline_ids=pool,
        rows=p6_rows,
        authority=authority,
    )
    p6_document["prompt5_deployment_evidence"] = _ref(p5_path)
    _json(p6_path, p6_document)

    extended = tmp_path / "extended_set.yaml"
    extended.write_text(
        yaml.safe_dump({"extended_pipeline_ids": list(pool)}, sort_keys=False),
        encoding="utf-8",
    )
    roles = {
        "PRIMARY": pool[0],
        "FALLBACK": pool[1],
        "ALTERNATIVE": None,
    }
    catalog = tmp_path / "production_candidate_catalog.yaml"
    catalog.write_text(
        yaml.safe_dump(
            {
                "schema_version": "full-pipeline-production-candidate-catalog.v1",
                **scope_fields(),
                "status": "PASS",
                "roles": roles,
                "candidates": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    selection_rows = {
        pipeline_id: {
            "pipeline_id": pipeline_id,
            "reliability_eligible": True,
            "production_role_eligible": pipeline_id != pool[2],
            "technical_rank": index + 1,
            "pareto_frontier": index < 2,
        }
        for index, pipeline_id in enumerate(pool)
    }
    selection = {
        "candidate_pool": list(pool),
        "roles": roles,
        "candidates": list(selection_rows.values()),
    }
    authorization = {
        "predeclared_extended_pipeline_ids": list(pool),
        "predeclared_extended_set": _ref(extended),
        "deployment_steering": authority,
        "prompt5_deployment_evidence": _ref(p5_path),
        "prompt6_deployment_evidence": _ref(p6_path),
    }
    return {
        "authorization": authorization,
        "selection": selection,
        "selection_rows": selection_rows,
        "evidence_files": evidence_files,
        "catalog": catalog,
        "extended_set": extended,
    }


def _deployment_document(
    *,
    schema: str,
    prompt_index: int,
    pipeline_ids,
    rows: list[dict[str, object]],
    authority: dict[str, object],
) -> dict[str, object]:
    return {
        "schema_version": schema,
        **scope_fields(),
        "prompt_index": prompt_index,
        "status": "PASS",
        "steering_authority": authority,
        "input_binding": {
            "deployment_steering_path": authority["path"],
            "deployment_steering_sha256": authority["sha256"],
            "deployment_steering_schema_version": authority["schema_version"],
            "deployment_steering_id": authority["steering_id"],
            "deployment_steering_status": authority["status"],
        },
        "pipeline_ids": list(pipeline_ids),
        "pipeline_count": len(pipeline_ids),
        "deployment_attribute_names": list(DEPLOYMENT_ATTRIBUTE_NAMES),
        "two_gib_feasibility_classes": list(TWO_GIB_FEASIBILITY_CLASSES),
        "linux_arm64_portability_classes": list(LINUX_ARM64_PORTABILITY_CLASSES),
        "raspberry_pi_candidate_fields": list(RASPBERRY_PI_CANDIDATE_FIELDS),
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


def _deployment_row(
    pipeline_id: str,
    *,
    matrix: FullPipelineMatrix,
    source: Path,
    metrics: dict[str, object],
    resource_offset: int,
) -> dict[str, object]:
    resolved = matrix.resolve(pipeline_id)
    attributes = {
        name: unknown_evidence(
            unit="not_measured", reason_code=f"UNKNOWN_{name.upper()}"
        )
        for name in DEPLOYMENT_ATTRIBUTE_NAMES
    }
    for name, value, unit, field in (
        (
            "model_file_size_bytes",
            80_000_000 + resource_offset * 1_000_000,
            "bytes",
            "model_bytes",
        ),
        (
            "total_pipeline_peak_rss_bytes",
            180_000_000 + resource_offset * 1_000_000,
            "bytes",
            "peak_rss_bytes",
        ),
        (
            "simultaneously_resident_neural_model_count",
            4,
            "count",
            "resident_model_count",
        ),
    ):
        attributes[name] = evidence(
            value,
            unit=unit,
            evidence_status="MEASURED",
            reason_code="SYNTHETIC_DESKTOP_RESOURCE",
            measurement_context="WINDOWS_X86_64_DESKTOP",
            source_path=source,
            source_field=field,
            desktop_measurement=True,
        )
    assumptions = unknown_evidence(
        unit="assumptions", reason_code="WINDOWS_ASSUMPTIONS_NOT_ARM_TESTED"
    )
    dependencies = unknown_evidence(
        unit="dependencies", reason_code="LINUX_ARM64_DEPENDENCIES_NOT_TESTED"
    )
    replacements = unknown_evidence(
        unit="replacements", reason_code="PLATFORM_REPLACEMENTS_NOT_ESTABLISHED"
    )
    return {
        "pipeline_id": pipeline_id,
        "asr_alias": resolved.asr_alias,
        "diarization_alias": resolved.diarization_alias,
        "identity_alias": resolved.identity_alias,
        "deployment_attributes": attributes,
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


def _ref(path: Path) -> dict[str, str]:
    return {"path": str(path.resolve()), "sha256": sha256_file(path)}


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
