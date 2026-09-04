"""Deterministic speaker-cluster bootstrap and paired comparisons."""

from __future__ import annotations

from collections import defaultdict
import hashlib
import math
import random
from typing import Iterable, Mapping, Sequence

from .io import scope_fields


ADDITIVE_METRICS = {
    "wrong_known_time_sec",
    "stranger_false_known_time_sec",
    "identity_revision_count",
    "transcript_revision_count",
    "ux_identity_revision_count",
}
DEFAULT_BOOTSTRAP_ITERATIONS = 2000


def bootstrap_intervals(
    rows: Sequence[Mapping[str, object]],
    *,
    iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    seed: int = 5107,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    scopes: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = defaultdict(
        list
    )
    for row in rows:
        if row.get("status") != "computed":
            continue
        key = (
            str(row["pipeline_id"]),
            str(row["category"]),
            str(row["metric_id"]),
            str(row["source_bucket"]),
        )
        scopes[key].append(row)
        scopes[(key[0], key[1], key[2], "all_applicable_reduced_panel")].append(row)
    for key, values in sorted(scopes.items()):
        contributions, estimator = _speaker_contributions(values)
        if not contributions:
            continue
        samples = _bootstrap_samples(
            contributions,
            estimator=estimator,
            iterations=iterations,
            seed=_derived_seed(seed, "|".join(key)),
        )
        point = _estimate(contributions.values(), estimator)
        results.append(
            {
                **scope_fields(),
                "pipeline_id": key[0],
                "category": key[1],
                "metric_id": key[2],
                "analysis_scope": key[3],
                "point_estimate": point,
                "ci_lower_95": _percentile(samples, 0.025),
                "ci_upper_95": _percentile(samples, 0.975),
                "speaker_cluster_count": len(contributions),
                "bootstrap_iterations": iterations,
                "bootstrap_seed": seed,
                "bootstrap_method": (
                    "speaker_cluster_resampling_with_fractional_multi_speaker_case_contributions.v1"
                ),
                "estimator": estimator,
            }
        )
    return results


def paired_comparisons(
    rows: Sequence[Mapping[str, object]],
    *,
    iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS,
    seed: int = 5107,
) -> list[dict[str, object]]:
    wanted = {
        "wer",
        "der",
        "jer",
        "correctly_named_known_rate",
        "wrong_known_time_sec",
        "stranger_false_known_time_sec",
        "fpir",
        "fnir",
        "cpwer",
        "speaker_attributed_wer",
        "correct_transcribed_attributed_word_rate",
        "first_readable_partial_latency_sec",
        "stable_prefix_latency_sec",
    }
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "computed" and row.get("metric_id") in wanted:
            grouped[
                (
                    str(row["pipeline_id"]),
                    str(row["category"]),
                    str(row["metric_id"]),
                )
            ].append(row)
    by_metric: dict[tuple[str, str], dict[str, list[Mapping[str, object]]]] = (
        defaultdict(dict)
    )
    for (pipeline, category, metric), values in grouped.items():
        by_metric[(category, metric)][pipeline] = values
    output: list[dict[str, object]] = []
    for (category, metric), pipelines in sorted(by_metric.items()):
        ids = sorted(pipelines)
        for left_index, left in enumerate(ids):
            for right in ids[left_index + 1 :]:
                left_stats, estimator_left = _speaker_contributions(pipelines[left])
                right_stats, estimator_right = _speaker_contributions(pipelines[right])
                if estimator_left != estimator_right:
                    continue
                speakers = sorted(set(left_stats) & set(right_stats))
                if not speakers:
                    continue
                left_paired = {key: left_stats[key] for key in speakers}
                right_paired = {key: right_stats[key] for key in speakers}
                point = _estimate(left_paired.values(), estimator_left) - _estimate(
                    right_paired.values(), estimator_left
                )
                rng = random.Random(
                    _derived_seed(seed, f"{category}|{metric}|{left}|{right}")
                )
                deltas: list[float] = []
                for _ in range(iterations):
                    chosen = [rng.choice(speakers) for _ in speakers]
                    left_values = [left_paired[key] for key in chosen]
                    right_values = [right_paired[key] for key in chosen]
                    deltas.append(
                        _estimate(left_values, estimator_left)
                        - _estimate(right_values, estimator_left)
                    )
                first = pipelines[left][0]
                output.append(
                    {
                        **scope_fields(),
                        "category": category,
                        "metric_id": metric,
                        "left_pipeline_id": left,
                        "right_pipeline_id": right,
                        "left_minus_right": point,
                        "ci_lower_95": _percentile(deltas, 0.025),
                        "ci_upper_95": _percentile(deltas, 0.975),
                        "paired_speaker_cluster_count": len(speakers),
                        "left_only_speaker_count": len(
                            set(left_stats) - set(right_stats)
                        ),
                        "right_only_speaker_count": len(
                            set(right_stats) - set(left_stats)
                        ),
                        "bootstrap_iterations": iterations,
                        "bootstrap_seed": seed,
                        "higher_is_better": first.get("higher_is_better"),
                        "estimator": estimator_left,
                    }
                )
    return output


def _speaker_contributions(
    rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, tuple[float, float]], str]:
    if not rows:
        return {}, "mean"
    metric_id = str(rows[0]["metric_id"])
    sufficient = all(
        row.get("numerator") is not None and row.get("denominator") is not None
        for row in rows
    )
    estimator = (
        "ratio" if sufficient else "sum" if metric_id in ADDITIVE_METRICS else "mean"
    )
    values: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for row in rows:
        speakers = [str(value) for value in row.get("reference_speaker_ids", [])]
        if not speakers:
            speakers = [f"case::{row['case_id']}"]
        fraction = 1.0 / len(speakers)
        if estimator == "ratio":
            numerator = float(row["numerator"])
            denominator = float(row["denominator"])
        else:
            numerator = float(row["value"])
            denominator = 0.0 if estimator == "sum" else 1.0
        for speaker in speakers:
            values[speaker][0] += numerator * fraction
            values[speaker][1] += denominator * fraction
    return {key: (value[0], value[1]) for key, value in values.items()}, estimator


def _estimate(values: Iterable[tuple[float, float]], estimator: str) -> float:
    rows = list(values)
    numerator = sum(value[0] for value in rows)
    denominator = sum(value[1] for value in rows)
    if estimator == "sum":
        return numerator
    return numerator / denominator if denominator > 0 else math.nan


def _bootstrap_samples(
    values: Mapping[str, tuple[float, float]],
    *,
    estimator: str,
    iterations: int,
    seed: int,
) -> list[float]:
    speakers = sorted(values)
    rng = random.Random(seed)
    result: list[float] = []
    for _ in range(iterations):
        chosen = [values[rng.choice(speakers)] for _ in speakers]
        estimate = _estimate(chosen, estimator)
        if math.isfinite(estimate):
            result.append(estimate)
    return result


def _derived_seed(seed: int, value: str) -> int:
    digest = hashlib.sha256(f"{seed}|{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _percentile(values: Sequence[float], probability: float) -> float | None:
    finite = sorted(value for value in values if math.isfinite(value))
    if not finite:
        return None
    if len(finite) == 1:
        return finite[0]
    position = (len(finite) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return finite[lower]
    fraction = position - lower
    return finite[lower] * (1 - fraction) + finite[upper] * fraction
