"""Deterministic open-set attribution and reference scoring.

This module deliberately has no model dependency.  It accepts cached embeddings so
threshold exploration cannot accidentally rerun either diarization or embedding.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import permutations
from typing import Iterable, Mapping, Sequence

import numpy as np

from app.hybrid_speaker_attribution.contracts import HybridAttributionError


@dataclass(frozen=True)
class AttributionSettings:
    product_threshold: float
    score_margin: float = 0.0
    minimum_segment_duration_sec: float = 0.75
    minimum_evidence_duration_sec: float = 0.75
    enrollment_aggregation: str = "normalized_mean"
    cluster_aggregation: str = "normalized_mean"
    overlap_policy: str = "include_predicted_overlap"

    def __post_init__(self) -> None:
        if self.minimum_segment_duration_sec < 0 or self.minimum_evidence_duration_sec <= 0:
            raise HybridAttributionError("evidence durations must be positive")
        if self.score_margin < 0:
            raise HybridAttributionError("score margin must be non-negative")
        if self.enrollment_aggregation not in {
            "normalized_mean", "duration_weighted_mean", "multi_template_mean_score"
        }:
            raise HybridAttributionError("unsupported enrollment aggregation")
        if self.cluster_aggregation not in {"normalized_mean", "duration_weighted_mean"}:
            raise HybridAttributionError("unsupported cluster aggregation")
        if self.overlap_policy not in {
            "include_predicted_overlap", "exclude_predicted_overlap_segments"
        }:
            raise HybridAttributionError("unsupported overlap policy")


def attribute_recording(
    *,
    recording_id: str,
    segments: Sequence[Mapping[str, object]],
    enrollment: Mapping[str, Sequence[Mapping[str, object]]],
    settings: AttributionSettings,
    evidence_checkpoints_sec: Sequence[float] = (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
) -> dict[str, object]:
    """Attribute diarization clusters in final and strictly causal progressive modes."""

    ordered = sorted(segments, key=lambda row: (float(row["start_sec"]), str(row["segment_id"])))
    by_cluster: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in ordered:
        if float(row["end_sec"]) <= float(row["start_sec"]):
            raise HybridAttributionError("segment end must be after segment start")
        by_cluster[str(row["cluster_id"])].append(row)
    unknown_labels = {
        cluster: f"Unknown_{index}"
        for index, cluster in enumerate(
            sorted(by_cluster, key=lambda value: (float(by_cluster[value][0]["start_sec"]), value)),
            start=1,
        )
    }
    templates = _prepare_templates(enrollment, settings.enrollment_aggregation)
    final_rows = []
    checkpoint_rows = []
    for cluster in sorted(by_cluster, key=lambda value: (float(by_cluster[value][0]["start_sec"]), value)):
        usable = _usable(by_cluster[cluster], settings)
        final_rows.append(
            _decision(
                recording_id=recording_id,
                cluster_id=cluster,
                usable=usable,
                templates=templates,
                settings=settings,
                unknown_label=unknown_labels[cluster],
                mode="final",
                observation_end_sec=max(float(row["end_sec"]) for row in by_cluster[cluster]),
            )
        )
        for checkpoint in evidence_checkpoints_sec:
            prefix = _prefix_for_budget(usable, float(checkpoint))
            checkpoint_rows.append(
                {
                    **_decision(
                        recording_id=recording_id,
                        cluster_id=cluster,
                        usable=prefix,
                        templates=templates,
                        settings=settings,
                        unknown_label=unknown_labels[cluster],
                        mode="progressive_checkpoint",
                        observation_end_sec=_observation_end(prefix, by_cluster[cluster]),
                    ),
                    "evidence_budget_sec": float(checkpoint),
                }
            )
    progressive_rows = []
    seen: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in ordered:
        cluster = str(row["cluster_id"])
        if _is_usable(row, settings):
            seen[cluster].append(row)
        progressive_rows.append(
            {
                **_decision(
                    recording_id=recording_id,
                    cluster_id=cluster,
                    usable=seen[cluster],
                    templates=templates,
                    settings=settings,
                    unknown_label=unknown_labels[cluster],
                    mode="progressive",
                    observation_end_sec=float(row["end_sec"]),
                ),
                "segment_id": str(row["segment_id"]),
                "start_sec": float(row["start_sec"]),
                "end_sec": float(row["end_sec"]),
            }
        )
    return {
        "schema_version": "hybrid-speaker-attribution-decisions.v1",
        "recording_id": recording_id,
        "final": final_rows,
        "progressive": progressive_rows,
        "evidence_checkpoints": checkpoint_rows,
    }


def score_recording(
    *,
    reference_turns: Sequence[Mapping[str, object]],
    predicted_turns: Sequence[Mapping[str, object]],
    local_to_global: Mapping[str, str],
    speaker_states: Mapping[str, Mapping[str, object]],
    final_decisions: Sequence[Mapping[str, object]],
    progressive_decisions: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Score known IDs exactly and unknown IDs with recording-local optimal mapping."""

    final_by_cluster = {str(row["cluster_id"]): str(row["assigned_label"]) for row in final_decisions}
    progressive_by_segment = {
        str(row["segment_id"]): dict(row) for row in progressive_decisions
    }
    refs = [_reference_row(row, local_to_global, speaker_states) for row in reference_turns]
    predictions_final = [
        {**dict(row), "assigned_label": final_by_cluster.get(str(row["cluster_id"]), "Provisional")}
        for row in predicted_turns
    ]
    predictions_progressive = [
        {
            **dict(row),
            **progressive_by_segment.get(
                str(row["segment_id"]),
                {"assigned_label": "Provisional", "observation_end_sec": row["end_sec"]},
            ),
        }
        for row in predicted_turns
    ]
    unknown_map = _optimal_unknown_mapping(refs, predictions_final)
    final_metrics = _time_metrics(refs, predictions_final, unknown_map)
    progressive_metrics = _time_metrics(refs, predictions_progressive, unknown_map)
    structure = _cluster_structure(refs, predictions_final)
    latency = _latency_and_churn(refs, predictions_progressive)
    reentry = _reentry_metrics(refs, predictions_progressive, unknown_map)
    return {
        "schema_version": "hybrid-speaker-attribution-metrics.v1",
        **final_metrics,
        "progressive_time_weighted_identity_accuracy": progressive_metrics["time_weighted_identity_accuracy"],
        "progressive_false_known_rate": progressive_metrics["false_known_rate"],
        **structure,
        **latency,
        **reentry,
        "unknown_label_mapping": unknown_map,
        "valid_output": all(
            value in {"KNOWN", "UNKNOWN", "PROVISIONAL"}
            for value in (str(row["decision_state"]) for row in final_decisions)
        ),
    }


def _prepare_templates(
    enrollment: Mapping[str, Sequence[Mapping[str, object]]], method: str
) -> dict[str, object]:
    templates: dict[str, object] = {}
    dimension = None
    for identity, observations in sorted(enrollment.items()):
        good = [row for row in observations if str(row.get("status", "ok")) == "ok"]
        if not good:
            continue
        vectors = np.asarray([_normal(row["vector"]) for row in good], dtype=np.float64)
        if dimension is None:
            dimension = vectors.shape[1]
        elif vectors.shape[1] != dimension:
            raise HybridAttributionError("embedding dimensions are inconsistent")
        if method == "multi_template_mean_score":
            templates[identity] = vectors
        else:
            weights = None
            if method == "duration_weighted_mean":
                weights = np.asarray([float(row.get("duration_sec", 1.0)) for row in good])
            templates[identity] = _normal(np.average(vectors, axis=0, weights=weights))
    return templates


def _decision(
    *, recording_id: str, cluster_id: str, usable: Sequence[Mapping[str, object]],
    templates: Mapping[str, object], settings: AttributionSettings,
    unknown_label: str, mode: str, observation_end_sec: float,
) -> dict[str, object]:
    evidence = sum(float(row.get("duration_sec") or float(row["end_sec"]) - float(row["start_sec"])) for row in usable)
    scores: list[tuple[str, float]] = []
    if usable and templates:
        weights = None
        if settings.cluster_aggregation == "duration_weighted_mean":
            weights = np.asarray([float(row.get("duration_sec", 1.0)) for row in usable])
        query = _normal(np.average(np.asarray([_normal(row["vector"]) for row in usable]), axis=0, weights=weights))
        for identity, raw_template in templates.items():
            template = np.asarray(raw_template)
            score = float(np.mean(template @ query)) if template.ndim == 2 else float(template @ query)
            scores.append((identity, score))
    scores.sort(key=lambda item: (-item[1], item[0]))
    top_identity, top_score = scores[0] if scores else (None, None)
    second_score = scores[1][1] if len(scores) > 1 else None
    margin = (top_score - second_score) if top_score is not None and second_score is not None else None
    if evidence < settings.minimum_evidence_duration_sec:
        assigned, state, category = f"Provisional_{cluster_id}", "PROVISIONAL", "INSUFFICIENT_EVIDENCE"
    elif top_score is not None and top_score >= settings.product_threshold and (
        margin is None or margin >= settings.score_margin
    ):
        assigned, state, category = str(top_identity), "KNOWN", "KNOWN_CANDIDATE"
    else:
        assigned, state, category = unknown_label, "UNKNOWN", "OPEN_SET_REJECTION"
    return {
        "recording_id": recording_id,
        "cluster_id": cluster_id,
        "mode": mode,
        "observation_end_sec": observation_end_sec,
        "evidence_duration_sec": evidence,
        "usable_segment_count": len(usable),
        "assigned_label": assigned,
        "decision_state": state,
        "decision_category": category,
        "top_candidate_id": top_identity,
        "top_score": top_score,
        "second_score": second_score,
        "score_margin": margin,
        "threshold": settings.product_threshold,
        "required_margin": settings.score_margin,
        "candidate_scores": [
            {"enrolled_id": identity, "score": score}
            for identity, score in scores
        ],
    }


def _usable(rows: Sequence[Mapping[str, object]], settings: AttributionSettings) -> list[Mapping[str, object]]:
    return [row for row in rows if _is_usable(row, settings)]


def _is_usable(row: Mapping[str, object], settings: AttributionSettings) -> bool:
    duration = float(row.get("duration_sec") or float(row["end_sec"]) - float(row["start_sec"]))
    return (
        str(row.get("status", "ok")) == "ok"
        and duration >= settings.minimum_segment_duration_sec
        and not (
            settings.overlap_policy == "exclude_predicted_overlap_segments"
            and bool(row.get("predicted_overlap", False))
        )
    )


def _prefix_for_budget(rows: Sequence[Mapping[str, object]], budget: float) -> list[Mapping[str, object]]:
    chosen = []
    elapsed = 0.0
    for row in rows:
        if elapsed >= budget:
            break
        chosen.append(row)
        elapsed += float(row.get("duration_sec") or float(row["end_sec"]) - float(row["start_sec"]))
    return chosen


def _observation_end(prefix: Sequence[Mapping[str, object]], fallback: Sequence[Mapping[str, object]]) -> float:
    rows = prefix or fallback[:1]
    return max(float(row["end_sec"]) for row in rows)


def _normal(vector: object) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float64)
    if value.ndim != 1 or value.size == 0:
        raise HybridAttributionError("embedding must be a non-empty vector")
    norm = float(np.linalg.norm(value))
    if not np.isfinite(norm) or norm <= 0:
        raise HybridAttributionError("embedding is not normalizable")
    return value / norm


def _reference_row(row: Mapping[str, object], local_to_global: Mapping[str, str], states: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    local = str(row.get("speaker_label") or row.get("speaker_id"))
    global_id = local_to_global[local]
    state = states[global_id]
    expected = state.get("enrolled_id") if state["identity_state"] == "KNOWN" else state.get("unknown_reference_id")
    return {**dict(row), "global_speaker_id": global_id, "identity_state": state["identity_state"], "expected_label": str(expected)}


def _optimal_unknown_mapping(refs: Sequence[Mapping[str, object]], predictions: Sequence[Mapping[str, object]]) -> dict[str, str]:
    ref_ids = sorted({str(row["expected_label"]) for row in refs if row["identity_state"] == "UNKNOWN"})
    pred_ids = sorted({str(row["assigned_label"]) for row in predictions if str(row["assigned_label"]).startswith("Unknown_")})
    if not ref_ids or not pred_ids:
        return {}
    weights = {(ref, pred): 0.0 for ref in ref_ids for pred in pred_ids}
    for ref in refs:
        if ref["identity_state"] != "UNKNOWN":
            continue
        for pred in predictions:
            overlap = _overlap(ref, pred)
            label = str(pred["assigned_label"])
            if label in pred_ids:
                weights[(str(ref["expected_label"]), label)] += overlap
    best_score = -1.0
    best: dict[str, str] = {}
    if len(ref_ids) <= len(pred_ids):
        for chosen in permutations(pred_ids, len(ref_ids)):
            score = sum(weights[(ref, pred)] for ref, pred in zip(ref_ids, chosen))
            if score > best_score:
                best_score, best = score, dict(zip(chosen, ref_ids))
    else:
        for chosen in permutations(ref_ids, len(pred_ids)):
            score = sum(weights[(ref, pred)] for ref, pred in zip(chosen, pred_ids))
            if score > best_score:
                best_score, best = score, dict(zip(pred_ids, chosen))
    return best


def _time_metrics(refs: Sequence[Mapping[str, object]], predictions: Sequence[Mapping[str, object]], unknown_map: Mapping[str, str]) -> dict[str, float | int]:
    totals = Counter()
    for ref in refs:
        ref_state = str(ref["identity_state"])
        start, end = float(ref["start_sec"]), float(ref["end_sec"])
        duration = end - start
        totals["reference_speaker_time_sec"] += duration
        totals[f"{ref_state.lower()}_reference_time_sec"] += duration
        relevant = [pred for pred in predictions if _overlap(ref, pred) > 0]
        boundaries = sorted({start, end, *(max(start, float(pred["start_sec"])) for pred in relevant), *(min(end, float(pred["end_sec"])) for pred in relevant)})
        for left, right in zip(boundaries, boundaries[1:]):
            value = right - left
            if value <= 0:
                continue
            labels = {
                str(pred["assigned_label"])
                for pred in relevant
                if float(pred["start_sec"]) < right and float(pred["end_sec"]) > left
            }
            if not labels:
                continue
            totals["covered_time_sec"] += value
            if ref_state == "KNOWN":
                if str(ref["expected_label"]) in labels:
                    totals["known_correct_time_sec"] += value
                    totals["correct_time_sec"] += value
                elif all(label.startswith("Unknown_") or label.startswith("Provisional_") for label in labels):
                    totals["known_rejected_as_unknown_time_sec"] += value
                else:
                    totals["wrong_known_time_sec"] += value
            elif any(label.startswith("Unknown_") and unknown_map.get(label) == ref["expected_label"] for label in labels):
                totals["unknown_correctly_rejected_time_sec"] += value
                totals["correct_time_sec"] += value
            elif any(not (label.startswith("Unknown_") or label.startswith("Provisional_")) for label in labels):
                totals["false_known_time_sec"] += value
            else:
                totals["unknown_rejected_wrong_instance_time_sec"] += value
    known = totals["known_reference_time_sec"]
    unknown = totals["unknown_reference_time_sec"]
    covered = totals["covered_time_sec"]
    reference = totals["reference_speaker_time_sec"]
    return {
        **{key: float(value) for key, value in totals.items()},
        "known_identity_accuracy": _ratio(totals["known_correct_time_sec"], known),
        "wrong_known_rate": _ratio(totals["wrong_known_time_sec"], known),
        "known_to_unknown_rate": _ratio(totals["known_rejected_as_unknown_time_sec"], known),
        "unknown_rejection_rate": _ratio(totals["unknown_correctly_rejected_time_sec"], unknown),
        "false_known_rate": _ratio(totals["false_known_time_sec"], unknown),
        "identity_coverage": _ratio(covered, reference),
        "identity_precision_on_covered_time": _ratio(totals["correct_time_sec"], covered),
        "time_weighted_identity_accuracy": _ratio(totals["correct_time_sec"], reference),
    }


def _cluster_structure(refs: Sequence[Mapping[str, object]], predictions: Sequence[Mapping[str, object]]) -> dict[str, int]:
    ref_to_clusters: dict[str, set[str]] = defaultdict(set)
    cluster_to_refs: dict[str, set[str]] = defaultdict(set)
    for ref in refs:
        for pred in predictions:
            if _overlap(ref, pred) > 0:
                ref_id, cluster = str(ref["global_speaker_id"]), str(pred["cluster_id"])
                ref_to_clusters[ref_id].add(cluster)
                cluster_to_refs[cluster].add(ref_id)
    return {
        "fragmentation_count": sum(max(0, len(values) - 1) for values in ref_to_clusters.values()),
        "merge_count": sum(max(0, len(values) - 1) for values in cluster_to_refs.values()),
        "reference_speaker_count": len({str(row["global_speaker_id"]) for row in refs}),
        "predicted_cluster_count": len({str(row["cluster_id"]) for row in predictions}),
    }


def _latency_and_churn(refs: Sequence[Mapping[str, object]], progressive: Sequence[Mapping[str, object]]) -> dict[str, object]:
    by_cluster: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in progressive:
        by_cluster[str(row["cluster_id"])].append(row)
    churn = 0
    for rows in by_cluster.values():
        labels = [str(row["assigned_label"]) for row in sorted(rows, key=lambda value: float(value["observation_end_sec"]))]
        churn += sum(left != right for left, right in zip(labels, labels[1:]))
    latencies = []
    for ref_id in sorted({str(row["expected_label"]) for row in refs if row["identity_state"] == "KNOWN"}):
        first_ref = min(float(row["start_sec"]) for row in refs if row["expected_label"] == ref_id)
        matching_refs = [row for row in refs if row["expected_label"] == ref_id]
        hits = [
            float(row["observation_end_sec"])
            for row in progressive
            if row["assigned_label"] == ref_id
            and any(_overlap(row, reference) > 0 for reference in matching_refs)
        ]
        if hits:
            latencies.append(max(0.0, min(hits) - first_ref))
    return {
        "identity_churn_count": churn,
        "stable_known_identity_latency_mean_sec": float(np.mean(latencies)) if latencies else None,
        "stable_known_identity_latency_count": len(latencies),
    }


def _reentry_metrics(refs: Sequence[Mapping[str, object]], progressive: Sequence[Mapping[str, object]], unknown_map: Mapping[str, str]) -> dict[str, object]:
    by_reference: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for ref in refs:
        by_reference[str(ref["expected_label"])].append(ref)
    total, consistent, unknown_total, unknown_consistent = 0, 0, 0, 0
    inverse_unknown = {reference: predicted for predicted, reference in unknown_map.items()}
    for reference_id, turns in by_reference.items():
        ordered = sorted(turns, key=lambda row: float(row["start_sec"]))
        if len(ordered) < 2:
            continue
        labels = []
        for turn in ordered:
            weights = Counter()
            for pred in progressive:
                value = _overlap(turn, pred)
                if value > 0:
                    weights[str(pred["assigned_label"])] += value
            labels.append(weights.most_common(1)[0][0] if weights else None)
        is_unknown = str(ordered[0]["identity_state"]) == "UNKNOWN"
        expected_unknown = inverse_unknown.get(reference_id)
        for left, right in zip(labels, labels[1:]):
            if left is None or right is None:
                continue
            total += 1
            consistent += left == right
            if is_unknown:
                unknown_total += 1
                unknown_consistent += left == right and (expected_unknown is None or left == expected_unknown)
    return {
        "reentry_comparison_count": total,
        "reentry_identity_consistency": _ratio(consistent, total),
        "unknown_reentry_comparison_count": unknown_total,
        "unknown_reentry_consistency": _ratio(unknown_consistent, unknown_total),
    }


def _overlap(left: Mapping[str, object], right: Mapping[str, object]) -> float:
    return max(0.0, min(float(left["end_sec"]), float(right["end_sec"])) - max(float(left["start_sec"]), float(right["start_sec"])))


def _ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 0 else 0.0
