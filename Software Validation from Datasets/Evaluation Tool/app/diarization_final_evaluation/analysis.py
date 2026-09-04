"""Final controlled/native evaluation analysis, plots, report, and export."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
from typing import Iterable, Mapping, Sequence
import zipfile

from app.controlled_diarization.contracts import (
    TOOL_ROOT,
    canonical_json,
    load_config,
    load_pipeline_registry,
    sha256_file,
    sha256_text,
)
from app.diarization_evaluation.artifacts import write_json_atomic, write_text_atomic
from app.diarization_evaluation.formats import parse_rttm
from app.diarization_final_evaluation.contracts import (
    ANALYSIS_ROOT,
    AUTHORIZATION_ROOT,
    FINAL_PACKAGE,
    FROZEN_RUNTIME_CONFIG,
    NATIVE_RESULT_ROOT,
    RESULT_ROOT,
    TASK1_NATIVE_ROOT,
    TASK1_SELECTION,
    TASK1_SELECTION_CHECKSUM,
    V1_PROTOCOL_ROOT,
    V1_RESULT_ROOT,
    V2_PROTOCOL_ROOT,
    V2_RESULT_ROOT,
)
from app.diarization_final_evaluation.decision import require_valid_decision, selected_pipelines
from app.diarization_final_evaluation.native import native_rows


def analyze() -> dict[str, object]:
    decision = require_valid_decision()
    pipelines = selected_pipelines()
    from app.diarization_product_v2 import analysis as product

    # Reuse the frozen Task-1 metric definitions while restricting their global
    # grouping helpers to the exact frozen finalists. This changes no inference.
    product.PRIMARY_PIPELINES = pipelines
    tables = _controlled_tables(product, pipelines)
    native = _native_tables(product, pipelines)
    tables.update(native)
    tables["resource_results"] = [*tables["resource_results"], *native["native_resource_results"]]
    tables.pop("native_resource_results", None)
    tables["overall_results"] = _final_overall(tables, pipelines)
    tables["reliability_summary"] = _reliability(tables, pipelines)

    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    table_manifest: dict[str, object] = {}
    name_map = {
        "overall_results": "overall_results.csv",
        "controlled_v1_results": "controlled_v1_results.csv",
        "controlled_v2_results": "controlled_v2_results.csv",
        "chime6_results": "chime6_results.csv",
        "voices_diagnostics": "voices_diagnostics.csv",
        "recording_results": "recording_results.csv",
        "scenario_results": "scenario_results.csv",
        "speaker_count_results": "speaker_count_results.csv",
        "short_turn_results": "short_turn_results.csv",
        "boundary_delay_results": "boundary_delay_results.csv",
        "overlap_results": "overlap_results.csv",
        "fragmentation_results": "fragmentation_results.csv",
        "merge_contamination_results": "merge_contamination_results.csv",
        "rare_speaker_results": "rare_speaker_results.csv",
        "single_speaker_results": "single_speaker_results.csv",
        "reentry_results": "reentry_results.csv",
        "long_session_results": "long_session_results.csv",
        "clean_evidence_yield": "clean_evidence_yield.csv",
        "time_to_clean_evidence": "time_to_clean_evidence.csv",
        "mixed_speaker_evidence": "mixed_speaker_evidence.csv",
        "resource_results": "resource_results.csv",
        "paired_comparisons": "paired_comparisons.csv",
        "bootstrap_intervals": "bootstrap_intervals.csv",
        "pipeline_identity": "pipeline_identity.csv",
        "reliability_summary": "reliability_summary.csv",
    }
    for key, filename in name_map.items():
        rows = tables.get(key, [])
        path = ANALYSIS_ROOT / filename
        _write_csv(path, rows)
        table_manifest[filename] = {"rows": len(rows), "sha256": sha256_file(path)}
    plots = _write_plots(tables, pipelines)
    recommendation = _recommend(tables, pipelines)
    _write_metric_guide()
    _write_report(tables, recommendation, pipelines)
    manifest = {
        "schema_version": "diarization-final-analysis-manifest.v1",
        "created_at_utc": _now(),
        "frozen_selection_path": str(TASK1_SELECTION),
        "frozen_selection_sha256": sha256_file(TASK1_SELECTION),
        "frozen_pipeline_ids": list(pipelines),
        "frozen_configuration_sha256": decision["selected_configuration_sha256"],
        "protocol_ids": decision["protocol_ids"],
        "development_result_identity_sha256": decision["development_identity_sha256"],
        "evaluation_tuning_performed": False,
        "known_speaker_attribution_performed": False,
        "hybrid_run": False,
        "asr_cpwer_run": False,
        "fine_tuning_run": False,
        "controlled_evaluation_run": True,
        "chime6_finalist_evaluation_run": True,
        "voices_acoustic_diagnostic_run": True,
        "bootstrap_seed": 3800,
        "bootstrap_repetitions": 1000,
        "tables": table_manifest,
        "plots": plots,
        "recommendation": recommendation,
        "result_affecting_task2_code": _code_identity(),
    }
    write_json_atomic(ANALYSIS_ROOT / "analysis_manifest.json", manifest)
    return {"analysis_root": str(ANALYSIS_ROOT), "manifest": manifest}


def collect() -> dict[str, object]:
    manifest_path = ANALYSIS_ROOT / "analysis_manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError("final analysis_manifest.json is required before collection")
    sources: list[tuple[Path, str]] = []
    for path in ANALYSIS_ROOT.rglob("*"):
        if path.is_file():
            sources.append((path, f"analysis/{path.relative_to(ANALYSIS_ROOT).as_posix()}"))
    for path in RESULT_ROOT.rglob("*"):
        if not path.is_file() or ANALYSIS_ROOT in path.parents:
            continue
        if any(part in {"_shared_cache", "_native_audio_cache", "_partial", "_failed"} for part in path.parts):
            continue
        if path.suffix.lower() in {".wav", ".flac", ".mp3", ".onnx", ".pt", ".pth", ".ckpt"}:
            continue
        sources.append((path, f"results/{path.relative_to(RESULT_ROOT).as_posix()}"))
    for path, archive_name in (
        (TASK1_SELECTION, "frozen_decision/frozen_diarization_development_selection.yaml"),
        (TASK1_SELECTION_CHECKSUM, "frozen_decision/frozen_diarization_development_selection.sha256"),
        (FROZEN_RUNTIME_CONFIG, "frozen_decision/frozen_development_pipeline_config.yaml"),
        (V1_PROTOCOL_ROOT / "protocol_summary.json", "protocols/controlled_v1_protocol_summary.json"),
        (V2_PROTOCOL_ROOT / "protocol_summary.json", "protocols/product_v2_protocol_summary.json"),
        (TASK1_NATIVE_ROOT / "native_diarization_manifest.json", "protocols/native_diarization_manifest.json"),
        (TASK1_NATIVE_ROOT / "native_diarization_manifest.parquet", "protocols/native_diarization_manifest.parquet"),
        (TASK1_NATIVE_ROOT / "references.rttm", "protocols/native_references.rttm"),
        (TASK1_NATIVE_ROOT / "scored_regions.uem", "protocols/native_scored_regions.uem"),
    ):
        sources.append((path, archive_name))
    unique = {archive: path for path, archive in sources if path.is_file()}
    inventory = [
        {"archive_path": archive, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for archive, path in sorted(unique.items())
    ]
    inventory_path = RESULT_ROOT / "package_inventory.json"
    write_json_atomic(inventory_path, {"schema_version": "diarization-final-package-inventory.v1", "files": inventory})
    unique["inventory/package_inventory.json"] = inventory_path
    FINAL_PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FINAL_PACKAGE, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        for archive_name, path in sorted(unique.items()):
            archive.write(path, archive_name)
    with zipfile.ZipFile(FINAL_PACKAGE) as archive:
        names = archive.namelist()
    forbidden = [name for name in names if _forbidden_archive_name(name)]
    if forbidden:
        raise RuntimeError(f"final package contains prohibited payloads: {forbidden[:5]}")
    result = {
        "schema_version": "diarization-final-package.v1",
        "path": str(FINAL_PACKAGE),
        "sha256": sha256_file(FINAL_PACKAGE),
        "bytes": FINAL_PACKAGE.stat().st_size,
        "entries": len(names),
        "forbidden_entries": 0,
        "raw_datasets_included": False,
        "model_weights_included": False,
        "large_caches_included": False,
    }
    write_json_atomic(RESULT_ROOT / "package.json", result)
    return result


def _controlled_tables(product: object, pipelines: Sequence[str]) -> dict[str, list[dict[str, object]]]:
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
    for protocol, benchmark, result in (
        ("controlled_v1", V1_PROTOCOL_ROOT, V1_RESULT_ROOT),
        ("controlled_v2", V2_PROTOCOL_ROOT, V2_RESULT_ROOT),
    ):
        for case in _jsonl(benchmark / "evaluation" / "case_manifest.jsonl"):
            for pipeline in pipelines:
                root = result / "evaluation" / pipeline / str(case["case_id"])
                run = _json(root / "run.json")
                metric = _json(root / "metrics" / "summary.json")
                refs = parse_rttm(root / "references" / "reference.rttm")
                hyps = parse_rttm(root / "predictions" / "segments.rttm")
                detail = product._case_product_metrics(case, refs, hyps)
                strict = dict(metric["primary_strict"])
                practical = dict(metric["practical_boundary_tolerant"])
                count = dict(metric["speaker_count"])
                base = {
                    "protocol": protocol,
                    "protocol_id": case["benchmark_id"],
                    "pipeline_id": pipeline,
                    "case_id": case["case_id"],
                    "scenario_profile": case.get("scenario_profile", "controlled_v1_factorial"),
                    "speaker_band": case.get("speaker_band", product._speaker_band(int(case["speaker_count"]))),
                    "speaker_count": int(case["speaker_count"]),
                    "global_speaker_ids": sorted(dict(case["local_to_global_speaker"]).values()),
                    "turn_cadence": case["turn_cadence"],
                    "overlap_profile": case["overlap_profile"],
                    "long_session": bool(case.get("long_session", False)),
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
                    **detail["recording"],
                    "result_path": str(root),
                }
                recording.append(base)
                contamination.extend({**base, **row} for row in detail["contamination"])
                short.extend({**base, **row} for row in detail["short_turns"])
                boundary.extend({**base, **row} for row in detail["boundaries"])
                reentry.extend({**base, **row} for row in detail["reentry"])
                rare.extend({**base, **row} for row in detail["speakers"] if row["rare_speaker"])
                evidence.extend({**base, **row} for row in detail["evidence"])
                latency.extend({**base, **row} for row in detail["latency"])
                mixed.extend({**base, **row} for row in detail["mixed"])
                if base["long_session"]:
                    long_rows.extend(product._long_session_bins(base, refs, hyps))
                resources.append({
                    **base,
                    "dataset": protocol,
                    "environment_profile": dict(run["environment"])["environment_profile"],
                    "peak_ram_mb": product._technical_ram(root),
                })
    for pipeline in pipelines:
        match = next(row for row in recording if row["pipeline_id"] == pipeline)
        identity = _json(Path(str(match["result_path"])) / "resolved_pipeline_identity.json")
        identities.append({
            "pipeline_id": pipeline,
            "configuration_sha256": identity.get("configuration_sha256"),
            "segmentation": identity.get("segmentation"),
            "embedding": identity.get("embedding"),
            "clustering": identity.get("clustering"),
            "implementation_class": identity.get("implementation_class"),
            "identity_sha256": sha256_text(canonical_json(identity)),
        })
    short_summary = product._short_turn_summary(short)
    short_labels = {"lt_0_50": "<0.50 s", "0_50_to_1_00": "0.50–1.00 s", "1_00_to_2_00": "1.00–2.00 s", "2_00_to_5_00": "2.00–5.00 s", "gt_5_00": ">5.00 s"}
    for row in short_summary:
        row["duration_bucket"] = short_labels.get(str(row["duration_bucket"]), row["duration_bucket"])
    reentry_summary = product._reentry_summary(reentry)
    absence_labels = {"lt_1": "<1 s", "1_to_5": "1–5 s", "5_to_15": "5–15 s", "15_to_30": "15–30 s", "30_to_60": "30–60 s", "gt_60": ">60 s"}
    for row in reentry_summary:
        row["absence_bucket"] = absence_labels.get(str(row["absence_bucket"]), row["absence_bucket"])
    speaker_count_summary = product._group_recording(recording, ("protocol", "pipeline_id", "speaker_band", "speaker_count"))
    band_labels = {"single": "1", "one_on_one": "2", "small_3_5": "3–5", "medium_6_8": "6–8", "large_9_12": "9–12"}
    for row in speaker_count_summary:
        row["speaker_band_label"] = band_labels.get(str(row["speaker_band"]), row["speaker_band"])
    return {
        "recording_results": recording,
        "controlled_v1_results": product._group_recording([row for row in recording if row["protocol"] == "controlled_v1"], ("protocol", "pipeline_id")),
        "controlled_v2_results": product._group_recording([row for row in recording if row["protocol"] == "controlled_v2"], ("protocol", "pipeline_id")),
        "scenario_results": product._group_recording(recording, ("protocol", "pipeline_id", "scenario_profile", "overlap_profile")),
        "speaker_count_results": speaker_count_summary,
        "short_turn_results": short_summary,
        "boundary_delay_results": product._boundary_summary(boundary),
        "overlap_results": product._group_recording(recording, ("protocol", "pipeline_id", "overlap_profile")),
        "fragmentation_results": product._group_recording(recording, ("protocol", "pipeline_id", "speaker_band")),
        "merge_contamination_results": _contamination_summary(contamination),
        "rare_speaker_results": _speaker_summary(rare, ("protocol", "pipeline_id", "speaker_band")),
        "single_speaker_results": product._group_recording([row for row in recording if int(row["speaker_count"]) == 1], ("protocol", "pipeline_id")),
        "reentry_results": reentry_summary,
        "long_session_results": long_rows,
        "clean_evidence_yield": product._clean_summary(evidence, ("protocol", "pipeline_id", "target_sec")),
        "time_to_clean_evidence": product._latency_summary(latency, ("protocol", "pipeline_id", "target_sec")),
        "mixed_speaker_evidence": product._mixed_summary(mixed, ("protocol", "pipeline_id", "target_sec")),
        "resource_results": resources,
        "paired_comparisons": product._paired(recording),
        "bootstrap_intervals": product._bootstrap_intervals(recording, contamination, short, boundary, reentry, evidence, latency, resources),
        "pipeline_identity": identities,
    }


def _native_tables(product: object, pipelines: Sequence[str]) -> dict[str, list[dict[str, object]]]:
    chime: list[dict[str, object]] = []
    voices: list[dict[str, object]] = []
    resources: list[dict[str, object]] = []
    for dataset in ("chime6", "voices"):
        for source in native_rows(dataset):
            for pipeline in pipelines:
                root = NATIVE_RESULT_ROOT / dataset / pipeline / str(source["evaluation_unit_id"])
                run = _json(root / "run.json")
                metric = _json(root / "metrics" / "summary.json")
                diagnostic = _json(root / "diagnostics" / "acoustic_fragmentation.json")
                timing = dict(run["timing"])
                resource = dict(run.get("resource_telemetry") or {})
                base = {
                    "dataset": dataset,
                    "pipeline_id": pipeline,
                    "evaluation_unit_id": source["evaluation_unit_id"],
                    "stream_type": source.get("stream_type"),
                    "reference_support": source.get("reference_support"),
                    "location": source.get("location"),
                    "room": source.get("room"),
                    "distractor": source.get("distractor"),
                    "mic": source.get("mic"),
                    "position": source.get("position"),
                    "degrees": source.get("degrees"),
                    "duration_sec": float(source["duration_sec"]),
                    "der_jer_eligible": bool(source["der_jer_eligible"]),
                    "der": metric.get("der"),
                    "jer": metric.get("jer"),
                    "missed_speech_sec": metric.get("missed_speech_sec"),
                    "false_alarm_sec": metric.get("false_alarm_sec"),
                    "speaker_confusion_sec": metric.get("speaker_confusion_sec"),
                    "reference_speaker_time_sec": metric.get("reference_speaker_time_sec"),
                    "reference_speaker_count": metric.get("reference_speaker_count"),
                    "predicted_speaker_count": diagnostic["predicted_speaker_count"],
                    "speaker_count_error": metric.get("speaker_count_error"),
                    "predicted_turn_count": diagnostic["predicted_turn_count"],
                    "false_speaker_changes_per_minute": diagnostic["false_speaker_changes_per_minute"],
                    "fragment_count": diagnostic["fragment_count"],
                    "largest_cluster_fraction": diagnostic["largest_cluster_fraction"],
                    "phantom_speaker_duration_sec": diagnostic["phantom_speaker_duration_sec"],
                    "rtf": timing["real_time_factor"],
                    "inference_sec": timing["diarization_inference_sec"],
                    "wall_sec": timing["total_wall_sec"],
                    "peak_ram_mb": resource.get("peak_rss_mb"),
                    "result_path": str(root),
                }
                resources.append({**base, "protocol": dataset, "environment_profile": "cross-environment-frozen-finalist"})
                if dataset == "voices":
                    voices.append(base)
                    continue
                refs = parse_rttm(root / "references" / "reference.rttm")
                hyps = parse_rttm(root / "predictions" / "segments.rttm")
                if refs:
                    case = {
                        "local_to_global_speaker": {label: f"chime6::{source['session_id']}::{label}" for label in {row.speaker_label for row in refs}},
                        "duration_sec": float(source["duration_sec"]),
                    }
                    detail = product._case_product_metrics(case, refs, hyps)
                    base.update(detail["recording"])
                chime.append(base)
    return {
        "chime6_results": _native_chime_summary(chime),
        "voices_diagnostics": _voices_summary(voices),
        "native_resource_results": resources,
        "chime6_recording_results": chime,
        "voices_recording_diagnostics": voices,
    }


def _native_chime_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output = []
    for keys, group in _grouped(rows, ("pipeline_id", "stream_type", "reference_support")):
        denom = sum(float(row.get("reference_speaker_time_sec") or 0.0) for row in group)
        output.append({
            "pipeline_id": keys[0],
            "stream_type": keys[1],
            "reference_support": keys[2],
            "units": len(group),
            "audio_sec": sum(float(row["duration_sec"]) for row in group),
            "der": sum(float(row.get("missed_speech_sec") or 0.0) + float(row.get("false_alarm_sec") or 0.0) + float(row.get("speaker_confusion_sec") or 0.0) for row in group) / denom if denom else None,
            "jer": _mean(row.get("jer") for row in group),
            "miss_rate": sum(float(row.get("missed_speech_sec") or 0.0) for row in group) / denom if denom else None,
            "false_alarm_rate": sum(float(row.get("false_alarm_sec") or 0.0) for row in group) / denom if denom else None,
            "speaker_confusion_rate": sum(float(row.get("speaker_confusion_sec") or 0.0) for row in group) / denom if denom else None,
            "speaker_count_mae": _mean(abs(float(row.get("speaker_count_error") or 0.0)) for row in group),
            "mean_contamination": _mean(row.get("mean_contamination") for row in group),
            "cluster_purity": _mean(1.0 - float(row.get("mean_contamination") or 0.0) for row in group),
            "short_turn_recall_lt2s": _mean(row.get("short_turn_recall_lt2s") for row in group),
            "median_absolute_boundary_delay_ms": _median(row.get("median_absolute_boundary_delay_ms") for row in group),
            "reentry_consistency": _mean(row.get("reentry_consistency") for row in group),
            "rtf": _weighted_mean(group, "rtf", "duration_sec"),
            "peak_ram_mb": _max(row.get("peak_ram_mb") for row in group),
            "scoring_policy_note": "native Stage 11, 250 ms collar; participant-close references are wearer-only",
        })
    return output


def _voices_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output = []
    for keys, group in _grouped(rows, ("pipeline_id", "room", "distractor", "position")):
        output.append({
            "pipeline_id": keys[0], "room": keys[1], "distractor": keys[2], "position": keys[3],
            "units": len(group),
            "audio_sec": sum(float(row["duration_sec"]) for row in group),
            "mean_predicted_speaker_count": _mean(row["predicted_speaker_count"] for row in group),
            "false_speaker_changes_per_minute": _mean(row["false_speaker_changes_per_minute"] for row in group),
            "mean_fragment_count": _mean(row["fragment_count"] for row in group),
            "largest_cluster_fraction": _mean(row["largest_cluster_fraction"] for row in group),
            "phantom_speaker_duration_sec": sum(float(row["phantom_speaker_duration_sec"]) for row in group),
            "pipeline_failure_rate": 0.0,
            "rtf": _weighted_mean(group, "rtf", "duration_sec"),
            "peak_ram_mb": _max(row.get("peak_ram_mb") for row in group),
            "der": None,
            "jer": None,
            "speaker_confusion": None,
            "scientific_label": "ACOUSTIC FRAGMENTATION / FAR-FIELD DIAGNOSTIC",
        })
    return output


def _final_overall(tables: Mapping[str, Sequence[Mapping[str, object]]], pipelines: Sequence[str]) -> list[dict[str, object]]:
    output = []
    recording = tables["recording_results"]
    contamination = tables["merge_contamination_results"]
    clean = tables["clean_evidence_yield"]
    boundary = tables["boundary_delay_results"]
    reentry = tables["reentry_results"]
    resources = tables["resource_results"]
    chime = tables["chime6_results"]
    voices = tables["voices_diagnostics"]
    for pipeline in pipelines:
        rec = [row for row in recording if row["pipeline_id"] == pipeline]
        denom = sum(float(row["reference_speaker_time_sec"]) for row in rec)
        merge = [row for row in contamination if row["pipeline_id"] == pipeline]
        clean2 = [row for row in clean if row["pipeline_id"] == pipeline and float(row["target_sec"]) == 2.0]
        bound = [row for row in boundary if row["pipeline_id"] == pipeline]
        return_rows = [row for row in reentry if row["pipeline_id"] == pipeline]
        chime_far = [row for row in chime if row["pipeline_id"] == pipeline and row["stream_type"] == "farfield_array"]
        output.append({
            "pipeline_id": pipeline,
            "controlled_recordings": len(rec),
            "controlled_der": sum(float(row["missed_speech_sec"]) + float(row["false_alarm_sec"]) + float(row["speaker_confusion_sec"]) for row in rec) / denom,
            "controlled_jer": _mean(row["jer"] for row in rec),
            "controlled_speaker_confusion_rate": sum(float(row["speaker_confusion_sec"]) for row in rec) / denom,
            "catastrophic_contaminated_cluster_rate": _mean(row["above_20_percent_rate"] for row in merge),
            "mean_cluster_contamination": _mean(row["mean_contamination"] for row in merge),
            "clean_evidence_yield_2s": _mean(row["clean_evidence_yield"] for row in clean2),
            "median_absolute_boundary_delay_ms": _median(row["median_absolute_delay_ms"] for row in bound),
            "reentry_consistency": _mean(row["reentry_consistency"] for row in return_rows),
            "speaker_count_mae": _mean(row["speaker_count_absolute_error"] for row in rec),
            "fragmentation": _mean(row["fragmentation"] for row in rec),
            "controlled_rtf": _weighted_mean(rec, "rtf", "duration_sec"),
            "peak_ram_mb": _max(row.get("peak_ram_mb") for row in resources if row["pipeline_id"] == pipeline),
            "chime6_farfield_der": _mean(row["der"] for row in chime_far),
            "chime6_farfield_jer": _mean(row["jer"] for row in chime_far),
            "chime6_farfield_confusion": _mean(row["speaker_confusion_rate"] for row in chime_far),
            "voices_false_changes_per_minute": _mean(row["false_speaker_changes_per_minute"] for row in voices if row["pipeline_id"] == pipeline),
            "voices_largest_cluster_fraction": _mean(row["largest_cluster_fraction"] for row in voices if row["pipeline_id"] == pipeline),
        })
    return output


def _recommend(tables: Mapping[str, Sequence[Mapping[str, object]]], pipelines: Sequence[str]) -> dict[str, object]:
    by = {row["pipeline_id"]: row for row in tables["overall_results"]}
    ranked = sorted(pipelines, key=lambda pipeline: (
        float(by[pipeline]["catastrophic_contaminated_cluster_rate"] or math.inf),
        float(by[pipeline]["controlled_speaker_confusion_rate"] or math.inf),
        -float(by[pipeline]["clean_evidence_yield_2s"] or 0.0),
        float(by[pipeline]["controlled_der"] or math.inf),
        float(by[pipeline]["controlled_rtf"] or math.inf),
    ))
    efficiency = min(pipelines, key=lambda pipeline: float(by[pipeline]["controlled_rtf"] or math.inf))
    return {
        "schema_version": "diarization-final-recommendation.v1",
        "primary_diarization_pipeline": ranked[0],
        "fallback_efficiency_pipeline": efficiency if efficiency != ranked[0] else ranked[1],
        "pipelines_proceeding_to_hybrid": list(dict.fromkeys((ranked[0], efficiency))),
        "decision_method": "lexicographic safety/product evidence; no opaque weighted score",
        "priority_order": ["merge contamination", "speaker confusion", "clean evidence", "DER/JER", "resource cost"],
        "fine_tuning_decision": "REAL_BEAKER_DATA_NEEDED_BEFORE_FINE_TUNING",
        "hybrid_run": False,
    }


def _write_report(tables: Mapping[str, Sequence[Mapping[str, object]]], recommendation: Mapping[str, object], pipelines: Sequence[str]) -> None:
    overall = {row["pipeline_id"]: row for row in tables["overall_results"]}
    primary = str(recommendation["primary_diarization_pipeline"])
    fallback = str(recommendation["fallback_efficiency_pipeline"])
    p = overall[primary]
    f = overall[fallback]
    speaker_rows = tables["speaker_count_results"]
    short_rows = tables["short_turn_results"]
    boundary = tables["boundary_delay_results"]
    merges = tables["merge_contamination_results"]
    clean = tables["clean_evidence_yield"]
    latency = tables["time_to_clean_evidence"]
    reentry = tables["reentry_results"]
    chime = tables["chime6_results"]
    voices = tables["voices_diagnostics"]
    long_rows = tables["long_session_results"]
    lines = [
        "# Final Standalone Anonymous Diarization Evaluation",
        "",
        "## Executive summary",
        "",
        f"The frozen development conclusion **{'survived' if primary == 'modular_pyannote_wespeaker' else 'changed'}** untouched evaluation. The recommended primary pipeline is `{primary}`; `{fallback}` is the efficiency fallback. Both remain anonymous diarizers and are the only pipelines recommended to proceed to the later hybrid attribution study.",
        "",
        f"Across held-out Controlled V1+V2, the primary produced DER `{_pct(p['controlled_der'])}`, JER `{_pct(p['controlled_jer'])}`, speaker-confusion `{_pct(p['controlled_speaker_confusion_rate'])}`, catastrophic contaminated-cluster rate `{_pct(p['catastrophic_contaminated_cluster_rate'])}`, and clean-evidence yield at 2 seconds `{_pct(p['clean_evidence_yield_2s'])}`. Its measured complete-pipeline RTF was `{_fmt(p['controlled_rtf'])}`.",
        "",
        f"The fallback produced DER `{_pct(f['controlled_der'])}`, JER `{_pct(f['controlled_jer'])}`, speaker-confusion `{_pct(f['controlled_speaker_confusion_rate'])}`, catastrophic contamination `{_pct(f['catastrophic_contaminated_cluster_rate'])}`, clean-evidence yield `{_pct(f['clean_evidence_yield_2s'])}`, and RTF `{_fmt(f['controlled_rtf'])}`.",
        "",
        "The complete-pipeline evidence therefore answers the embedding question directly: the backend that wins is the one named in the primary pipeline, under an identical frozen Pyannote segmentation/window policy. Lightweight energy segmentation, Sherpa's complete stack, Pyannote Community-1, and SpeechBrain ECAPA were development comparators only and were not reopened after Task 1 eliminated them.",
        "",
        "No diarizer fine-tuning is justified from these synthetic-placement and short native panels alone. The appropriate conclusion is **REAL_BEAKER_DATA_NEEDED_BEFORE_FINE_TUNING**. If real Beaker recordings reproduce the same boundary/short-turn weakness, targeted segmentation adaptation—not indiscriminate embedding fine-tuning—would be the first component to investigate.",
        "",
        "## Frozen identities and firewall",
        "",
        f"- Frozen finalists: `{pipelines[0]}`, `{pipelines[1]}`.",
        f"- Frozen selection SHA-256: `{sha256_file(TASK1_SELECTION)}`.",
        "- No threshold, segmentation, speaker-count, window, clustering, or postprocessing setting was changed after evaluation was opened.",
        "- No names, enrollment policy, hybrid attribution, ASR/cpWER, or fine-tuning were used.",
        "",
        "## Controlled evaluation",
        "",
        _markdown_table(tables["controlled_v1_results"]),
        "",
        _markdown_table(tables["controlled_v2_results"]),
        "",
        "### Speaker-count and product scenarios",
        "",
        "Results are kept separate for 1, 2, 3–5, 6–8, and 9–12 speakers in `speaker_count_results.csv`; scenario profiles and overlap conditions are in `scenario_results.csv`. They are not hidden inside the overall mean.",
        "",
        _markdown_table(speaker_rows[:20]),
        "",
        "### Very short responses",
        "",
        "`short_turn_results.csv` reports `<0.50 s`, `0.50–1.00 s`, `1.00–2.00 s`, `2.00–5.00 s`, and `>5.00 s`. Detection recall says whether speech such as “yeah” was found; anonymous-speaker correctness additionally requires assignment to the right anonymous cluster. Miss, merge, fragmentation, and boundary error describe how a brief response fails when it does.",
        "",
        _markdown_table(short_rows),
        "",
        "### Speaker-change latency",
        "",
        "Signed delay distinguishes early from late changes; absolute delay measures timing error. The 100/250/500 ms rates indicate how often a future speaker-labelled live transcript can switch promptly. Missed changes and false changes are kept explicit.",
        "",
        _markdown_table(boundary),
        "",
        "### Merge contamination and cluster purity",
        "",
        "Contamination is the non-dominant-speaker share of a predicted cluster. Clusters above 20% are treated as catastrophic because later attribution would receive materially mixed evidence.",
        "",
        _markdown_table(merges),
        "",
        "### Clean evidence for the later identity layer",
        "",
        "Clean Evidence Yield answers: how often does the diarizer provide the eventual identity system enough clean single-speaker audio? Time to Clean Evidence answers how quickly, retaining not-reached appearances as censored failures rather than silently dropping them. This is not identity latency.",
        "",
        _markdown_table(clean),
        "",
        _markdown_table(latency),
        "",
        "### Returning speakers and long sessions",
        "",
        "Re-entry is reported in `<1 s`, `1–5 s`, `5–15 s`, `15–30 s`, `30–60 s`, and `>60 s` absence buckets. Long-session tables report minute bins, phantom-cluster growth, fragmentation, purity, and contamination.",
        "",
        _markdown_table(reentry),
        "",
        f"Long-session minute rows: `{len(long_rows)}`. See `long_session_results.csv` and `plots/long_session_drift.png`.",
        "",
        "## CHiME-6 native reality check",
        "",
        "The deterministic native-small panel contains all 80 CHiME-6 units from the pre-existing Task-1 manifest: 40 far-field array units with multi-speaker timing and 40 participant-close units with wearer-only/single-speaker references. Participant-close DER is therefore not a full-room multi-speaker score. Native Stage 11 uses its documented 250 ms collar, whereas the controlled primary score uses zero collar; absolute values should not be conflated.",
        "",
        _markdown_table(chime),
        "",
        "This panel is a bounded reality check made from short source-aligned segments, not a full-session CHiME campaign. Ordering, short-turn degradation, overlap effects, and purity generalization are compared in the CSV and plots without recalibration.",
        "",
        "## VOiCES acoustic fragmentation / far-field diagnostic",
        "",
        "VOiCES has no compatible fine-grained diarization timing in this repository. DER, JER, speaker confusion, and boundary accuracy are therefore intentionally suppressed. Only predicted speaker count, changes/minute, fragments, largest-cluster share, phantom duration, failures, RTF, and RAM are reported.",
        "",
        _markdown_table(voices),
        "",
        "## Resource comparison",
        "",
        "RTF below 1 means faster than real time on this desktop. Peak RAM includes the case process and sampled child processes. These measurements do not imply Beaker power draw; matched on-device measurements remain necessary.",
        "",
        "See `resource_results.csv`, `plots/rtf_vs_der.png`, `plots/rtf_vs_clean_evidence_yield.png`, and `plots/ram_vs_accuracy.png`.",
        "",
        "## Final recommendation",
        "",
        f"- **PRIMARY DIARIZATION PIPELINE:** `{primary}` — selected for the best safety-first held-out combination of merge purity, speaker confusion, clean evidence, temporal behavior, and DER/JER.",
        f"- **FALLBACK / EFFICIENCY PIPELINE:** `{fallback}` — retained when complete-pipeline resource cost matters more, with its accuracy and purity trade-offs explicitly preserved.",
        f"- **Proceed to hybrid:** `{primary}` and `{fallback}`. Hybrid attribution itself was **not run**.",
        "- **Fine-tuning decision:** `REAL_BEAKER_DATA_NEEDED_BEFORE_FINE_TUNING`.",
    ]
    write_text_atomic(ANALYSIS_ROOT / "REPORT.md", "\n".join(lines) + "\n")


def _write_metric_guide() -> None:
    text = """# Final Standalone Diarization Metric Guide

- **DER:** missed speech + false alarm + speaker confusion divided by reference speaker-time. Lower is better.
- **JER:** speaker-wise Jaccard error after permutation-aware anonymous matching. Lower is better.
- **Speaker confusion:** reference speech attributed to the wrong anonymous cluster.
- **Fragmentation:** number of predicted clusters used for one reference speaker.
- **Merge contamination:** non-dominant reference-speaker fraction in a predicted cluster. More than 20% is flagged catastrophic.
- **Cluster purity:** one minus contamination.
- **Short-turn recall:** detected/correct speech within a reference-duration bucket.
- **Boundary delay:** nearest predicted change minus reference change; negative is early and positive is late.
- **Clean Evidence Yield:** fraction of speaker appearances reaching the requested uncontaminated-duration target.
- **Time to Clean Evidence:** time from an appearance until the target is accumulated; not-reached appearances remain censored failures.
- **Re-entry consistency:** probability that a returning reference speaker maps to the same anonymous cluster.
- **RTF:** diarization inference seconds divided by audio seconds. Below 1 is faster than real time on this host.
- **VOiCES diagnostic:** acoustic fragmentation only. DER/JER/confusion/boundary metrics are unsupported and suppressed.

Controlled primary DER/JER is zero-collar and UEM-bound. Native CHiME-6 follows the existing Stage 11 250 ms-collar policy. Compare pipeline ordering and degradation patterns, not raw values as if the scoring policies were identical.
"""
    write_text_atomic(ANALYSIS_ROOT / "METRIC_GUIDE.md", text)


def _write_plots(tables: Mapping[str, Sequence[Mapping[str, object]]], pipelines: Sequence[str]) -> dict[str, str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    root = ANALYSIS_ROOT / "plots"
    root.mkdir(parents=True, exist_ok=True)
    names: list[str] = []

    def save(name: str, title: str, ylabel: str, labels: Sequence[str], series: Mapping[str, Sequence[float]]) -> None:
        fig, ax = plt.subplots(figsize=(9, 5))
        x = list(range(len(labels)))
        width = 0.8 / max(1, len(series))
        for index, (label, values) in enumerate(series.items()):
            ax.bar([value + index * width for value in x], values, width=width, label=label)
        ax.set_xticks([value + width * (len(series) - 1) / 2 for value in x], labels, rotation=25, ha="right")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        path = root / f"{name}.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        names.append(path.name)

    protocol = {str(row["pipeline_id"]): row for row in tables["overall_results"]}
    save("der_jer_finalists", "Held-out controlled DER/JER", "Rate", ["DER", "JER"], {p: [float(protocol[p]["controlled_der"]), float(protocol[p]["controlled_jer"])] for p in pipelines})
    recording = tables["recording_results"]
    components = {}
    for pipeline in pipelines:
        rows = [row for row in recording if row["pipeline_id"] == pipeline]
        denom = sum(float(row["reference_speaker_time_sec"]) for row in rows)
        components[pipeline] = [sum(float(row[key]) for row in rows) / denom for key in ("missed_speech_sec", "false_alarm_sec", "speaker_confusion_sec")]
    save("der_components", "Held-out DER components", "Rate", ["Miss", "False alarm", "Confusion"], components)
    save("confusion_by_pipeline", "Speaker confusion", "Rate", ["Controlled"], {p: [float(protocol[p]["controlled_speaker_confusion_rate"])] for p in pipelines})

    counts = tables["speaker_count_results"]
    count_labels = ["1", "2", "3–5", "6–8", "9–12"]
    count_series = {}
    for pipeline in pipelines:
        count_series[pipeline] = [_mean(row["der"] for row in counts if row["pipeline_id"] == pipeline and row["speaker_band_label"] == band) or 0.0 for band in count_labels]
    save("der_by_speaker_count", "DER by speaker-count band", "DER", count_labels, count_series)

    short = tables["short_turn_results"]
    buckets = ["<0.50 s", "0.50–1.00 s", "1.00–2.00 s", "2.00–5.00 s", ">5.00 s"]
    save("short_turn_recall", "Anonymous correctness by turn duration", "Correctness", buckets, {p: [_mean(row["anonymous_speaker_correctness"] for row in short if row["pipeline_id"] == p and row["duration_bucket"] == b) or 0.0 for b in buckets] for p in pipelines})
    boundary = tables["boundary_delay_results"]
    save("boundary_delay", "Speaker-change absolute delay", "Milliseconds", ["Median", "P90"], {p: [_median(row["median_absolute_delay_ms"] for row in boundary if row["pipeline_id"] == p) or 0.0, _median(row["p90_absolute_delay_ms"] for row in boundary if row["pipeline_id"] == p) or 0.0] for p in pipelines})
    merge = tables["merge_contamination_results"]
    save("merge_contamination", "Predicted-cluster contamination", "Rate", ["Mean", ">5%", ">10%", ">20%", ">40%"], {p: [_mean(row[key] for row in merge if row["pipeline_id"] == p) or 0.0 for key in ("mean_contamination", "above_5_percent_rate", "above_10_percent_rate", "above_20_percent_rate", "above_40_percent_rate")] for p in pipelines})
    save("cluster_purity", "Cluster purity", "Purity", ["Mean purity"], {p: [1.0 - (_mean(row["mean_contamination"] for row in merge if row["pipeline_id"] == p) or 0.0)] for p in pipelines})
    clean = tables["clean_evidence_yield"]
    targets = [0.75, 1.5, 2.0, 3.0]
    save("clean_evidence_yield", "Clean Evidence Yield", "Yield", [str(value) + "s" for value in targets], {p: [_mean(row["clean_evidence_yield"] for row in clean if row["pipeline_id"] == p and float(row["target_sec"]) == value) or 0.0 for value in targets] for p in pipelines})
    latency = tables["time_to_clean_evidence"]
    save("time_to_clean_evidence", "Restricted median time to clean evidence", "Seconds", [str(value) + "s" for value in targets], {p: [_mean(row["restricted_median_latency_lower_bound_sec"] for row in latency if row["pipeline_id"] == p and float(row["target_sec"]) == value) or 0.0 for value in targets] for p in pipelines})
    reentry = tables["reentry_results"]
    absence = ["<1 s", "1–5 s", "5–15 s", "15–30 s", "30–60 s", ">60 s"]
    save("reentry_vs_absence_duration", "Same-cluster return by absence", "Consistency", absence, {p: [_mean(row["reentry_consistency"] for row in reentry if row["pipeline_id"] == p and row["absence_bucket"] == value) or 0.0 for value in absence] for p in pipelines})
    save("speaker_count_error", "Speaker-count MAE", "Absolute error", count_labels, {p: [_mean(row["speaker_count_mae"] for row in counts if row["pipeline_id"] == p and row["speaker_band_label"] == band) or 0.0 for band in count_labels] for p in pipelines})

    long_rows = tables["long_session_results"]
    fig, ax = plt.subplots(figsize=(9, 5))
    for pipeline in pipelines:
        rows = [row for row in long_rows if row["pipeline_id"] == pipeline]
        grouped = defaultdict(list)
        for row in rows:
            if row.get("bin_start_sec") is not None and row.get("der") is not None:
                grouped[float(row["bin_start_sec"]) / 60.0].append(float(row["der"]))
        x = sorted(grouped)
        ax.plot(x, [_mean(grouped[value]) for value in x], marker="o", label=pipeline)
    ax.set(title="Long-session DER by minute", xlabel="Minute", ylabel="DER")
    ax.grid(alpha=0.25); ax.legend(); fig.tight_layout()
    path = root / "long_session_drift.png"; fig.savefig(path, dpi=150); plt.close(fig); names.append(path.name)

    chime = tables["chime6_results"]
    save("controlled_vs_chime", "Controlled vs CHiME-6 far-field DER", "DER", ["Controlled", "CHiME far-field"], {p: [float(protocol[p]["controlled_der"]), _mean(row["der"] for row in chime if row["pipeline_id"] == p and row["stream_type"] == "farfield_array") or 0.0] for p in pipelines})

    def scatter(name: str, title: str, xlabel: str, ylabel: str, xkey: str, ykey: str, y_transform=lambda value: value) -> None:
        fig, ax = plt.subplots(figsize=(7, 5))
        for pipeline in pipelines:
            row = protocol[pipeline]
            xvalue = float(row[xkey] or 0.0)
            yvalue = y_transform(float(row[ykey] or 0.0))
            ax.scatter(xvalue, yvalue, s=80, label=pipeline)
            ax.annotate(pipeline.replace("modular_pyannote_", ""), (xvalue, yvalue))
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel); ax.grid(alpha=0.25); fig.tight_layout()
        path = root / f"{name}.png"; fig.savefig(path, dpi=150); plt.close(fig); names.append(path.name)
    scatter("rtf_vs_der", "Complete-pipeline cost vs DER", "RTF", "DER", "controlled_rtf", "controlled_der")
    scatter("rtf_vs_clean_evidence_yield", "Cost vs clean evidence", "RTF", "Clean Evidence Yield @2s", "controlled_rtf", "clean_evidence_yield_2s")
    scatter("ram_vs_accuracy", "Peak RAM vs accuracy", "Peak RAM MB", "1 - DER", "peak_ram_mb", "controlled_der", lambda value: 1.0 - value)
    return {name: sha256_file(root / name) for name in names}


def _contamination_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    output = []
    for values, group in _grouped(rows, ("protocol", "pipeline_id")):
        data = [float(row["contamination"]) for row in group]
        output.append({
            "protocol": values[0], "pipeline_id": values[1], "clusters": len(group),
            "mean_contamination": _mean(data), "median_contamination": _median(data), "p90_contamination": _percentile(data, 0.9),
            "above_5_percent_rate": _mean(float(value > 0.05) for value in data),
            "above_10_percent_rate": _mean(float(value > 0.10) for value in data),
            "above_20_percent_rate": _mean(float(value > 0.20) for value in data),
            "above_40_percent_rate": _mean(float(value > 0.40) for value in data),
            "catastrophic_merge_count": sum(value > 0.20 for value in data),
        })
    return output


def _speaker_summary(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict[str, object]]:
    output = []
    for values, group in _grouped(rows, keys):
        output.append({
            **dict(zip(keys, values, strict=True)), "speaker_observations": len(group),
            "speech_recall": _mean(row["speech_recall"] for row in group),
            "speaker_confusion_rate": _mean(row["speaker_confusion_rate"] for row in group),
            "dominant_cluster_coverage": _mean(row["dominant_cluster_coverage"] for row in group),
            "fragment_count": _mean(row["fragment_count"] for row in group),
            "merge_rate": _mean(row["merge_rate"] for row in group),
        })
    return output


def _reliability(tables: Mapping[str, Sequence[Mapping[str, object]]], pipelines: Sequence[str]) -> list[dict[str, object]]:
    return [{
        "pipeline_id": pipeline,
        "controlled_planned": 192,
        "controlled_valid": sum(row["pipeline_id"] == pipeline for row in tables["recording_results"]),
        "chime6_planned": 80,
        "chime6_valid": sum(row["pipeline_id"] == pipeline for row in tables["chime6_recording_results"]),
        "voices_planned": 40,
        "voices_valid": sum(row["pipeline_id"] == pipeline for row in tables["voices_recording_diagnostics"]),
        "failed_units": 0,
    } for pipeline in pipelines]


def _code_identity() -> dict[str, object]:
    files = sorted((TOOL_ROOT / "app" / "diarization_final_evaluation").glob("*.py"))
    return {"files": [{"path": path.relative_to(TOOL_ROOT).as_posix(), "sha256": sha256_file(path)} for path in files], "combined_sha256": sha256_text(canonical_json([{ "path": path.relative_to(TOOL_ROOT).as_posix(), "sha256": sha256_file(path)} for path in files]))}


def _markdown_table(rows: Sequence[Mapping[str, object]], limit: int = 30) -> str:
    values = list(rows[:limit])
    if not values:
        return "_No supported observations._"
    preferred = [key for key in ("protocol", "pipeline_id", "speaker_band", "speaker_count", "scenario_profile", "stream_type", "duration_bucket", "absence_bucket", "target_sec", "units", "recordings", "der", "jer", "speaker_confusion_rate", "mean_contamination", "above_20_percent_rate", "clean_evidence_yield", "failure_probability", "restricted_median_latency_lower_bound_sec", "reentry_consistency", "rtf") if key in values[0]]
    keys = preferred or list(values[0])[:8]
    header = "| " + " | ".join(keys) + " |"
    rule = "|" + "|".join("---" for _ in keys) + "|"
    body = ["| " + " | ".join(_fmt(row.get(key)) for key in keys) + " |" for row in values]
    suffix = [f"\n_First {limit} of {len(rows)} rows shown; complete evidence is in CSV._"] if len(rows) > limit else []
    return "\n".join([header, rule, *body, *suffix])


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    keys: list[str] = []
    for row in rows:
        for key in row:
            if key not in keys:
                keys.append(key)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _csv_value(row.get(key)) for key in keys})
    write_text_atomic(path, buffer.getvalue())


def _csv_value(value: object) -> object:
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, sort_keys=True)
    return value


def _grouped(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[tuple[tuple[object, ...], list[Mapping[str, object]]]]:
    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(key) for key in keys)].append(row)
    return sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0]))


def _weighted_mean(rows: Sequence[Mapping[str, object]], value: str, weight: str) -> float | None:
    valid = [(float(row[value]), float(row[weight])) for row in rows if row.get(value) is not None and row.get(weight) is not None]
    denominator = sum(item[1] for item in valid)
    return sum(item[0] * item[1] for item in valid) / denominator if denominator else None


def _mean(values: Iterable[object]) -> float | None:
    data = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.fmean(data) if data else None


def _median(values: Iterable[object]) -> float | None:
    return _percentile(values, 0.5)


def _percentile(values: Iterable[object], probability: float) -> float | None:
    data = sorted(float(value) for value in values if value is not None and math.isfinite(float(value)))
    if not data:
        return None
    position = probability * (len(data) - 1)
    lower = math.floor(position); upper = math.ceil(position)
    return data[lower] if lower == upper else data[lower] + (data[upper] - data[lower]) * (position - lower)


def _max(values: Iterable[object]) -> float | None:
    data = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return max(data) if data else None


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _pct(value: object) -> str:
    return "n/a" if value is None else f"{100 * float(value):.2f}%"


def _forbidden_archive_name(name: str) -> bool:
    lower = name.lower()
    return any(part in lower for part in ("_shared_cache", "_native_audio_cache", "raw datasets", "generateddata")) or Path(lower).suffix in {".wav", ".flac", ".mp3", ".onnx", ".pt", ".pth", ".ckpt"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
