from __future__ import annotations

from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_core_evaluation.analysis import (
    END_TO_END_COVERAGE_POPULATION,
    REQUIRED_METRIC_CATEGORIES,
    _attach_failure_coverage,
    _merge_category_rows,
    _wide_metric_tables,
)


def _terminal_row(
    pipeline_id: str,
    *,
    campaign_kind: str,
    state: str,
    completed_cases: int,
) -> dict[str, object]:
    return {
        "campaign_kind": campaign_kind,
        "pipeline_id": pipeline_id,
        "state": state,
        "case_count": 10,
        "completed_cases": completed_cases,
        "planned_audio_sec": 100.0,
        "completed_audio_sec": float(completed_cases * 10),
        "explicit_failure": state == "failed",
    }


def test_all_failed_empty_metric_categories_still_have_exact_all18_rows() -> None:
    pipelines = list(matrix().pipeline_ids)
    failures = [
        _terminal_row(
            pipeline_id,
            campaign_kind="accuracy",
            state="failed",
            completed_cases=0,
        )
        for pipeline_id in pipelines
    ] + [
        _terminal_row(
            pipeline_id,
            campaign_kind="resources",
            state="failed",
            completed_cases=0,
        )
        for pipeline_id in pipelines
    ]

    tables = _attach_failure_coverage(_wide_metric_tables([]), failures)

    assert set(REQUIRED_METRIC_CATEGORIES).issubset(tables)
    for category in REQUIRED_METRIC_CATEGORIES:
        assert [row["pipeline_id"] for row in tables[category]] == pipelines
        assert len(tables[category]) == 18
        assert all(
            row["end_to_end_job_failure_rate"] == 1.0 for row in tables[category]
        )
        assert all(
            row["end_to_end_coverage_population"] == END_TO_END_COVERAGE_POPULATION
            for row in tables[category]
        )

    merged = _merge_category_rows([*tables["streaming"], *tables["ux"]])
    assert [row["pipeline_id"] for row in merged] == pipelines
    assert len(merged) == 18


def test_mixed_terminal_failures_keep_conditional_and_end_to_end_separate() -> None:
    pipelines = list(matrix().pipeline_ids)
    first = pipelines[0]
    failures = [
        _terminal_row(
            pipeline_id,
            campaign_kind="accuracy",
            state="failed" if pipeline_id == first else "complete",
            completed_cases=4 if pipeline_id == first else 10,
        )
        for pipeline_id in pipelines
    ]
    tables = _attach_failure_coverage(_wide_metric_tables([]), failures)
    rows = {row["pipeline_id"]: row for row in tables["identity"]}

    failed = rows[first]
    assert failed["conditional_complete_job_count"] == 0
    assert failed["end_to_end_job_failure_numerator"] == 1
    assert failed["end_to_end_job_failure_denominator"] == 1
    assert failed["end_to_end_job_failure_rate"] == 1.0
    assert failed["conditional_completed_case_count"] == 4
    assert failed["end_to_end_case_noncompletion_numerator"] == 6
    assert failed["end_to_end_case_noncompletion_denominator"] == 10
    assert failed["end_to_end_case_noncompletion_rate"] == 0.6
    assert failed["row_status"] == "MISSING"

    complete = rows[pipelines[1]]
    assert complete["conditional_complete_job_count"] == 1
    assert complete["end_to_end_job_failure_rate"] == 0.0
    assert complete["end_to_end_case_noncompletion_rate"] == 0.0


def test_empty_streaming_merge_is_total_not_key_error() -> None:
    rows = _merge_category_rows([])
    assert len(rows) == 18
    assert [row["pipeline_id"] for row in rows] == list(matrix().pipeline_ids)
    assert all(row["row_status"] == "MISSING" for row in rows)
