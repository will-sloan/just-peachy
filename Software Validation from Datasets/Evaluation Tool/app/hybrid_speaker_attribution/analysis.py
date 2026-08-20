"""Read-only analysis and compact collection for hybrid attribution results."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import random
import shutil
import statistics
from typing import Iterable, Mapping, Sequence

from app.hybrid_speaker_attribution.contracts import HybridAttributionError, canonical_sha256
from app.hybrid_speaker_attribution.attribution import score_recording
from app.hybrid_speaker_attribution.runner import validate_result


REQUIRED_TABLES = {
    "overall_results.csv": ("tier", "configuration_id", "units", "valid_units", "time_weighted_identity_accuracy", "false_known_rate", "known_identity_accuracy", "unknown_rejection_rate"),
    "recording_results.csv": ("tier", "configuration_id", "pipeline_id", "speaker_backend_id", "case_id", "overlay_id", "valid_output", "time_weighted_identity_accuracy", "false_known_rate", "known_identity_accuracy", "unknown_rejection_rate", "identity_coverage", "fragmentation_count", "merge_count"),
    "overlay_results.csv": ("tier", "configuration_id", "overlay_id", "units", "time_weighted_identity_accuracy", "false_known_rate", "known_identity_accuracy", "unknown_rejection_rate"),
    "known_identity_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "known_identity_accuracy", "wrong_known_rate", "known_to_unknown_rate", "known_reference_time_sec"),
    "unknown_identity_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "unknown_rejection_rate", "false_known_rate", "unknown_reference_time_sec"),
    "false_known_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "false_known_time_sec", "false_known_rate"),
    "identity_latency_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "stable_known_identity_latency_mean_sec", "stable_known_identity_latency_count"),
    "identity_churn_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "identity_churn_count"),
    "reentry_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "reentry_condition", "reentry_comparison_count", "reentry_identity_consistency", "unknown_reentry_comparison_count", "unknown_reentry_consistency", "identity_churn_count"),
    "fragmentation_merge_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "fragmentation_count", "merge_count"),
    "speaker_count_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "reference_speaker_count", "predicted_cluster_count", "speaker_count_error"),
    "turn_cadence_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "turn_cadence", "time_weighted_identity_accuracy", "false_known_rate"),
    "overlap_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "overlap_profile", "time_weighted_identity_accuracy", "false_known_rate"),
    "time_weighted_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "reference_speaker_time_sec", "correct_time_sec", "time_weighted_identity_accuracy", "false_known_time_sec", "false_known_rate"),
    "oracle_diagnostics.csv": ("tier", "configuration_id", "case_id", "overlay_id", "observed_accuracy", "oracle_diarization_accuracy", "diagnostic_gap"),
    "resource_results.csv": ("tier", "configuration_id", "case_id", "overlay_id", "embedding_extraction_wall_sec", "backend_inference_sec", "peak_cpu_memory_mb", "peak_gpu_memory_mb", "cache_observations", "cache_reused_observations_this_invocation", "shared_case_level_cost_repeated_across_overlays", "asr_runtime_sec"),
    "reliability_summary.csv": ("tier", "configuration_id", "planned_units", "valid_units", "invalid_units", "valid_fraction", "scientifically_interpretable"),
}


def analyze(
    *, result_root: Path, output_root: Path, tiers: Sequence[str] = ("development", "evaluation"),
    include_development_curves: bool = False,
) -> dict[str, object]:
    roots = []
    invalid = []
    for tier in tiers:
        for run_path in sorted((result_root / tier).glob("hybrid_*/*/*/*/*/run.json")) if (result_root / tier).is_dir() else ():
            root = run_path.parent
            try:
                validate_result(root)
                roots.append(root)
            except Exception as exc:
                invalid.append({"path": str(root), "error": f"{type(exc).__name__}: {exc}"})
    rows = [_result_row(root) for root in roots]
    output_root.mkdir(parents=True, exist_ok=True)
    tables = _tables(rows, invalid)
    for filename, fields in REQUIRED_TABLES.items():
        _write_csv(output_root / filename, tables.get(filename, []), fields)
    if include_development_curves:
        _development_tables(roots, output_root)
    manifest = {
        "schema_version": "hybrid-speaker-attribution-analysis-manifest.v1",
        "tiers": list(tiers),
        "valid_units": len(rows),
        "invalid_units": len(invalid),
        "configuration_ids": sorted({str(row["configuration_id"]) for row in rows}),
        "contains_non_scientific_units": any(row.get("scientific") is False for row in rows),
        "bootstrap_seed": 3800,
        "bootstrap_repetitions": 500,
        "files": sorted([*REQUIRED_TABLES, "report.md"] + (["development_overall.csv", "threshold_curve.csv", "evidence_duration_curve.csv", "margin_analysis.csv", "false_known_analysis.csv", "identity_latency.csv"] if include_development_curves else [])),
    }
    manifest["analysis_id"] = "hybrid_analysis_" + canonical_sha256(manifest)[:16].lower()
    _write_json(output_root / "analysis_manifest.json", manifest)
    report = _report(manifest, tables)
    (output_root / "report.md").write_text(report, encoding="utf-8", newline="\n")
    return manifest


def collect(
    *, analysis_root: Path, output_root: Path, protocol_root: Path,
    frozen_hybrid_config: Path | None = None,
) -> dict[str, object]:
    manifest = json.loads((analysis_root / "analysis_manifest.json").read_text(encoding="utf-8"))
    if output_root.exists():
        raise HybridAttributionError(f"collection destination already exists: {output_root}")
    output_root.mkdir(parents=True)
    copied = []
    for path in sorted(analysis_root.iterdir()):
        if path.is_file() and path.suffix.lower() in {".json", ".csv", ".md"}:
            destination = output_root / "analysis" / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
            copied.append(f"analysis/{path.name}")
    for relative in ("protocol_summary.json", "selection_config.yaml", "checksums.json", "enrollment_clip_inventory.csv"):
        source = protocol_root / relative
        if source.is_file():
            destination = output_root / "protocol" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(f"protocol/{relative}")
    if frozen_hybrid_config:
        destination = output_root / "frozen" / frozen_hybrid_config.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(frozen_hybrid_config, destination)
        copied.append(f"frozen/{frozen_hybrid_config.name}")
    collection = {
        "schema_version": "hybrid-speaker-attribution-collection.v1",
        "analysis_id": manifest["analysis_id"],
        "files": copied,
        "contains_audio": False,
        "contains_model_assets": False,
        "contains_embedding_cache": False,
    }
    _write_json(output_root / "collection_manifest.json", collection)
    return collection


def _result_row(root: Path) -> dict[str, object]:
    run = _read_json(root / "run.json")
    metrics = _read_json(root / "metrics" / "summary.json")
    oracle = _read_json(root / "oracle" / "oracle_diarization_identity_metrics.json")
    resource = _read_json(root / "resource_usage.json")
    anonymous = dict(metrics.get("anonymous_diarization_metrics") or {})
    return {
        **run,
        **{key: value for key, value in metrics.items() if not isinstance(value, (dict, list))},
        "turn_cadence": anonymous.get("turn_cadence") or run.get("turn_cadence"),
        "overlap_profile": anonymous.get("overlap_profile") or run.get("overlap_profile"),
        "oracle_diarization_accuracy": oracle.get("time_weighted_identity_accuracy"),
        "diagnostic_gap": _difference(oracle.get("time_weighted_identity_accuracy"), metrics.get("time_weighted_identity_accuracy")),
        **resource,
    }


def _tables(rows: list[dict[str, object]], invalid: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    tables: dict[str, list[dict[str, object]]] = {}
    tables["recording_results.csv"] = rows
    mappings = {
        "known_identity_results.csv": rows,
        "unknown_identity_results.csv": rows,
        "false_known_results.csv": rows,
        "identity_latency_results.csv": rows,
        "identity_churn_results.csv": rows,
        "reentry_results.csv": [{**row, "reentry_condition": "controlled_case"} for row in rows],
        "fragmentation_merge_results.csv": rows,
        "speaker_count_results.csv": [{**row, "speaker_count_error": int(row.get("predicted_cluster_count") or 0) - int(row.get("reference_speaker_count") or 0)} for row in rows],
        "turn_cadence_results.csv": rows,
        "overlap_results.csv": rows,
        "time_weighted_results.csv": rows,
        "oracle_diagnostics.csv": [{**row, "observed_accuracy": row.get("time_weighted_identity_accuracy")} for row in rows],
        "resource_results.csv": rows,
    }
    tables.update(mappings)
    tables["overall_results.csv"] = _group(rows, ("tier", "configuration_id"))
    tables["overlay_results.csv"] = _group(rows, ("tier", "configuration_id", "overlay_id"))
    reliability = []
    for row in tables["overall_results.csv"]:
        valid = int(row["valid_units"])
        bad = sum(1 for value in invalid if f"\\{row['tier']}\\{row['configuration_id']}\\" in str(value["path"]))
        planned = valid + bad
        selected = [value for value in rows if value["tier"] == row["tier"] and value["configuration_id"] == row["configuration_id"]]
        scientific = bool(selected) and all(value.get("scientific") is not False for value in selected)
        reliability.append({"tier": row["tier"], "configuration_id": row["configuration_id"], "planned_units": planned, "valid_units": valid, "invalid_units": bad, "valid_fraction": valid / planned if planned else 0.0, "scientifically_interpretable": bool(valid and not bad and scientific)})
    tables["reliability_summary.csv"] = reliability
    return tables


def _group(rows: Sequence[Mapping[str, object]], keys: tuple[str, ...]) -> list[dict[str, object]]:
    grouped: dict[tuple[object, ...], list[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row.get(key) for key in keys), []).append(row)
    result = []
    measures = ("time_weighted_identity_accuracy", "false_known_rate", "known_identity_accuracy", "unknown_rejection_rate", "wrong_known_rate", "known_to_unknown_rate")
    pooled_fields = {
        "time_weighted_identity_accuracy": ("correct_time_sec", "reference_speaker_time_sec"),
        "false_known_rate": ("false_known_time_sec", "unknown_reference_time_sec"),
        "known_identity_accuracy": ("known_correct_time_sec", "known_reference_time_sec"),
        "unknown_rejection_rate": ("unknown_correctly_rejected_time_sec", "unknown_reference_time_sec"),
        "wrong_known_rate": ("wrong_known_time_sec", "known_reference_time_sec"),
        "known_to_unknown_rate": ("known_rejected_as_unknown_time_sec", "known_reference_time_sec"),
    }
    for identity, values in sorted(grouped.items()):
        row = dict(zip(keys, identity))
        row.update({"units": len(values), "valid_units": len(values)})
        for measure in measures:
            observed = [float(value[measure]) for value in values if value.get(measure) is not None]
            numerator_field, denominator_field = pooled_fields[measure]
            numerator = sum(float(value.get(numerator_field) or 0) for value in values)
            denominator = sum(float(value.get(denominator_field) or 0) for value in values)
            row[measure] = numerator / denominator if denominator else (statistics.fmean(observed) if observed else None)
            if measure == "time_weighted_identity_accuracy" and observed:
                row["bootstrap_ci_low"], row["bootstrap_ci_high"] = _bootstrap(observed)
        result.append(row)
    return result


def _bootstrap(values: Sequence[float]) -> tuple[float, float]:
    randomizer = random.Random(3800)
    samples = sorted(statistics.fmean(randomizer.choices(values, k=len(values))) for _ in range(500))
    return samples[int(0.025 * len(samples))], samples[min(len(samples) - 1, int(0.975 * len(samples)))]


def _development_tables(roots: Sequence[Path], output: Path) -> None:
    cluster_scores, evidence = [], []
    for root in roots:
        run = _read_json(root / "run.json")
        for row in _read_jsonl(root / "predictions" / "final_clusters.jsonl"):
            cluster_scores.append({"configuration_id": run["configuration_id"], "case_id": run["case_id"], "overlay_id": run["overlay_id"], "threshold": row["threshold"], "required_margin": row["required_margin"], "top_score": row["top_score"], "observed_margin": row["score_margin"], "decision_state": row["decision_state"]})
        for row in _read_jsonl(root / "predictions" / "evidence_checkpoints.jsonl"):
            evidence.append({"configuration_id": run["configuration_id"], "case_id": run["case_id"], "overlay_id": run["overlay_id"], "evidence_budget_sec": row["evidence_budget_sec"], "decision_state": row["decision_state"], "assigned_label": row["assigned_label"]})
    threshold_rows = []
    margin_rows = []
    by_config: dict[str, list[Path]] = {}
    for root in roots:
        by_config.setdefault(str(_read_json(root / "run.json")["configuration_id"]), []).append(root)
    for config_id, config_roots in sorted(by_config.items()):
        identity = _read_json(config_roots[0] / "configuration_identity.json")
        settings = dict(identity["attribution_settings"])
        product_threshold = float(settings["product_threshold"])
        observed_scores = [
            float(row["top_score"])
            for row in cluster_scores
            if row["configuration_id"] == config_id and row["top_score"] is not None
        ]
        for threshold in _candidate_thresholds(observed_scores, product_threshold):
            rescored = [
                _rescore_root(
                    root,
                    threshold=threshold,
                    margin=float(settings.get("score_margin") or 0.0),
                    minimum_evidence=float(settings["minimum_evidence_duration_sec"]),
                )
                for root in config_roots
            ]
            grouped = _group(rescored, ("tier", "configuration_id"))[0]
            threshold_rows.append({
                **grouped,
                "threshold": threshold,
                "threshold_source": "product_policy" if threshold == product_threshold else "hybrid_development_candidate",
                "selection_status": "OPERATOR_REVIEW_REQUIRED",
            })
        for margin in (0.0, 0.05):
            rescored = [
                _rescore_root(
                    root,
                    threshold=product_threshold,
                    margin=margin,
                    minimum_evidence=float(settings["minimum_evidence_duration_sec"]),
                )
                for root in config_roots
            ]
            grouped = _group(rescored, ("tier", "configuration_id"))[0]
            margin_rows.append({**grouped, "threshold": product_threshold, "required_margin": margin})
    _write_csv(output / "threshold_curve.csv", threshold_rows, ("tier", "configuration_id", "threshold", "threshold_source", "units", "known_identity_accuracy", "wrong_known_rate", "known_to_unknown_rate", "unknown_rejection_rate", "false_known_rate", "time_weighted_identity_accuracy", "selection_status"))
    _write_csv(output / "margin_analysis.csv", margin_rows, ("tier", "configuration_id", "threshold", "required_margin", "units", "known_identity_accuracy", "wrong_known_rate", "known_to_unknown_rate", "unknown_rejection_rate", "false_known_rate", "time_weighted_identity_accuracy"))
    _write_csv(output / "evidence_duration_curve.csv", evidence, ("configuration_id", "case_id", "overlay_id", "evidence_budget_sec", "decision_state", "assigned_label"))
    overall = _group([_result_row(root) for root in roots], ("tier", "configuration_id"))
    _write_csv(output / "development_overall.csv", overall, ("tier", "configuration_id", "units", "time_weighted_identity_accuracy", "false_known_rate", "known_identity_accuracy", "unknown_rejection_rate"))
    result_rows = [_result_row(root) for root in roots]
    _write_csv(output / "false_known_analysis.csv", result_rows, REQUIRED_TABLES["false_known_results.csv"])
    _write_csv(output / "identity_latency.csv", result_rows, REQUIRED_TABLES["identity_latency_results.csv"])


def _rescore_root(root: Path, *, threshold: float, margin: float, minimum_evidence: float) -> dict[str, object]:
    run = _read_json(root / "run.json")
    final = _read_jsonl(root / "predictions" / "final_clusters.jsonl")
    progressive = _read_jsonl(root / "predictions" / "progressive_turns.jsonl")
    turns = _read_jsonl(root / "predictions" / "future_asr_turns.jsonl")
    references = _read_jsonl(root / "references" / "reference_turns.jsonl")
    enrollment = _read_json(root / "enrollment_identity.json")
    first_appearance: dict[str, float] = {}
    for row in turns:
        cluster = str(row["anonymous_cluster_id"])
        first_appearance[cluster] = min(float(row["start_sec"]), first_appearance.get(cluster, float("inf")))
    unknown = {
        cluster: f"Unknown_{index}"
        for index, cluster in enumerate(sorted(first_appearance, key=lambda value: (first_appearance[value], value)), start=1)
    }
    adjusted_final = [_adjust_decision(row, threshold, margin, minimum_evidence, unknown[str(row["cluster_id"])]) for row in final]
    adjusted_progressive = [_adjust_decision(row, threshold, margin, minimum_evidence, unknown[str(row["cluster_id"])]) for row in progressive]
    predicted = [{"recording_id": row["recording_id"], "segment_id": row["turn_id"], "start_sec": row["start_sec"], "end_sec": row["end_sec"], "cluster_id": row["anonymous_cluster_id"]} for row in turns]
    metrics = score_recording(reference_turns=references, predicted_turns=predicted, local_to_global=dict(enrollment["local_to_global_speaker"]), speaker_states=dict(enrollment["speaker_states"]), final_decisions=adjusted_final, progressive_decisions=adjusted_progressive)
    return {"tier": run["tier"], "configuration_id": run["configuration_id"], **{key: value for key, value in metrics.items() if not isinstance(value, (dict, list))}}


def _adjust_decision(row: Mapping[str, object], threshold: float, margin: float, minimum_evidence: float, unknown_label: str) -> dict[str, object]:
    result = dict(row)
    evidence = float(row["evidence_duration_sec"])
    score = row.get("top_score")
    observed_margin = row.get("score_margin")
    if evidence < minimum_evidence:
        result.update({"assigned_label": f"Provisional_{row['cluster_id']}", "decision_state": "PROVISIONAL", "decision_category": "INSUFFICIENT_EVIDENCE"})
    elif score is not None and float(score) >= threshold and (observed_margin is None or float(observed_margin) >= margin):
        result.update({"assigned_label": row["top_candidate_id"], "decision_state": "KNOWN", "decision_category": "KNOWN_CANDIDATE"})
    else:
        result.update({"assigned_label": unknown_label, "decision_state": "UNKNOWN", "decision_category": "OPEN_SET_REJECTION"})
    result["threshold"] = threshold
    result["required_margin"] = margin
    return result


def _candidate_thresholds(scores: Sequence[float], product_threshold: float) -> list[float]:
    if not scores:
        return [product_threshold]
    ordered = sorted(scores)
    candidates = {product_threshold}
    for step in range(21):
        index = round(step * (len(ordered) - 1) / 20)
        candidates.add(round(float(ordered[index]), 8))
    return sorted(candidates)


def _report(manifest: Mapping[str, object], tables: Mapping[str, Sequence[Mapping[str, object]]]) -> str:
    reliability = list(tables["reliability_summary.csv"])
    interpretable = bool(reliability) and all(bool(row["scientifically_interpretable"]) for row in reliability)
    lines = ["# Hybrid speaker attribution analysis", "", f"Analysis ID: `{manifest['analysis_id']}`", "", f"Validated result units: {manifest['valid_units']}", f"Invalid result units: {manifest['invalid_units']}", f"Scientifically interpretable: {'YES' if interpretable else 'NO'}", "", "Known identities are scored by exact enrolled ID. Unknown identities use recording-local permutation-invariant mapping. Anonymous diarization metrics remain separate and unchanged.", ""]
    if manifest.get("contains_non_scientific_units"):
        lines.extend(["NON-SCIENTIFIC SMOKE: engineering contract validation only; do not use these scores for selection.", ""])
    return "\n".join(lines)


def _write_csv(path: Path, rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _difference(left: object, right: object) -> float | None:
    return float(left) - float(right) if left is not None and right is not None else None
