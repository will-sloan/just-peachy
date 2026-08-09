"""Declared multi-objective advancement and Pareto screening rules."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


SELECTION_SCHEMA_VERSION = "core-screening-selection.v1"


@dataclass(frozen=True)
class Objective:
    """One comparable metric used for Pareto screening."""

    metric: str
    direction: str
    category: str
    required: bool = True
    tolerance: float = 0.0

    def __post_init__(self) -> None:
        if self.direction not in {"min", "max"}:
            raise ValueError("objective direction must be min or max")
        if self.category not in {"accuracy", "reliability", "resource", "robustness"}:
            raise ValueError(f"unsupported objective category {self.category!r}")
        if self.tolerance < 0:
            raise ValueError("objective tolerance must be >= 0")


@dataclass(frozen=True)
class AdvancementRules:
    """Hard gates plus multi-objective shortlist limit."""

    objectives: tuple[Objective, ...]
    maximum_candidates: int
    minimum_valid_output_rate: float = 0.95
    maximum_failure_rate: float = 0.05
    maximum_timeout_rate: float = 0.0
    maximum_oom_rate: float = 0.0
    minimum_repetitions: int = 1

    def __post_init__(self) -> None:
        if self.maximum_candidates < 1:
            raise ValueError("maximum_candidates must be positive")
        if self.minimum_repetitions < 1:
            raise ValueError("minimum_repetitions must be positive")
        if not self.objectives:
            raise ValueError("at least one objective is required")


def select_candidates(
    candidates: Sequence[Mapping[str, object]],
    rules: AdvancementRules,
) -> dict[str, object]:
    """Apply hard gates, Pareto dominance, and deterministic diverse capping."""

    if len({str(row.get("candidate_id")) for row in candidates}) != len(candidates):
        raise ValueError("candidate IDs must be unique")
    evaluations: dict[str, dict[str, object]] = {}
    eligible: list[Mapping[str, object]] = []
    for candidate in sorted(candidates, key=lambda row: str(row.get("candidate_id"))):
        candidate_id = str(candidate.get("candidate_id") or "")
        reasons = _hard_gate_reasons(candidate, rules)
        evaluations[candidate_id] = {
            "candidate_id": candidate_id,
            "eligible": not reasons,
            "hard_gate_reasons": reasons,
            "dominated_by": [],
            "advanced": False,
        }
        if not reasons:
            eligible.append(candidate)

    frontier = []
    for candidate in eligible:
        candidate_id = str(candidate["candidate_id"])
        dominators = [
            str(other["candidate_id"])
            for other in eligible
            if other is not candidate and _dominates(other, candidate, rules.objectives)
        ]
        evaluations[candidate_id]["dominated_by"] = sorted(dominators)
        if not dominators:
            frontier.append(candidate)

    selected = _cap_frontier(frontier, rules)
    selected_ids = [str(row["candidate_id"]) for row in selected]
    for candidate_id in selected_ids:
        evaluations[candidate_id]["advanced"] = True
    for candidate in frontier:
        candidate_id = str(candidate["candidate_id"])
        if candidate_id not in selected_ids:
            evaluations[candidate_id]["shortlist_reason"] = (
                "non-dominated but outside the declared shortlist limit"
            )
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "rules": _rules_json(rules),
        "candidate_count": len(candidates),
        "eligible_count": len(eligible),
        "pareto_frontier": sorted(str(row["candidate_id"]) for row in frontier),
        "advanced_candidate_ids": selected_ids,
        "evaluations": [evaluations[key] for key in sorted(evaluations)],
    }


def _hard_gate_reasons(
    candidate: Mapping[str, object], rules: AdvancementRules
) -> list[str]:
    reasons = []
    checks = (
        ("valid_output_rate", rules.minimum_valid_output_rate, "minimum"),
        ("failure_rate", rules.maximum_failure_rate, "maximum"),
        ("timeout_rate", rules.maximum_timeout_rate, "maximum"),
        ("oom_rate", rules.maximum_oom_rate, "maximum"),
    )
    for metric, limit, mode in checks:
        value = _metric_value(candidate, metric)
        if value is None:
            reasons.append(f"missing required hard-gate metric {metric}")
        elif mode == "minimum" and value < limit:
            reasons.append(f"{metric}={value} is below minimum {limit}")
        elif mode == "maximum" and value > limit:
            reasons.append(f"{metric}={value} exceeds maximum {limit}")
    repetitions = _metric_value(candidate, "repetitions")
    if repetitions is None or repetitions < rules.minimum_repetitions:
        reasons.append(f"repetitions must be at least {rules.minimum_repetitions}")
    for objective in rules.objectives:
        if objective.required and _metric_value(candidate, objective.metric) is None:
            reasons.append(f"missing required objective {objective.metric}")
    return reasons


def _dominates(
    candidate: Mapping[str, object],
    other: Mapping[str, object],
    objectives: Sequence[Objective],
) -> bool:
    no_worse = True
    strictly_better = False
    compared = 0
    for objective in objectives:
        candidate_value = _metric_value(candidate, objective.metric)
        other_value = _metric_value(other, objective.metric)
        if candidate_value is None or other_value is None:
            continue
        compared += 1
        tolerance = objective.tolerance
        if objective.direction == "min":
            no_worse &= candidate_value <= other_value + tolerance
            strictly_better |= candidate_value < other_value - tolerance
        else:
            no_worse &= candidate_value >= other_value - tolerance
            strictly_better |= candidate_value > other_value + tolerance
    return compared > 0 and no_worse and strictly_better


def _cap_frontier(
    frontier: Sequence[Mapping[str, object]], rules: AdvancementRules
) -> list[Mapping[str, object]]:
    if len(frontier) <= rules.maximum_candidates:
        return sorted(frontier, key=lambda row: str(row["candidate_id"]))

    selected: list[Mapping[str, object]] = []
    quality_objectives = [
        objective
        for objective in rules.objectives
        if objective.category in {"accuracy", "reliability", "robustness"}
    ]
    for objective in quality_objectives:
        ranked = _rank_for_objective(frontier, objective)
        if ranked and ranked[0] not in selected:
            selected.append(ranked[0])
        if len(selected) == rules.maximum_candidates:
            return selected

    remaining = [row for row in frontier if row not in selected]
    remaining.sort(
        key=lambda row: (
            _normalized_score(row, frontier, rules.objectives),
            str(row["candidate_id"]),
        )
    )
    return [*selected, *remaining[: rules.maximum_candidates - len(selected)]]


def _rank_for_objective(
    candidates: Sequence[Mapping[str, object]], objective: Objective
) -> list[Mapping[str, object]]:
    factor = 1.0 if objective.direction == "min" else -1.0
    return sorted(
        candidates,
        key=lambda row: (
            factor * (_metric_value(row, objective.metric) or 0.0),
            str(row["candidate_id"]),
        ),
    )


def _normalized_score(
    candidate: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]],
    objectives: Sequence[Objective],
) -> float:
    scores = []
    for objective in objectives:
        values = [
            value
            for row in candidates
            if (value := _metric_value(row, objective.metric)) is not None
        ]
        current = _metric_value(candidate, objective.metric)
        if current is None or not values:
            continue
        low, high = min(values), max(values)
        normalized = 0.0 if math.isclose(low, high) else (current - low) / (high - low)
        scores.append(normalized if objective.direction == "min" else 1.0 - normalized)
    return sum(scores) / len(scores) if scores else math.inf


def _metric_value(candidate: Mapping[str, object], path: str) -> float | None:
    value: object = candidate
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return None
        value = value[part]
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _rules_json(rules: AdvancementRules) -> dict[str, object]:
    return {
        "maximum_candidates": rules.maximum_candidates,
        "minimum_valid_output_rate": rules.minimum_valid_output_rate,
        "maximum_failure_rate": rules.maximum_failure_rate,
        "maximum_timeout_rate": rules.maximum_timeout_rate,
        "maximum_oom_rate": rules.maximum_oom_rate,
        "minimum_repetitions": rules.minimum_repetitions,
        "objectives": [
            {
                "metric": objective.metric,
                "direction": objective.direction,
                "category": objective.category,
                "required": objective.required,
                "tolerance": objective.tolerance,
            }
            for objective in rules.objectives
        ],
    }
