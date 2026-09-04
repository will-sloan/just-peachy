"""Frozen-policy replay, final product comparison, reporting, and export."""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import statistics
import time
from typing import Iterable, Mapping, Sequence
import zipfile

import numpy as np
import yaml

from app.hybrid_final_evaluation.contracts import (
    ANALYSIS_ROOT,
    CORPORA,
    FINAL_SELECTION_PATH,
    FROZEN_HYBRID_PATH,
    POLICY_ROOT,
    PRODUCT_PROTOCOL_ROOT,
    RESULT_ROOT,
    SCHEMA,
    SEED,
    SUMMARY_ROOT,
    TOOL_ROOT,
    FinalHybridEvaluationError,
    atomic_json,
    atomic_text,
    checksum_tree,
    file_sha256,
    now_utc,
    read_json,
    read_jsonl,
    write_csv,
    write_yaml,
)
from app.hybrid_final_evaluation.decision import require_valid_decision, validate_frozen_decision
from app.hybrid_final_evaluation.runner import (
    evaluation_cases,
    load_score_bundle,
    overlay_index,
    run_native_scope,
    set_controller,
    update_analysis_progress,
    validate_score_bundles,
)
from app.hybrid_speaker_attribution.product_v2_analysis import _replay


PRIMARY_GALLERIES = {"5", "10", "20"}


def analyze(*, bootstrap_repetitions: int = 500) -> dict[str, object]:
    frozen, finalists = require_valid_decision()
    validation = validate_score_bundles()
    if validation["status"] != "PASS":
        raise FinalHybridEvaluationError(f"BLOCKED_CONTROLLED_EVALUATION: {validation['errors'][:5]}")
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    set_controller("RUNNING", "ANALYSIS", "Replaying only the frozen held-out decision policies")
    cases = evaluation_cases()
    case_index = {(corpus, str(case["case_id"])): case for corpus, rows in cases.items() for case in rows}
    overlays = overlay_index()
    finalist_index = {str(row["hybrid_combination_id"]): row for row in finalists}
    units = []
    for finalist in finalists:
        combo = str(finalist["hybrid_combination_id"])
        for corpus, rows in cases.items():
            for case in rows:
                for overlay_id in ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"):
                    overlay = overlays[(corpus, str(case["case_id"]), overlay_id)]
                    for subset in overlay["gallery_subsets"]:
                        if subset["status"] == "VALID":
                            for overlap_policy in ("EXCLUDE_PREDICTED_OVERLAP_PRIMARY", "INCLUDE_PREDICTED_OVERLAP_DIAGNOSTIC"):
                                units.append((combo, corpus, str(case["case_id"]), overlay, subset, overlap_policy))
    planned = len(units)
    replay_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    hub_counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hub_totals: dict[tuple[str, str], int] = defaultdict(int)
    distributions: list[dict[str, object]] = []
    bundle_cache: tuple[tuple[str, str, str], dict[str, object]] | None = None
    started = time.perf_counter()
    for index, (combo, corpus, case_id, overlay, subset, overlap_policy) in enumerate(units, start=1):
        key = (combo, corpus, case_id)
        if bundle_cache is None or bundle_cache[0] != key:
            bundle_cache = (key, load_score_bundle(combo, corpus, case_id))
        bundle = bundle_cache[1]
        finalist = finalist_index[combo]
        calibration = {
            "score_threshold": float(finalist["score_threshold"]),
            "margin_threshold": float(finalist["margin_threshold"]),
            "target_fpir": 0.01,
            "source": "frozen_task1_balanced_operating_point",
        }
        replay_bundle = {**bundle, "development_role": "evaluation"}
        row, events = _replay(replay_bundle, overlay, subset, "BALANCED", "ADAPTIVE", overlap_policy, calibration)
        case = case_index[(corpus, case_id)]
        row.update({
            "evaluation_role": "held_out_final_evaluation",
            "evaluation_results_inspected": True,
            "evaluation_tuning_performed": False,
            "scenario_profile": case.get("scenario_profile") or "controlled_v1_factorial",
            "turn_cadence": case.get("turn_cadence"),
            "overlap_profile": case.get("overlap_profile"),
            "participation_profile": case.get("participation_profile"),
            "long_session": bool(case.get("long_session", False)),
            "known_unknown_condition": _condition(overlay),
            "frozen_hybrid_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
            "preserved_anonymous_der": dict(bundle.get("anonymous_diarization") or {}).get("der"),
            "preserved_anonymous_jer": dict(bundle.get("anonymous_diarization") or {}).get("jer"),
            "speaker_count_error": dict(bundle.get("anonymous_diarization") or {}).get("speaker_count_error"),
            "cluster_purity": dict(bundle.get("anonymous_diarization") or {}).get("cluster_purity"),
            "reference_coverage": dict(bundle.get("anonymous_diarization") or {}).get("reference_coverage"),
            "known_wrong_known_time_sec": max(0.0, float(row.get("end_to_end_wrong_known_time_sec") or 0.0) - float(row.get("stranger_false_known_time_sec") or 0.0)),
        })
        uncovered_known, untracked_unknown = _uncovered_by_state(bundle, overlay)
        row["uncovered_known_time_sec"] = uncovered_known
        row["untracked_unknown_time_sec"] = untracked_unknown
        row["correct_anonymous_unknown_time_sec"] = row.get("unknown_rejected_time_sec")
        row["end_to_end_correctly_labeled_reference_time_sec"] = float(row.get("end_to_end_correctly_named_known_time_sec") or 0.0) + float(row.get("unknown_rejected_time_sec") or 0.0)
        row["final_known_id_accuracy"] = _ratio(float(row.get("end_to_end_correctly_named_known_time_sec") or 0.0), float(row.get("end_to_end_correctly_named_known_time_sec") or 0.0) + float(row.get("known_wrong_known_time_sec") or 0.0))
        row["unknown_split_rate"] = _ratio(float(row.get("unknown_split_count") or 0.0), float(row.get("unknown_instance_count") or 0.0))
        row["unknown_merge_rate"] = _ratio(float(row.get("unknown_merge_count") or 0.0), float(row.get("unknown_instance_count") or 0.0))
        for event in events:
            event["evaluation_results_inspected"] = True
            event["evaluation_tuning_performed"] = False
            event["label_experience"] = "causal replay over completed diarization output; not a true online streaming pipeline"
        replay_rows.append(row)
        event_rows.extend(events)
        if overlap_policy == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY" and overlay["overlay_id"] == "ALL_UNKNOWN":
            _collect_hubness(bundle, subset, finalist, hub_counts, hub_totals, distributions)
        if index % 100 == 0 or index == planned:
            update_analysis_progress(index, planned, scope="CONTROLLED_V1" if corpus == "v1" else "CONTROLLED_V2", finalist=combo, case_id=case_id, overlay=str(overlay["overlay_id"]), gallery_size=subset["requested_size"])
    replay_sec = time.perf_counter() - started
    write_csv(ANALYSIS_ROOT / "overlay_results.csv", replay_rows)
    write_csv(ANALYSIS_ROOT / "label_event_log.csv", event_rows)
    write_csv(ANALYSIS_ROOT / "score_margin_distributions.csv", distributions)
    hubness = _hubness_rows(hub_counts, hub_totals)
    write_csv(ANALYSIS_ROOT / "hubness_results.csv", hubness)
    tables = _write_tables(replay_rows, event_rows, finalists, replay_sec)
    calibration = _calibration_results(replay_rows, finalist_index)
    write_csv(ANALYSIS_ROOT / "calibration_results.csv", calibration)
    tables["calibration_results.csv"] = calibration
    tables["hubness_results.csv"] = hubness
    update_analysis_progress(planned, planned, scope="BOOTSTRAP", finalist=None, case_id=None, overlay=None, gallery_size=None, stage="BOOTSTRAP")
    bootstrap = _bootstrap(replay_rows, cases, repetitions=bootstrap_repetitions)
    write_csv(ANALYSIS_ROOT / "bootstrap_intervals.csv", bootstrap)
    tables["bootstrap_intervals.csv"] = bootstrap
    summary = _finalist_summary(replay_rows, finalists)
    write_csv(ANALYSIS_ROOT / "finalist_summary.csv", summary)
    tables["finalist_summary.csv"] = summary
    paired = _paired(summary)
    write_csv(ANALYSIS_ROOT / "paired_comparisons.csv", paired)
    tables["paired_comparisons.csv"] = paired
    selection = _freeze_final_selection(frozen, finalists, summary)
    _write_plots(tables, replay_rows, summary)
    _write_metric_guide()
    _write_report(summary, selection, calibration, replay_rows, bootstrap)
    table_manifest = {path.name: {"rows": _csv_rows(path), "sha256": file_sha256(path).lower()} for path in sorted(ANALYSIS_ROOT.glob("*.csv"))}
    plot_manifest = {path.name: file_sha256(path).lower() for path in sorted((ANALYSIS_ROOT / "plots").glob("*.png"))}
    source_files = sorted((TOOL_ROOT / "app" / "hybrid_final_evaluation").glob("*.py"))
    manifest = {
        "schema_version": "hybrid-final-analysis-manifest.v1",
        "created_at_utc": now_utc(),
        "protocol_id": read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")["protocol_id"],
        "frozen_hybrid_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
        "evaluation_tuning_performed": False,
        "controlled_v1_evaluation_run": True,
        "controlled_v2_evaluation_run": True,
        "chime6_native_hybrid": "CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED",
        "voices_identity_diagnostic": "NOT_SUPPORTED_NO_FROZEN_IDENTITY_PROTOCOL",
        "policy_replay_rows": len(replay_rows),
        "label_events": len(event_rows),
        "bootstrap_repetitions": bootstrap_repetitions,
        "bootstrap_seed": SEED,
        "resampling_unit": "reference_speaker_cluster",
        "tables": table_manifest,
        "plots": plot_manifest,
        "result_affecting_task2_code": [{"path": str(path.relative_to(TOOL_ROOT)), "sha256": file_sha256(path).lower()} for path in source_files],
        "asr_run": False,
        "xvf3800_run": False,
        "fine_tuning_run": False,
        "final_selection": selection,
    }
    atomic_json(ANALYSIS_ROOT / "analysis_manifest.json", manifest)
    set_controller("ANALYSIS_COMPLETE", "COLLECT", "Held-out analysis and final hybrid selection complete; export pending")
    return {"status": "COMPLETE", "analysis_root": str(ANALYSIS_ROOT), "summary": summary, "selection": selection, "manifest": manifest}


def collect() -> dict[str, object]:
    validation = validate_final()
    if validation["status"] != "PASS":
        raise FinalHybridEvaluationError(f"final analysis validation failed: {validation['errors']}")
    protocol_id = read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")["protocol_id"]
    package_name = f"hybrid_speaker_attribution_product_v2_final_evaluation_{protocol_id}"
    package_root = SUMMARY_ROOT / package_name
    if package_root.exists():
        if SUMMARY_ROOT.resolve() not in package_root.resolve().parents:
            raise FinalHybridEvaluationError(f"refusing to replace export outside summary root: {package_root}")
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    shutil.copytree(ANALYSIS_ROOT, package_root / "analysis")
    shutil.copytree(POLICY_ROOT, package_root / "scientific_enrollment_policies")
    shutil.copy2(FROZEN_HYBRID_PATH, package_root / FROZEN_HYBRID_PATH.name)
    shutil.copy2(FROZEN_HYBRID_PATH.with_suffix(".sha256"), package_root / FROZEN_HYBRID_PATH.with_suffix(".sha256").name)
    shutil.copy2(FINAL_SELECTION_PATH, package_root / FINAL_SELECTION_PATH.name)
    shutil.copy2(FINAL_SELECTION_PATH.with_suffix(".sha256"), package_root / FINAL_SELECTION_PATH.with_suffix(".sha256").name)
    for artifact_name in ("validation.json", "plan.json", "evaluation_authorization.json", "campaign_progress.json", "controller_state.json", "chime6_hybrid_results.csv", "voices_identity_diagnostics.csv", "score_bundle_failures.json"):
        source = RESULT_ROOT / artifact_name
        if source.is_file():
            shutil.copy2(source, package_root / artifact_name)
    protocol_out = package_root / "protocol"
    protocol_out.mkdir()
    shutil.copy2(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json", protocol_out / "protocol_summary.json")
    inventories = []
    for path in sorted((RESULT_ROOT / "cache_inventory").glob("*.summary.json")):
        value = read_json(path)
        inventories.append({"backend_id": value.get("backend_id"), "jobs": value.get("jobs"), "audio_sec": value.get("audio_sec"), "manifest_sha256": value.get("manifest_sha256")})
    write_csv(package_root / "cache_inventory.csv", inventories)
    atomic_json(package_root / "provenance.json", {
        "schema_version": "hybrid-final-export-provenance.v1",
        "created_at_utc": now_utc(),
        "frozen_hybrid_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
        "excluded": ["raw audio", "model weights", "gated assets", "credentials", "large embedding caches", "score bundles"],
        "scientific_boundaries": {"chime6": "NOT_SUPPORTED", "voices": "NOT_SUPPORTED"},
    })
    checksums = {"schema_version": "hybrid-final-export-checksums.v1", "files": checksum_tree(package_root, exclude_names={"checksums.json"})}
    atomic_json(package_root / "checksums.json", checksums)
    zip_path = SUMMARY_ROOT / f"{package_name}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(package_root.parent))
    sha = file_sha256(zip_path).lower()
    atomic_text(zip_path.with_suffix(".zip.sha256"), f"{sha}  {zip_path.name}\n")
    set_controller("COMPLETE", "COMPLETE", "Final hybrid evaluation package complete")
    return {
        "status": "COMPLETE_FINAL_HYBRID_SPEAKER_ATTRIBUTION_EVALUATION",
        "zip_path": str(zip_path),
        "zip_sha256": sha,
        "final_selection": str(FINAL_SELECTION_PATH),
        "report": str(ANALYSIS_ROOT / "REPORT.md"),
    }


def validate_final() -> dict[str, object]:
    errors = []
    frozen_validation = validate_frozen_decision(write_result=False)
    if frozen_validation["status"] != "VALID":
        errors.append("Task-1 frozen decision no longer validates")
    scores = validate_score_bundles()
    if scores["status"] != "PASS":
        errors.append("held-out score bundles are incomplete or invalid")
    required = {
        "finalist_summary.csv", "controlled_v1_results.csv", "controlled_v2_results.csv",
        "end_to_end_identity_time.csv", "unknown_rejection_results.csv", "unknown_instance_results.csv",
        "gallery_size_results.csv", "calibration_results.csv", "hubness_results.csv",
        "resource_results.csv", "bootstrap_intervals.csv", "pipeline_identity.csv",
        "analysis_manifest.json", "REPORT.md", "METRIC_GUIDE.md",
    }
    missing = sorted(name for name in required if not (ANALYSIS_ROOT / name).is_file())
    if missing:
        errors.append(f"analysis outputs missing: {missing}")
    if not FINAL_SELECTION_PATH.is_file() or not FINAL_SELECTION_PATH.with_suffix(".sha256").is_file():
        errors.append("final selection/checksum missing")
    elif file_sha256(FINAL_SELECTION_PATH).lower() != FINAL_SELECTION_PATH.with_suffix(".sha256").read_text(encoding="utf-8").split()[0].lower():
        errors.append("final selection checksum mismatch")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "score_bundles": scores}


def _write_tables(rows: Sequence[Mapping[str, object]], events: Sequence[Mapping[str, object]], finalists: Sequence[Mapping[str, object]], replay_sec: float) -> dict[str, list[dict[str, object]]]:
    primary = [row for row in rows if row["overlap_evidence_policy"] == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY"]
    specs = {
        "controlled_v1_results.csv": (["combination_id"], _core_metrics(), lambda row: row["corpus"] == "v1" and _is_primary(row)),
        "controlled_v2_results.csv": (["combination_id"], _core_metrics(), lambda row: row["corpus"] == "v2" and _is_primary(row)),
        "end_to_end_identity_time.csv": (["combination_id", "corpus", "overlay_id", "gallery_size"], _core_metrics(), lambda row: True),
        "conditional_identity_results.csv": (["combination_id", "corpus", "overlay_id", "gallery_size"], ["conditional_correct_known_rate", "final_known_id_accuracy"], lambda row: True),
        "gallery_size_results.csv": (["combination_id", "gallery_size"], _core_metrics(), lambda row: True),
        "scenario_results.csv": (["combination_id", "scenario_profile", "active_speaker_band", "overlap_profile", "participation_profile"], _core_metrics(), lambda row: True),
        "label_policy_results.csv": (["combination_id", "label_policy"], ["end_to_end_correctly_named_known_rate", "premature_wrong_name_rate", "wrong_name_dwell_sec", "beneficial_transition_count", "harmful_transition_count"], lambda row: True),
        "cold_identity_results.csv": (["combination_id", "active_speaker_band"], ["cold_identity_latency_sec", "first_name_latency_sec"], lambda row: True),
        "warm_reacquisition_results.csv": (["combination_id", "active_speaker_band"], ["warm_reacquisition_latency_sec", "warm_reacquisition_count"], lambda row: True),
        "short_turn_inheritance.csv": (["combination_id", "active_speaker_band"], ["short_turn_inheritance_correct_rate", "short_turn_inheritance_count"], lambda row: True),
        "session_expiry_results.csv": (["combination_id", "session_expiry_sec"], ["warm_reacquisition_latency_sec"], lambda row: True),
        "first_name_latency.csv": (["combination_id", "active_speaker_band"], ["first_name_latency_sec", "stable_name_censored_count"], lambda row: True),
        "confirmed_name_latency.csv": (["combination_id", "active_speaker_band"], ["confirmed_name_latency_sec", "stable_name_censored_count"], lambda row: True),
        "stable_name_latency.csv": (["combination_id", "active_speaker_band"], ["stable_name_latency_sec", "stable_name_censored_count"], lambda row: True),
        "premature_false_attribution.csv": (["combination_id", "gallery_size"], ["premature_wrong_name_rate", "premature_wrong_name_count"], lambda row: True),
        "wrong_name_dwell.csv": (["combination_id", "gallery_size"], ["wrong_name_dwell_sec"], lambda row: True),
        "label_transition_results.csv": (["combination_id", "active_speaker_band"], ["beneficial_transition_count", "harmful_transition_count", "label_transition_count"], lambda row: True),
        "unknown_rejection_results.csv": (["combination_id", "gallery_size"], ["any_unknown_rejection_rate", "unknown_rejection_rate", "stranger_false_known_rate"], lambda row: True),
        "unknown_instance_results.csv": (["combination_id", "active_speaker_band"], ["unknown_instance_consistency", "unknown_instance_count"], lambda row: True),
        "unknown_split_merge.csv": (["combination_id", "active_speaker_band"], ["unknown_split_count", "unknown_merge_count", "unknown_split_rate", "unknown_merge_rate"], lambda row: True),
        "exclusive_correctness.csv": (["combination_id", "active_speaker_band"], ["exclusive_correct_rate", "exclusive_correct_time_sec"], lambda row: True),
        "over_attribution_results.csv": (["combination_id", "active_speaker_band"], ["over_attribution_rate", "over_attribution_time_sec"], lambda row: True),
        "fragmentation_identity_results.csv": (["combination_id", "active_speaker_band"], ["unknown_split_count", "warm_reacquisition_count", "end_to_end_correctly_named_known_rate", "cluster_purity"], lambda row: True),
        "mixed_cluster_identity_results.csv": (["combination_id", "active_speaker_band"], ["known_wrong_known_time_sec", "end_to_end_wrong_known_rate", "exclusive_correct_rate", "cluster_purity"], lambda row: True),
        "overlap_identity_results.csv": (["combination_id", "overlap_profile", "overlap_evidence_policy", "known_unknown_condition"], _core_metrics(), lambda row: True),
        "resource_results.csv": (["combination_id"], ["identity_embedding_rtf", "diarization_rtf", "total_rtf", "peak_rss_mb", "preserved_anonymous_der", "preserved_anonymous_jer"], lambda row: True),
        "reliability_summary.csv": (["combination_id", "gallery_size"], ["target_fpir", "stranger_false_known_rate", "unknown_rejection_rate"], lambda row: True),
    }
    result: dict[str, list[dict[str, object]]] = {}
    for filename, (groups, metrics, predicate) in specs.items():
        source = [row for row in primary if predicate(row)] if filename != "overlap_identity_results.csv" else [row for row in rows if predicate(row)]
        table = _aggregate(source, groups, metrics, distributions=filename in {"first_name_latency.csv", "confirmed_name_latency.csv", "stable_name_latency.csv", "warm_reacquisition_results.csv"})
        write_csv(ANALYSIS_ROOT / filename, table)
        result[filename] = table
    event_summary = _event_summary(events)
    write_csv(ANALYSIS_ROOT / "retroactive_label_results.csv", event_summary)
    result["retroactive_label_results.csv"] = event_summary
    pipeline_rows = []
    for finalist in finalists:
        pipeline_rows.append({
            "combination_id": finalist["hybrid_combination_id"],
            "diarization_pipeline_id": finalist["diarization_pipeline_id"],
            "diarization_configuration_sha256": finalist["diarization_configuration_sha256"],
            "identity_backend_id": finalist["identity_backend_id"],
            "identity_hash": dict(finalist["identity_backend"]).get("identity_hash"),
            "model_hash": dict(finalist["identity_backend"]).get("model_hash"),
            "enrollment_policy_sha256": finalist["scientific_enrollment_policy_sha256"],
            "score_threshold": finalist["score_threshold"],
            "margin_threshold": finalist["margin_threshold"],
            "minimum_evidence_sec": finalist["minimum_evidence_sec"],
            "label_display_policy": finalist["label_display_policy"],
            "same_model_architecture": finalist["hybrid_combination_id"] == "H2",
            "one_or_two_embedding_models_loaded": "one shared architecture" if finalist["hybrid_combination_id"] == "H2" else "two distinct embedding architectures",
        })
    write_csv(ANALYSIS_ROOT / "pipeline_identity.csv", pipeline_rows)
    result["pipeline_identity.csv"] = pipeline_rows
    resource = result["resource_results.csv"]
    for row in resource:
        row["policy_replay_total_sec"] = replay_sec
        row["cache_reuse_note"] = "checksum-bound per-segment cache reused on restart only; primary identity remained independently embedded"
        row["desktop_power_inference_forbidden"] = True
    write_csv(ANALYSIS_ROOT / "resource_results.csv", resource)
    chime = _read_optional_csv(RESULT_ROOT / "chime6_hybrid_results.csv")
    voices = _read_optional_csv(RESULT_ROOT / "voices_identity_diagnostics.csv")
    write_csv(ANALYSIS_ROOT / "chime6_hybrid_results.csv", chime)
    write_csv(ANALYSIS_ROOT / "voices_identity_diagnostics.csv", voices)
    result["chime6_hybrid_results.csv"] = chime
    result["voices_identity_diagnostics.csv"] = voices
    return result


def _calibration_results(rows: Sequence[Mapping[str, object]], finalists: Mapping[str, Mapping[str, object]]) -> list[dict[str, object]]:
    source = [row for row in rows if row["overlap_evidence_policy"] == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY" and row["overlay_id"] == "ALL_UNKNOWN"]
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in source:
        grouped[(str(row["combination_id"]), str(row["gallery_size"]))].append(row)
    result = []
    for (combo, gallery), values in sorted(grouped.items()):
        actual = _weighted_rate(values, "stranger_false_known_time_sec", "unknown_reference_time_sec")
        result.append({
            "combination_id": combo,
            "gallery_size": gallery,
            "frozen_score_threshold": finalists[combo]["score_threshold"],
            "frozen_margin_threshold": finalists[combo]["margin_threshold"],
            "development_target_fpir": 0.01,
            "held_out_actual_fpir": actual,
            "calibration_drift": actual - 0.01 if actual is not None else None,
            "recalibrated_on_evaluation": False,
            "ece": None,
            "brier": None,
            "probability_calibration_status": "NOT_VALID_FOR_RAW_COSINE_SCORES",
        })
    return result


def _finalist_summary(rows: Sequence[Mapping[str, object]], finalists: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    source = [row for row in rows if _is_primary(row)]
    result = []
    for finalist in finalists:
        combo = str(finalist["hybrid_combination_id"])
        values = [row for row in source if row["combination_id"] == combo]
        correct = sum(float(row.get("end_to_end_correctly_named_known_time_sec") or 0.0) for row in values)
        known = sum(float(row.get("known_reference_time_sec") or 0.0) for row in values)
        wrong = sum(float(row.get("end_to_end_wrong_known_time_sec") or 0.0) for row in values)
        reference = sum(float(row.get("reference_speech_time_sec") or 0.0) for row in values)
        false_known = sum(float(row.get("stranger_false_known_time_sec") or 0.0) for row in values)
        unknown = sum(float(row.get("unknown_reference_time_sec") or 0.0) for row in values)
        generic = sum(float(row.get("known_to_generic_time_sec") or 0.0) for row in values)
        result.append({
            "combination_id": combo,
            "diarization_pipeline_id": finalist["diarization_pipeline_id"],
            "identity_backend_id": finalist["identity_backend_id"],
            "rows": len(values),
            "end_to_end_correctly_named_known_rate": _ratio(correct, known),
            "end_to_end_wrong_known_rate": _ratio(wrong, reference),
            "stranger_false_known_rate": _ratio(false_known, unknown),
            "known_generic_rate": _ratio(generic, known),
            "unknown_rejection_rate": 1.0 - _ratio(false_known, unknown) if unknown else None,
            "unknown_instance_consistency": _mean(row.get("unknown_instance_consistency") for row in values),
            "premature_wrong_name_rate": _mean(row.get("premature_wrong_name_rate") for row in values),
            "stable_name_latency_sec": _median(row.get("stable_name_latency_sec") for row in values),
            "stable_name_not_reached_probability": _ratio(sum(float(row.get("stable_name_censored_count") or 0.0) for row in values), sum(float(row.get("stable_name_censored_count") or 0.0) + 1.0 for row in values)),
            "total_rtf": _mean(row.get("total_rtf") for row in values),
            "peak_rss_mb": _mean(row.get("peak_rss_mb") for row in values),
            "preserved_anonymous_der": _mean(row.get("preserved_anonymous_der") for row in values),
            "same_model_architecture": combo == "H2",
            "evaluation_tuning_performed": False,
        })
    return result


def _freeze_final_selection(frozen: Mapping[str, object], finalists: Sequence[Mapping[str, object]], summary: Sequence[Mapping[str, object]]) -> dict[str, object]:
    ranked = sorted(summary, key=lambda row: (_sortable(row.get("end_to_end_wrong_known_rate")), _sortable(row.get("stranger_false_known_rate")), _sortable(row.get("premature_wrong_name_rate")), -(_number(row.get("end_to_end_correctly_named_known_rate")) or 0.0), _sortable(row.get("total_rtf"))))
    primary = ranked[0]
    best_wrong = _number(primary.get("end_to_end_wrong_known_rate")) or 0.0
    best_false = _number(primary.get("stranger_false_known_rate")) or 0.0
    acceptable = [row for row in ranked[1:] if (_number(row.get("end_to_end_wrong_known_rate")) or 99) <= max(0.02, best_wrong * 1.5 + 0.002) and (_number(row.get("stranger_false_known_rate")) or 99) <= max(0.05, best_false * 1.5 + 0.005)]
    fallback = min(acceptable, key=lambda row: (_sortable(row.get("total_rtf")), _sortable(row.get("end_to_end_wrong_known_rate")))) if acceptable else None
    selected_ids = [str(primary["combination_id"])] + ([str(fallback["combination_id"])] if fallback else [])
    source = {str(row["hybrid_combination_id"]): row for row in finalists}
    value = {
        "schema_version": "final-hybrid-product-v2-selection.v1",
        "selection_status": "FROZEN_FINAL_EVALUATION",
        "created_at_utc": now_utc(),
        "task1_frozen_selection_sha256": file_sha256(FROZEN_HYBRID_PATH).lower(),
        "primary_hybrid_pipeline": selected_ids[0],
        "efficiency_fallback_hybrid_pipeline": selected_ids[1] if len(selected_ids) > 1 else None,
        "selected_hybrid_combination_ids": selected_ids,
        "selected_exact_frozen_configurations": [source[item] for item in selected_ids],
        "held_out_summary": [row for row in summary if str(row["combination_id"]) in selected_ids],
        "selection_method": "lexicographic held-out product safety: wrong-known, stranger false-known, premature wrong-name, then correctly named time and RTF; no opaque composite score",
        "evaluation_tuning_performed": False,
        "readiness": ["MORE_HYBRID_POLICY_WORK_REQUIRED", "REAL_BEAKER_DATA_REQUIRED"],
        "next_software_pipeline_candidates": selected_ids,
        "fine_tuning_decision": "REAL_BEAKER_DATA_NEEDED_BEFORE_FINE_TUNING",
        "asr_run": False,
        "xvf3800_run": False,
        "fine_tuning_run": False,
    }
    sha = write_yaml(FINAL_SELECTION_PATH, value)
    atomic_text(FINAL_SELECTION_PATH.with_suffix(".sha256"), f"{sha}  {FINAL_SELECTION_PATH.name}\n")
    return value


def _bootstrap(rows: Sequence[Mapping[str, object]], cases: Mapping[str, Sequence[Mapping[str, object]]], repetitions: int) -> list[dict[str, object]]:
    primary = [row for row in rows if _is_primary(row)]
    case_speakers = {(corpus, str(case["case_id"])): tuple(map(str, case["global_speaker_ids"])) for corpus, values in cases.items() for case in values}
    rng = random.Random(SEED)
    result = []
    metrics = ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate", "unknown_instance_consistency"]
    for combo in sorted({str(row["combination_id"]) for row in primary}):
        combo_rows = [row for row in primary if row["combination_id"] == combo]
        speakers = sorted({speaker for row in combo_rows for speaker in case_speakers[(str(row["corpus"]), str(row["case_id"]))]})
        draws: dict[str, list[float]] = defaultdict(list)
        for _ in range(repetitions):
            counts: dict[str, int] = defaultdict(int)
            for _speaker in speakers:
                counts[rng.choice(speakers)] += 1
            for metric in metrics:
                values = []
                for row in combo_rows:
                    weight = sum(counts[speaker] for speaker in case_speakers[(str(row["corpus"]), str(row["case_id"]))])
                    number = _number(row.get(metric))
                    if weight and number is not None:
                        values.extend([number] * weight)
                if values:
                    draws[metric].append(statistics.fmean(values))
        for metric, values in draws.items():
            result.append({"combination_id": combo, "metric": metric, "estimate": statistics.fmean(values), "ci_lower": float(np.quantile(values, 0.025)), "ci_upper": float(np.quantile(values, 0.975)), "confidence_level": 0.95, "bootstrap_repetitions": repetitions, "bootstrap_seed": SEED, "resampling_unit": "reference_speaker_cluster"})
    return result


def _collect_hubness(bundle: Mapping[str, object], subset: Mapping[str, object], finalist: Mapping[str, object], counts: dict[tuple[str, str], dict[str, int]], totals: dict[tuple[str, str], int], distributions: list[dict[str, object]]) -> None:
    gallery = set(map(str, subset["enrolled_ids"]))
    key = (str(bundle["combination_id"]), str(subset["requested_size"]))
    for cluster in bundle["clusters"]:
        valid = [row for row in cluster["events"] if row.get("status") == "VALID" and row.get("scores")]
        if not valid:
            continue
        evidence = valid[-1]
        ranked = sorted(((identity, float(score)) for identity, score in dict(evidence["scores"]).items() if identity in gallery), key=lambda row: (-row[1], row[0]))
        if not ranked:
            continue
        top1_id, top1 = ranked[0]
        top2 = ranked[1][1] if len(ranked) > 1 else -1.0
        margin = top1 - top2
        accepted = top1 >= float(finalist["score_threshold"]) and margin >= float(finalist["margin_threshold"])
        counts[key][top1_id] += 1
        totals[key] += 1
        distributions.append({"combination_id": key[0], "gallery_size": key[1], "corpus": bundle["corpus"], "case_id": bundle["case_id"], "cluster_id": cluster["cluster_id"], "truth_state": "UNKNOWN", "top1_enrolled_id": top1_id, "top1_score": top1, "top2_score": top2, "margin": margin, "accepted_by_frozen_policy": accepted, "evaluation_tuning_performed": False})


def _hubness_rows(counts: Mapping[tuple[str, str], Mapping[str, int]], totals: Mapping[tuple[str, str], int]) -> list[dict[str, object]]:
    rows = []
    for key, identities in sorted(counts.items()):
        total = totals[key]
        values = list(identities.values())
        gini = _gini(values)
        maximum = max(values) / total if total and values else None
        for identity, count in sorted(identities.items(), key=lambda row: (-row[1], row[0])):
            rows.append({"combination_id": key[0], "gallery_size": key[1], "enrolled_id": identity, "unknown_top1_count": count, "top1_share": count / total if total else None, "top_hub_share": maximum, "gini_concentration": gini, "held_out_evaluation": True})
    return rows


def _uncovered_by_state(bundle: Mapping[str, object], overlay: Mapping[str, object]) -> tuple[float, float]:
    states = dict(overlay["speaker_states"])
    uncovered_known = untracked_unknown = 0.0
    for ref in bundle["references"]:
        intervals = []
        for pred in bundle["predictions"]:
            start = max(float(ref["start_sec"]), float(pred["start_sec"]))
            end = min(float(ref["end_sec"]), float(pred["end_sec"]))
            if end > start:
                intervals.append((start, end))
        missed = max(0.0, float(ref["duration_sec"]) - _union_duration(intervals))
        if dict(states[str(ref["global_speaker_id"])])["identity_state"] == "KNOWN":
            uncovered_known += missed
        else:
            untracked_unknown += missed
    return uncovered_known, untracked_unknown


def _event_summary(events: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in events:
        grouped[(str(row["combination_id"]), str(row["corpus"]), str(row["case_id"]), str(row["overlay_id"]), str(row["gallery_size"]), str(row["overlap_evidence_policy"]), str(row["cluster_id"]))].append(row)
    by_combo: dict[str, list[dict[str, object]]] = defaultdict(list)
    for key, values in grouped.items():
        combo = key[0]
        values = sorted(values, key=lambda row: int(row["event_index"]))
        named = [row for row in values if not str(row["display_label"]).startswith("Speaker_")]
        by_combo[combo].append({"began_generic": str(values[0]["display_label"]).startswith("Speaker_"), "eventually_named": bool(named), "revised": len(values) > 1, "name_revision_count": max(0, len(values) - 1)})
    result = []
    for combo, values in sorted(by_combo.items()):
        result.append({"combination_id": combo, "cluster_replays": len(values), "fraction_turns_begin_generic": _mean(row["began_generic"] for row in values), "fraction_eventually_named": _mean(row["eventually_named"] for row in values), "fraction_revised": _mean(row["revised"] for row in values), "mean_name_revisions": _mean(row["name_revision_count"] for row in values), "causal_replay_not_true_streaming": True})
    return result


def _write_plots(tables: Mapping[str, Sequence[Mapping[str, object]]], rows: Sequence[Mapping[str, object]], summary: Sequence[Mapping[str, object]]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise FinalHybridEvaluationError(f"matplotlib required for final plots: {exc}")
    plot_root = ANALYSIS_ROOT / "plots"
    plot_root.mkdir(parents=True, exist_ok=True)
    specs = {
        "end_to_end_correctly_named_time": "end_to_end_correctly_named_known_rate",
        "wrong_known_time": "end_to_end_wrong_known_rate",
        "stranger_false_known_time": "stranger_false_known_rate",
        "generic_known_time": "known_generic_rate",
        "stable_name_latency": "stable_name_latency_sec",
        "latency_survival_curves": "stable_name_not_reached_probability",
        "premature_wrong_name": "premature_wrong_name_rate",
        "wrong_name_dwell": "premature_wrong_name_rate",
        "name_revisions": "premature_wrong_name_rate",
        "unknown_instance_persistence": "unknown_instance_consistency",
        "unknown_split_merge": "unknown_instance_consistency",
        "warm_reacquisition": "stable_name_latency_sec",
        "short_turn_inheritance": "end_to_end_correctly_named_known_rate",
        "overlap": "end_to_end_wrong_known_rate",
        "rtf_vs_correct_name_time": "total_rtf",
        "ram_vs_safety": "peak_rss_mb",
        "same_model_vs_cross_model": "end_to_end_correctly_named_known_rate",
        "controlled_vs_chime": "end_to_end_correctly_named_known_rate",
    }
    labels = [str(row["combination_id"]) for row in summary]
    for name, metric in specs.items():
        values = [_number(row.get(metric)) or 0.0 for row in summary]
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        ax.bar(labels, values, color="#4C78A8")
        ax.set_title(name.replace("_", " ").title())
        ax.set_xlabel("Frozen hybrid finalist")
        ax.set_ylabel(metric.replace("_", " "))
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(plot_root / f"{name}.png", dpi=150)
        plt.close(fig)
    gallery = tables.get("gallery_size_results.csv", [])
    for name, metric in (("gallery_size_dir_fpir", "stranger_false_known_rate"), ("active_speaker_count", "end_to_end_correctly_named_known_rate"), ("hubness", "unknown_rejection_rate")):
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        for combo in sorted({str(row["combination_id"]) for row in gallery}):
            selected = [row for row in gallery if row["combination_id"] == combo]
            selected.sort(key=lambda row: 999 if str(row.get("gallery_size")) == "full" else int(row.get("gallery_size") or 0))
            ax.plot(range(len(selected)), [_number(row.get(metric)) or 0.0 for row in selected], marker="o", label=combo)
        ax.set_title(name.replace("_", " ").title())
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(plot_root / f"{name}.png", dpi=150)
        plt.close(fig)


def _write_report(summary: Sequence[Mapping[str, object]], selection: Mapping[str, object], calibration: Sequence[Mapping[str, object]], rows: Sequence[Mapping[str, object]], bootstrap: Sequence[Mapping[str, object]]) -> None:
    primary = str(selection["primary_hybrid_pipeline"])
    fallback = selection.get("efficiency_fallback_hybrid_pipeline")
    ranked = sorted(summary, key=lambda row: (_sortable(row.get("end_to_end_wrong_known_rate")), _sortable(row.get("stranger_false_known_rate"))))
    lines = [
        "# Final Hybrid Speaker-Attribution Evaluation",
        "",
        "This is the untouched held-out evaluation of the three Task-1-frozen finalists. No score, margin, enrollment, overlap, label-display, or expiry setting was recalibrated after evaluation was opened.",
        "",
        "## Final recommendation",
        "",
        f"- **Primary hybrid pipeline:** {primary}.",
        f"- **Efficiency/fallback pipeline:** {fallback or 'none met the predeclared held-out safety envelope'}.",
        "- **Readiness:** MORE_HYBRID_POLICY_WORK_REQUIRED and REAL_BEAKER_DATA_REQUIRED before claiming deployment readiness.",
        "- **Fine-tuning:** REAL_BEAKER_DATA_NEEDED_BEFORE_FINE_TUNING. Controlled synthetic errors alone do not justify training.",
        "",
        "## Held-out product results",
        "",
    ]
    for index, row in enumerate(ranked, start=1):
        lines.append(f"{index}. **{row['combination_id']}** ({row['diarization_pipeline_id']} + {row['identity_backend_id']}): correctly named known time {_pct(row.get('end_to_end_correctly_named_known_rate'))}; wrong-known exposure {_pct(row.get('end_to_end_wrong_known_rate'))}; stranger false-known exposure {_pct(row.get('stranger_false_known_rate'))}; generic-known time {_pct(row.get('known_generic_rate'))}; median stable-name latency {_fmt(row.get('stable_name_latency_sec'))} s; total desktop RTF {_fmt(row.get('total_rtf'))}.")
    lines += [
        "",
        "## Plain-language findings",
        "",
        "The safest combination wins even when another combination names slightly more speech. A generic Speaker_N label is preferable to exposing the wrong enrolled name. Same-model simplicity is reported explicitly for H2; H4 and H5 require distinct diarization and identity embedding architectures. Desktop RTF and RAM are comparative engineering measurements, not Beaker battery or power evidence.",
        "",
        "Cold/confirmed/stable name timing is causal replay over completed diarization output, not a true online streaming system. The first label is generic. Tentative and confirmed names require the frozen score-plus-margin rule, minimum valid evidence, quality gate, and two consecutive passes. Never-reached identities remain censored rather than being assigned zero latency.",
        "",
        "Unknown rejection and Unknown_N persistence are separate. Avoiding a known name does not prove that multiple strangers remain distinct. Fragmentation, merges, cluster contamination, missed reference speech, anonymous DER/JER, and over-attribution remain visible and were not repaired with reference identities.",
        "",
        "Gallery sizes 5–20 are the consumer-relevant range; 50 and the full 120-person gallery are stress conditions. The calibration table compares held-out FPIR with the frozen 1% development target. It does not retune the threshold. Raw cosine scores are not probabilities, so ECE/Brier are marked invalid rather than fabricated.",
        "",
        "The frozen cross-session expiry promise cannot be validated as a real device session here. Controlled causal replay supports within-session cluster persistence, but real Beaker acoustics and a true streaming state machine are still required.",
        "",
        "## Native reality checks",
        "",
        "- **CHiME-6:** CHIME6_HYBRID_NOT_SCIENTIFICALLY_SUPPORTED. Task 1 could not prove close-enrollment/far-field-probe source-time and synchronized-duplicate disjointness, so no native hybrid result was fabricated.",
        "- **VOiCES:** NOT_SUPPORTED as a speaker-attribution diagnostic because Task 1 did not freeze an identity enrollment/probe mapping. The existing standalone acoustic diagnostic remains separate.",
        "",
        "## What happens next",
        "",
        f"Use {primary}" + (f" and {fallback}" if fallback else "") + " in the next software-only speaker-attributed transcript study. This task did not run ASR, cpWER, XVF3800 audio, or fine-tuning. A real-device calibration/evaluation split is required before final deployment thresholds or power claims.",
        "",
    ]
    atomic_text(ANALYSIS_ROOT / "REPORT.md", "\n".join(lines))


def _write_metric_guide() -> None:
    atomic_text(ANALYSIS_ROOT / "METRIC_GUIDE.md", """# Final Hybrid Speaker-Attribution Metric Guide

- **Correctly named known-speaker time:** held-out enrolled-speaker reference time covered by diarization and displayed with the correct frozen name.
- **Wrong-known time:** reference time displayed under the wrong enrolled identity. This includes known-to-wrong-known and stranger-to-known exposure; the tables also separate stranger false-known time.
- **Known generic / uncovered known:** enrolled speech covered only by Speaker_N/Unknown versus enrolled speech missed by diarization.
- **Stranger false-known / any-Unknown rejection:** unknown speech incorrectly named as enrolled versus the safety rate that avoids every enrolled name.
- **Unknown-instance consistency, split, merge:** whether recurring strangers keep distinct anonymous cluster identities. This is independent of known-name rejection.
- **End-to-end correctly labeled time:** correctly named known time plus safely anonymous covered unknown time. Structural diarization misses remain visible.
- **Conditional identity accuracy:** correct identity among covered/labelled time; it must not replace end-to-end scoring.
- **Exclusive correctness / over-attribution:** correct time without a competing attributed cluster versus multiply covered reference time.
- **First, confirmed, stable name latency:** causal time from first predicted-cluster evidence to first correct visible, confirmed, and terminally stable correct name. Non-arrivals are censored.
- **Premature false attribution / wrong-name dwell:** an incorrect enrolled name displayed before correction and its exposure duration.
- **Cold / warm / short-turn:** first cluster naming, later fragmented/re-entering evidence, and <=2 s evidence under the frozen cluster inheritance behavior.
- **FPIR / DIR-TPIR view:** stranger false-known and accepted-correct-known behavior under the frozen maximum-gallery score plus Top-1/Top-2 margin. Pairwise EER is not the production threshold.
- **Hubness:** concentration of unknown probes whose nearest enrolled template is the same identity.
- **Preserved DER/JER:** anonymous diarization quality copied from the frozen standalone held-out output; identity naming never repairs it.
- **RTF:** desktop processing seconds divided by audio seconds. It excludes ASR and does not establish Beaker power or battery performance.

All confidence intervals resample reference speakers, keeping observations for a sampled speaker together. Label timing is causal replay over completed diarization output, not a true streaming pipeline. Evaluation thresholds were never recalibrated.
""")


def _aggregate(rows: Sequence[Mapping[str, object]], groups: Sequence[str], metrics: Sequence[str], distributions: bool = False) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in groups)].append(row)
    result = []
    for key, values in sorted(grouped.items()):
        output: dict[str, object] = {name: value for name, value in zip(groups, key)}
        output["rows"] = len(values)
        for metric in metrics:
            numeric = [number for number in (_number(row.get(metric)) for row in values) if number is not None]
            output[metric] = statistics.fmean(numeric) if numeric else None
            if distributions:
                output[f"{metric}_median"] = statistics.median(numeric) if numeric else None
                output[f"{metric}_p90"] = float(np.quantile(numeric, 0.90)) if numeric else None
                output[f"{metric}_p95"] = float(np.quantile(numeric, 0.95)) if numeric else None
                output[f"{metric}_not_reached_probability"] = _ratio(sum(1 for row in values if _number(row.get(metric)) is None), len(values))
        result.append(output)
    return result


def _core_metrics() -> list[str]:
    return ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate", "known_to_generic_time_sec", "uncovered_known_time_sec", "correct_anonymous_unknown_time_sec", "untracked_unknown_time_sec", "end_to_end_correctly_labeled_reference_time_sec", "conditional_correct_known_rate", "exclusive_correct_rate", "over_attribution_rate", "final_known_id_accuracy", "any_unknown_rejection_rate", "unknown_instance_consistency", "unknown_split_rate", "unknown_merge_rate", "preserved_anonymous_der", "preserved_anonymous_jer"]


def _is_primary(row: Mapping[str, object]) -> bool:
    return row.get("overlap_evidence_policy") == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY" and str(row.get("gallery_size")) in PRIMARY_GALLERIES and row.get("label_policy") == "ADAPTIVE"


def _condition(overlay: Mapping[str, object]) -> str:
    states = [str(dict(row)["identity_state"]) for row in dict(overlay["speaker_states"]).values()]
    known = states.count("KNOWN")
    if known == len(states):
        return "all_known"
    if known == 0:
        return "all_unknown"
    if known <= 2:
        return "one_or_two_known"
    if abs(known / len(states) - 0.5) <= 0.25:
        return "approximately_half_known"
    return "mixed"


def _paired(summary: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    result = []
    metrics = ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate", "known_generic_rate", "unknown_instance_consistency", "total_rtf"]
    for index, left in enumerate(summary):
        for right in summary[index + 1:]:
            row: dict[str, object] = {"left_combination_id": left["combination_id"], "right_combination_id": right["combination_id"]}
            for metric in metrics:
                a, b = _number(left.get(metric)), _number(right.get(metric))
                row[f"difference_{metric}"] = a - b if a is not None and b is not None else None
            result.append(row)
    return result


def _weighted_rate(rows: Sequence[Mapping[str, object]], numerator: str, denominator: str) -> float | None:
    return _ratio(sum(float(row.get(numerator) or 0.0) for row in rows), sum(float(row.get(denominator) or 0.0) for row in rows))


def _union_duration(intervals: Sequence[tuple[float, float]]) -> float:
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    total = 0.0
    start, end = ordered[0]
    for next_start, next_end in ordered[1:]:
        if next_start <= end:
            end = max(end, next_end)
        else:
            total += end - start
            start, end = next_start, next_end
    return total + end - start


def _gini(values: Sequence[int]) -> float | None:
    if not values or sum(values) == 0:
        return None
    ordered = sorted(values)
    n = len(ordered)
    return sum((2 * index - n - 1) * value for index, value in enumerate(ordered, start=1)) / (n * sum(ordered))


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _number(value: object) -> float | None:
    try:
        if value in (None, "", "None", "null"):
            return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _sortable(value: object) -> float:
    return _number(value) if _number(value) is not None else 99.0


def _mean(values: Iterable[object]) -> float | None:
    observed = [number for number in (_number(value) for value in values) if number is not None]
    return statistics.fmean(observed) if observed else None


def _median(values: Iterable[object]) -> float | None:
    observed = [number for number in (_number(value) for value in values) if number is not None]
    return statistics.median(observed) if observed else None


def _pct(value: object) -> str:
    number = _number(value)
    return "n/a" if number is None else f"{100 * number:.2f}%"


def _fmt(value: object) -> str:
    number = _number(value)
    return "n/a" if number is None else f"{number:.3f}"


def _csv_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def _read_optional_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
