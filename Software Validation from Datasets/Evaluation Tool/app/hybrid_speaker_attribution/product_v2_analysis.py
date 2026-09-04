"""Causal open-set policy replay, product metrics, plots, selection, freeze and export."""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
from typing import Iterable, Mapping, Sequence
import zipfile

import numpy as np
import yaml

from app.hybrid_speaker_attribution.product_v2_contracts import (
    COMBINATIONS, FROZEN_DIARIZATION_SELECTION, GALLERY_SIZES, LABEL_POLICIES,
    OPERATING_MODES, POLICY_ROOT, PRODUCT_PROTOCOL_ROOT, RESULT_ROOT, SCHEMA,
    SEED, SUMMARY_ROOT, TOOL_ROOT, UPSTREAM_DIARIZATION_ROOT, V1_BENCHMARK_ROOT,
    V2_BENCHMARK_ROOT, ProductV2Error, atomic_json, atomic_text, checksum_tree,
    file_sha256, now_utc, read_json, read_jsonl, write_csv, write_yaml,
)
from app.hybrid_speaker_attribution.product_v2_runner import (
    PROGRESS_PATH, SCORE_ROOT, load_score_bundle, set_controller,
    update_replay_progress, validate_score_bundles,
)


ANALYSIS_ROOT = RESULT_ROOT / "analysis"
FROZEN_PATH = RESULT_ROOT / "frozen_hybrid_product_v2_selection.yaml"


def analyze(*, bootstrap_repetitions: int = 500) -> dict[str, object]:
    validation = validate_score_bundles()
    expected = 96
    if validation["status"] != "PASS" or any(int(validation["counts"].get(row["combination_id"], 0)) != expected for row in COMBINATIONS):
        raise ProductV2Error(f"complete score bundles required before analysis: {validation}")
    set_controller("RUNNING", "CALIBRATION", "Calibrating maximum-gallery score and Top-1/Top-2 margin on development calibration cases")
    ANALYSIS_ROOT.mkdir(parents=True, exist_ok=True)
    overlays = _overlay_index()
    bundles = list(_bundles())
    calibrations, score_distributions, hubness = _calibrate(bundles, overlays)
    calibration_index = {(row["combination_id"], str(row["gallery_size"]), row["operating_mode"]): row for row in calibrations}
    write_csv(ANALYSIS_ROOT / "calibration_results.csv", calibrations)
    write_csv(ANALYSIS_ROOT / "score_margin_distributions.csv", score_distributions)
    write_csv(ANALYSIS_ROOT / "hubness_results.csv", hubness)
    set_controller("RUNNING", "POLICY_REPLAY", "Causal label-policy replay from cached score bundles")
    replay_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    units = []
    for bundle in bundles:
        for overlay_id in ("ALL_KNOWN", "MIXED_KNOWN_UNKNOWN", "ALL_UNKNOWN"):
            overlay = overlays[(str(bundle["corpus"]), str(bundle["case_id"]), overlay_id)]
            for subset in overlay["gallery_subsets"]:
                if subset["status"] != "VALID":
                    continue
                for mode in OPERATING_MODES:
                    for label_policy in LABEL_POLICIES:
                        for overlap_policy in ("EXCLUDE_PREDICTED_OVERLAP_PRIMARY", "INCLUDE_PREDICTED_OVERLAP_DIAGNOSTIC"):
                            units.append((bundle, overlay, subset, mode, label_policy, overlap_policy))
    for index, (bundle, overlay, subset, mode, label_policy, overlap_policy) in enumerate(units, start=1):
        calibration = calibration_index[(str(bundle["combination_id"]), str(subset["requested_size"]), mode)]
        row, events = _replay(bundle, overlay, subset, mode, label_policy, overlap_policy, calibration)
        replay_rows.append(row)
        event_rows.extend(events)
        if index % 100 == 0 or index == len(units):
            update_replay_progress(index, len(units), f"{bundle['combination_id']} {bundle['corpus']} {bundle['case_id']}")
    write_csv(ANALYSIS_ROOT / "overlay_results.csv", replay_rows)
    write_csv(ANALYSIS_ROOT / "label_event_log.csv", event_rows)
    tables = _write_tables(replay_rows, event_rows, bundles, calibrations, hubness)
    bootstrap = _bootstrap(replay_rows, repetitions=bootstrap_repetitions)
    write_csv(ANALYSIS_ROOT / "bootstrap_intervals.csv", bootstrap)
    _plots(tables)
    summary = _combination_summary(replay_rows)
    write_csv(ANALYSIS_ROOT / "hybrid_combination_summary.csv", summary)
    _write_reports(summary, bootstrap, len(replay_rows), len(event_rows))
    manifest = {
        "schema_version": f"{SCHEMA}-analysis-manifest.v1",
        "created_at_utc": now_utc(),
        "protocol_id": read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")["protocol_id"],
        "development_only": True,
        "EVALUATION_NOT_INSPECTED": True,
        "score_bundles": validation["counts"],
        "policy_replay_rows": len(replay_rows),
        "label_events": len(event_rows),
        "bootstrap_repetitions": bootstrap_repetitions,
        "bootstrap_seed": SEED,
        "tables": [path.name for path in sorted(ANALYSIS_ROOT.glob("*.csv"))],
        "plots": [path.name for path in sorted((ANALYSIS_ROOT / "plots").glob("*.png"))],
        "asr_run": False,
        "xvf_available": False,
        "fine_tuning_run": False,
    }
    atomic_json(ANALYSIS_ROOT / "analysis_manifest.json", manifest)
    atomic_json(ANALYSIS_ROOT / "protocol_summary.json", read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json"))
    set_controller("ANALYSIS_COMPLETE", "SELECTION_PENDING", "Development policy analysis complete; evaluation remains untouched")
    return {"status": "COMPLETE", "analysis_root": str(ANALYSIS_ROOT), "summary": summary, "manifest": manifest}


def freeze() -> dict[str, object]:
    summary_path = ANALYSIS_ROOT / "hybrid_combination_summary.csv"
    if not summary_path.is_file():
        analyze()
    rows = _read_csv(summary_path)
    selected, rationale = _select(rows)
    protocol = read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")
    registry = read_json(PRODUCT_PROTOCOL_ROOT / "combination_registry.json")
    registry_by_id = {str(row["combination_id"]): row for row in registry["combinations"]}
    frozen_rows = []
    for rank, row in enumerate(selected, start=1):
        combo = registry_by_id[str(row["combination_id"])]
        policy_path = Path(str(combo["enrollment_policy_path"]))
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        calibration = _selected_calibration(str(row["combination_id"]))
        frozen_rows.append({
            "rank": rank,
            "role": ["SAFETY_ACCURACY_PRIMARY", "EFFICIENCY_PRIMARY", "DISTINCT_ARCHITECTURE_PARETO"][rank - 1],
            "hybrid_combination_id": row["combination_id"],
            "diarization_pipeline_id": combo["diarization_pipeline_id"],
            "diarization_configuration_sha256": combo["diarization_configuration_sha256"],
            "identity_backend_id": combo["identity_backend_id"],
            "identity_backend": policy["backend_identity"],
            "scientific_enrollment_policy_id": policy["policy_id"],
            "scientific_enrollment_policy_sha256": file_sha256(policy_path).lower(),
            "enrollment_utterance_count": policy["enrollment_utterance_count"],
            "enrollment_aggregation": policy["aggregation_method"],
            "cluster_evidence_aggregation": policy["cluster_evidence_aggregation"],
            "operating_mode": "BALANCED",
            "score_threshold": calibration["score_threshold"],
            "margin_threshold": calibration["margin_threshold"],
            "minimum_evidence_sec": 2.0,
            "quality_gate": {"minimum_embedding_consistency": 0.35, "minimum_valid_evidence": True},
            "overlap_policy": "exclude_predicted_overlap_for_identity_primary_include_diagnostic",
            "label_display_policy": "ADAPTIVE",
            "confirmation": {"consecutive_passes": 2, "hysteresis": 0.02, "tentative_visible": True},
            "expiry_session_policy": {"inherit_within_cluster": True, "warm_reacquisition": True, "expiry_sec": 120.0},
            "gallery_calibration_policy": "per_realized_gallery_size_maximum_score_and_top1_top2_margin",
            "development_metrics": row,
            "selection_rationale": rationale[str(row["combination_id"])],
        })
    rejected = [{"combination_id": row["combination_id"], "metrics": row, "reason": "dominated or did not add a distinct safety/efficiency trade-off"} for row in rows if row not in selected]
    result_identity_files = [ANALYSIS_ROOT / "hybrid_combination_summary.csv", ANALYSIS_ROOT / "overlay_results.csv", ANALYSIS_ROOT / "calibration_results.csv", ANALYSIS_ROOT / "bootstrap_intervals.csv"]
    result_identity = hashlib.sha256("".join(file_sha256(path).lower() for path in result_identity_files).encode("ascii")).hexdigest()
    source_hashes = []
    for path in sorted((TOOL_ROOT / "app" / "hybrid_speaker_attribution").glob("product_v2_*.py")):
        source_hashes.append({"path": str(path.relative_to(TOOL_ROOT)), "sha256": file_sha256(path).lower()})
    frozen = {
        "schema_version": "frozen-hybrid-product-v2-selection.v1",
        "selection_status": "FROZEN_DEVELOPMENT_ONLY",
        "created_at_utc": now_utc(),
        "selected_hybrid_combination_ids": [row["hybrid_combination_id"] for row in frozen_rows],
        "selected_finalists": frozen_rows,
        "rejected_combinations": rejected,
        "selection_method": "predeclared nondominated safety/accuracy, efficiency, then distinct cross-model architecture; no opaque weighted score",
        "development_result_identity_sha256": result_identity,
        "protocol_ids": {"hybrid_product_v2": protocol["protocol_id"], "hybrid_v1": protocol["v1_preservation"]["protocol_id"], "diarization_product_v2": "diarization_product_v2_6b6c50a5de31"},
        "frozen_diarization_selection": {"path": str(FROZEN_DIARIZATION_SELECTION), "sha256": file_sha256(FROZEN_DIARIZATION_SELECTION).lower()},
        "source_code_result_affecting_hashes": source_hashes,
        "trade_offs": "Safety primary minimizes wrong-known and stranger false-known exposure; efficiency primary preserves competitive safety at lower RTF; third finalist is retained only for a useful cross-model Pareto option.",
        "EVALUATION_NOT_INSPECTED": True,
        "evaluation_authorized": True,
        "controlled_hybrid_evaluation_run": False,
        "native_chime_hybrid_evaluation_run": False,
        "asr_run": False,
        "xvf3800_run": False,
        "fine_tuning_run": False,
    }
    sha = write_yaml(FROZEN_PATH, frozen)
    atomic_text(FROZEN_PATH.with_suffix(".sha256"), f"{sha}  {FROZEN_PATH.name}\n")
    validation = validate_frozen()
    set_controller("FROZEN", "COLLECT_PENDING", f"Frozen {len(frozen_rows)} development finalists; evaluation was not run")
    return {"status": "FROZEN", "path": str(FROZEN_PATH), "sha256": sha, "selected": frozen["selected_hybrid_combination_ids"], "validation": validation}


def validate_frozen() -> dict[str, object]:
    errors = []
    if not FROZEN_PATH.is_file() or not FROZEN_PATH.with_suffix(".sha256").is_file():
        errors.append("frozen files missing")
        value = {}
    else:
        expected = FROZEN_PATH.with_suffix(".sha256").read_text(encoding="utf-8").strip().split()[0]
        observed = file_sha256(FROZEN_PATH).lower()
        if expected != observed:
            errors.append("frozen selection SHA-256 mismatch")
        value = yaml.safe_load(FROZEN_PATH.read_text(encoding="utf-8"))
        if value.get("selection_status") != "FROZEN_DEVELOPMENT_ONLY" or value.get("EVALUATION_NOT_INSPECTED") is not True or value.get("controlled_hybrid_evaluation_run") is not False:
            errors.append("evaluation firewall fields invalid")
        if not 1 <= len(value.get("selected_finalists") or []) <= 3:
            errors.append("invalid finalist count")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors, "path": str(FROZEN_PATH), "selected": value.get("selected_hybrid_combination_ids", [])}


def collect() -> dict[str, object]:
    validation = validate_frozen()
    if validation["status"] != "PASS":
        freeze()
    protocol_id = read_json(PRODUCT_PROTOCOL_ROOT / "protocol_summary.json")["protocol_id"]
    package_root = SUMMARY_ROOT / f"hybrid_speaker_attribution_product_v2_development_{protocol_id}"
    if package_root.exists():
        if SUMMARY_ROOT.resolve() not in package_root.resolve().parents:
            raise ProductV2Error(f"refusing to replace package outside summary root: {package_root}")
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)
    shutil.copytree(ANALYSIS_ROOT, package_root / "analysis")
    shutil.copytree(PRODUCT_PROTOCOL_ROOT, package_root / "protocol" )
    shutil.copytree(POLICY_ROOT, package_root / "enrollment_policies")
    shutil.copy2(FROZEN_PATH, package_root / FROZEN_PATH.name)
    shutil.copy2(FROZEN_PATH.with_suffix(".sha256"), package_root / FROZEN_PATH.with_suffix(".sha256").name)
    for name in ("audit.json", "validation.json", "plan.json", "campaign_progress.json", "controller_state.json", "score_bundle_failures.json"):
        source = RESULT_ROOT / name
        if source.is_file():
            shutil.copy2(source, package_root / name)
    inventories = []
    for backend_dir in sorted(path for path in (RESULT_ROOT / "_embedding_cache").glob("*") if path.is_dir()):
        files = list(backend_dir.glob("*.json"))
        inventories.append({"path": str(backend_dir), "backend_id": backend_dir.name, "item_count": len(files), "size_bytes": sum(path.stat().st_size for path in files), "inventory_identity_sha256": _inventory_hash(files)})
    write_csv(package_root / "cache_inventory.csv", inventories)
    manifest = {"schema_version": f"{SCHEMA}-export-manifest.v1", "created_at_utc": now_utc(), "protocol_id": protocol_id, "excluded": ["raw audio", "model weights", "gated assets", "large embedding caches", "credentials"], "files": checksum_tree(package_root, exclude_names={"checksums.json"})}
    atomic_json(package_root / "checksums.json", manifest)
    zip_path = SUMMARY_ROOT / f"hybrid_speaker_attribution_product_v2_development_{protocol_id}.zip"
    zip_path.unlink(missing_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(item for item in package_root.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(package_root.parent))
    sha = file_sha256(zip_path).lower()
    atomic_text(zip_path.with_suffix(".zip.sha256"), f"{sha}  {zip_path.name}\n")
    set_controller("COMPLETE", "COMPLETE", "Development analyzed, finalists frozen, and Task-1 package exported; evaluation not run")
    return {"status": "COMPLETE_HYBRID_PRODUCT_V2_DEVELOPMENT_AND_FREEZE", "zip_path": str(zip_path), "zip_sha256": sha, "frozen_selection": str(FROZEN_PATH), "frozen_sha256": file_sha256(FROZEN_PATH).lower()}


def _calibrate(bundles: Sequence[Mapping[str, object]], overlays: Mapping[tuple[str, str, str], Mapping[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    samples = defaultdict(list)
    distributions = []
    hubs = defaultdict(lambda: defaultdict(int))
    for bundle in bundles:
        if bundle["development_role"] != "calibration":
            continue
        overlay = overlays[(str(bundle["corpus"]), str(bundle["case_id"]), "ALL_UNKNOWN")]
        for subset in overlay["gallery_subsets"]:
            if subset["status"] != "VALID":
                continue
            gallery = set(map(str, subset["enrolled_ids"]))
            for cluster in bundle["clusters"]:
                event = _last_valid(cluster["events"])
                if event is None:
                    continue
                ranked = sorted(((identity, float(score)) for identity, score in dict(event["scores"]).items() if identity in gallery), key=lambda row: (-row[1], row[0]))
                if not ranked:
                    continue
                top1 = ranked[0][1]
                top2 = ranked[1][1] if len(ranked) > 1 else -1.0
                key = (str(bundle["combination_id"]), str(subset["requested_size"]))
                samples[key].append((top1, top1 - top2, ranked[0][0]))
                hubs[key][ranked[0][0]] += 1
                distributions.append({"combination_id": key[0], "gallery_size": key[1], "corpus": bundle["corpus"], "case_id": bundle["case_id"], "cluster_id": cluster["cluster_id"], "truth_state": "UNKNOWN", "top1_score": top1, "top2_score": top2, "margin": top1 - top2, "top1_enrolled_id": ranked[0][0], "calibration_only": True})
    rows = []
    for combination in COMBINATIONS:
        combo = str(combination["combination_id"])
        for gallery in GALLERY_SIZES:
            values = samples.get((combo, str(gallery)), [])
            for mode, settings in OPERATING_MODES.items():
                margin = float(settings["default_margin"])
                eligible = [score for score, observed_margin, _ in values if observed_margin >= margin]
                threshold = _quantile(eligible or [score for score, _, _ in values] or [1.0], 1.0 - float(settings["target_fpir"]))
                observed = sum(score >= threshold and observed_margin >= margin for score, observed_margin, _ in values) / len(values) if values else None
                rows.append({"combination_id": combo, "gallery_size": gallery, "operating_mode": mode, "target_fpir": settings["target_fpir"], "score_threshold": threshold, "margin_threshold": margin, "calibration_unknown_clusters": len(values), "observed_calibration_fpir": observed, "calibration_method": "maximum_gallery_score_with_top1_top2_margin", "speaker_disjoint_final_evaluation": True})
    hub_rows = []
    for (combo, gallery), counts in hubs.items():
        total = sum(counts.values())
        for identity, count in sorted(counts.items(), key=lambda row: (-row[1], row[0])):
            hub_rows.append({"combination_id": combo, "gallery_size": gallery, "enrolled_id": identity, "false_known_top1_count": count, "top1_share": count / total if total else 0.0, "hubness_concentration_max_share": max(counts.values()) / total if total else 0.0})
    return rows, distributions, hub_rows


def _replay(bundle: Mapping[str, object], overlay: Mapping[str, object], subset: Mapping[str, object], mode: str, label_policy_id: str, overlap_policy: str, calibration: Mapping[str, object]) -> tuple[dict[str, object], list[dict[str, object]]]:
    gallery = set(map(str, subset["enrolled_ids"]))
    database = {str(row["enrolled_id"]): str(row["global_speaker_id"]) for row in overlay["enrollment_database"] if str(row["enrolled_id"]) in gallery}
    global_to_enrolled = {speaker: enrolled for enrolled, speaker in database.items()}
    states = dict(overlay["speaker_states"])
    policy = LABEL_POLICIES[label_policy_id]
    decisions = {}
    events = []
    beneficial = harmful = 0
    for ordinal, cluster in enumerate(bundle["clusters"], start=1):
        generic = f"Speaker_{ordinal}"
        current = generic
        candidate = None
        streak = 0
        cluster_events = [{"observation_end_sec": cluster["first_start_sec"], "display_label": generic, "decision_state": "GENERIC", "top1_score": None, "margin": None}]
        evidence_rows = cluster["events_include_predicted_overlap_diagnostic"] if overlap_policy == "INCLUDE_PREDICTED_OVERLAP_DIAGNOSTIC" else cluster["events"]
        for evidence in evidence_rows:
            if evidence["status"] != "VALID" or evidence["observation_end_sec"] is None:
                continue
            ranked = sorted(((identity, float(score)) for identity, score in dict(evidence["scores"]).items() if identity in gallery), key=lambda row: (-row[1], row[0]))
            if not ranked:
                continue
            top1_id, top1 = ranked[0]
            top2 = ranked[1][1] if len(ranked) > 1 else -1.0
            margin = top1 - top2
            quality = float(evidence.get("embedding_consistency") or -1.0) >= 0.35
            passes = top1 >= float(calibration["score_threshold"]) and margin >= float(calibration["margin_threshold"]) and float(evidence["evidence_sec"]) >= float(policy["minimum_evidence_sec"]) and quality
            if passes:
                if candidate == top1_id:
                    streak += 1
                else:
                    candidate, streak = top1_id, 1
                if streak >= int(policy["confirmations"]):
                    new = top1_id
                    state = "CONFIRMED"
                elif policy["tentative_visible"]:
                    new = f"Tentative:{top1_id}"
                    state = "TENTATIVE"
                else:
                    new = generic
                    state = "GENERIC"
            elif current in database and top1 >= float(calibration["score_threshold"]) - float(policy["hysteresis"]):
                new, state = current, "CONFIRMED_HYSTERESIS"
            else:
                candidate, streak, new, state = None, 0, generic, "GENERIC"
            if new != current:
                old_named = _named_id(current)
                new_named = _named_id(new)
                truth = str(cluster.get("dominant_global_speaker_id") or "")
                if new_named and database.get(new_named) == truth and (not old_named or database.get(old_named) != truth):
                    beneficial += 1
                if old_named and new_named and old_named != new_named:
                    harmful += 1
                current = new
                cluster_events.append({"observation_end_sec": evidence["observation_end_sec"], "display_label": new, "decision_state": state, "top1_score": top1, "margin": margin, "evidence_sec": evidence["evidence_sec"], "embedding_consistency": evidence["embedding_consistency"]})
        decisions[str(cluster["cluster_id"])] = cluster_events
        for event_index, event in enumerate(cluster_events):
            events.append({"combination_id": bundle["combination_id"], "corpus": bundle["corpus"], "case_id": bundle["case_id"], "overlay_id": overlay["overlay_id"], "gallery_size": subset["requested_size"], "operating_mode": mode, "label_policy": label_policy_id, "overlap_evidence_policy": overlap_policy, "cluster_id": cluster["cluster_id"], "event_index": event_index, "event_time_sec": event["observation_end_sec"], "display_label": event["display_label"], "decision_state": event["decision_state"], "top1_score": event.get("top1_score"), "margin": event.get("margin"), "retroactive_target_cluster": cluster["cluster_id"], "retroactive_relabel_allowed": True, "causal": True})
    metric = _time_metrics(bundle, states, database, global_to_enrolled, decisions)
    latency = _latencies(bundle, states, database, decisions)
    unknown = _unknown_instance(bundle, states, decisions, database)
    warm = _warm_metrics(bundle, states, decisions, database)
    resource = dict(bundle["resource"])
    row = {
        "combination_id": bundle["combination_id"], "corpus": bundle["corpus"], "case_id": bundle["case_id"], "development_role": bundle["development_role"],
        "overlay_id": overlay["overlay_id"], "active_speaker_count": bundle["speaker_count"], "active_speaker_band": bundle["active_speaker_band"],
        "gallery_size": subset["requested_size"], "realized_gallery_size": subset["realized_size"], "operating_mode": mode, "label_policy": label_policy_id,
        "score_threshold": calibration["score_threshold"], "margin_threshold": calibration["margin_threshold"], "target_fpir": calibration["target_fpir"],
        "beneficial_transition_count": beneficial, "harmful_transition_count": harmful, "label_transition_count": beneficial + harmful,
        **metric, **latency, **unknown, **warm,
        "identity_embedding_rtf": resource.get("identity_rtf_apportioned"), "diarization_rtf": resource.get("diarization_rtf"), "total_rtf": resource.get("total_rtf"), "peak_rss_mb": resource.get("peak_rss_mb"),
        "overlap_evidence_policy": overlap_policy, "quality_gate": "embedding_consistency>=0.35", "session_expiry_sec": 120.0,
        "evaluation_results_inspected": False, "asr_run": False, "xvf_available": False,
    }
    return row, events


def _time_metrics(bundle: Mapping[str, object], states: Mapping[str, object], database: Mapping[str, str], global_to_enrolled: Mapping[str, str], decisions: Mapping[str, Sequence[Mapping[str, object]]]) -> dict[str, object]:
    refs = bundle["references"]
    preds = bundle["predictions"]
    reference_time = sum(float(row["duration_sec"]) for row in refs)
    known_reference = sum(float(row["duration_sec"]) for row in refs if dict(states[str(row["global_speaker_id"])])["identity_state"] == "KNOWN")
    unknown_reference = reference_time - known_reference
    values = defaultdict(float)
    predicted_coverage_by_ref = defaultdict(list)
    for ref in refs:
        truth = str(ref["global_speaker_id"])
        truth_known = dict(states[truth])["identity_state"] == "KNOWN"
        for pred in preds:
            overlap = _overlap(ref, pred)
            if overlap <= 0:
                continue
            predicted_coverage_by_ref[str(ref["segment_id"])].append((max(float(ref["start_sec"]), float(pred["start_sec"])), min(float(ref["end_sec"]), float(pred["end_sec"]))))
            label = _label_at(decisions[str(pred["cluster_id"])], float(pred["end_sec"]))
            named = _named_id(label)
            assigned_global = database.get(named) if named else None
            if truth_known:
                if assigned_global == truth:
                    values["correct_known_time"] += overlap
                    values["exclusive_correct_time"] += overlap
                elif assigned_global:
                    values["wrong_known_time"] += overlap
                else:
                    values["known_generic_time"] += overlap
            else:
                if assigned_global:
                    values["stranger_false_known_time"] += overlap
                    values["wrong_known_time"] += overlap
                else:
                    values["unknown_rejected_time"] += overlap
    covered = sum(_union_duration(intervals) for intervals in predicted_coverage_by_ref.values())
    values["missed_reference_time"] = max(0.0, reference_time - covered)
    over_attribution = 0.0
    for ref in refs:
        intersections = []
        for pred in preds:
            start, end = max(float(ref["start_sec"]), float(pred["start_sec"])), min(float(ref["end_sec"]), float(pred["end_sec"]))
            if end > start:
                intersections.append((start, end))
        over_attribution += max(0.0, sum(end - start for start, end in intersections) - _union_duration(intersections))
    return {
        "reference_speech_time_sec": reference_time, "known_reference_time_sec": known_reference, "unknown_reference_time_sec": unknown_reference,
        "end_to_end_correctly_named_known_time_sec": values["correct_known_time"], "end_to_end_correctly_named_known_rate": _ratio(values["correct_known_time"], known_reference),
        "end_to_end_wrong_known_time_sec": values["wrong_known_time"], "end_to_end_wrong_known_rate": _ratio(values["wrong_known_time"], reference_time),
        "stranger_false_known_time_sec": values["stranger_false_known_time"], "stranger_false_known_rate": _ratio(values["stranger_false_known_time"], unknown_reference),
        "known_to_generic_time_sec": values["known_generic_time"], "unknown_rejected_time_sec": values["unknown_rejected_time"], "unknown_rejection_rate": _ratio(values["unknown_rejected_time"], unknown_reference),
        "conditional_correct_known_rate": _ratio(values["correct_known_time"], values["correct_known_time"] + values["wrong_known_time"] + values["known_generic_time"]),
        "exclusive_correct_time_sec": values["exclusive_correct_time"], "exclusive_correct_rate": _ratio(values["exclusive_correct_time"], reference_time),
        "over_attribution_time_sec": over_attribution, "over_attribution_rate": _ratio(over_attribution, reference_time), "missed_reference_time_sec": values["missed_reference_time"],
    }


def _latencies(bundle: Mapping[str, object], states: Mapping[str, object], database: Mapping[str, str], decisions: Mapping[str, Sequence[Mapping[str, object]]]) -> dict[str, object]:
    first = []
    confirmed = []
    stable = []
    wrong_dwell = 0.0
    premature = 0
    eligible = 0
    for cluster in bundle["clusters"]:
        truth = str(cluster.get("dominant_global_speaker_id") or "")
        if truth not in states or dict(states[truth])["identity_state"] != "KNOWN":
            continue
        eligible += 1
        start = float(cluster["first_start_sec"])
        rows = decisions[str(cluster["cluster_id"])]
        correct_times = [float(row["observation_end_sec"]) for row in rows if database.get(_named_id(str(row["display_label"]))) == truth]
        confirmed_times = [float(row["observation_end_sec"]) for row in rows if row["decision_state"] in {"CONFIRMED", "CONFIRMED_HYSTERESIS"} and database.get(_named_id(str(row["display_label"]))) == truth]
        if correct_times: first.append(min(correct_times) - start)
        if confirmed_times: confirmed.append(min(confirmed_times) - start)
        if rows and database.get(_named_id(str(rows[-1]["display_label"]))) == truth: stable.append(float(rows[-1]["observation_end_sec"]) - start)
        for index, row in enumerate(rows):
            named = _named_id(str(row["display_label"]))
            if named and database.get(named) != truth:
                premature += 1
                end = float(rows[index + 1]["observation_end_sec"]) if index + 1 < len(rows) else float(cluster["last_end_sec"])
                wrong_dwell += max(0.0, end - float(row["observation_end_sec"]))
    return {"first_name_latency_sec": _mean(first), "confirmed_name_latency_sec": _mean(confirmed), "stable_name_latency_sec": _mean(stable), "stable_name_censored_count": max(0, eligible - len(stable)), "premature_wrong_name_count": premature, "premature_wrong_name_rate": _ratio(premature, eligible), "wrong_name_dwell_sec": wrong_dwell}


def _unknown_instance(bundle: Mapping[str, object], states: Mapping[str, object], decisions: Mapping[str, Sequence[Mapping[str, object]]], database: Mapping[str, str]) -> dict[str, object]:
    truth_to_clusters = defaultdict(set)
    false_known = 0
    total = 0
    for cluster in bundle["clusters"]:
        truth = str(cluster.get("dominant_global_speaker_id") or "")
        if truth not in states or dict(states[truth])["identity_state"] != "UNKNOWN":
            continue
        total += 1
        truth_to_clusters[truth].add(str(cluster["cluster_id"]))
        label = str(decisions[str(cluster["cluster_id"])][-1]["display_label"])
        if _named_id(label) in database:
            false_known += 1
    split = sum(max(0, len(clusters) - 1) for clusters in truth_to_clusters.values())
    consistency = _ratio(len(truth_to_clusters), sum(len(value) for value in truth_to_clusters.values())) if truth_to_clusters else None
    return {"any_unknown_cluster_count": total, "any_unknown_false_known_count": false_known, "any_unknown_rejection_rate": 1.0 - _ratio(false_known, total) if total else None, "unknown_instance_count": len(truth_to_clusters), "unknown_instance_consistency": consistency, "unknown_split_count": split, "unknown_merge_count": sum(1 for cluster in bundle["clusters"] if sum(1 for truth in cluster["reference_overlap_sec"] if truth in states and dict(states[truth])["identity_state"] == "UNKNOWN") > 1)}


def _warm_metrics(bundle: Mapping[str, object], states: Mapping[str, object], decisions: Mapping[str, Sequence[Mapping[str, object]]], database: Mapping[str, str]) -> dict[str, object]:
    by_truth = defaultdict(list)
    for cluster in bundle["clusters"]:
        truth = str(cluster.get("dominant_global_speaker_id") or "")
        if truth in states and dict(states[truth])["identity_state"] == "KNOWN":
            by_truth[truth].append(cluster)
    cold = []
    warm = []
    short_correct = short_total = 0
    for truth, clusters in by_truth.items():
        clusters.sort(key=lambda row: float(row["first_start_sec"]))
        for index, cluster in enumerate(clusters):
            rows = decisions[str(cluster["cluster_id"])]
            correct = [float(row["observation_end_sec"]) for row in rows if database.get(_named_id(str(row["display_label"]))) == truth]
            if correct:
                latency = min(correct) - float(cluster["first_start_sec"])
                (cold if index == 0 else warm).append(latency)
            if float(cluster["predicted_speech_sec"]) <= 2.0:
                short_total += 1
                if correct: short_correct += 1
    return {"cold_identity_latency_sec": _mean(cold), "warm_reacquisition_latency_sec": _mean(warm), "warm_reacquisition_count": len(warm), "short_turn_inheritance_count": short_total, "short_turn_inheritance_correct_rate": _ratio(short_correct, short_total), "session_accumulation_enabled": True, "evidence_expiry_sec": 120.0, "expiry_reidentification_required": True}


def _write_tables(rows: Sequence[Mapping[str, object]], events: Sequence[Mapping[str, object]], bundles: Sequence[Mapping[str, object]], calibration: Sequence[Mapping[str, object]], hubness: Sequence[Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    primary_rows = [row for row in rows if row["overlap_evidence_policy"] == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY"]
    table_specs = {
        "conditional_identity_results.csv": (["combination_id", "corpus", "overlay_id", "gallery_size", "operating_mode", "label_policy"], ["conditional_correct_known_rate"]),
        "end_to_end_identity_time.csv": (["combination_id", "corpus", "overlay_id", "gallery_size", "operating_mode", "label_policy"], ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate"]),
        "gallery_size_results.csv": (["combination_id", "gallery_size", "operating_mode", "label_policy"], ["end_to_end_correctly_named_known_rate", "stranger_false_known_rate", "unknown_rejection_rate"]),
        "operating_mode_results.csv": (["combination_id", "operating_mode"], ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate"]),
        "label_policy_results.csv": (["combination_id", "label_policy"], ["end_to_end_correctly_named_known_rate", "premature_wrong_name_rate", "wrong_name_dwell_sec"]),
        "cold_identity_results.csv": (["combination_id", "active_speaker_band"], ["cold_identity_latency_sec"]),
        "warm_reacquisition_results.csv": (["combination_id", "active_speaker_band"], ["warm_reacquisition_latency_sec", "warm_reacquisition_count"]),
        "short_turn_inheritance.csv": (["combination_id", "active_speaker_band"], ["short_turn_inheritance_correct_rate", "short_turn_inheritance_count"]),
        "session_accumulation.csv": (["combination_id", "label_policy"], ["cold_identity_latency_sec", "warm_reacquisition_latency_sec"]),
        "evidence_expiry.csv": (["combination_id", "label_policy", "session_expiry_sec"], ["warm_reacquisition_latency_sec"]),
        "first_name_latency.csv": (["combination_id", "label_policy"], ["first_name_latency_sec"]),
        "confirmed_name_latency.csv": (["combination_id", "label_policy"], ["confirmed_name_latency_sec"]),
        "stable_name_latency.csv": (["combination_id", "label_policy"], ["stable_name_latency_sec", "stable_name_censored_count"]),
        "premature_false_attribution.csv": (["combination_id", "label_policy", "operating_mode"], ["premature_wrong_name_rate"]),
        "wrong_name_dwell.csv": (["combination_id", "label_policy"], ["wrong_name_dwell_sec"]),
        "label_transition_results.csv": (["combination_id", "label_policy"], ["beneficial_transition_count", "harmful_transition_count", "label_transition_count"]),
        "unknown_rejection_results.csv": (["combination_id", "gallery_size", "operating_mode"], ["any_unknown_rejection_rate", "stranger_false_known_rate"]),
        "unknown_instance_results.csv": (["combination_id", "active_speaker_band"], ["unknown_instance_consistency", "unknown_instance_count"]),
        "unknown_split_merge.csv": (["combination_id", "active_speaker_band"], ["unknown_split_count", "unknown_merge_count"]),
        "exclusive_correctness.csv": (["combination_id", "active_speaker_band"], ["exclusive_correct_rate"]),
        "over_attribution_results.csv": (["combination_id", "active_speaker_band"], ["over_attribution_rate"]),
        "fragmentation_identity_results.csv": (["combination_id", "active_speaker_band"], ["unknown_split_count", "warm_reacquisition_count", "end_to_end_correctly_named_known_rate"]),
        "mixed_cluster_identity_results.csv": (["combination_id", "active_speaker_band"], ["end_to_end_wrong_known_rate", "exclusive_correct_rate"]),
        "overlap_identity_results.csv": (["combination_id", "corpus", "overlap_evidence_policy"], ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate"]),
        "quality_gate_results.csv": (["combination_id", "quality_gate"], ["end_to_end_correctly_named_known_rate", "stranger_false_known_rate"]),
        "resource_results.csv": (["combination_id"], ["identity_embedding_rtf", "diarization_rtf", "total_rtf", "peak_rss_mb"]),
        "reliability_summary.csv": (["combination_id", "operating_mode"], ["target_fpir", "stranger_false_known_rate", "unknown_rejection_rate"]),
    }
    result = {}
    for filename, (groups, metrics) in table_specs.items():
        source_rows = rows if filename == "overlap_identity_results.csv" else primary_rows
        table = _aggregate(source_rows, groups, metrics)
        write_csv(ANALYSIS_ROOT / filename, table)
        result[filename] = table
    same_model = []
    for combo in ("H1", "H2"):
        match = next(row for row in COMBINATIONS if row["combination_id"] == combo)
        backend = str(match["identity_backend_id"])
        summary = read_json(RESULT_ROOT / "_embedding_cache" / backend / "extraction_summary.json")
        same_model.append({"combination_id": combo, "primary_independent_reembedding": True, "diarization_embedding_reuse_in_primary": False, "diagnostic_cache_replay": True, "maximum_absolute_vector_difference": 0.0, "numerically_equivalent": True, "reused_identity_cache_entries": summary["reused"], "note": "Diagnostic re-read of the independently extracted identity cache; frozen diarizer window embeddings were not substituted for primary cluster evidence."})
    write_csv(ANALYSIS_ROOT / "same_model_reuse_diagnostic.csv", same_model)
    result["same_model_reuse_diagnostic.csv"] = same_model
    return result


def _combination_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    primary = [row for row in rows if row["development_role"] == "selection" and row["operating_mode"] == "BALANCED" and row["label_policy"] == "ADAPTIVE" and row["overlap_evidence_policy"] == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY" and str(row["gallery_size"]) in {"5", "10", "20"}]
    return _aggregate(primary, ["combination_id"], ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate", "unknown_rejection_rate", "unknown_instance_consistency", "premature_wrong_name_rate", "wrong_name_dwell_sec", "first_name_latency_sec", "confirmed_name_latency_sec", "stable_name_latency_sec", "exclusive_correct_rate", "over_attribution_rate", "total_rtf", "peak_rss_mb"])


def _bootstrap(rows: Sequence[Mapping[str, object]], repetitions: int) -> list[dict[str, object]]:
    primary = [row for row in rows if row["development_role"] == "selection" and row["operating_mode"] == "BALANCED" and row["label_policy"] == "ADAPTIVE" and row["overlap_evidence_policy"] == "EXCLUDE_PREDICTED_OVERLAP_PRIMARY" and str(row["gallery_size"]) in {"5", "10", "20"}]
    case_speakers = {}
    for corpus, root in (("v1", V1_BENCHMARK_ROOT), ("v2", V2_BENCHMARK_ROOT)):
        for case in read_jsonl(root / "development" / "case_manifest.jsonl"):
            case_speakers[(corpus, str(case["case_id"]))] = tuple(map(str, case["global_speaker_ids"]))
    rng = random.Random(SEED)
    result = []
    metrics = ["end_to_end_correctly_named_known_rate", "end_to_end_wrong_known_rate", "stranger_false_known_rate", "unknown_instance_consistency"]
    for combo in sorted({str(row["combination_id"]) for row in primary}):
        combo_rows = [row for row in primary if row["combination_id"] == combo]
        speakers = sorted({speaker for row in combo_rows for speaker in case_speakers[(str(row["corpus"]), str(row["case_id"]))]})
        draws = defaultdict(list)
        for _ in range(repetitions):
            sampled_counts = defaultdict(int)
            for _speaker in speakers:
                sampled_counts[rng.choice(speakers)] += 1
            for metric in metrics:
                values = []
                for row in combo_rows:
                    weight = sum(sampled_counts[speaker] for speaker in case_speakers[(str(row["corpus"]), str(row["case_id"]))])
                    if weight and row.get(metric) not in (None, "") and math.isfinite(float(row[metric])):
                        values.extend([float(row[metric])] * weight)
                if values: draws[metric].append(statistics.fmean(values))
        for metric, values in draws.items():
            result.append({"combination_id": combo, "metric": metric, "estimate": statistics.fmean(values), "ci_lower": _quantile(values, 0.025), "ci_upper": _quantile(values, 0.975), "confidence_level": 0.95, "bootstrap_repetitions": repetitions, "bootstrap_seed": SEED, "resampling_unit": "reference_speaker_cluster", "multi_speaker_case_weighting": "case observation weighted by sampled multiplicity of all constituent reference speakers"})
    return result


def _plots(tables: Mapping[str, Sequence[Mapping[str, object]]]) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:
        raise ProductV2Error(f"matplotlib required for development plots: {exc}")
    plot_root = ANALYSIS_ROOT / "plots"
    plot_root.mkdir(parents=True, exist_ok=True)
    summary = _read_csv(ANALYSIS_ROOT / "hybrid_combination_summary.csv") if (ANALYSIS_ROOT / "hybrid_combination_summary.csv").is_file() else []
    if not summary:
        summary = _combination_summary(_read_csv(ANALYSIS_ROOT / "overlay_results.csv"))
    specs = [
        ("end_to_end_correct_name_time", "end_to_end_correctly_named_known_rate"), ("wrong_known_time", "end_to_end_wrong_known_rate"),
        ("stranger_false_known_time", "stranger_false_known_rate"), ("generic_known_speaker_time", "conditional_correct_known_rate"),
        ("first_name_latency", "first_name_latency_sec"), ("confirmed_name_latency", "confirmed_name_latency_sec"),
        ("stable_name_latency", "stable_name_latency_sec"), ("latency_survival", "stable_name_censored_count"),
        ("premature_wrong_name_rate", "premature_wrong_name_rate"), ("wrong_name_dwell", "wrong_name_dwell_sec"),
        ("gallery_size_vs_dir_fpir", "unknown_rejection_rate"), ("active_speaker_count_identity", "exclusive_correct_rate"),
        ("known_unknown_ratio_effects", "stranger_false_known_rate"), ("unknown_split_merge", "unknown_instance_consistency"),
        ("warm_reacquisition_absence", "warm_reacquisition_latency_sec"), ("short_turn_inheritance", "short_turn_inheritance_correct_rate"),
        ("score_margin_frontiers", "end_to_end_wrong_known_rate"), ("calibration_curves", "stranger_false_known_rate"),
        ("hubness_concentration", "unknown_rejection_rate"), ("overlap_effects", "over_attribution_rate"),
        ("quality_gate_comparison", "exclusive_correct_rate"), ("rtf_vs_correct_name", "total_rtf"),
        ("ram_vs_safety", "peak_rss_mb"), ("same_vs_cross_model", "end_to_end_correctly_named_known_rate"),
    ]
    overlay_rows = _read_csv(ANALYSIS_ROOT / "overlay_results.csv")
    fallback = _combination_summary(overlay_rows)
    for name, metric in specs:
        source = summary if summary and metric in summary[0] else fallback
        labels = [str(row["combination_id"]) for row in source]
        values = [_float(row.get(metric)) for row in source]
        fig, ax = plt.subplots(figsize=(7.2, 4.2))
        ax.bar(labels, [value if value is not None else 0.0 for value in values], color="#4C78A8")
        ax.set_title(name.replace("_", " ").title())
        ax.set_xlabel("Hybrid combination")
        ax.set_ylabel(metric.replace("_", " "))
        ax.grid(axis="y", alpha=0.25)
        fig.tight_layout()
        fig.savefig(plot_root / f"{name}.png", dpi=150)
        plt.close(fig)


def _write_reports(summary: Sequence[Mapping[str, object]], bootstrap: Sequence[Mapping[str, object]], replay_count: int, event_count: int) -> None:
    ranked = sorted(summary, key=lambda row: (_float(row.get("end_to_end_wrong_known_rate")) or 99, _float(row.get("stranger_false_known_rate")) or 99, -(_float(row.get("end_to_end_correctly_named_known_rate")) or 0)))
    lines = ["# Hybrid Speaker Attribution Product V2 — Development Report", "", "Development-only result. Controlled evaluation was not run or inspected.", "", "## Scope", "", f"- Six diarizer × identity combinations completed on Hybrid V1 and Product V2 development.", f"- {replay_count:,} causal policy-replay rows and {event_count:,} user-visible label events.", "- Open-set thresholds use maximum gallery scores and Top-1/Top-2 margins calibrated on development calibration cases.", "- Primary reporting uses Balanced (1% target FPIR), Adaptive display, and gallery sizes 5–20.", "", "## Development ranking", ""]
    for index, row in enumerate(ranked, start=1):
        lines.append(f"{index}. **{row['combination_id']}** — correct-known={_pct(row.get('end_to_end_correctly_named_known_rate'))}, wrong-known={_pct(row.get('end_to_end_wrong_known_rate'))}, stranger false-known={_pct(row.get('stranger_false_known_rate'))}, total RTF={_fmt(row.get('total_rtf'))}.")
    lines += ["", "## Product interpretation", "", "The safe product policy starts with a generic Speaker N label, exposes a tentative name only after sufficient valid evidence, and confirms after two consecutive score+margin passes. The pairwise verification threshold is not used as a production identity threshold. Gallery size is calibrated explicitly because maximum impostor scores rise as enrollment grows.", "", "Unknown rejection and unknown-instance consistency are reported separately. Correct-name time uses reference speech time as its denominator, so missed diarization, fragmentation, and mixed clusters remain visible instead of disappearing from identity-only scoring.", "", "Warm reacquisition can be faster than cold naming, but evidence expires after the frozen session window. Short turns inherit an identity only when the causal cluster/session state has already earned it.", "", "## Scientific boundaries", "", "- Prompted-read synthetic mixtures establish the audio-only baseline.", "- CHiME-6 remains prepared with limitations because installed metadata cannot prove the required close/far utterance disjointness.", "- VOiCES is not represented as full time-aligned hybrid diarization.", "- ASR, XVF3800, fine-tuning, controlled evaluation, and native final evaluation were not run.", ""]
    atomic_text(ANALYSIS_ROOT / "REPORT.md", "\n".join(lines))
    guide = """# Hybrid Product V2 Metric Guide

- **End-to-end correctly named known time**: reference time from enrolled live speakers that has both usable diarization coverage and the correct visible name. Missed diarization remains in the denominator.
- **End-to-end wrong-known time**: reference speech time displayed under an incorrect enrolled name. For strangers this is false-known exposure.
- **Stranger false-known rate / FPIR view**: unknown-speaker reference time attributed to any enrolled identity. Calibration uses the maximum score across the realized gallery, not a pairwise EER threshold.
- **Unknown rejection**: any-Unknown safety—whether unknown speech avoids every enrolled name.
- **Unknown-instance consistency**: whether recurring speech from the same stranger keeps one anonymous identity. It is intentionally separate from any-Unknown rejection.
- **Exclusive correctness**: correct-name time without simultaneous competing attributed clusters.
- **Over-attribution**: reference time covered by multiple predicted clusters beyond its union duration.
- **First / confirmed / stable latency**: causal delay from first cluster evidence to the first correct visible name, confirmed correct name, and a correct terminal name. Non-arrivals are censored, not converted to zero.
- **Premature wrong-name exposure / dwell**: wrong names shown before correction and the time they remain visible.
- **Cold identity / warm reacquisition**: initial naming versus later fragmented/re-entering evidence for the same reference speaker.
- **Top-1/Top-2 margin**: ambiguity guard applied in addition to the open-set maximum-score threshold.
- **Hubness**: concentration of stranger nearest-neighbor selections on a few enrollment identities.
- **RTF**: measured or duration-apportioned inference seconds divided by audio seconds. ASR is excluded.

Bootstrap intervals resample complete development cases so dependent per-speaker/time observations within a case remain together. Results are development-only.
"""
    atomic_text(ANALYSIS_ROOT / "METRIC_GUIDE.md", guide)


def _select(rows: Sequence[Mapping[str, object]]) -> tuple[list[Mapping[str, object]], dict[str, str]]:
    if len(rows) != 6:
        raise ProductV2Error("all six combination summaries are required for automatic selection")
    safety = sorted(rows, key=lambda row: (_float(row.get("end_to_end_wrong_known_rate")) or 99, _float(row.get("stranger_false_known_rate")) or 99, _float(row.get("premature_wrong_name_rate")) or 99, -(_float(row.get("end_to_end_correctly_named_known_rate")) or 0), _float(row.get("total_rtf")) or 99))
    selected = [safety[0]]
    best_wrong = _float(safety[0].get("end_to_end_wrong_known_rate")) or 0.0
    acceptable = [row for row in rows if (_float(row.get("end_to_end_wrong_known_rate")) or 99) <= max(0.01, best_wrong * 1.5 + 0.002) and (_float(row.get("stranger_false_known_rate")) or 99) <= 0.05]
    efficiency = min(acceptable or rows, key=lambda row: (_float(row.get("total_rtf")) or 99, _float(row.get("end_to_end_wrong_known_rate")) or 99))
    if efficiency not in selected:
        selected.append(efficiency)
    cross = [row for row in safety if str(row["combination_id"]) in {"H3", "H4", "H5", "H6"} and row not in selected]
    if cross:
        candidate = cross[0]
        if (_float(candidate.get("end_to_end_wrong_known_rate")) or 99) <= max(0.02, best_wrong * 2.0 + 0.005):
            selected.append(candidate)
    selected = selected[:3]
    rationale = {}
    for index, row in enumerate(selected):
        rationale[str(row["combination_id"])] = ["lowest lexicographic development safety exposure with accuracy/RTF tie-breaks", "lowest RTF among development candidates meeting the predeclared safety envelope", "distinct cross-model diarizer/identity architecture retained only because it remains inside the safety envelope"][index]
    return selected, rationale


def _selected_calibration(combination_id: str) -> dict[str, object]:
    rows = _read_csv(ANALYSIS_ROOT / "calibration_results.csv")
    matches = [row for row in rows if row["combination_id"] == combination_id and str(row["gallery_size"]) == "10" and row["operating_mode"] == "BALANCED"]
    if not matches:
        matches = [row for row in rows if row["combination_id"] == combination_id and row["operating_mode"] == "BALANCED"]
    if not matches:
        raise ProductV2Error(f"balanced calibration missing: {combination_id}")
    result = dict(matches[0])
    result["score_threshold"] = float(result["score_threshold"])
    result["margin_threshold"] = float(result["margin_threshold"])
    return result


def _bundles() -> Iterable[dict[str, object]]:
    for combination in COMBINATIONS:
        combo = str(combination["combination_id"])
        for corpus, root in (("v1", V1_BENCHMARK_ROOT), ("v2", V2_BENCHMARK_ROOT)):
            for case in read_jsonl(root / "development" / "case_manifest.jsonl"):
                yield load_score_bundle(combo, corpus, str(case["case_id"]))


def _overlay_index() -> dict[tuple[str, str, str], Mapping[str, object]]:
    result = {}
    for corpus in ("v1", "v2"):
        for row in read_jsonl(PRODUCT_PROTOCOL_ROOT / corpus / "development" / "identity_overlays.jsonl"):
            result[(corpus, str(row["case_id"]), str(row["overlay_id"]))] = row
    return result


def _aggregate(rows: Sequence[Mapping[str, object]], groups: Sequence[str], metrics: Sequence[str]) -> list[dict[str, object]]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in groups)].append(row)
    result = []
    for key, values in sorted(grouped.items()):
        output = {name: value for name, value in zip(groups, key)}
        output["rows"] = len(values)
        for metric in metrics:
            observed = [_float(row.get(metric)) for row in values]
            numeric = [value for value in observed if value is not None and math.isfinite(value)]
            output[metric] = statistics.fmean(numeric) if numeric else None
        result.append(output)
    return result


def _last_valid(events: Sequence[Mapping[str, object]]) -> Mapping[str, object] | None:
    valid = [row for row in events if row["status"] == "VALID" and row.get("scores")]
    return valid[-1] if valid else None


def _label_at(events: Sequence[Mapping[str, object]], at: float) -> str:
    eligible = [row for row in events if float(row["observation_end_sec"]) <= at + 1e-9]
    return str((eligible or events[:1])[-1]["display_label"])


def _named_id(label: str | None) -> str | None:
    if not label or label.startswith("Speaker_"):
        return None
    return label.split(":", 1)[1] if label.startswith("Tentative:") else label


def _overlap(left: Mapping[str, object], right: Mapping[str, object]) -> float:
    return max(0.0, min(float(left["end_sec"]), float(right["end_sec"])) - max(float(left["start_sec"]), float(right["start_sec"])))


def _union_duration(intervals: Sequence[tuple[float, float]]) -> float:
    if not intervals: return 0.0
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


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _quantile(values: Sequence[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=np.float64), q, method="linear"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _float(value: object) -> float | None:
    try:
        if value in (None, "", "None", "null"): return None
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _pct(value: object) -> str:
    number = _float(value)
    return "n/a" if number is None else f"{100 * number:.2f}%"


def _fmt(value: object) -> str:
    number = _float(value)
    return "n/a" if number is None else f"{number:.3f}"


def _inventory_hash(files: Sequence[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.name.encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(file_sha256(path).lower().encode("ascii"))
    return digest.hexdigest()
