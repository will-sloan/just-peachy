"""Vectorized, calibration-only deployment replay over frozen embedding bundles."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import time
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from .contracts import (
    SpeakerDeploymentError,
    canonical_sha256,
    file_sha256,
    git_sha,
    load_config,
    resolve_tool_path,
    write_json_atomic,
)


def _unit(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    if np.any(~np.isfinite(norms)) or np.any(norms <= 0):
        raise SpeakerDeploymentError("embedding bundle contains an invalid vector")
    return values / norms


def _rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _threshold_for_cap(scores: np.ndarray, eligible: np.ndarray, cap: float, denominator: int) -> float:
    """Lowest inclusive threshold whose accepted count does not exceed the cap."""
    permitted = int(math.floor(float(cap) * int(denominator) + 1e-12))
    values = np.sort(np.asarray(scores)[np.asarray(eligible, dtype=bool)])[::-1]
    if len(values) <= permitted:
        return -1.0
    return float(np.nextafter(values[permitted], np.inf))


def calibrate_open_set_policy(
    known_scores: np.ndarray,
    known_margins: np.ndarray,
    known_correct: np.ndarray,
    unknown_scores: np.ndarray,
    unknown_margins: np.ndarray,
    *,
    fpir_target: float,
    wrong_name_rate_cap: float,
    margin_grid: Sequence[float],
) -> dict[str, object]:
    """Fit score+margin gates using calibration data only.

    The chosen gate maximizes correctly named known probes while independently
    capping unknown false identification and known-speaker wrong-name assignment.
    """
    candidates: list[dict[str, object]] = []
    for margin in margin_grid:
        unknown_margin_ok = unknown_margins >= float(margin)
        wrong = (~known_correct) & (known_margins >= float(margin))
        score_threshold = max(
            _threshold_for_cap(unknown_scores, unknown_margin_ok, fpir_target, len(unknown_scores)),
            _threshold_for_cap(known_scores, wrong, wrong_name_rate_cap, len(known_scores)),
        )
        known_accept = (known_scores >= score_threshold) & (known_margins >= float(margin))
        unknown_accept = (unknown_scores >= score_threshold) & unknown_margin_ok
        row = {
            "score_threshold": float(score_threshold),
            "margin_threshold": float(margin),
            "calibration_fpir": _rate(int(unknown_accept.sum()), len(unknown_scores)),
            "calibration_known_correct_acceptance": _rate(int((known_accept & known_correct).sum()), len(known_scores)),
            "calibration_known_wrong_name_rate": _rate(int((known_accept & ~known_correct).sum()), len(known_scores)),
        }
        candidates.append(row)
    candidates.sort(
        key=lambda row: (
            -float(row["calibration_known_correct_acceptance"] or 0.0),
            float(row["calibration_known_wrong_name_rate"] or 0.0),
            float(row["calibration_fpir"] or 0.0),
            -float(row["margin_threshold"]),
            -float(row["score_threshold"]),
        )
    )
    selected = dict(candidates[0])
    selected.update(
        {
            "fpir_target": float(fpir_target),
            "known_wrong_name_rate_cap": float(wrong_name_rate_cap),
            "threshold_source": "calibration_only",
            "evaluation_used_for_selection": False,
            "acceptance_rule": "top1_score >= score_threshold AND top1_minus_top2 >= margin_threshold",
        }
    )
    return selected


def _top(scores: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if scores.ndim != 2 or scores.shape[1] < 1:
        raise SpeakerDeploymentError("score matrix must contain at least one gallery identity")
    order = np.argsort(scores, axis=1)
    best = order[:, -1]
    top1 = scores[np.arange(len(scores)), best]
    if scores.shape[1] == 1:
        margin = np.full(len(scores), np.inf)
    else:
        margin = top1 - scores[np.arange(len(scores)), order[:, -2]]
    return best, top1, margin


def _decision_metrics(
    scores: np.ndarray,
    true_speakers: np.ndarray,
    gallery: Sequence[str],
    policy: Mapping[str, object],
    *,
    known: bool,
) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    best, top1, margin = _top(scores)
    accepted = (top1 >= float(policy["score_threshold"])) & (margin >= float(policy["margin_threshold"]))
    predicted = np.asarray(gallery, dtype=object)[best]
    correct = predicted == true_speakers if known else np.zeros(len(scores), dtype=bool)
    if known:
        metrics = {
            "probes": len(scores),
            "closed_set_top1": _rate(int(correct.sum()), len(scores)),
            "dir_rank1": _rate(int((accepted & correct).sum()), len(scores)),
            "known_correct_acceptance": _rate(int((accepted & correct).sum()), len(scores)),
            "fnir": _rate(int((~(accepted & correct)).sum()), len(scores)),
            "known_rejection_rate": _rate(int((~accepted).sum()), len(scores)),
            "known_wrong_name_rate": _rate(int((accepted & ~correct).sum()), len(scores)),
        }
    else:
        metrics = {
            "probes": len(scores),
            "fpir": _rate(int(accepted.sum()), len(scores)),
            "unknown_rejection_rate": _rate(int((~accepted).sum()), len(scores)),
        }
    return metrics, {"best": best, "top1": top1, "margin": margin, "accepted": accepted, "correct": correct, "predicted": predicted}


def _read_bundle(path: Path) -> tuple[dict[str, np.ndarray], str, dict[str, float]]:
    if not path.is_file():
        raise SpeakerDeploymentError(f"missing observation bundle: {path}")
    with np.load(path, allow_pickle=False) as bundle:
        ids = [str(value) for value in bundle["item_ids"]]
        statuses = [str(value) for value in bundle["statuses"]]
        vectors = _unit(np.asarray(bundle["vectors"], dtype=np.float64))
        identity = str(bundle["backend_identity_hash"][0])
        durations = np.asarray(bundle["durations_sec"], dtype=np.float64)
        extraction = np.asarray(bundle["extraction_sec"], dtype=np.float64)
    if len(set(ids)) != len(ids) or len(ids) != len(vectors):
        raise SpeakerDeploymentError("observation bundle item identity mismatch")
    valid = np.asarray([value == "ok" for value in statuses], dtype=bool)
    resource = {
        "successful_items": int(valid.sum()),
        "audio_duration_sec": float(durations[valid].sum()),
        "extraction_wall_sec_sum": float(extraction[valid].sum()),
        "mean_extraction_sec": float(extraction[valid].mean()),
        "embedding_rtf": float(extraction[valid].sum() / durations[valid].sum()),
    }
    return {item_id: vectors[index] for index, item_id in enumerate(ids) if statuses[index] == "ok"}, identity, resource


def _dataset_paths(config: Mapping[str, object], backend: str, dataset: str) -> tuple[Path, Path]:
    spec = config["datasets"][dataset]
    protocol = resolve_tool_path(str(spec["protocol_root"]))
    if dataset == "common_voice_60plus":
        result = resolve_tool_path(str(spec["result_root"])) / backend
        bundle = result / "extraction" / "observations.npz"
    else:
        result = resolve_tool_path(str(spec["result_roots"][backend]))
        bundle = result / "extraction" / "observations.npz"
    return protocol, bundle


def _load_dataset(config: Mapping[str, object], backend: str, dataset: str) -> dict[str, object]:
    protocol, bundle_path = _dataset_paths(config, backend, dataset)
    condition = str(config["datasets"][dataset]["condition"])
    observations, identity, resource = _read_bundle(bundle_path)
    names = ("enrollment", "calibration", "known_evaluation", "unknown_evaluation")
    tables = {name: pd.read_parquet(protocol / f"{name}.parquet") for name in names}
    for name, frame in list(tables.items()):
        if "protocol_condition" in frame.columns:
            frame = frame[frame["protocol_condition"] == condition]
        frame = frame[frame["item_id"].isin(observations)].copy()
        tables[name] = frame.sort_values(["speaker_key", "selection_rank", "item_id"]).reset_index(drop=True)
    speakers = sorted(str(value) for value in tables["enrollment"]["speaker_key"].unique())
    if not speakers:
        raise SpeakerDeploymentError(f"{dataset}/{backend} has no enrolled speakers")
    for name in names:
        if tables[name].empty:
            raise SpeakerDeploymentError(f"{dataset}/{backend} has no usable {name} rows")
    return {
        "dataset": dataset,
        "condition": condition,
        "protocol_root": protocol,
        "bundle_path": bundle_path,
        "bundle_sha256": file_sha256(bundle_path),
        "backend_identity_hash": identity,
        "resource": resource,
        "observations": observations,
        "tables": tables,
        "speakers": speakers,
    }


def _speaker_order(speakers: Sequence[str], seed: int, repetition: int) -> list[str]:
    return sorted(speakers, key=lambda value: hashlib.sha256(f"{seed}|gallery|{repetition}|{value}".encode()).hexdigest())


def _enrollment_rows(data: Mapping[str, object], speaker: str, repetition: int, count: int) -> pd.DataFrame:
    rows = data["tables"]["enrollment"]
    rows = rows[rows["speaker_key"] == speaker]
    if len(rows) < count:
        raise SpeakerDeploymentError(f"speaker {speaker} has fewer than {count} enrollment clips")
    values = list(range(len(rows)))
    shift = repetition % len(values)
    indexes = values[shift:] + values[:shift]
    return rows.iloc[indexes[:count]]


def _representations(
    data: Mapping[str, object], gallery: Sequence[str], *, count: int, repetition: int, method: str,
) -> tuple[np.ndarray, np.ndarray]:
    observations = data["observations"]
    groups: list[np.ndarray] = []
    for speaker in gallery:
        rows = _enrollment_rows(data, speaker, repetition, count)
        vectors = np.stack([observations[str(value)] for value in rows["item_id"]])
        durations = rows["duration_sec"].to_numpy(dtype=np.float64)
        if method == "qc_trimmed_normalized_mean" and len(vectors) >= 3:
            cohesion = vectors @ vectors.T
            quality = (cohesion.sum(axis=1) - 1.0) / (len(vectors) - 1)
            vectors = np.delete(vectors, int(np.argmin(quality)), axis=0)
            durations = np.delete(durations, int(np.argmin(quality)))
        groups.append(vectors)
    max_count = max(len(value) for value in groups)
    padded = np.zeros((len(groups), max_count, groups[0].shape[1]), dtype=np.float64)
    weights = np.zeros((len(groups), max_count), dtype=np.float64)
    for index, (speaker, vectors) in enumerate(zip(gallery, groups, strict=True)):
        padded[index, : len(vectors)] = vectors
        if method == "duration_weighted_mean":
            rows = _enrollment_rows(data, speaker, repetition, count)
            durations = rows["duration_sec"].to_numpy(dtype=np.float64)
            if len(vectors) != len(durations):
                durations = np.ones(len(vectors))
            weights[index, : len(vectors)] = durations / durations.sum()
        else:
            weights[index, : len(vectors)] = 1.0 / len(vectors)
    centroids = np.einsum("gk,gkd->gd", weights, padded)
    if method in {"normalized_mean", "duration_weighted_mean", "qc_trimmed_normalized_mean"}:
        centroids = _unit(centroids)
    return centroids, padded


def _probe_matrix(data: Mapping[str, object], frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    observations = data["observations"]
    return (
        np.stack([observations[str(value)] for value in frame["item_id"]]),
        frame["speaker_key"].astype(str).to_numpy(dtype=object),
    )


def _scores(probes: np.ndarray, centroid: np.ndarray, templates: np.ndarray, method: str) -> np.ndarray:
    if method in {"normalized_mean", "duration_weighted_mean", "multi_template_mean_score", "qc_trimmed_normalized_mean"}:
        return probes @ centroid.T
    raw = np.einsum("pd,gkd->pgk", probes, templates)
    valid = np.linalg.norm(templates, axis=2) > 0
    raw = np.where(valid[None, :, :], raw, np.nan)
    if method == "multi_template_max_score":
        return np.nanmax(raw, axis=2)
    if method == "multi_template_top2_mean_score":
        ordered = np.sort(raw, axis=2)
        if raw.shape[2] == 1:
            return ordered[:, :, -1]
        return np.nanmean(ordered[:, :, -2:], axis=2)
    raise SpeakerDeploymentError(f"unsupported aggregation method: {method}")


def _partitions(data: Mapping[str, object], gallery: Sequence[str]) -> dict[str, tuple[np.ndarray, np.ndarray, pd.DataFrame]]:
    tables = data["tables"]
    result = {}
    for key, name, known in (
        ("cal_known", "calibration", True), ("cal_unknown", "calibration", False),
        ("eval_known", "known_evaluation", True), ("eval_unknown", "unknown_evaluation", False),
    ):
        frame = tables[name]
        if name == "calibration":
            frame = frame[frame["known_speaker"].astype(bool) == known]
        if known:
            frame = frame[frame["speaker_key"].astype(str).isin(gallery)]
        matrix, speakers = _probe_matrix(data, frame)
        result[key] = (matrix, speakers, frame.reset_index(drop=True))
    return result


def _fit_and_evaluate(
    score_sets: Mapping[str, np.ndarray], speaker_sets: Mapping[str, np.ndarray], gallery: Sequence[str],
    config: Mapping[str, object], fpir_target: float,
) -> tuple[dict[str, object], dict[str, dict[str, np.ndarray]]]:
    cal_best, cal_score, cal_margin = _top(score_sets["cal_known"])
    cal_correct = np.asarray(gallery, dtype=object)[cal_best] == speaker_sets["cal_known"]
    _, cal_u_score, cal_u_margin = _top(score_sets["cal_unknown"])
    policy = calibrate_open_set_policy(
        cal_score, cal_margin, cal_correct, cal_u_score, cal_u_margin,
        fpir_target=fpir_target,
        wrong_name_rate_cap=float(config["known_wrong_name_rate_cap"]),
        margin_grid=[float(value) for value in config["margin_grid"]],
    )
    known_metrics, known_decisions = _decision_metrics(
        score_sets["eval_known"], speaker_sets["eval_known"], gallery, policy, known=True,
    )
    unknown_metrics, unknown_decisions = _decision_metrics(
        score_sets["eval_unknown"], speaker_sets["eval_unknown"], gallery, policy, known=False,
    )
    return {**policy, **known_metrics, **unknown_metrics}, {"known": known_decisions, "unknown": unknown_decisions}


def _score_sets(data: Mapping[str, object], gallery: Sequence[str], count: int, repetition: int, method: str):
    centroids, templates = _representations(data, gallery, count=count, repetition=repetition, method=method)
    parts = _partitions(data, gallery)
    scores = {key: _scores(value[0], centroids, templates, method) for key, value in parts.items()}
    speakers = {key: value[1] for key, value in parts.items()}
    frames = {key: value[2] for key, value in parts.items()}
    return scores, speakers, frames, centroids, templates


def _gallery_study(data: Mapping[str, object], config: Mapping[str, object], progress) -> list[dict[str, object]]:
    speakers = data["speakers"]
    sizes = [int(value) for value in config["gallery_sizes"] if int(value) <= len(speakers)]
    if len(speakers) not in sizes:
        sizes.append(len(speakers))
    rows = []
    for size in sorted(set(sizes)):
        repetitions = 1 if size == len(speakers) else int(config["gallery_repetitions"])
        for repetition in range(repetitions):
            gallery = _speaker_order(speakers, int(config["selection_seed"]), repetition)[:size]
            scores, speaker_sets, _, _, _ = _score_sets(data, gallery, 5, repetition, "normalized_mean")
            for target in config["fpir_targets"]:
                metrics, _ = _fit_and_evaluate(scores, speaker_sets, gallery, config, float(target))
                rows.append({
                    "dataset": data["dataset"], "gallery_size": size, "repetition": repetition,
                    "enrollment_count": 5, "aggregation_method": "normalized_mean", **metrics,
                })
            progress("gallery_scale", len(rows))
    return rows


def _enrollment_study(data: Mapping[str, object], config: Mapping[str, object], progress) -> list[dict[str, object]]:
    gallery = data["speakers"]
    target = float(config["primary_fpir_target"])
    rows = []
    for count in [int(value) for value in config["enrollment_counts"]]:
        for repetition in range(int(config["enrollment_repetitions"])):
            for method in config["aggregation_methods"]:
                if method == "qc_trimmed_normalized_mean" and count < 3:
                    continue
                scores, speaker_sets, _, _, _ = _score_sets(data, gallery, count, repetition, str(method))
                metrics, _ = _fit_and_evaluate(scores, speaker_sets, gallery, config, target)
                rows.append({
                    "dataset": data["dataset"], "gallery_size": len(gallery), "repetition": repetition,
                    "enrollment_count": count, "aggregation_method": str(method), **metrics,
                })
                progress("enrollment_modes", len(rows))
    return rows


def _hubness(data, config) -> tuple[list[dict[str, object]], dict[str, object]]:
    gallery = data["speakers"]
    scores, speaker_sets, _, _, _ = _score_sets(data, gallery, 5, 0, "normalized_mean")
    metrics, decisions = _fit_and_evaluate(scores, speaker_sets, gallery, config, float(config["primary_fpir_target"]))
    counter = Counter(str(value) for value in decisions["unknown"]["predicted"][decisions["unknown"]["accepted"]])
    rows = [
        {"dataset": data["dataset"], "candidate_speaker_key": speaker, "false_known_assignments": counter.get(speaker, 0)}
        for speaker in gallery
    ]
    rows.sort(key=lambda row: (-int(row["false_known_assignments"]), str(row["candidate_speaker_key"])))
    total = sum(int(row["false_known_assignments"]) for row in rows)
    values = np.asarray([int(row["false_known_assignments"]) for row in rows], dtype=float)
    gini = 0.0
    if total:
        ordered = np.sort(values)
        gini = float((2 * np.sum((np.arange(len(ordered)) + 1) * ordered) / (len(ordered) * ordered.sum())) - (len(ordered) + 1) / len(ordered))
    summary = {
        **metrics,
        "false_known_assignments": total,
        "identities_receiving_false_assignments": int(np.sum(values > 0)),
        "largest_hub_share": _rate(int(values.max()) if len(values) else 0, total),
        "top_10_hub_share": _rate(int(sum(sorted(values, reverse=True)[:10])), total),
        "gini": gini,
    }
    return rows, summary


def _subgroups(data, config) -> list[dict[str, object]]:
    gallery = data["speakers"]
    scores, speaker_sets, frames, _, _ = _score_sets(data, gallery, 5, 0, "normalized_mean")
    _, decisions = _fit_and_evaluate(scores, speaker_sets, gallery, config, float(config["primary_fpir_target"]))
    rows = []
    for partition, frame in (("known", frames["eval_known"]), ("unknown", frames["eval_unknown"])):
        decision = decisions[partition]
        for field in ("gender", "accent_group"):
            if field not in frame:
                continue
            for value in sorted(frame[field].fillna("unknown").astype(str).unique()):
                mask = frame[field].fillna("unknown").astype(str).to_numpy() == value
                if partition == "known":
                    accepted_correct = decision["accepted"] & decision["correct"]
                    metric = _rate(int(accepted_correct[mask].sum()), int(mask.sum()))
                    name = "dir_rank1"
                else:
                    metric = _rate(int(decision["accepted"][mask].sum()), int(mask.sum()))
                    name = "fpir"
                rows.append({"dataset": data["dataset"], "partition": partition, "field": field, "value": value, "probes": int(mask.sum()), "metric": name, "metric_value": metric})
    return rows


def _session_accumulation(data, config) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    gallery = data["speakers"]
    scores, speaker_sets, frames, centroids, templates = _score_sets(data, gallery, 5, 0, "normalized_mean")
    base, _ = _fit_and_evaluate(scores, speaker_sets, gallery, config, float(config["primary_fpir_target"]))
    policy = {"score_threshold": base["score_threshold"], "margin_threshold": base["margin_threshold"]}
    observations = data["observations"]
    rows = []
    trajectories = []
    for partition, frame, known in (("known", frames["eval_known"], True), ("unknown", frames["eval_unknown"], False)):
        per_turn: dict[int, list[tuple[bool, bool]]] = {}
        for _speaker, group in frame.groupby("speaker_key", sort=True):
            group = group.sort_values(["selection_rank", "item_id"]).head(int(config["session_turns"]))
            cumulative = []
            labels: list[str] = []
            correct_by_turn: list[bool] = []
            false_by_turn: list[bool] = []
            for turn, item_id in enumerate(group["item_id"], start=1):
                cumulative.append(observations[str(item_id)])
                probe = _unit(np.mean(np.stack(cumulative), axis=0, keepdims=True))
                score = _scores(probe, centroids, templates, "normalized_mean")
                metrics, decision = _decision_metrics(score, np.asarray([str(_speaker)], dtype=object), gallery, policy, known=known)
                correct_accept = bool(decision["accepted"][0] and (decision["correct"][0] if known else False))
                false_accept = bool(decision["accepted"][0] and not known)
                labels.append(str(decision["predicted"][0]) if bool(decision["accepted"][0]) else "Unknown")
                correct_by_turn.append(correct_accept)
                false_by_turn.append(false_accept)
                per_turn.setdefault(turn, []).append((correct_accept, false_accept))
            first_correct = next((index + 1 for index, value in enumerate(correct_by_turn) if value), None)
            stable_correct = next(
                (index + 1 for index in range(len(correct_by_turn)) if correct_by_turn[index] and all(correct_by_turn[index:])),
                None,
            )
            first_false = next((index + 1 for index, value in enumerate(false_by_turn) if value), None)
            confirmed_labels = []
            previous = "Unknown"
            for index, label in enumerate(labels):
                if label != "Unknown" and index > 0 and labels[index - 1] == label:
                    previous = label
                confirmed_labels.append(previous)
            trajectories.append({
                "dataset": data["dataset"], "partition": partition, "speaker_key": str(_speaker),
                "turns": len(labels), "first_correct_turn": first_correct, "stable_correct_turn": stable_correct,
                "first_false_identification_turn": first_false,
                "wrong_known_turns": sum(label not in {"Unknown", str(_speaker)} for label in labels) if known else None,
                "false_identification_turns": sum(false_by_turn) if not known else None,
                "label_flip_count": sum(labels[index] != labels[index - 1] for index in range(1, len(labels))),
                "premature_false_attribution": bool(known and any(label not in {"Unknown", str(_speaker)} for label in labels[: (first_correct - 1 if first_correct else len(labels))])),
                "two_confirmation_first_named_turn": next((index + 1 for index, label in enumerate(confirmed_labels) if label != "Unknown"), None),
                "two_confirmation_wrong_name_ever": any(label not in {"Unknown", str(_speaker)} for label in confirmed_labels) if known else any(label != "Unknown" for label in confirmed_labels),
                "trajectory_scope": "complete_utterance_accumulation_not_causal_audio_prefix",
            })
        for turn, values in sorted(per_turn.items()):
            rows.append({
                "dataset": data["dataset"], "partition": partition, "turn": turn, "speaker_sessions": len(values),
                "correct_known_acceptance": _rate(sum(value[0] for value in values), len(values)) if known else None,
                "unknown_false_identification": _rate(sum(value[1] for value in values), len(values)) if not known else None,
                "simulation_scope": "deterministic_cross_utterance_embedding_accumulation_not_live_diarization",
            })
    return rows, trajectories


def _bootstrap_default(data, config) -> dict[str, object]:
    gallery = data["speakers"]
    scores, speaker_sets, frames, _, _ = _score_sets(data, gallery, 5, 0, "normalized_mean")
    metrics, decisions = _fit_and_evaluate(scores, speaker_sets, gallery, config, float(config["primary_fpir_target"]))
    known_frame, unknown_frame = frames["eval_known"], frames["eval_unknown"]
    known_groups = {str(key): np.flatnonzero(known_frame["speaker_key"].astype(str).to_numpy() == str(key)) for key in known_frame["speaker_key"].unique()}
    unknown_groups = {str(key): np.flatnonzero(unknown_frame["speaker_key"].astype(str).to_numpy() == str(key)) for key in unknown_frame["speaker_key"].unique()}
    rng = np.random.default_rng(int(config["selection_seed"]) + 701)
    draws = {"dir_rank1": [], "known_wrong_name_rate": [], "fpir": []}
    repetitions = int(config["bootstrap_repetitions"])
    kg, ug = list(known_groups), list(unknown_groups)
    for _ in range(repetitions):
        ki = np.concatenate([known_groups[key] for key in rng.choice(kg, len(kg), replace=True)])
        ui = np.concatenate([unknown_groups[key] for key in rng.choice(ug, len(ug), replace=True)])
        kd = decisions["known"]
        ud = decisions["unknown"]
        draws["dir_rank1"].append(float(np.mean(kd["accepted"][ki] & kd["correct"][ki])))
        draws["known_wrong_name_rate"].append(float(np.mean(kd["accepted"][ki] & ~kd["correct"][ki])))
        draws["fpir"].append(float(np.mean(ud["accepted"][ui])))
    alpha = (1.0 - float(config["confidence_level"])) / 2.0
    return {
        "point_estimates": {key: metrics[key] for key in draws},
        "speaker_cluster_bootstrap": {
            key: {"lower": float(np.quantile(value, alpha)), "upper": float(np.quantile(value, 1 - alpha))}
            for key, value in draws.items()
        },
        "repetitions": repetitions,
        "confidence_level": float(config["confidence_level"]),
        "cluster": "speaker",
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({str(key) for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run_backend(backend: str, output_root: Path, config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    if backend not in config["backends"]:
        raise SpeakerDeploymentError(f"backend is outside the frozen study: {backend}")
    root = output_root.resolve() / backend
    root.mkdir(parents=True, exist_ok=True)
    existing_path = root / "summary.json"
    if existing_path.is_file():
        existing = json.loads(existing_path.read_text(encoding="utf-8"))
        if existing.get("status") == "COMPLETE" and existing.get("study_identity") == canonical_sha256(config):
            return {**existing, "reused": True}
    started = time.monotonic()

    def progress(phase: str, completed: int) -> None:
        write_json_atomic(root / "progress.json", {
            "schema_version": "speaker-embedding-deployment-progress.v1", "backend": backend,
            "status": "RUNNING", "phase": phase, "completed_units": completed,
            "elapsed_sec": time.monotonic() - started, "pid": os.getpid(),
        })

    gallery_rows: list[dict[str, object]] = []
    enrollment_rows: list[dict[str, object]] = []
    hub_rows: list[dict[str, object]] = []
    subgroup_rows: list[dict[str, object]] = []
    session_rows: list[dict[str, object]] = []
    trajectory_rows: list[dict[str, object]] = []
    datasets = []
    bootstraps = {}
    hub_summaries = {}
    for dataset in config["datasets"]:
        progress(f"load_{dataset}", 0)
        data = _load_dataset(config, backend, str(dataset))
        datasets.append({
            "dataset": dataset, "condition": data["condition"], "enrolled_speakers": len(data["speakers"]),
            "backend_identity_hash": data["backend_identity_hash"], "observation_bundle": str(data["bundle_path"]),
            "observation_bundle_sha256": data["bundle_sha256"],
            "resource": data["resource"],
            "calibration_rows": len(data["tables"]["calibration"]),
            "known_evaluation_rows": len(data["tables"]["known_evaluation"]),
            "unknown_evaluation_rows": len(data["tables"]["unknown_evaluation"]),
        })
        gallery_rows.extend(_gallery_study(data, config, progress))
        enrollment_rows.extend(_enrollment_study(data, config, progress))
        hubs, hub_summary = _hubness(data, config)
        hub_rows.extend(hubs)
        hub_summaries[str(dataset)] = hub_summary
        subgroup_rows.extend(_subgroups(data, config))
        curves, trajectories = _session_accumulation(data, config)
        session_rows.extend(curves)
        trajectory_rows.extend(trajectories)
        bootstraps[str(dataset)] = _bootstrap_default(data, config)
    _write_csv(root / "gallery_operating_points.csv", gallery_rows)
    _write_csv(root / "enrollment_operating_modes.csv", enrollment_rows)
    _write_csv(root / "hubness.csv", hub_rows)
    _write_csv(root / "subgroup_metrics.csv", subgroup_rows)
    _write_csv(root / "session_accumulation.csv", session_rows)
    _write_csv(root / "session_trajectories.csv", trajectory_rows)
    summary = {
        "schema_version": "speaker-embedding-deployment-backend.v1", "status": "COMPLETE",
        "study_identity": canonical_sha256(config), "backend": backend, "datasets": datasets,
        "primary_fpir_target": config["primary_fpir_target"], "known_wrong_name_rate_cap": config["known_wrong_name_rate_cap"],
        "hubness": hub_summaries, "bootstrap": bootstraps,
        "evaluation_used_for_threshold_selection": False,
        "pairwise_eer_used_as_deployment_threshold": False,
        "elapsed_sec": time.monotonic() - started, "git_sha": git_sha(),
    }
    write_json_atomic(root / "summary.json", summary)
    write_json_atomic(root / "progress.json", {
        "schema_version": "speaker-embedding-deployment-progress.v1", "backend": backend,
        "status": "COMPLETE", "phase": "complete", "completed_units": len(gallery_rows) + len(enrollment_rows),
        "elapsed_sec": time.monotonic() - started, "pid": os.getpid(),
    })
    return summary
