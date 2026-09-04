"""Development-only Pareto promotion for H2 successive halving.

The selector reads only completed development result trees.  It uses an
ordered, disclosed metric vector rather than a hidden weighted score.  Missing
safety metrics make a candidate ineligible; other unavailable metrics are
reported and omitted consistently for the whole comparison tier.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline_evaluation.metrics import METRIC_CATALOG
from app.full_pipeline_evaluation.schema import TRACK_B_CATEGORY_TO_RESULT_VIEW

from .contracts import H2Job, H2ProgramError
from .io import read_json, write_json_atomic


METRIC_PRIORITY: tuple[tuple[str, str, str], ...] = (
    ("wrong_known_time_sec", "identity", "min"),
    ("stranger_false_known_time_sec", "identity", "min"),
    ("wrong_name_dwell_sec", "ux", "min"),
    ("short_turn_der_lt_0_5_sec", "diarization", "min"),
    ("short_turn_der_0_5_to_1_0_sec", "diarization", "min"),
    ("short_turn_der_1_0_to_2_0_sec", "diarization", "min"),
    ("miss_rate", "diarization", "min"),
    (
        "correct_transcribed_attributed_word_rate",
        "speaker_transcription",
        "max",
    ),
    ("boundary_delay_sec", "diarization", "min"),
    ("stable_name_latency_sec", "identity", "min"),
    ("warm_identity_accuracy", "identity", "max"),
    ("unknown_n_consistency", "identity", "max"),
    ("transcript_revision_count", "ux", "min"),
    ("total_rtf", "resources", "min"),
)
REQUIRED_SAFETY_METRICS = frozenset(
    {"wrong_known_time_sec", "stranger_false_known_time_sec"}
)
REQUIRED_SHORT_TURN_METRICS = frozenset(
    {
        "short_turn_der_lt_0_5_sec",
        "short_turn_der_0_5_to_1_0_sec",
        "short_turn_der_1_0_to_2_0_sec",
    }
)
REQUIRED_PROMOTION_METRICS = REQUIRED_SAFETY_METRICS | REQUIRED_SHORT_TURN_METRICS


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    job_id: str
    result_root: Path
    metrics: Mapping[str, float | None]
    missing: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return not (set(self.missing) & REQUIRED_PROMOTION_METRICS)


def select_promotions(
    jobs: Sequence[H2Job],
    *,
    results_root: Path,
    maximum: int,
    decision_path: Path | None = None,
) -> dict[str, object]:
    """Select a bounded development Pareto set with deterministic tie breaks."""

    if maximum < 1:
        raise ValueError("maximum promotions must be >= 1")
    validate_metric_priority_contract()
    if not jobs:
        raise H2ProgramError("promotion tier contains no jobs")
    if any(job.split != "development" for job in jobs):
        raise H2ProgramError("promotion attempted with non-development evidence")
    evidence = tuple(
        read_candidate_evidence(
            job,
            results_root=results_root,
            candidate_id=_candidate_base(job.configuration_id),
        )
        for job in jobs
    )
    eligible = tuple(row for row in evidence if row.eligible)
    if not eligible:
        raise H2ProgramError(
            "no promotion candidate has every required development safety and "
            "short-turn metric"
        )
    common_metrics = tuple(
        metric_id
        for metric_id, _view, _direction in METRIC_PRIORITY
        if all(row.metrics.get(metric_id) is not None for row in eligible)
    )
    if not set(REQUIRED_PROMOTION_METRICS).issubset(common_metrics):
        raise H2ProgramError(
            "required safety and short-turn metrics are not common across candidates"
        )
    frontier = tuple(
        row
        for row in eligible
        if not any(
            _dominates(other, row, common_metrics)
            for other in eligible
            if other.candidate_id != row.candidate_id
        )
    )
    ordered_frontier = sorted(
        frontier, key=lambda row: _lexicographic_key(row, common_metrics)
    )
    if len(ordered_frontier) >= maximum:
        selected = ordered_frontier[:maximum]
    else:
        selected_ids = {row.candidate_id for row in ordered_frontier}
        remaining = sorted(
            (row for row in eligible if row.candidate_id not in selected_ids),
            key=lambda row: _lexicographic_key(row, common_metrics),
        )
        selected = [*ordered_frontier, *remaining[: maximum - len(ordered_frontier)]]
    selected_ids = [row.candidate_id for row in selected]
    payload: dict[str, object] = {
        "schema_version": "h2-development-promotion.v1",
        "status": "COMPLETE",
        "development_only": True,
        "evaluation_material_inspected": False,
        "weighted_composite_used": False,
        "method": "Pareto nondominance followed by declared-priority lexicographic truncation",
        "maximum_promotions": maximum,
        "common_metric_priority": list(common_metrics),
        "required_safety_metrics": sorted(REQUIRED_SAFETY_METRICS),
        "required_short_turn_metrics": sorted(REQUIRED_SHORT_TURN_METRICS),
        "required_promotion_metrics": sorted(REQUIRED_PROMOTION_METRICS),
        "pareto_frontier": [row.candidate_id for row in ordered_frontier],
        "selected_candidates": selected_ids,
        "candidates": [
            {
                "candidate_id": row.candidate_id,
                "job_id": row.job_id,
                "result_root": str(row.result_root),
                "eligible": row.eligible,
                "metrics": dict(row.metrics),
                "missing_metrics": list(row.missing),
            }
            for row in sorted(evidence, key=lambda item: item.candidate_id)
        ],
    }
    if decision_path is not None:
        write_json_atomic(decision_path, payload)
    return payload


def read_candidate_evidence(
    job: H2Job, *, results_root: Path, candidate_id: str
) -> CandidateEvidence:
    root = Path(results_root) / "jobs" / job.job_id / "result"
    metrics: dict[str, float | None] = {}
    for metric_id, category, _direction in METRIC_PRIORITY:
        result_view = TRACK_B_CATEGORY_TO_RESULT_VIEW.get(category)
        if result_view is None:
            raise H2ProgramError(
                f"promotion category {category!r} has no result-view mapping"
            )
        path = root / "metrics" / f"{result_view}.json"
        metrics[metric_id] = _metric_value(
            path,
            metric_id,
            subview_id=category,
        )
    return CandidateEvidence(
        candidate_id=candidate_id,
        job_id=job.job_id,
        result_root=root,
        metrics=metrics,
        missing=tuple(key for key, value in metrics.items() if value is None),
    )


def metric_vector_from_result(result_root: Path) -> dict[str, float | None]:
    validate_metric_priority_contract()
    root = Path(result_root)
    return {
        metric_id: _metric_value(
            root / "metrics" / f"{TRACK_B_CATEGORY_TO_RESULT_VIEW[category]}.json",
            metric_id,
            subview_id=category,
        )
        for metric_id, category, _direction in METRIC_PRIORITY
    }


def validate_metric_priority_contract() -> None:
    """Fail closed when promotion priorities drift from the metric catalog.

    The second tuple value is both the frozen metric category and the JSON
    filename read by :func:`read_candidate_evidence`.  A spelling/category
    mismatch would otherwise silently remove a steering priority from every
    candidate's common comparison vector.
    """

    errors: list[str] = []
    seen: set[str] = set()
    for metric_id, category, direction in METRIC_PRIORITY:
        if metric_id in seen:
            errors.append(f"duplicate priority metric {metric_id}")
        seen.add(metric_id)
        definition = METRIC_CATALOG.get(metric_id)
        if definition is None:
            errors.append(f"unknown priority metric {metric_id}")
            continue
        result_view = TRACK_B_CATEGORY_TO_RESULT_VIEW.get(category)
        if result_view is None:
            errors.append(f"{metric_id} category {category!r} has no result view")
        if definition.category != category:
            errors.append(
                f"{metric_id} category {category!r} differs from catalog "
                f"{definition.category!r}"
            )
        expected_direction = None
        if definition.higher_is_better is True:
            expected_direction = "max"
        elif definition.higher_is_better is False:
            expected_direction = "min"
        if direction not in {"min", "max"}:
            errors.append(f"{metric_id} has invalid direction {direction!r}")
        elif expected_direction is not None and direction != expected_direction:
            errors.append(
                f"{metric_id} direction {direction!r} differs from catalog "
                f"{expected_direction!r}"
            )
    if errors:
        raise H2ProgramError("invalid promotion metric contract: " + "; ".join(errors))


def _metric_value(
    path: Path,
    metric_id: str,
    *,
    subview_id: str,
) -> float | None:
    if not path.is_file():
        return None
    value = read_json(path)
    subviews = value.get("subviews")
    if not isinstance(subviews, Mapping):
        return None
    subview = subviews.get(subview_id)
    if not isinstance(subview, Mapping):
        return None
    metrics = subview.get("metrics")
    if not isinstance(metrics, Mapping):
        return None
    metric = metrics.get(metric_id)
    if not isinstance(metric, Mapping) or metric.get("status") != "computed":
        return None
    raw = metric.get("value")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    number = float(raw)
    return number if math.isfinite(number) else None


def _dominates(
    left: CandidateEvidence,
    right: CandidateEvidence,
    metric_ids: Sequence[str],
) -> bool:
    no_worse = True
    strictly_better = False
    directions = {
        metric_id: direction for metric_id, _view, direction in METRIC_PRIORITY
    }
    for metric_id in metric_ids:
        left_value = float(left.metrics[metric_id])  # common metrics are non-null
        right_value = float(right.metrics[metric_id])
        if directions[metric_id] == "max":
            left_value, right_value = -left_value, -right_value
        if left_value > right_value:
            no_worse = False
            break
        if left_value < right_value:
            strictly_better = True
    return no_worse and strictly_better


def _lexicographic_key(
    row: CandidateEvidence, metric_ids: Sequence[str]
) -> tuple[object, ...]:
    directions = {
        metric_id: direction for metric_id, _view, direction in METRIC_PRIORITY
    }
    values: list[object] = []
    for metric_id in metric_ids:
        number = float(row.metrics[metric_id])
        values.append(number if directions[metric_id] == "min" else -number)
    values.append(row.candidate_id)
    return tuple(values)


def _candidate_base(configuration_id: str) -> str:
    for suffix in ("_SMALL", "_MEDIUM", "_FULL"):
        if configuration_id.endswith(suffix):
            return configuration_id[: -len(suffix)]
    return configuration_id


__all__ = [
    "CandidateEvidence",
    "METRIC_PRIORITY",
    "REQUIRED_PROMOTION_METRICS",
    "REQUIRED_SAFETY_METRICS",
    "REQUIRED_SHORT_TURN_METRICS",
    "read_candidate_evidence",
    "metric_vector_from_result",
    "select_promotions",
    "validate_metric_priority_contract",
]
