from __future__ import annotations

import math

from app.full_pipeline_core_evaluation.bootstrap import (
    bootstrap_intervals,
    paired_comparisons,
)


def _row(
    pipeline: str,
    case: str,
    speakers: list[str],
    numerator: float,
    denominator: float,
) -> dict[str, object]:
    return {
        "pipeline_id": pipeline,
        "category": "asr",
        "metric_id": "wer",
        "source_bucket": "synthetic",
        "case_id": case,
        "reference_speaker_ids": speakers,
        "status": "computed",
        "value": numerator / denominator,
        "numerator": numerator,
        "denominator": denominator,
        "higher_is_better": False,
    }


def test_bootstrap_uses_speaker_clusters_and_fractional_multi_speaker_cases() -> None:
    rows = [
        _row("pipeline_a", "case_shared", ["s1", "s2"], 2, 4),
        _row("pipeline_a", "case_s1", ["s1"], 0, 4),
    ]

    result = bootstrap_intervals(rows, iterations=100, seed=7)
    overall = next(
        row for row in result if row["analysis_scope"] == "all_applicable_reduced_panel"
    )

    assert overall["speaker_cluster_count"] == 2
    assert math.isclose(float(overall["point_estimate"]), 0.25)
    assert overall["bootstrap_iterations"] == 100


def test_paired_comparison_uses_only_shared_speaker_clusters() -> None:
    rows = [
        _row("pipeline_a", "a1", ["s1"], 1, 10),
        _row("pipeline_a", "a2", ["s2"], 2, 10),
        _row("pipeline_b", "b1", ["s1"], 2, 10),
        _row("pipeline_b", "b3", ["s3"], 3, 10),
    ]

    result = paired_comparisons(rows, iterations=50, seed=9)

    assert len(result) == 1
    assert result[0]["paired_speaker_cluster_count"] == 1
    assert result[0]["left_only_speaker_count"] == 1
    assert result[0]["right_only_speaker_count"] == 1
    assert math.isclose(float(result[0]["left_minus_right"]), -0.1)
