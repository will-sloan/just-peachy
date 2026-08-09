"""Deterministic verification, identification, and confidence-interval metrics."""

from __future__ import annotations

import math
import random
from statistics import mean, pstdev
from typing import Iterable, Mapping, Sequence

from app.speaker_protocol.contracts import SpeakerProtocolError


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise SpeakerProtocolError("cosine vectors must be non-empty and dimension matched")
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm <= 0 or right_norm <= 0:
        raise SpeakerProtocolError("cosine vectors must have positive norm")
    return max(
        -1.0,
        min(
            1.0,
            sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
            / (left_norm * right_norm),
        ),
    )


def threshold_sweep(
    trials: Iterable[Mapping[str, object]],
    *,
    split: str,
) -> list[dict[str, object]]:
    materialized = [
        (float(row["score"]), bool(row["is_target"]))
        for row in trials
        if row.get("score") is not None and row.get("is_target") is not None
    ]
    positives = sum(1 for _, target in materialized if target)
    negatives = len(materialized) - positives
    if not materialized or positives == 0 or negatives == 0:
        return []
    values = sorted({score for score, _ in materialized}, reverse=True)
    epsilon = 1e-12
    thresholds = [values[0] + epsilon, *values, values[-1] - epsilon]
    result = []
    for threshold in thresholds:
        tp = fp = tn = fn = 0
        for score, target in materialized:
            accepted = score >= threshold
            if accepted and target:
                tp += 1
            elif accepted:
                fp += 1
            elif target:
                fn += 1
            else:
                tn += 1
        far = fp / negatives
        frr = fn / positives
        result.append(
            {
                "schema_version": "speaker-threshold-sweep.v1",
                "split": split,
                "threshold": float(threshold),
                "true_accepts": tp,
                "false_accepts": fp,
                "true_rejects": tn,
                "false_rejects": fn,
                "positive_trials": positives,
                "negative_trials": negatives,
                "far": far,
                "frr": frr,
                "tar": tp / positives,
                "tpr": tp / positives,
                "fpr": far,
                "fnr": frr,
            }
        )
    return result


def equal_error_rate(sweep: Sequence[Mapping[str, object]]) -> dict[str, object] | None:
    if not sweep:
        return None
    row = min(
        sweep,
        key=lambda value: (
            abs(float(value["far"]) - float(value["frr"])),
            -float(value["threshold"]),
        ),
    )
    return {
        "eer": (float(row["far"]) + float(row["frr"])) / 2.0,
        "threshold": float(row["threshold"]),
        "far": float(row["far"]),
        "frr": float(row["frr"]),
        "positive_trials": int(row["positive_trials"]),
        "negative_trials": int(row["negative_trials"]),
    }


def operating_point(
    trials: Iterable[Mapping[str, object]],
    threshold: float,
) -> dict[str, object] | None:
    materialized = [
        (float(row["score"]), bool(row["is_target"]))
        for row in trials
        if row.get("score") is not None and row.get("is_target") is not None
    ]
    positives = sum(1 for _, target in materialized if target)
    negatives = len(materialized) - positives
    if positives == 0 or negatives == 0:
        return None
    tp = sum(1 for score, target in materialized if target and score >= threshold)
    fn = positives - tp
    fp = sum(1 for score, target in materialized if not target and score >= threshold)
    tn = negatives - fp
    far = fp / negatives
    frr = fn / positives
    return {
        "threshold": float(threshold),
        "true_accepts": tp,
        "false_accepts": fp,
        "true_rejects": tn,
        "false_rejects": fn,
        "positive_trials": positives,
        "negative_trials": negatives,
        "far": far,
        "frr": frr,
        "tar": tp / positives,
        "far_ci": proportion_interval(fp, negatives),
        "frr_ci": proportion_interval(fn, positives),
        "tar_ci": proportion_interval(tp, positives),
    }


def tar_at_fixed_far(
    sweep: Sequence[Mapping[str, object]],
    target_far: float,
) -> dict[str, object] | None:
    eligible = [row for row in sweep if float(row["far"]) <= target_far]
    if not eligible:
        return None
    row = max(
        eligible,
        key=lambda value: (float(value["tar"]), -float(value["threshold"])),
    )
    return {
        "target_far": float(target_far),
        "observed_far": float(row["far"]),
        "tar": float(row["tar"]),
        "threshold": float(row["threshold"]),
        "positive_trials": int(row["positive_trials"]),
        "negative_trials": int(row["negative_trials"]),
    }


def proportion_metric(numerator: int, denominator: int) -> dict[str, object]:
    return {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "value": float(numerator) / float(denominator) if denominator else None,
        "confidence_interval": proportion_interval(numerator, denominator),
    }


def proportion_interval(
    numerator: int,
    denominator: int,
    *,
    z: float = 1.959963984540054,
) -> dict[str, float] | None:
    if denominator <= 0:
        return None
    estimate = numerator / denominator
    z2 = z * z
    denominator_adjusted = 1.0 + z2 / denominator
    center = (estimate + z2 / (2.0 * denominator)) / denominator_adjusted
    spread = (
        z
        * math.sqrt(
            estimate * (1.0 - estimate) / denominator
            + z2 / (4.0 * denominator * denominator)
        )
        / denominator_adjusted
    )
    return {"confidence_level": 0.95, "lower": max(0.0, center - spread), "upper": min(1.0, center + spread)}


def score_distribution(
    values: Iterable[float],
    *,
    seed: int = 3800,
    repetitions: int = 500,
) -> dict[str, object]:
    samples = [float(value) for value in values if math.isfinite(float(value))]
    if not samples:
        return {"count": 0, "mean": None, "standard_deviation": None, "mean_ci": None}
    return {
        "count": len(samples),
        "mean": mean(samples),
        "standard_deviation": pstdev(samples) if len(samples) > 1 else 0.0,
        "minimum": min(samples),
        "maximum": max(samples),
        "mean_ci": bootstrap_mean_interval(samples, seed=seed, repetitions=repetitions),
    }


def bootstrap_mean_interval(
    values: Sequence[float],
    *,
    seed: int,
    repetitions: int,
) -> dict[str, float] | None:
    if not values:
        return None
    if len(values) == 1:
        value = float(values[0])
        return {"confidence_level": 0.95, "lower": value, "upper": value}
    rng = random.Random(seed)
    estimates = []
    for _ in range(max(1, int(repetitions))):
        estimates.append(mean(rng.choice(values) for _ in values))
    estimates.sort()
    lower = _quantile(estimates, 0.025)
    upper = _quantile(estimates, 0.975)
    return {"confidence_level": 0.95, "lower": lower, "upper": upper}


def _quantile(values: Sequence[float], probability: float) -> float:
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return float(values[lower]) * (1.0 - weight) + float(values[upper]) * weight
