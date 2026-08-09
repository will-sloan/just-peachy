"""Deterministic paired and cluster-aware campaign comparisons."""

from __future__ import annotations

import math
from pathlib import Path
import random
from typing import Mapping, Sequence

import pandas as pd
import pyarrow.parquet as pq

from .contracts import COMPARISON_SCHEMA_VERSION, AnalysisContractError


ITEM_KEY_PRIORITY = (
    "item_id",
    "utt_id",
    "recording_id",
    "source_recording_id",
    "meeting_id",
    "session_id",
)
CLUSTER_PRIORITY = (
    "speaker_id",
    "meeting_id",
    "session_id",
    "source_recording_id",
    "recording_id",
    "item_id",
    "utt_id",
)


def paired_comparison(
    baseline_path: Path,
    candidate_path: Path,
    *,
    metric: str,
    baseline_scenario_id: str,
    candidate_scenario_id: str,
    seed: int = 3800,
    bootstrap_repetitions: int = 2000,
    confidence_level: float = 0.95,
) -> dict[str, object]:
    """Compare shared item rows with a deterministic cluster bootstrap."""

    if bootstrap_repetitions < 100:
        raise AnalysisContractError("cluster bootstrap requires at least 100 repetitions")
    baseline = pq.read_table(baseline_path).to_pandas()
    candidate = pq.read_table(candidate_path).to_pandas()
    if metric not in baseline.columns or metric not in candidate.columns:
        raise AnalysisContractError(f"item metric field is unavailable: {metric}")
    keys = [name for name in ITEM_KEY_PRIORITY if name in baseline.columns and name in candidate.columns]
    if not keys:
        raise AnalysisContractError("paired comparison has no shared stable item key")
    key = keys[0]
    _require_unique(baseline, key, "baseline")
    _require_unique(candidate, key, "candidate")
    cluster = next(
        (name for name in CLUSTER_PRIORITY if name in baseline.columns and name in candidate.columns),
        key,
    )
    baseline_columns = [key, metric] + ([cluster] if cluster != key else [])
    candidate_columns = [key, metric]
    joined = baseline[baseline_columns].merge(
        candidate[candidate_columns],
        on=key,
        how="inner",
        suffixes=("_baseline", "_candidate"),
        validate="one_to_one",
    )
    baseline_metric = f"{metric}_baseline"
    candidate_metric = f"{metric}_candidate"
    joined[baseline_metric] = pd.to_numeric(joined[baseline_metric], errors="coerce")
    joined[candidate_metric] = pd.to_numeric(joined[candidate_metric], errors="coerce")
    valid = joined.dropna(subset=[baseline_metric, candidate_metric]).copy()
    if valid.empty:
        raise AnalysisContractError("paired comparison has no finite shared metric values")
    valid["difference"] = valid[candidate_metric] - valid[baseline_metric]
    clusters = {
        str(name): frame["difference"].astype(float).tolist()
        for name, frame in valid.groupby(cluster, dropna=False, sort=True)
    }
    differences = valid["difference"].astype(float).tolist()
    baseline_values = valid[baseline_metric].astype(float).tolist()
    candidate_values = valid[candidate_metric].astype(float).tolist()
    duration_field = next(
        (
            name
            for name in ("duration_sec", "audio_duration_sec", "segment_duration_sec")
            if name in baseline.columns and name in candidate.columns
        ),
        None,
    )
    mean_difference = _mean(differences)
    baseline_mean = _mean(baseline_values)
    distribution = _cluster_bootstrap(clusters, seed, bootstrap_repetitions)
    alpha = (1.0 - confidence_level) / 2.0
    return {
        "schema_version": COMPARISON_SCHEMA_VERSION,
        "metric": metric,
        "baseline_scenario_id": baseline_scenario_id,
        "candidate_scenario_id": candidate_scenario_id,
        "pair_key": key,
        "cluster_key": cluster,
        "baseline_item_count": int(len(baseline)),
        "candidate_item_count": int(len(candidate)),
        "shared_item_count": int(len(joined)),
        "valid_pair_count": int(len(valid)),
        "missing_or_invalid_pair_count": int(len(joined) - len(valid)),
        "baseline_only_count": int(len(baseline) - len(joined)),
        "candidate_only_count": int(len(candidate) - len(joined)),
        "cluster_count": len(clusters),
        "duration": _duration_summary(baseline, candidate, valid, duration_field, key),
        "baseline_mean": baseline_mean,
        "candidate_mean": _mean(candidate_values),
        "absolute_change": mean_difference,
        "relative_change": mean_difference / baseline_mean if baseline_mean != 0 else None,
        "effect_size": _paired_effect_size(differences),
        "confidence_interval": {
            "level": confidence_level,
            "lower": _quantile(distribution, alpha),
            "upper": _quantile(distribution, 1.0 - alpha),
            "method": "deterministic_cluster_bootstrap_mean_difference",
            "repetitions": bootstrap_repetitions,
            "seed": seed,
        },
        "missing_failure_policy": "all unmatched and invalid rows are counted explicitly; no value is imputed",
        "multiple_comparison": {
            "warning": "Apply the preregistered correction when three or more confirmatory comparisons are interpreted together.",
            "adjusted_p_value": None,
        },
    }


def repeated_finalist_variance(values: Sequence[float]) -> dict[str, object]:
    finite = [float(value) for value in values if math.isfinite(float(value))]
    if len(finite) < 2:
        return {"count": len(finite), "mean": _mean(finite) if finite else None, "variance": None, "stddev": None}
    mean = _mean(finite)
    variance = sum((value - mean) ** 2 for value in finite) / (len(finite) - 1)
    return {"count": len(finite), "mean": mean, "variance": variance, "stddev": math.sqrt(variance)}


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Return monotone Benjamini-Hochberg adjusted p-values."""

    count = len(p_values)
    ordered = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * count
    running = 1.0
    for reverse_rank, (index, value) in enumerate(reversed(ordered), start=1):
        rank = count - reverse_rank + 1
        running = min(running, float(value) * count / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


def _cluster_bootstrap(
    clusters: Mapping[str, Sequence[float]], seed: int, repetitions: int
) -> list[float]:
    names = sorted(clusters)
    rng = random.Random(seed)
    values: list[float] = []
    for _ in range(repetitions):
        selected = [names[rng.randrange(len(names))] for _ in names]
        sample = [value for name in selected for value in clusters[name]]
        values.append(_mean(sample))
    return sorted(values)


def _paired_effect_size(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = _mean(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    deviation = math.sqrt(variance)
    return mean / deviation if deviation > 0 else None


def _duration_summary(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    valid: pd.DataFrame,
    field: str | None,
    key: str,
) -> dict[str, object]:
    if field is None:
        return {
            "field": None,
            "baseline_total_sec": None,
            "candidate_total_sec": None,
            "valid_shared_total_sec": None,
            "availability_reason": "no shared registered duration field",
        }
    baseline_values = pd.to_numeric(baseline[field], errors="coerce")
    candidate_values = pd.to_numeric(candidate[field], errors="coerce")
    duration_by_key = baseline[[key, field]].copy()
    duration_by_key[field] = pd.to_numeric(duration_by_key[field], errors="coerce")
    valid_keys = set(valid[key].astype(str))
    valid_duration = duration_by_key[duration_by_key[key].astype(str).isin(valid_keys)][field]
    return {
        "field": field,
        "baseline_total_sec": float(baseline_values.sum(min_count=1)) if baseline_values.notna().any() else None,
        "candidate_total_sec": float(candidate_values.sum(min_count=1)) if candidate_values.notna().any() else None,
        "valid_shared_total_sec": float(valid_duration.sum(min_count=1)) if valid_duration.notna().any() else None,
        "availability_reason": "registered shared duration field present",
    }


def _require_unique(frame: pd.DataFrame, key: str, label: str) -> None:
    if frame[key].isna().any() or frame[key].astype(str).duplicated().any():
        raise AnalysisContractError(f"{label} item key {key} is null or duplicated")


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise AnalysisContractError("cannot calculate a quantile from no values")
    position = (len(values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(values[lower])
    fraction = position - lower
    return float(values[lower] * (1.0 - fraction) + values[upper] * fraction)
