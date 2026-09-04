from __future__ import annotations

from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_core_evaluation.analysis import _separated_metric_tables


def _row(
    *, pipeline_id: str, category: str, metric_id: str, value: float
) -> dict[str, object]:
    return {
        "pipeline_id": pipeline_id,
        "category": category,
        "metric_id": metric_id,
        "source_key": "fixture",
        "job_id": "fixture",
        "case_count": 1,
        "status": "computed",
        "value": value,
        "numerator": None,
        "denominator": None,
        "reason": None,
        "unit": None,
        "higher_is_better": None,
        "details": {},
    }


def test_serial_resource_diagnostics_do_not_enter_accuracy_tables() -> None:
    pipeline_id = matrix().pipeline_ids[0]
    tables = _separated_metric_tables(
        accuracy_metrics=[
            _row(
                pipeline_id=pipeline_id,
                category="asr",
                metric_id="wer",
                value=0.25,
            )
        ],
        resource_metrics=[
            _row(
                pipeline_id=pipeline_id,
                category="asr",
                metric_id="wer",
                value=0.99,
            ),
            _row(
                pipeline_id=pipeline_id,
                category="resources",
                metric_id="total_rtf",
                value=0.5,
            ),
        ],
    )

    asr = next(row for row in tables["asr"] if row["pipeline_id"] == pipeline_id)
    resources = next(
        row for row in tables["resources"] if row["pipeline_id"] == pipeline_id
    )
    assert asr["wer"] == 0.25
    assert resources["total_rtf"] == 0.5
