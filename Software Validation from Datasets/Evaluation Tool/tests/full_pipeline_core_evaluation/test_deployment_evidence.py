from __future__ import annotations

import json
from pathlib import Path

from app.full_pipeline_deployment_evidence import (
    DEPLOYMENT_ATTRIBUTE_NAMES,
    LINUX_ARM64_PORTABILITY_CLASSES,
    TWO_GIB_FEASIBILITY_CLASSES,
    load_deployment_steering,
    steering_ref,
    validate_deployment_evidence_document,
)
from app.full_pipeline_core_evaluation import (
    EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
    DEFAULT_PI_DEPLOYMENT_STEERING,
)
from app.full_pipeline_core_evaluation.analysis import _deployment_evidence_document
from app.full_pipeline_core_evaluation.controller import layout
from app.full_pipeline_evaluation.io import write_json_atomic
from app.full_pipeline_evaluation.planning import matrix


def _resource_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, pipeline_id in enumerate(matrix().pipeline_ids):
        rows.append(
            {
                "pipeline_id": pipeline_id,
                "model_bytes": 500_000_000 + index,
                "model_bytes__status": "computed",
                "model_bytes__aggregation": "case_count_weighted_mean_across_disjoint_jobs",
                "peak_rss_bytes": 1_500_000_000 + index,
                "peak_rss_bytes__status": "computed",
                "peak_rss_bytes__aggregation": "case_count_weighted_mean_across_disjoint_jobs",
                "cache_bytes": 20_000_000 + index,
                "cache_bytes__status": "computed",
                "cache_bytes__aggregation": "case_count_weighted_mean_across_disjoint_jobs",
                "model_startup_sec": None,
                "model_startup_sec__status": "unsupported",
            }
        )
    return rows


def test_all18_deployment_evidence_is_additive_ordered_and_explicit(
    tmp_path: Path,
) -> None:
    paths = layout(tmp_path / "prompt5")
    paths.report.mkdir(parents=True)
    (paths.report / "all18_resources.csv").write_text(
        "pipeline_id,synthetic\n", encoding="utf-8"
    )
    steering = load_deployment_steering(
        DEFAULT_PI_DEPLOYMENT_STEERING,
        expected_prompt_index=5,
        expected_sha256=EXPECTED_PI_DEPLOYMENT_STEERING_SHA256,
    )
    write_json_atomic(
        paths.authorization,
        {"deployment_steering": steering_ref(DEFAULT_PI_DEPLOYMENT_STEERING, steering)},
    )

    document = _deployment_evidence_document(paths, resource_rows=_resource_rows())
    artifact_path = paths.report / "all18_deployment_evidence.json"
    write_json_atomic(artifact_path, document)
    round_tripped = json.loads(artifact_path.read_text(encoding="utf-8"))
    validate_deployment_evidence_document(
        round_tripped,
        schema_version="full-pipeline-all18-deployment-evidence.v1",
        prompt_index=5,
        expected_pipeline_ids=matrix().pipeline_ids,
        steering=steering,
    )

    assert document["pipeline_ids"] == list(matrix().pipeline_ids)
    assert document["pipeline_count"] == 18
    assert document["scientific_firewall"] == {
        "scientific_methodology_changed": False,
        "pipeline_membership_changed": False,
        "heldout_selection_or_retuning_performed": False,
        "deployment_evidence_used_as_filter": False,
        "desktop_rank_used_as_final_arm_rank": False,
    }
    for row in document["pipelines"]:
        assert set(row["deployment_attributes"]) == set(DEPLOYMENT_ATTRIBUTE_NAMES)
        assert row["two_gib_feasibility"]["class"] in TWO_GIB_FEASIBILITY_CLASSES
        assert (
            row["linux_arm64_portability"]["class"] in LINUX_ARM64_PORTABILITY_CLASSES
        )
        assert row["used_to_filter_pipeline"] is False
        assert row["desktop_resource_context"]["arm_measurement"] is False
        for cell in row["deployment_attributes"].values():
            assert cell["evidence_status"] in {
                "MEASURED",
                "DERIVED",
                "UNKNOWN",
                "UNSUPPORTED",
            }
            assert cell["arm_measurement"] is False
            assert {
                "source_path",
                "source_sha256",
                "source_field",
            } <= set(cell)


def test_prompt5_wrapper_binds_authoritative_deployment_steering() -> None:
    root = Path(__file__).resolve().parents[2]
    wrapper = (root / "scripts/run_full_pipeline_core_evaluation.ps1").read_text(
        encoding="utf-8"
    )
    assert "PiDeploymentSteeringPath" in wrapper
    assert "RASPBERRY_PI_DEPLOYMENT_STEERING.json" in wrapper
    assert "--pi-deployment-steering-path" in wrapper
    assert "[ValidateRange(1,2)]" in wrapper


def test_authority_hash_and_scientific_contract_are_exact() -> None:
    value = json.loads(DEFAULT_PI_DEPLOYMENT_STEERING.read_text(encoding="utf-8"))
    assert set(value["two_gib_feasibility_classes"]) == set(TWO_GIB_FEASIBILITY_CLASSES)
    assert set(value["linux_arm64_portability_classes"]) == set(
        LINUX_ARM64_PORTABILITY_CLASSES
    )
    assert all(flag is False for flag in value["scientific_contract"].values())
