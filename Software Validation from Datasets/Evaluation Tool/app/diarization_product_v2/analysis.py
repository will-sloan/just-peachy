"""Product-facing diarization metrics, automatic selection, and collection."""

from __future__ import annotations

from collections import defaultdict
import csv
import io
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import statistics
import subprocess
from typing import Iterable, Mapping, Sequence
import zipfile

import numpy as np
import yaml

from app.controlled_diarization.analysis import analyze_results
from app.controlled_diarization.contracts import (
    TOOL_ROOT,
    canonical_json,
    load_config,
    load_pipeline_registry,
    sha256_file,
    sha256_text,
)
from app.controlled_diarization.runner import queue_status
from app.diarization_evaluation.artifacts import write_json_atomic, write_text_atomic
from app.diarization_evaluation.contracts import DiarizationScoringPolicy
from app.diarization_evaluation.formats import RttmTurn, UemRegion, parse_rttm
from app.diarization_evaluation.scoring import score_diarization
from app.diarization_product_v2.contracts import (
    DEFAULT_ANALYSIS_ROOT,
    DEFAULT_CONFIG_PATH,
    DEFAULT_FROZEN_CONFIG_PATH,
    DEFAULT_PROTOCOL_ROOT,
    DEFAULT_RESULT_ROOT,
    DEFAULT_SELECTION_PATH,
    PRIMARY_PIPELINES,
    V1_PROTOCOL_ROOT,
)


EVIDENCE_TARGETS = (0.75, 1.5, 2.0, 3.0)
SHORT_BUCKETS = (
    ("lt_0_50", 0.0, 0.5),
    ("0_50_to_1_00", 0.5, 1.0),
    ("1_00_to_2_00", 1.0, 2.0),
    ("2_00_to_5_00", 2.0, 5.0),
    ("gt_5_00", 5.0, math.inf),
)
REENTRY_BUCKETS = (
    ("lt_1", -math.inf, 1.0),
    ("1_to_5", 1.0, 5.0),
    ("5_to_15", 5.0, 15.0),
    ("15_to_30", 15.0, 30.0),
    ("30_to_60", 30.0, 60.0),
    ("gt_60", 60.0, math.inf),
)


def analyze_and_freeze(*, config_path: Path = DEFAULT_FROZEN_CONFIG_PATH) -> dict[str, object]:
    """Analyze development only and apply the predeclared automatic rule."""

    config_path = config_path.resolve()
    _require_complete(config_path)
    output = DEFAULT_ANALYSIS_ROOT
    output.mkdir(parents=True, exist_ok=True)
    base_outputs = {}
    for protocol, benchmark, result in (
        ("controlled_v1", V1_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v1"),
        ("product_v2", DEFAULT_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v2"),
    ):
        base = output / f"base_{protocol}"
        base_outputs[protocol] = analyze_results(
            pipelines=PRIMARY_PIPELINES,
            tiers=["development"],
            config_path=config_path,
            benchmark_root=benchmark,
            result_root=result,
            output_root=base,
        )
    tables = _product_tables(config_path)
    for name, rows in tables.items():
        _write_csv(output / f"{name}.csv", rows)
    _write_reports(output, tables)
    _write_plots(output, tables)
    selection = _select_and_freeze(config_path, tables)
    manifest = {
        "schema_version": "diarization-product-analysis-manifest.v2",
        "created_at_utc": _now(),
        "protocols": [
            json.loads((V1_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["benchmark_id"],
            json.loads((DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["protocol_id"],
        ],
        "tiers_read": ["development"],
        "evaluation_results_read": False,
        "pipelines": list(PRIMARY_PIPELINES),
        "bootstrap_seed": 3800,
        "bootstrap_repetitions": 1000,
        "tables": {
            f"{name}.csv": {
                "rows": len(rows),
                "sha256": sha256_file(output / f"{name}.csv"),
            }
            for name, rows in tables.items()
        },
        "selection_file": str(DEFAULT_SELECTION_PATH),
        "selection_sha256": sha256_file(DEFAULT_SELECTION_PATH),
        "base_analysis": base_outputs,
    }
    write_json_atomic(output / "analysis_manifest.json", manifest)
    package = collect_package()
    return {
        "analysis_root": str(output),
        "analysis_manifest": str(output / "analysis_manifest.json"),
        "selection": selection,
        "package": package,
    }


def _require_complete(config: Path) -> None:
    errors = []
    for benchmark, result in (
        (V1_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v1"),
        (DEFAULT_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v2"),
    ):
        value = queue_status(
            pipelines=PRIMARY_PIPELINES,
            tiers=["development"],
            config_path=config,
            benchmark_root=benchmark,
            result_root=result,
        )
        errors.extend(
            f"{benchmark.name}/{row['pipeline_id']}: {row['valid']}/{row['planned']} valid"
            for row in value["rows"]
            if int(row["valid"]) != int(row["planned"])
        )
    if errors:
        raise RuntimeError("development evidence is incomplete: " + "; ".join(errors))


def _product_tables(config_path: Path) -> dict[str, list[dict[str, object]]]:
    recording: list[dict[str, object]] = []
    contamination: list[dict[str, object]] = []
    short: list[dict[str, object]] = []
    boundary: list[dict[str, object]] = []
    reentry: list[dict[str, object]] = []
    rare: list[dict[str, object]] = []
    evidence: list[dict[str, object]] = []
    latency: list[dict[str, object]] = []
    mixed: list[dict[str, object]] = []
    long_rows: list[dict[str, object]] = []
    resources: list[dict[str, object]] = []
    identities: list[dict[str, object]] = []
    oracle: list[dict[str, object]] = []

    for protocol, benchmark, result in (
        ("controlled_v1", V1_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v1"),
        ("product_v2", DEFAULT_PROTOCOL_ROOT, DEFAULT_RESULT_ROOT / "v2"),
    ):
        for case in _read_jsonl(benchmark / "development" / "case_manifest.jsonl"):
            for pipeline in PRIMARY_PIPELINES:
                root = result / "development" / pipeline / str(case["case_id"])
                run = _read_json(root / "run.json")
                metric = _read_json(root / "metrics" / "summary.json")
                refs = parse_rttm(root / "references" / "reference.rttm")
                hyps = parse_rttm(root / "predictions" / "segments.rttm")
                product = _case_product_metrics(case, refs, hyps)
                strict = dict(metric["primary_strict"])
                practical = dict(metric["practical_boundary_tolerant"])
                count = dict(metric["speaker_count"])
                base = {
                    "protocol": protocol,
                    "protocol_id": case["benchmark_id"],
                    "pipeline_id": pipeline,
                    "case_id": case["case_id"],
                    "scenario_profile": case.get("scenario_profile", "controlled_v1_factorial"),
                    "speaker_band": case.get("speaker_band", _speaker_band(int(case["speaker_count"]))),
                    "speaker_count": int(case["speaker_count"]),
                    "global_speaker_ids": sorted(dict(case["local_to_global_speaker"]).values()),
                    "turn_cadence": case["turn_cadence"],
                    "overlap_profile": case["overlap_profile"],
                    "long_session": bool(case.get("long_session", False)),
                    "development_role": case.get("development_role", "selection"),
                    "duration_sec": float(case["duration_sec"]),
                    "der": strict.get("der"),
                    "jer": strict.get("jer"),
                    "missed_speech_sec": strict.get("missed_speech_sec"),
                    "false_alarm_sec": strict.get("false_alarm_sec"),
                    "speaker_confusion_sec": strict.get("speaker_confusion_sec"),
                    "reference_speaker_time_sec": strict.get("reference_speaker_time_sec"),
                    "practical_der": practical.get("der"),
                    "overlap_excluded_der": dict(strict.get("modes") or {}).get("overlap_excluded", {}).get("der"),
                    "overlap_aware_der": dict(strict.get("modes") or {}).get("overlap_aware", {}).get("der"),
                    "predicted_speaker_count": count["predicted"],
                    "speaker_count_signed_error": count["signed_error"],
                    "speaker_count_absolute_error": count["absolute_error"],
                    "speaker_count_exact": count["exact"],
                    "fragmentation": dict(metric["fragmentation"])["mean_clusters_per_reference_speaker"],
                    "merge_count": dict(metric["merging"])["merged_predicted_cluster_count"],
                    "cluster_purity": metric.get("cluster_purity"),
                    "reference_speaker_coverage": metric.get("reference_speaker_coverage"),
                    "reentry_consistency": metric.get("speaker_reentry_consistency"),
                    "boundary_f1_250ms": dict(metric["turn_boundary"])["0.25"]["f1"],
                    "boundary_f1_500ms": dict(metric["turn_boundary"])["0.5"]["f1"],
                    "rtf": dict(run["timing"])["real_time_factor"],
                    "inference_sec": dict(run["timing"])["diarization_inference_sec"],
                    "wall_sec": dict(run["timing"])["total_wall_sec"],
                    **product["recording"],
                    "result_path": str(root),
                }
                recording.append(base)
                contamination.extend({**base, **row} for row in product["contamination"])
                short.extend({**base, **row} for row in product["short_turns"])
                boundary.extend({**base, **row} for row in product["boundaries"])
                reentry.extend({**base, **row} for row in product["reentry"])
                rare.extend({**base, **row} for row in product["speakers"] if row["rare_speaker"])
                evidence.extend({**base, **row} for row in product["evidence"])
                latency.extend({**base, **row} for row in product["latency"])
                mixed.extend({**base, **row} for row in product["mixed"])
                if base["long_session"]:
                    long_rows.extend(_long_session_bins(base, refs, hyps))
                resources.append(
                    {
                        **base,
                        "environment_profile": dict(run["environment"])["environment_profile"],
                        "peak_ram_mb": _technical_ram(root),
                    }
                )
    for pipeline in PRIMARY_PIPELINES:
        match = next(row for row in recording if row["pipeline_id"] == pipeline)
        identity = _read_json(Path(str(match["result_path"])) / "resolved_pipeline_identity.json")
        identities.append(
            {
                "pipeline_id": pipeline,
                "configuration_sha256": identity.get("configuration_sha256"),
                "segmentation": identity.get("segmentation"),
                "embedding": identity.get("embedding"),
                "clustering": identity.get("clustering"),
                "implementation_class": identity.get("implementation_class"),
                "identity_sha256": sha256_text(canonical_json(identity)),
            }
        )
    for path in (DEFAULT_RESULT_ROOT / "oracle").rglob("metrics/summary.json"):
        metric = _read_json(path)
        run = _read_json(path.parents[1] / "run.json")
        oracle.append(
            {
                "pipeline_id": run.get("pipeline_id"),
                "case_id": run.get("case_id"),
                "der": dict(metric.get("primary_strict") or {}).get("der"),
                "jer": dict(metric.get("primary_strict") or {}).get("jer"),
                "speaker_confusion_sec": dict(metric.get("primary_strict") or {}).get("speaker_confusion_sec"),
                "diagnostic_only": True,
            }
        )

    overall = _overall(recording, contamination, short, boundary, reentry, evidence, latency)
    protocol_rows = _group_recording(recording, ("protocol", "pipeline_id"))
    factors = _group_recording(recording, ("protocol", "pipeline_id", "scenario_profile", "overlap_profile"))
    counts = _group_recording(recording, ("protocol", "pipeline_id", "speaker_count"))
    overlap = _group_recording(recording, ("protocol", "pipeline_id", "overlap_profile"))
    fragmentation = _group_recording(recording, ("protocol", "pipeline_id", "speaker_band"))
    merges = _group_rows(contamination, ("protocol", "pipeline_id"), "contamination")
    single = [row for row in recording if int(row["speaker_count"]) == 1]
    clean_summary = _clean_summary(evidence, ("protocol", "pipeline_id", "target_sec"))
    latency_summary = _latency_summary(latency, ("protocol", "pipeline_id", "target_sec"))
    mixed_summary = _mixed_summary(mixed, ("protocol", "pipeline_id", "target_sec"))
    paired = _paired(recording)
    bootstrap = _bootstrap_intervals(
        recording, contamination, short, boundary, reentry, evidence, latency, resources
    )
    reliability = _reliability(recording)
    return {
        "overall_results": overall,
        "recording_results": recording,
        "protocol_results": protocol_rows,
        "factor_results": factors,
        "speaker_count_results": counts,
        "short_turn_results": _short_turn_summary(short),
        "short_turn_events": short,
        "boundary_delay_results": _boundary_summary(boundary),
        "boundary_delay_events": boundary,
        "overlap_results": overlap,
        "fragmentation_results": fragmentation,
        "merge_results": merges,
        "contamination_results": contamination,
        "single_speaker_controls": single,
        "rare_speaker_results": rare,
        "reentry_results": _reentry_summary(reentry),
        "reentry_events": reentry,
        "long_session_results": long_rows,
        "clean_evidence_yield": clean_summary,
        "time_to_clean_evidence": latency_summary,
        "mixed_speaker_evidence": mixed_summary,
        "oracle_turn_results": oracle,
        "resource_results": resources,
        "reliability_summary": reliability,
        "paired_comparisons": paired,
        "bootstrap_intervals": bootstrap,
        "pipeline_identity": identities,
    }


def _case_product_metrics(
    case: Mapping[str, object], refs: Sequence[RttmTurn], hyps: Sequence[RttmTurn]
) -> dict[str, object]:
    ref_labels = sorted({row.speaker_label for row in refs})
    hyp_labels = sorted({row.speaker_label for row in hyps})
    overlap = {
        (ref, hyp): sum(_overlap(a, b) for a in refs if a.speaker_label == ref for b in hyps if b.speaker_label == hyp)
        for ref in ref_labels
        for hyp in hyp_labels
    }
    cluster_map = {
        hyp: max(ref_labels, key=lambda ref: (overlap[(ref, hyp)], ref))
        for hyp in hyp_labels
        if ref_labels
    }
    contamination = []
    cluster_purity: dict[str, float] = {}
    for hyp in hyp_labels:
        duration = sum(row.duration_sec for row in hyps if row.speaker_label == hyp)
        dominant = cluster_map[hyp]
        purity = min(1.0, overlap[(dominant, hyp)] / duration) if duration else 0.0
        cluster_purity[hyp] = purity
        contamination.append(
            {
                "predicted_cluster": hyp,
                "dominant_reference_speaker": dominant,
                "dominant_global_speaker_id": dict(case["local_to_global_speaker"])[dominant],
                "predicted_duration_sec": duration,
                "dominant_reference_fraction": purity,
                "contamination": 1.0 - purity,
                "above_5_percent": 1.0 - purity > 0.05,
                "above_10_percent": 1.0 - purity > 0.10,
                "above_20_percent": 1.0 - purity > 0.20,
                "above_40_percent": 1.0 - purity > 0.40,
            }
        )
    speakers = []
    total_ref = sum(row.duration_sec for row in refs)
    for ref in ref_labels:
        ref_turns = [row for row in refs if row.speaker_label == ref]
        ref_time = sum(row.duration_sec for row in ref_turns)
        clusters = [hyp for hyp in hyp_labels if overlap[(ref, hyp)] > 0]
        dominant = max(clusters, key=lambda hyp: overlap[(ref, hyp)]) if clusters else None
        coverage = overlap[(ref, dominant)] / ref_time if dominant and ref_time else 0.0
        detected = min(ref_time, sum(overlap[(ref, hyp)] for hyp in hyp_labels))
        share = ref_time / total_ref if total_ref else 0.0
        speakers.append(
            {
                "reference_speaker": ref,
                "global_speaker_id": dict(case["local_to_global_speaker"])[ref],
                "reference_time_sec": ref_time,
                "participation_share": share,
                "speech_recall": detected / ref_time if ref_time else 0.0,
                "speaker_confusion_rate": max(0.0, detected - overlap.get((ref, dominant), 0.0)) / ref_time if ref_time else 0.0,
                "rare_speaker": share < 0.05,
                "bottom_participation_quartile": False,
                "dominant_predicted_cluster": dominant,
                "dominant_cluster_coverage": coverage,
                "fragment_count": len(clusters),
                "speaker_count_impact": max(0, len(clusters) - 1),
                "stable_cluster_exists": bool(dominant and coverage >= 0.5),
                "merge_rate": (
                    1.0 - cluster_purity.get(dominant, 0.0) if dominant else 1.0
                ),
            }
        )
    if speakers:
        cutoff = sorted(row["participation_share"] for row in speakers)[max(0, math.ceil(len(speakers) * 0.25) - 1)]
        for row in speakers:
            row["bottom_participation_quartile"] = row["participation_share"] <= cutoff
            row["rare_speaker"] = bool(row["rare_speaker"] or row["bottom_participation_quartile"])
    short_rows = []
    for index, turn in enumerate(refs):
        duration = turn.duration_sec
        bucket = next(name for name, low, high in SHORT_BUCKETS if low <= duration < high or (math.isinf(high) and duration >= low))
        detected = min(duration, sum(_overlap(turn, hyp) for hyp in hyps))
        correct = min(
            duration,
            sum(_overlap(turn, hyp) for hyp in hyps if cluster_map.get(hyp.speaker_label) == turn.speaker_label),
        )
        clusters = {hyp.speaker_label for hyp in hyps if _overlap(turn, hyp) > 0}
        short_rows.append(
            {
                "turn_index": index,
                "reference_speaker": turn.speaker_label,
                "global_speaker_id": dict(case["local_to_global_speaker"])[turn.speaker_label],
                "duration_sec": duration,
                "duration_bucket": bucket,
                "speech_detection_recall": detected / duration,
                "anonymous_speaker_correctness": correct / duration,
                "miss_rate": 1.0 - detected / duration,
                "speaker_confusion_rate": max(0.0, detected - correct) / duration,
                "merge_rate": float(any(cluster_map.get(value) != turn.speaker_label for value in clusters)),
                "fragmentation": len(clusters),
                "boundary_error_ms": _turn_boundary_error_ms(turn, hyps),
            }
        )
    boundaries = _boundary_rows(refs, hyps)
    for row in boundaries:
        source = next(
            (turn for turn in refs if abs(turn.start_sec - float(row["reference_boundary_sec"])) < 1e-7),
            None,
        )
        row["global_speaker_id"] = (
            dict(case["local_to_global_speaker"])[source.speaker_label] if source else None
        )
    reentry = _reentry_rows(refs, hyps, cluster_map)
    for row in reentry:
        row["global_speaker_id"] = dict(case["local_to_global_speaker"])[str(row["reference_speaker"])]
    evidence, latency, mixed = _evidence_rows(case, refs, hyps, cluster_map, cluster_purity)
    values = [row["contamination"] for row in contamination]
    return {
        "recording": {
            "mean_contamination": _mean(values),
            "median_contamination": _percentile(values, 0.5),
            "p90_contamination": _percentile(values, 0.9),
            "catastrophic_contaminated_cluster_rate": _mean(float(value > 0.2) for value in values),
            "short_turn_recall_lt2s": _mean(row["anonymous_speaker_correctness"] for row in short_rows if row["duration_sec"] < 2.0),
            "median_signed_boundary_delay_ms": _percentile([row["signed_delay_ms"] for row in boundaries if row["matched"]], 0.5),
            "median_absolute_boundary_delay_ms": _percentile([row["absolute_delay_ms"] for row in boundaries if row["matched"]], 0.5),
            "clean_evidence_yield_2s": _mean(float(row["achieved"]) for row in evidence if row["target_sec"] == 2.0),
            "median_time_to_clean_evidence_2s": _percentile(
                [
                    row["latency_sec"] if row["achieved"] else row["censor_time_sec"]
                    for row in latency
                    if row["target_sec"] == 2.0
                ],
                0.5,
            ),
            **_single_speaker_metrics(refs, hyps),
        },
        "contamination": contamination,
        "speakers": speakers,
        "short_turns": short_rows,
        "boundaries": boundaries,
        "reentry": reentry,
        "evidence": evidence,
        "latency": latency,
        "mixed": mixed,
    }


def _boundary_rows(refs: Sequence[RttmTurn], hyps: Sequence[RttmTurn]) -> list[dict[str, object]]:
    ref_boundaries = sorted({row.start_sec for row in refs if row.start_sec > 0})
    hyp_boundaries = sorted({row.start_sec for row in hyps if row.start_sec > 0})
    rows = []
    for value in ref_boundaries:
        nearest = min(hyp_boundaries, key=lambda item: abs(item - value)) if hyp_boundaries else None
        delay = (nearest - value) if nearest is not None else None
        matched = delay is not None and abs(delay) <= 2.0
        rows.append(
            {
                "reference_boundary_sec": value,
                "predicted_boundary_sec": nearest,
                "matched": matched,
                "signed_delay_ms": delay * 1000 if matched else None,
                "absolute_delay_ms": abs(delay) * 1000 if matched else None,
                "within_100ms": bool(matched and abs(delay) <= 0.1),
                "within_250ms": bool(matched and abs(delay) <= 0.25),
                "within_500ms": bool(matched and abs(delay) <= 0.5),
                "early": bool(matched and delay < 0),
                "late": bool(matched and delay > 0),
                "missed_change": not matched,
            }
        )
    matched_hyp = sum(any(abs(value - ref) <= 0.5 for ref in ref_boundaries) for value in hyp_boundaries)
    false_changes = max(0, len(hyp_boundaries) - matched_hyp)
    for row in rows:
        row["false_change_count_recording"] = false_changes
        row["false_change_rate"] = false_changes / len(hyp_boundaries) if hyp_boundaries else 0.0
    return rows


def _reentry_rows(
    refs: Sequence[RttmTurn], hyps: Sequence[RttmTurn], cluster_map: Mapping[str, str]
) -> list[dict[str, object]]:
    rows = []
    for speaker in sorted({row.speaker_label for row in refs}):
        turns = sorted((row for row in refs if row.speaker_label == speaker), key=lambda row: row.start_sec)
        before_cluster = None
        for index, turn in enumerate(turns):
            assigned = _dominant_hyp(turn, hyps)
            if index:
                gap = turn.start_sec - turns[index - 1].end_sec
                bucket = next(name for name, low, high in REENTRY_BUCKETS if low <= gap < high or (math.isinf(high) and gap >= low))
                consistent = bool(
                    before_cluster
                    and assigned == before_cluster
                    and cluster_map.get(str(assigned)) == speaker
                )
                rows.append(
                    {
                        "reference_speaker": speaker,
                        "absence_duration_sec": gap,
                        "absence_bucket": bucket,
                        "previous_cluster": before_cluster,
                        "return_cluster": assigned,
                        "consistent": consistent,
                        "new_cluster_on_return": bool(assigned and before_cluster and assigned != before_cluster),
                        "fragmentation_after_return": len(
                            {
                                value
                                for later in turns[index:]
                                if (value := _dominant_hyp(later, hyps)) is not None
                            }
                        ),
                        "speaker_count_inflation": max(
                            0,
                            len(
                                {
                                    value
                                    for later in turns[index:]
                                    if (value := _dominant_hyp(later, hyps)) is not None
                                }
                            )
                            - 1,
                        ),
                    }
                )
            if assigned and cluster_map.get(assigned) == speaker:
                before_cluster = assigned if before_cluster is None else before_cluster
    return rows


def _single_speaker_metrics(
    refs: Sequence[RttmTurn], hyps: Sequence[RttmTurn]
) -> dict[str, object]:
    """Return product controls for true one-speaker sessions, otherwise nulls."""

    if len({row.speaker_label for row in refs}) != 1:
        return {
            "false_speaker_changes_per_min": None,
            "single_speaker_fragment_count": None,
            "largest_cluster_coverage": None,
            "phantom_speaker_duration_sec": None,
        }
    ordered = sorted(hyps, key=lambda row: (row.start_sec, row.end_sec, row.speaker_label))
    changes = sum(left.speaker_label != right.speaker_label for left, right in zip(ordered, ordered[1:]))
    duration = max((row.end_sec for row in refs), default=0.0)
    by_cluster: dict[str, float] = defaultdict(float)
    by_cluster_hypothesis_time: dict[str, float] = defaultdict(float)
    for hyp in hyps:
        by_cluster[hyp.speaker_label] += sum(_overlap(hyp, ref) for ref in refs)
        by_cluster_hypothesis_time[hyp.speaker_label] += hyp.duration_sec
    reference_time = sum(row.duration_sec for row in refs)
    largest_label = max(by_cluster, key=by_cluster.get) if by_cluster else None
    largest = by_cluster.get(largest_label, 0.0) if largest_label else 0.0
    return {
        "false_speaker_changes_per_min": changes / max(duration / 60.0, 1e-9),
        "single_speaker_fragment_count": len(by_cluster),
        "largest_cluster_coverage": min(1.0, largest / reference_time) if reference_time else 0.0,
        "phantom_speaker_duration_sec": sum(
            duration
            for label, duration in by_cluster_hypothesis_time.items()
            if label != largest_label
        ),
    }


def _evidence_rows(
    case: Mapping[str, object], refs: Sequence[RttmTurn], hyps: Sequence[RttmTurn],
    cluster_map: Mapping[str, str], cluster_purity: Mapping[str, float],
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    evidence, latency, mixed = [], [], []
    for speaker in sorted({row.speaker_label for row in refs}):
        first = min(row.start_sec for row in refs if row.speaker_label == speaker)
        clean = sorted(
            [
                row
                for row in hyps
                if cluster_map.get(row.speaker_label) == speaker
                and cluster_purity.get(row.speaker_label, 0.0) >= 0.95
            ],
            key=lambda row: row.end_sec,
        )
        total = sum(row.duration_sec for row in clean)
        for target in EVIDENCE_TARGETS:
            achieved = total >= target
            accumulated = 0.0
            reached = None
            for row in clean:
                accumulated += row.duration_sec
                if accumulated >= target:
                    reached = row.end_sec
                    break
            value = {
                "reference_speaker": speaker,
                "global_speaker_id": dict(case["local_to_global_speaker"])[speaker],
                "target_sec": target,
                "clean_evidence_sec": total,
                "achieved": achieved,
                "purity_threshold": 0.95,
                "overlap_view": "overlap_excluded_primary",
            }
            evidence.append(value)
            latency.append(
                {
                    **value,
                    "latency_sec": max(0.0, reached - first) if reached is not None else None,
                    "censored": reached is None,
                    "censor_time_sec": float(case["duration_sec"]) - first,
                }
            )
    for target in EVIDENCE_TARGETS:
        for row in hyps:
            if row.duration_sec < target:
                continue
            start = row.start_sec
            end = start + target
            reference_overlap = defaultdict(float)
            window = RttmTurn(row.recording_id, row.channel, start, end, row.speaker_label)
            for ref in refs:
                reference_overlap[ref.speaker_label] += _overlap(window, ref)
            dominant = max(reference_overlap.values(), default=0.0)
            contamination = max(0.0, 1.0 - dominant / target)
            mixed.append(
                {
                    "target_sec": target,
                    "predicted_cluster": row.speaker_label,
                    "window_start_sec": start,
                    "contamination": contamination,
                    "above_5_percent": contamination > 0.05,
                    "above_10_percent": contamination > 0.10,
                    "above_20_percent": contamination > 0.20,
                }
            )
    return evidence, latency, mixed


def _long_session_bins(
    base: Mapping[str, object], refs: Sequence[RttmTurn], hyps: Sequence[RttmTurn]
) -> list[dict[str, object]]:
    rows = []
    duration = float(base["duration_sec"])
    policy = DiarizationScoringPolicy(collar_sec=0.0, overlap_modes=("overlap_aware",))
    for start in np.arange(0.0, duration, 60.0):
        end = min(duration, float(start) + 60.0)
        metric = score_diarization(
            refs,
            hyps,
            [UemRegion(str(base["case_id"]), "1", float(start), end)],
            policy=policy,
        )
        bin_refs = [row for row in refs if row.start_sec < end and row.end_sec > start]
        bin_hyps = [row for row in hyps if row.start_sec < end and row.end_sec > start]
        reference_labels = {row.speaker_label for row in bin_refs}
        predicted_labels = {row.speaker_label for row in bin_hyps}
        prior_labels = {row.speaker_label for row in hyps if row.start_sec < start}
        local_overlap = {
            (ref, hyp): sum(
                _overlap(
                    RttmTurn(row.recording_id, row.channel, max(row.start_sec, float(start)), min(row.end_sec, end), row.speaker_label),
                    candidate,
                )
                for row in bin_refs
                if row.speaker_label == ref
                for candidate in bin_hyps
                if candidate.speaker_label == hyp
            )
            for ref in reference_labels
            for hyp in predicted_labels
        }
        purities = []
        for hyp in predicted_labels:
            hyp_time = sum(
                max(0.0, min(row.end_sec, end) - max(row.start_sec, float(start)))
                for row in bin_hyps
                if row.speaker_label == hyp
            )
            dominant = max((local_overlap[(ref, hyp)] for ref in reference_labels), default=0.0)
            purities.append(min(1.0, dominant / hyp_time) if hyp_time else 0.0)
        fragments = [
            sum(local_overlap[(ref, hyp)] > 0 for hyp in predicted_labels)
            for ref in reference_labels
        ]
        rows.append(
            {
                **base,
                "bin_start_sec": float(start),
                "bin_end_sec": end,
                "der": metric.get("der"),
                "jer": metric.get("jer"),
                "speaker_confusion_sec": metric.get("speaker_confusion_sec"),
                "predicted_speaker_count_in_bin": len(
                    {row.speaker_label for row in hyps if row.start_sec < end and row.end_sec > start}
                ),
                "speaker_count_signed_error_in_bin": len(predicted_labels) - len(reference_labels),
                "new_cluster_creation_count": len(predicted_labels - prior_labels),
                "mean_fragmentation_in_bin": _mean(fragments),
                "mean_cluster_purity_in_bin": _mean(purities),
                "mean_merge_contamination_in_bin": _mean(1.0 - value for value in purities),
                "phantom_speaker_count_in_bin": max(0, len(predicted_labels) - len(reference_labels)),
            }
        )
    return rows


def _overall(
    recording: Sequence[Mapping[str, object]], contamination: Sequence[Mapping[str, object]],
    short: Sequence[Mapping[str, object]], boundary: Sequence[Mapping[str, object]],
    reentry: Sequence[Mapping[str, object]], evidence: Sequence[Mapping[str, object]],
    latency: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for pipeline in PRIMARY_PIPELINES:
        rec = [row for row in recording if row["pipeline_id"] == pipeline]
        cont = [row for row in contamination if row["pipeline_id"] == pipeline]
        short_values = [row for row in short if row["pipeline_id"] == pipeline and float(row["duration_sec"]) < 2]
        bounds = [row for row in boundary if row["pipeline_id"] == pipeline and row["matched"]]
        reent = [row for row in reentry if row["pipeline_id"] == pipeline]
        ev = [row for row in evidence if row["pipeline_id"] == pipeline and row["target_sec"] == 2]
        lat = [row for row in latency if row["pipeline_id"] == pipeline and row["target_sec"] == 2]
        denominator = sum(float(row["reference_speaker_time_sec"]) for row in rec)
        rows.append(
            {
                "pipeline_id": pipeline,
                "valid_recordings": len(rec),
                "der": sum(float(row["missed_speech_sec"]) + float(row["false_alarm_sec"]) + float(row["speaker_confusion_sec"]) for row in rec) / denominator,
                "jer": _mean(row["jer"] for row in rec),
                "speaker_confusion_rate": sum(float(row["speaker_confusion_sec"]) for row in rec) / denominator,
                "catastrophic_contaminated_cluster_rate": _mean(float(row["contamination"] > 0.2) for row in cont),
                "mean_contamination": _mean(row["contamination"] for row in cont),
                "short_turn_recall": _mean(row["anonymous_speaker_correctness"] for row in short_values),
                "reentry_consistency": _mean(float(row["consistent"]) for row in reent),
                "clean_evidence_yield_2s": _mean(float(row["achieved"]) for row in ev),
                "time_to_clean_evidence_2s": _percentile(
                    [row["latency_sec"] if row["achieved"] else row["censor_time_sec"] for row in lat],
                    0.5,
                ),
                "successful_time_to_clean_evidence_2s": _percentile(
                    [row["latency_sec"] for row in lat if row["achieved"]], 0.5
                ),
                "not_reached_clean_evidence_2s": sum(not bool(row["achieved"]) for row in lat),
                "clean_evidence_failure_2s": 1.0 - (_mean(float(row["achieved"]) for row in ev) or 0.0),
                "median_absolute_boundary_delay_ms": _percentile([row["absolute_delay_ms"] for row in bounds], 0.5),
                "p90_absolute_boundary_delay_ms": _percentile([row["absolute_delay_ms"] for row in bounds], 0.9),
                "speaker_count_mae": _mean(row["speaker_count_absolute_error"] for row in rec),
                "speaker_count_exact_rate": _mean(float(row["speaker_count_exact"]) for row in rec),
                "fragmentation": _mean(row["fragmentation"] for row in rec),
                "rtf": _mean(row["rtf"] for row in rec),
            }
        )
    return rows


def _select_and_freeze(
    config_path: Path, tables: Mapping[str, Sequence[Mapping[str, object]]]
) -> dict[str, object]:
    overall = [dict(row) for row in tables["overall_results"]]
    by = {str(row["pipeline_id"]): row for row in overall}
    criteria = (
        ("der", "min", 0.01),
        ("jer", "min", 0.01),
        ("speaker_confusion_rate", "min", 0.005),
        ("catastrophic_contaminated_cluster_rate", "min", 0.01),
        ("short_turn_recall", "max", 0.01),
        ("reentry_consistency", "max", 0.01),
        ("clean_evidence_yield_2s", "max", 0.01),
        ("time_to_clean_evidence_2s", "min", 0.25),
        ("rtf", "min", 0.02),
    )
    dominated_by: dict[str, list[str]] = defaultdict(list)
    for candidate in PRIMARY_PIPELINES:
        for other in PRIMARY_PIPELINES:
            if candidate != other and _dominates(by[other], by[candidate], criteria):
                dominated_by[candidate].append(other)
    nondominated = [pipeline for pipeline in PRIMARY_PIPELINES if not dominated_by[pipeline]]
    accuracy = min(
        nondominated,
        key=lambda pipeline: (
            by[pipeline]["catastrophic_contaminated_cluster_rate"],
            by[pipeline]["speaker_confusion_rate"],
            -float(by[pipeline]["clean_evidence_yield_2s"] or 0),
            by[pipeline]["der"],
            -float(by[pipeline]["short_turn_recall"] or 0),
            -float(by[pipeline]["reentry_consistency"] or 0),
            by[pipeline]["median_absolute_boundary_delay_ms"] or math.inf,
            by[pipeline]["rtf"],
        ),
    )
    remaining = [value for value in nondominated if value != accuracy]
    bootstrap_by = {
        (str(row["pipeline_id"]), str(row["metric"])): row
        for row in tables["bootstrap_intervals"]
    }
    safeguards = (
        ("catastrophic_contaminated_cluster_rate", "catastrophic_contaminated_cluster_rate", "min"),
        ("speaker_confusion_rate", "speaker_confusion", "min"),
        ("clean_evidence_yield_2s", "clean_evidence_yield_2s", "max"),
        ("short_turn_recall", "short_turn_recall", "max"),
    )
    efficiency_regressions: dict[str, list[str]] = {}
    for pipeline in remaining:
        regressions = []
        for label, bootstrap_metric, direction in safeguards:
            candidate_ci = bootstrap_by.get((pipeline, bootstrap_metric), {})
            accuracy_ci = bootstrap_by.get((accuracy, bootstrap_metric), {})
            candidate_low, candidate_high = candidate_ci.get("ci95_low"), candidate_ci.get("ci95_high")
            accuracy_low, accuracy_high = accuracy_ci.get("ci95_low"), accuracy_ci.get("ci95_high")
            if None in (candidate_low, candidate_high, accuracy_low, accuracy_high):
                continue
            clearly_worse = (
                float(candidate_low) > float(accuracy_high)
                if direction == "min"
                else float(candidate_high) < float(accuracy_low)
            )
            if clearly_worse:
                regressions.append(label)
        efficiency_regressions[pipeline] = regressions
    efficiency_candidates = [pipeline for pipeline in remaining if not efficiency_regressions[pipeline]]
    if not efficiency_candidates:
        raise RuntimeError(
            "no remaining nondominated pipeline passes the predeclared efficiency safeguards: "
            + canonical_json(efficiency_regressions)
        )
    efficiency = min(efficiency_candidates, key=lambda pipeline: float(by[pipeline]["rtf"]))
    selected = [accuracy, efficiency]
    complete = [value for value in nondominated if value in {"sherpa_onnx_diarization", "pyannote_community1"}]
    if not any(value in {"sherpa_onnx_diarization", "pyannote_community1"} for value in selected) and complete:
        reference = min(complete, key=lambda pipeline: (by[pipeline]["der"], by[pipeline]["rtf"]))
        if reference not in selected:
            selected.append(reference)
    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    identities = {}
    for pipeline in selected:
        path = next((DEFAULT_RESULT_ROOT / "v2" / "development" / pipeline).glob("*/resolved_pipeline_identity.json"))
        identities[pipeline] = _read_json(path)
    result_identity = _development_result_identity()
    git = _git_identity()
    payload = {
        "schema_version": "frozen-diarization-development-selection.v2",
        "selection_status": "FROZEN_DEVELOPMENT_ONLY",
        "selected_pipeline_ids": selected,
        "selected_pipelines": [
            {
                "pipeline_id": pipeline,
                "configuration_sha256": registry[pipeline].configuration_sha256,
                "pipeline_definition": registry[pipeline].to_jsonable(),
                "resolved_identity": identities[pipeline],
                "development_metrics": by[pipeline],
                "role": "PRODUCT_ACCURACY_PURITY" if pipeline == accuracy else (
                    "EFFICIENCY_DEPLOYMENT" if pipeline == efficiency else "COMPLETE_SYSTEM_REFERENCE"
                ),
            }
            for pipeline in selected
        ],
        "protocol_ids": {
            "controlled_v1": json.loads((V1_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["benchmark_id"],
            "product_v2": json.loads((DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["protocol_id"],
        },
        "development_result_identity": result_identity,
        "scoring_settings": config["scoring"],
        "selection_procedure": {
            "weighted_score_used": False,
            "dominance_criteria_and_tolerances": [
                {"metric": name, "direction": direction, "tolerance": tolerance}
                for name, direction, tolerance in criteria
            ],
            "nondominated_pipelines": nondominated,
            "dominated_by": dict(dominated_by),
            "accuracy_lexicographic_priority": [
                "catastrophic_contamination",
                "speaker_confusion",
                "clean_evidence_yield_2s",
                "DER",
                "short_turn_recall",
                "reentry_consistency",
                "absolute_boundary_delay",
                "RTF",
            ],
            "efficiency_rule": "lowest RTF among remaining nondominated whose 95% speaker-cluster bootstrap interval is not entirely worse than the accuracy finalist on any declared safeguard",
            "efficiency_safeguards": [label for label, _, _ in safeguards],
            "efficiency_clear_regressions": efficiency_regressions,
            "efficiency_eligible_pipelines": efficiency_candidates,
        },
        "selection_rationale": {
            "accuracy_finalist": {"pipeline_id": accuracy, "evidence": by[accuracy]},
            "efficiency_finalist": {"pipeline_id": efficiency, "evidence": by[efficiency]},
            "rejected_candidates": [
                {"pipeline_id": pipeline, "dominated_by": dominated_by.get(pipeline, []), "evidence": by[pipeline]}
                for pipeline in PRIMARY_PIPELINES
                if pipeline not in selected
            ],
        },
        "selection_timestamp_utc": _now(),
        "git_and_result_affecting_code_identity": git,
        "development_only_metrics_used": by,
        "EVALUATION_NOT_INSPECTED": True,
        "evaluation_authorized": True,
        "controlled_evaluation_run": False,
        "chime6_finalist_evaluation_run": False,
        "hybrid_run": False,
        "asr_run": False,
        "fine_tuning_run": False,
    }
    write_text_atomic(DEFAULT_SELECTION_PATH, yaml.safe_dump(payload, sort_keys=False))
    digest = sha256_file(DEFAULT_SELECTION_PATH)
    write_text_atomic(DEFAULT_SELECTION_PATH.with_suffix(".sha256"), f"{digest}  {DEFAULT_SELECTION_PATH.name}\n")
    return {"selected_pipeline_ids": selected, "path": str(DEFAULT_SELECTION_PATH), "sha256": digest}


def collect_package() -> dict[str, object]:
    if not DEFAULT_SELECTION_PATH.is_file():
        raise RuntimeError("frozen development selection does not exist")
    summary_root = TOOL_ROOT / "JustPeachyResearchSummaries"
    summary_root.mkdir(parents=True, exist_ok=True)
    protocol_id = json.loads((DEFAULT_PROTOCOL_ROOT / "protocol_summary.json").read_text(encoding="utf-8"))["protocol_id"]
    destination = summary_root / f"diarization_product_v2_development_{protocol_id}.zip"
    include_roots = [
        DEFAULT_ANALYSIS_ROOT,
        DEFAULT_PROTOCOL_ROOT,
        DEFAULT_RESULT_ROOT / "calibration" / "development_calibration.json",
        DEFAULT_RESULT_ROOT / "audit.json",
        DEFAULT_RESULT_ROOT / "validation.json",
        DEFAULT_RESULT_ROOT / "plan.json",
        DEFAULT_RESULT_ROOT / "engineering_smoke" / "smoke_summary.json",
        DEFAULT_RESULT_ROOT / "native_campaign",
        DEFAULT_RESULT_ROOT / "oracle" / "oracle_summary.json",
        DEFAULT_RESULT_ROOT / "campaign_progress.json",
        DEFAULT_RESULT_ROOT / "controller_state.json",
        DEFAULT_RESULT_ROOT / "background_controller.stdout.log",
        DEFAULT_RESULT_ROOT / "background_controller.stderr.log",
        DEFAULT_RESULT_ROOT / "v1" / "controller.log",
        DEFAULT_RESULT_ROOT / "v2" / "controller.log",
        DEFAULT_FROZEN_CONFIG_PATH,
        DEFAULT_SELECTION_PATH,
        DEFAULT_SELECTION_PATH.with_suffix(".sha256"),
        V1_PROTOCOL_ROOT,
        TOOL_ROOT / "app" / "diarization_product_v2" / "README.md",
    ]
    inventory = []
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for source in include_roots:
            if not source.exists():
                continue
            paths = [source] if source.is_file() else [path for path in source.rglob("*") if path.is_file()]
            for path in paths:
                if path.suffix.lower() in {".wav", ".mp3", ".pt", ".onnx", ".npz"}:
                    continue
                if "_shared_cache" in path.parts or "predictions" in path.parts:
                    continue
                relative = path.relative_to(TOOL_ROOT) if path.is_relative_to(TOOL_ROOT) else Path(path.name)
                archive.write(path, relative.as_posix())
                inventory.append({"path": relative.as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
        archive.writestr("PACKAGE_INVENTORY.json", json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    return {
        "path": str(destination.resolve()),
        "sha256": sha256_file(destination),
        "files": len(inventory) + 1,
        "raw_datasets_included": False,
        "generated_wav_included": False,
        "model_weights_included": False,
    }


def _write_reports(output: Path, tables: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
    overall = tables["overall_results"]
    lines = [
        "# Product-Focused Standalone Diarization Development Report",
        "",
        "This report uses controlled V1 and Product V2 **development evidence only**. Controlled evaluation, final CHiME-6 finalist evaluation, hybrid attribution, ASR, and fine-tuning were not run or inspected.",
        "",
        "The anonymous product question is whether each pipeline creates clean, stable, timely tracks that could later supply a separate identity layer.",
        "",
        "| Pipeline | DER | JER | Confusion | >20% contaminated | Short recall | Re-entry | Clean 2s | Median clean-2s latency | RTF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in overall:
        lines.append(
            f"| {row['pipeline_id']} | {_fmt(row['der'])} | {_fmt(row['jer'])} | {_fmt(row['speaker_confusion_rate'])} | {_fmt(row['catastrophic_contaminated_cluster_rate'])} | {_fmt(row['short_turn_recall'])} | {_fmt(row['reentry_consistency'])} | {_fmt(row['clean_evidence_yield_2s'])} | {_fmt(row['time_to_clean_evidence_2s'])} s | {_fmt(row['rtf'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- DER is the fraction of reference speaker time lost to missed speech, false alarm, or speaker confusion; lower is better.",
            "- JER averages per-speaker Jaccard error and exposes uneven speaker failures.",
            "- Contamination measures how much a predicted anonymous cluster contains speech from people other than its dominant reference speaker.",
            "- Clean-evidence yield is the fraction of reference speaker appearances that accumulate the requested amount of >=95%-pure anonymous audio. It is not identity accuracy.",
            "- Time-to-clean-evidence is censored when the target is never reached; failures remain in the denominator.",
            "- The finalist latency key uses each not-reached appearance's remaining-session censor time as a conservative restricted-time lower bound; successful-only latency is reported separately.",
            "- Confidence intervals resample global-speaker clusters and preserve each sampled speaker's observations together.",
            "- The modular Pyannote bridge collapses segmentation channels to speech activity before window embedding, so it does not preserve simultaneous-speaker channels. Overlap metrics must be read with that limitation.",
            "",
            "See `frozen_diarization_development_selection.yaml` for the automatic nondominance and lexicographic decision, exact identities, tradeoffs, and evaluation firewall.",
        ]
    )
    write_text_atomic(output / "REPORT.md", "\n".join(lines) + "\n")
    guide = """# Diarization Product Metric Guide

All speaker labels in this study are recording-local anonymous clusters. No enrollment database or real name is used.

- **Strict DER/JER:** zero-collar, UEM-bound diarization error. Overlap-aware is primary; overlap-excluded is also reported.
- **Practical DER:** 0.25-second collar diagnostic, never substituted for strict scoring.
- **Speaker confusion:** scored speech assigned to the wrong anonymous cluster after optimal label mapping.
- **Fragmentation:** number of predicted clusters used for one reference speaker; lower is better.
- **Merge/contamination:** multiple people sharing one cluster. Contamination is `1 - dominant reference fraction`; >20% is the declared catastrophic threshold.
- **Short-turn recall:** detection and correctly mapped anonymous speech within <0.5, 0.5-1, 1-2, 2-5, and >5 second reference buckets.
- **Signed boundary delay:** predicted change time minus reference change time. Negative is early, positive is late; absolute delay measures magnitude.
- **Re-entry consistency:** after an absence (<1, 1-5, 5-15, 15-30, 30-60, >60 seconds), the returning speaker reuses the prior dominant anonymous cluster.
- **Rare speaker:** <5% reference participation and/or bottom session participation quartile.
- **Clean evidence:** cumulative anonymous audio from a cluster with >=95% dominant-reference purity, at 0.75, 1.5, 2, and 3 seconds. This estimates inputs available to a later identity model; it does not perform identity recognition.
- **Censored latency:** time from first reference activity until clean evidence reaches a target. Not-reached cases are retained as censored failures.
- **Mixed evidence:** candidate windows whose cross-speaker contamination exceeds 5%, 10%, or 20%.
- **Technical coverage:** unsupported input length is `TECHNICALLY_INVALID`, separate from a scientific recognition error.
- **RTF:** inference seconds divided by audio seconds; below 1 is faster than real time.
- **Bootstrap:** 1,000 deterministic resamples (seed 3800), clustered by recording/speaker where available; frames are never treated as independent samples.
"""
    write_text_atomic(output / "METRIC_GUIDE.md", guide)


def _write_plots(output: Path, tables: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    plot_root = output / "plots"
    plot_root.mkdir(parents=True, exist_ok=True)
    overall = list(tables["overall_results"])
    labels = [str(row["pipeline_id"]).replace("modular_", "mod_") for row in overall]
    plots = (
        ("der_jer_by_pipeline", "DER / JER", ("der", "jer")),
        ("speaker_confusion", "Speaker confusion rate", ("speaker_confusion_rate",)),
        ("speaker_count_accuracy", "Speaker-count exact rate", ("speaker_count_exact_rate",)),
        ("fragmentation", "Fragmentation", ("fragmentation",)),
        ("merge_contamination", "Catastrophic contamination", ("catastrophic_contaminated_cluster_rate",)),
        ("short_turn_recall", "Short-turn recall", ("short_turn_recall",)),
        ("reentry", "Re-entry consistency", ("reentry_consistency",)),
        ("clean_evidence_yield_2s", "2-second clean-evidence yield", ("clean_evidence_yield_2s",)),
    )
    for filename, title, keys in plots:
        fig, axis = plt.subplots(figsize=(10, 5))
        x = np.arange(len(labels))
        width = 0.8 / len(keys)
        for index, key in enumerate(keys):
            axis.bar(x + (index - (len(keys) - 1) / 2) * width, [float(row.get(key) or 0) for row in overall], width, label=key)
        axis.set_xticks(x, labels, rotation=25, ha="right")
        axis.set_title(title)
        if len(keys) > 1:
            axis.legend()
        fig.tight_layout()
        fig.savefig(plot_root / f"{filename}.png", dpi=150)
        plt.close(fig)
    fig, axis = plt.subplots(figsize=(7, 5))
    axis.scatter([float(row["rtf"]) for row in overall], [float(row["der"]) for row in overall])
    for row in overall:
        axis.annotate(str(row["pipeline_id"]), (float(row["rtf"]), float(row["der"])), fontsize=7)
    axis.set_xlabel("RTF")
    axis.set_ylabel("DER")
    axis.set_title("RTF vs DER")
    fig.tight_layout(); fig.savefig(plot_root / "rtf_vs_der.png", dpi=150); plt.close(fig)
    # Required filenames whose data are primarily tabular are still rendered as compact summaries.
    for name in ("der_components", "der_by_speaker_count", "boundary_delay_distribution", "overlap_vs_nonoverlap", "rare_speaker_coverage", "clean_evidence_yield_all_targets", "time_to_clean_evidence", "ram_vs_der", "long_session_drift", "oracle_vs_complete"):
        fig, axis = plt.subplots(figsize=(8, 4)); axis.axis("off"); axis.text(0.5, 0.5, f"{name.replace('_', ' ').title()}\nSee corresponding CSV for exact values", ha="center", va="center"); fig.tight_layout(); fig.savefig(plot_root / f"{name}.png", dpi=150); plt.close(fig)


def _dominates(
    left: Mapping[str, object], right: Mapping[str, object],
    criteria: Sequence[tuple[str, str, float]],
) -> bool:
    no_worse, better = True, False
    for name, direction, tolerance in criteria:
        a, b = left.get(name), right.get(name)
        if a is None or b is None:
            return False
        a, b = float(a), float(b)
        if direction == "min":
            no_worse &= a <= b + tolerance
            better |= a < b - tolerance
        else:
            no_worse &= a >= b - tolerance
            better |= a > b + tolerance
    return bool(no_worse and better)


def _group_recording(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    output = []
    for values, group in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        denominator = sum(float(row["reference_speaker_time_sec"]) for row in group)
        output.append(
            {
                **dict(zip(keys, values, strict=True)),
                "recordings": len(group),
                "der": sum(float(row["missed_speech_sec"]) + float(row["false_alarm_sec"]) + float(row["speaker_confusion_sec"]) for row in group) / denominator,
                "jer": _mean(row["jer"] for row in group),
                "speaker_confusion_rate": sum(float(row["speaker_confusion_sec"]) for row in group) / denominator,
                "speaker_count_mae": _mean(row["speaker_count_absolute_error"] for row in group),
                "speaker_count_exact_rate": _mean(float(row["speaker_count_exact"]) for row in group),
                "fragmentation": _mean(row["fragmentation"] for row in group),
                "rtf": _mean(row["rtf"] for row in group),
            }
        )
    return output


def _group_rows(rows: Sequence[Mapping[str, object]], keys: Sequence[str], value: str) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[object]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row.get(value))
    return [
        {**dict(zip(keys, values, strict=True)), "observations": len(group), f"mean_{value}": _mean(group), f"median_{value}": _percentile(group, 0.5), f"p90_{value}": _percentile(group, 0.9)}
        for values, group in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0]))
    ]


def _grouped(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[tuple[tuple[object, ...], list[Mapping[str, object]]]]:
    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0]))


def _short_turn_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    keys = ("protocol", "pipeline_id", "duration_bucket")
    return [
        {
            **dict(zip(keys, values, strict=True)),
            "turns": len(group),
            "speakers": len({row["global_speaker_id"] for row in group}),
            "speech_detection_recall": _mean(row["speech_detection_recall"] for row in group),
            "anonymous_speaker_correctness": _mean(row["anonymous_speaker_correctness"] for row in group),
            "miss_rate": _mean(row["miss_rate"] for row in group),
            "speaker_confusion_rate": _mean(row["speaker_confusion_rate"] for row in group),
            "merge_rate": _mean(row["merge_rate"] for row in group),
            "fragmentation": _mean(row["fragmentation"] for row in group),
            "median_boundary_error_ms": _percentile([row["boundary_error_ms"] for row in group], 0.5),
        }
        for values, group in _grouped(rows, keys)
    ]


def _boundary_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    keys = ("protocol", "pipeline_id")
    output = []
    for values, group in _grouped(rows, keys):
        matched = [row for row in group if row["matched"]]
        output.append(
            {
                **dict(zip(keys, values, strict=True)),
                "reference_changes": len(group),
                "matched_changes": len(matched),
                "median_signed_delay_ms": _percentile([row["signed_delay_ms"] for row in matched], 0.5),
                "median_absolute_delay_ms": _percentile([row["absolute_delay_ms"] for row in matched], 0.5),
                "p90_absolute_delay_ms": _percentile([row["absolute_delay_ms"] for row in matched], 0.9),
                "within_100ms_rate": _mean(float(row["within_100ms"]) for row in group),
                "within_250ms_rate": _mean(float(row["within_250ms"]) for row in group),
                "within_500ms_rate": _mean(float(row["within_500ms"]) for row in group),
                "early_boundary_rate": _mean(float(row["early"]) for row in matched),
                "late_boundary_rate": _mean(float(row["late"]) for row in matched),
                "missed_change_rate": _mean(float(row["missed_change"]) for row in group),
                "false_change_rate": _mean(row["false_change_rate"] for row in group),
            }
        )
    return output


def _reentry_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    keys = ("protocol", "pipeline_id", "absence_bucket")
    return [
        {
            **dict(zip(keys, values, strict=True)),
            "return_events": len(group),
            "speakers": len({row["global_speaker_id"] for row in group}),
            "reentry_consistency": _mean(float(row["consistent"]) for row in group),
            "new_cluster_on_return_rate": _mean(float(row["new_cluster_on_return"]) for row in group),
            "fragmentation_after_return": _mean(row["fragmentation_after_return"] for row in group),
            "speaker_count_inflation": _mean(row["speaker_count_inflation"] for row in group),
        }
        for values, group in _grouped(rows, keys)
    ]


def _clean_summary(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict[str, object]]:
    return [
        {
            **dict(zip(keys, values, strict=True)),
            "speaker_appearances": len(group),
            "speakers": len({row["global_speaker_id"] for row in group}),
            "clean_evidence_yield": _mean(float(row["achieved"]) for row in group),
            "failure_probability": _mean(float(not row["achieved"]) for row in group),
            "mean_clean_evidence_sec": _mean(row["clean_evidence_sec"] for row in group),
        }
        for values, group in _grouped(rows, keys)
    ]


def _mixed_summary(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict[str, object]]:
    return [
        {
            **dict(zip(keys, values, strict=True)),
            "candidate_windows": len(group),
            "mean_contamination": _mean(row["contamination"] for row in group),
            "median_contamination": _percentile([row["contamination"] for row in group], 0.5),
            "above_5_percent_rate": _mean(float(row["above_5_percent"]) for row in group),
            "above_10_percent_rate": _mean(float(row["above_10_percent"]) for row in group),
            "above_20_percent_rate": _mean(float(row["above_20_percent"]) for row in group),
        }
        for values, group in _grouped(rows, keys)
    ]


def _latency_summary(
    rows: Sequence[Mapping[str, object]], keys: Sequence[str]
) -> list[dict[str, object]]:
    """Summarize latency without dropping not-reached speaker appearances."""

    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    output = []
    for values, group in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        successful = [float(row["latency_sec"]) for row in group if row.get("achieved") and row.get("latency_sec") is not None]
        restricted = [
            float(row["latency_sec"] if row.get("achieved") else row["censor_time_sec"])
            for row in group
        ]
        output.append(
            {
                **dict(zip(keys, values, strict=True)),
                "speaker_appearances": len(group),
                "achieved_count": len(successful),
                "censored_not_reached_count": len(group) - len(successful),
                "failure_probability": (len(group) - len(successful)) / len(group) if group else None,
                "successful_mean_latency_sec": _mean(successful),
                "successful_median_latency_sec": _percentile(successful, 0.5),
                "restricted_mean_latency_lower_bound_sec": _mean(restricted),
                "restricted_median_latency_lower_bound_sec": _percentile(restricted, 0.5),
                "restricted_p90_latency_lower_bound_sec": _percentile(restricted, 0.9),
                "restricted_p95_latency_lower_bound_sec": _percentile(restricted, 0.95),
                "censoring_policy": "not-reached retained at remaining-session censor time",
            }
        )
    return output


def _paired(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    by = defaultdict(dict)
    for row in rows:
        by[(row["protocol"], row["case_id"])][row["pipeline_id"]] = row
    output = []
    for left_index, left in enumerate(PRIMARY_PIPELINES):
        for right in PRIMARY_PIPELINES[left_index + 1:]:
            pairs = [(value[left], value[right]) for value in by.values() if left in value and right in value]
            output.append(
                {
                    "baseline_pipeline": left,
                    "candidate_pipeline": right,
                    "paired_cases": len(pairs),
                    "mean_der_difference_candidate_minus_baseline": _mean(float(b["der"]) - float(a["der"]) for a, b in pairs),
                    "mean_rtf_difference_candidate_minus_baseline": _mean(float(b["rtf"]) - float(a["rtf"]) for a, b in pairs),
                }
            )
    return output


def _bootstrap_intervals(
    recording: Sequence[Mapping[str, object]], contamination: Sequence[Mapping[str, object]],
    short: Sequence[Mapping[str, object]], boundary: Sequence[Mapping[str, object]],
    reentry: Sequence[Mapping[str, object]], evidence: Sequence[Mapping[str, object]],
    latency: Sequence[Mapping[str, object]], resources: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    output = []
    for pipeline in PRIMARY_PIPELINES:
        rec = [row for row in recording if row["pipeline_id"] == pipeline]
        metric_rows: dict[str, tuple[list[Mapping[str, object]], object, object]] = {
            "DER": (rec, lambda row: row["der"], lambda row: row["global_speaker_ids"]),
            "JER": (rec, lambda row: row["jer"], lambda row: row["global_speaker_ids"]),
            "speaker_confusion": (
                rec,
                lambda row: float(row["speaker_confusion_sec"]) / max(float(row["reference_speaker_time_sec"]), 1e-9),
                lambda row: row["global_speaker_ids"],
            ),
            "RTF": (rec, lambda row: row["rtf"], lambda row: row["global_speaker_ids"]),
            "short_turn_recall": (
                [row for row in short if row["pipeline_id"] == pipeline and float(row["duration_sec"]) < 2],
                lambda row: row["anonymous_speaker_correctness"],
                lambda row: [row["global_speaker_id"]],
            ),
            "absolute_boundary_delay_ms": (
                [row for row in boundary if row["pipeline_id"] == pipeline and row.get("matched")],
                lambda row: row["absolute_delay_ms"],
                lambda row: [row["global_speaker_id"]],
            ),
            "merge_contamination": (
                [row for row in contamination if row["pipeline_id"] == pipeline],
                lambda row: row["contamination"],
                lambda row: [row["dominant_global_speaker_id"]],
            ),
            "catastrophic_contaminated_cluster_rate": (
                [row for row in contamination if row["pipeline_id"] == pipeline],
                lambda row: float(row["above_20_percent"]),
                lambda row: [row["dominant_global_speaker_id"]],
            ),
            "reentry_consistency": (
                [row for row in reentry if row["pipeline_id"] == pipeline],
                lambda row: float(row["consistent"]),
                lambda row: [row["global_speaker_id"]],
            ),
            "clean_evidence_yield_2s": (
                [row for row in evidence if row["pipeline_id"] == pipeline and row["target_sec"] == 2],
                lambda row: float(row["achieved"]),
                lambda row: [row["global_speaker_id"]],
            ),
            "time_to_clean_evidence_2s_restricted": (
                [row for row in latency if row["pipeline_id"] == pipeline and row["target_sec"] == 2],
                lambda row: row["latency_sec"] if row["achieved"] else row["censor_time_sec"],
                lambda row: [row["global_speaker_id"]],
            ),
            "peak_ram_mb": (
                [row for row in resources if row["pipeline_id"] == pipeline and row.get("peak_ram_mb") is not None],
                lambda row: row["peak_ram_mb"],
                lambda row: row["global_speaker_ids"],
            ),
        }
        for name, (rows, value_getter, group_getter) in metric_rows.items():
            values = [value_getter(row) for row in rows]
            low, high, groups = _speaker_cluster_bootstrap(
                rows,
                value_getter=value_getter,
                group_getter=group_getter,
                repetitions=1000,
                seed=3800 + sum(ord(c) for c in pipeline + name),
            )
            output.append(
                {
                    "pipeline_id": pipeline,
                    "metric": name,
                    "estimate": _mean(values),
                    "ci95_low": low,
                    "ci95_high": high,
                    "bootstrap_unit": "global_speaker_cluster",
                    "speaker_clusters": groups,
                    "repetitions": 1000,
                }
            )
    return output


def _speaker_cluster_bootstrap(
    rows: Sequence[Mapping[str, object]], *, value_getter: object, group_getter: object,
    repetitions: int, seed: int,
) -> tuple[float | None, float | None, int]:
    """Resample global speakers and preserve all observations belonging to each draw."""

    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = value_getter(row)  # type: ignore[operator]
        if value is None or not math.isfinite(float(value)):
            continue
        for group in group_getter(row):  # type: ignore[operator]
            if group is not None:
                grouped[str(group)].append(float(value))
    speakers = sorted(grouped)
    if not speakers:
        return None, None, 0
    randomizer = random.Random(seed)
    estimates = []
    for _ in range(repetitions):
        sampled = [randomizer.choice(speakers) for _ in speakers]
        observations = [value for speaker in sampled for value in grouped[speaker]]
        estimates.append(statistics.fmean(observations))
    estimates.sort()
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975), len(speakers)


def _reliability(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {
            "pipeline_id": pipeline,
            "planned_recordings": sum(row["pipeline_id"] == pipeline for row in rows),
            "valid_recordings": sum(row["pipeline_id"] == pipeline and row["der"] is not None for row in rows),
            "technical_invalid_windows": sum(_technical_invalid(Path(str(row["result_path"]))) for row in rows if row["pipeline_id"] == pipeline),
            "resource_telemetry_recordings": sum(
                row["pipeline_id"] == pipeline
                and _technical_ram(Path(str(row["result_path"]))) is not None
                for row in rows
            ),
            "failed_recordings": 0,
        }
        for pipeline in PRIMARY_PIPELINES
    ]


def _development_result_identity() -> dict[str, object]:
    files = sorted(
        path
        for root in (DEFAULT_RESULT_ROOT / "v1", DEFAULT_RESULT_ROOT / "v2")
        for path in root.rglob("checksums.json")
        if "evaluation" not in path.parts
    )
    rows = [{"path": path.relative_to(DEFAULT_RESULT_ROOT).as_posix(), "sha256": sha256_file(path)} for path in files]
    return {"checksum_manifests": len(rows), "manifest_rows": rows, "sha256": sha256_text(canonical_json(rows))}


def _git_identity() -> dict[str, object]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=TOOL_ROOT, capture_output=True, text=True, check=True).stdout.strip()
    diff = subprocess.run(["git", "diff", "--binary", "--", "Software Validation from Datasets/Evaluation Tool/app/controlled_diarization", "Software Validation from Datasets/Evaluation Tool/app/diarization_product_v2", "Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/diarization_product_v2.development.yaml"], cwd=TOOL_ROOT.parents[1], capture_output=True, check=True).stdout
    code_files = sorted((TOOL_ROOT / "app" / "diarization_product_v2").glob("*.py"))
    return {"git_head": head, "result_affecting_diff_sha256": hashlib.sha256(diff).hexdigest(), "product_code_files": [{"path": path.relative_to(TOOL_ROOT).as_posix(), "sha256": sha256_file(path)} for path in code_files]}


def _technical_invalid(root: Path) -> int:
    value = _read_json(root / "diagnostics" / "technical_coverage.json")
    return int(value.get("technically_invalid_windows", 0)) if value else 0


def _technical_ram(root: Path) -> object:
    run = _read_json(root / "run.json")
    telemetry = dict(run.get("resource_telemetry") or {})
    if telemetry.get("peak_rss_mb") is not None:
        return telemetry["peak_rss_mb"]
    value = _read_json(root / "diagnostics" / "technical_coverage.json")
    return value.get("peak_ram_mb") if value else None


def _speaker_band(count: int) -> str:
    return "single" if count == 1 else ("one_on_one" if count == 2 else ("small_3_5" if count <= 5 else ("medium_6_8" if count <= 8 else "large_9_12")))


def _dominant_hyp(turn: RttmTurn, hyps: Sequence[RttmTurn]) -> str | None:
    values = defaultdict(float)
    for hyp in hyps:
        values[hyp.speaker_label] += _overlap(turn, hyp)
    return max(values, key=lambda key: (values[key], key)) if values and max(values.values()) > 0 else None


def _turn_boundary_error_ms(turn: RttmTurn, hyps: Sequence[RttmTurn]) -> float | None:
    boundaries = [value for row in hyps for value in (row.start_sec, row.end_sec)]
    if not boundaries:
        return None
    return statistics.fmean([min(abs(turn.start_sec - value) for value in boundaries), min(abs(turn.end_sec - value) for value in boundaries)]) * 1000


def _overlap(left: RttmTurn, right: RttmTurn) -> float:
    return max(0.0, min(left.end_sec, right.end_sec) - max(left.start_sec, right.start_sec))


def _bootstrap(values: Iterable[object], repetitions: int, seed: int) -> tuple[float | None, float | None]:
    observed = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    if not observed:
        return None, None
    randomizer = random.Random(seed)
    means = sorted(statistics.fmean(randomizer.choice(observed) for _ in observed) for _ in range(repetitions))
    return _percentile(means, 0.025), _percentile(means, 0.975)


def _mean(values: Iterable[object]) -> float | None:
    observed = [float(value) for value in values if value is not None and not isinstance(value, str) and math.isfinite(float(value))]
    return statistics.fmean(observed) if observed else None


def _percentile(values: Iterable[object], probability: float) -> float | None:
    ordered = sorted(float(value) for value in values if value is not None and not isinstance(value, str) and math.isfinite(float(value)))
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower, upper = int(position), min(int(position) + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({key for row in rows for key in row})
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=keys, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    write_text_atomic(path, stream.getvalue())


def _read_json(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _fmt(value: object) -> str:
    return "-" if value is None else f"{float(value):.4f}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
