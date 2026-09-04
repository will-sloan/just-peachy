"""Cross-model tables, metric guide, and product-facing findings."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import defaultdict
from typing import Mapping, Sequence

from .contracts import SpeakerDeploymentError, load_config, write_json_atomic


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields = sorted({str(key) for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _number(row: Mapping[str, str], key: str) -> float:
    return float(row[key])


def analyze(result_root: Path, output_root: Path, config_path: Path) -> dict[str, object]:
    config = load_config(config_path)
    result_root = result_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    comparison = []
    mode_rows = []
    all_gallery: list[dict[str, object]] = []
    all_enrollment: list[dict[str, object]] = []
    all_sessions: list[dict[str, object]] = []
    all_trajectories: list[dict[str, object]] = []
    hub_rows: list[dict[str, object]] = []
    summaries = {}
    primary = float(config["primary_fpir_target"])
    for backend in config["backends"]:
        root = result_root / str(backend)
        summary_path = root / "summary.json"
        if not summary_path.is_file():
            raise SpeakerDeploymentError(f"backend is incomplete: {backend}")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status") != "COMPLETE":
            raise SpeakerDeploymentError(f"backend is incomplete: {backend}")
        summaries[str(backend)] = summary
        gallery = _read_csv(root / "gallery_operating_points.csv")
        enrollment = _read_csv(root / "enrollment_operating_modes.csv")
        sessions = _read_csv(root / "session_accumulation.csv")
        trajectories = _read_csv(root / "session_trajectories.csv")
        all_gallery.extend({"backend": backend, **row} for row in gallery)
        all_enrollment.extend({"backend": backend, **row} for row in enrollment)
        all_sessions.extend({"backend": backend, **row} for row in sessions)
        all_trajectories.extend({"backend": backend, **row} for row in trajectories)
        default_rows = [
            row for row in gallery
            if row["dataset"] == "common_voice_60plus"
            and int(row["gallery_size"]) == 272
            and int(row["repetition"]) == 0
            and abs(float(row["fpir_target"]) - primary) < 1e-12
        ]
        if len(default_rows) != 1:
            raise SpeakerDeploymentError(f"missing primary operating point: {backend}")
        row = default_rows[0]
        cv_resource = next(value["resource"] for value in summary["datasets"] if value["dataset"] == "common_voice_60plus")
        boot = summary["bootstrap"]["common_voice_60plus"]["speaker_cluster_bootstrap"]
        original_summary_path = Path(next(value["observation_bundle"] for value in summary["datasets"] if value["dataset"] == "common_voice_60plus")).parent.parent / "result" / "metrics" / "summary.json"
        original_summary = json.loads(original_summary_path.read_text(encoding="utf-8"))
        comparison.append({
            "backend": backend,
            "fpir_target": primary,
            "evaluation_fpir": _number(row, "fpir"),
            "dir_rank1": _number(row, "dir_rank1"),
            "known_wrong_name_rate": _number(row, "known_wrong_name_rate"),
            "known_rejection_rate": _number(row, "known_rejection_rate"),
            "closed_set_top1": _number(row, "closed_set_top1"),
            "score_threshold": _number(row, "score_threshold"),
            "margin_threshold": _number(row, "margin_threshold"),
            "dir_ci_lower": boot["dir_rank1"]["lower"],
            "dir_ci_upper": boot["dir_rank1"]["upper"],
            "fpir_ci_lower": boot["fpir"]["lower"],
            "fpir_ci_upper": boot["fpir"]["upper"],
            "embedding_rtf_observed": cv_resource["embedding_rtf"],
            "mean_extraction_sec_observed": cv_resource["mean_extraction_sec"],
            "largest_unknown_hub_share": summary["hubness"]["common_voice_60plus"]["largest_hub_share"],
            "pairwise_eer_diagnostic": original_summary["calibration_vs_evaluation"]["evaluation_oracle_eer_diagnostic"]["eer"],
            "unknown_rejection_at_old_pairwise_eer_threshold": original_summary["open_set_identification"]["unknown_rejection"]["value"],
        })
        hub_rows.append({"backend": backend, "dataset": "common_voice_60plus", **summary["hubness"]["common_voice_60plus"]})
        eligible_modes = [
            value for value in enrollment
            if value["dataset"] == "common_voice_60plus"
            and abs(float(value["fpir_target"]) - primary) < 1e-12
        ]
        grouped: dict[tuple[int, str], list[dict[str, str]]] = {}
        for value in eligible_modes:
            grouped.setdefault((int(value["enrollment_count"]), value["aggregation_method"]), []).append(value)
        aggregate_modes = []
        for (count, method), values in grouped.items():
            aggregate_modes.append({
                "enrollment_count": count,
                "aggregation_method": method,
                "repetitions": len(values),
                "mean_dir_rank1": sum(_number(value, "dir_rank1") for value in values) / len(values),
                "min_dir_rank1": min(_number(value, "dir_rank1") for value in values),
                "max_dir_rank1": max(_number(value, "dir_rank1") for value in values),
                "mean_fpir": sum(_number(value, "fpir") for value in values) / len(values),
                "mean_known_wrong_name_rate": sum(_number(value, "known_wrong_name_rate") for value in values) / len(values),
            })
        aggregate_modes.sort(key=lambda value: (
            bool(float(value["mean_fpir"]) > primary or float(value["mean_known_wrong_name_rate"]) > float(config["known_wrong_name_rate_cap"])),
            max(0.0, float(value["mean_fpir"]) - primary) + max(0.0, float(value["mean_known_wrong_name_rate"]) - float(config["known_wrong_name_rate_cap"])),
            -float(value["mean_dir_rank1"]),
            float(value["mean_known_wrong_name_rate"]),
            float(value["mean_fpir"]),
        ))
        best = aggregate_modes[0]
        mode_rows.append({
            "backend": backend,
            "recommended_enrollment_count_within_tested_read_speech": int(best["enrollment_count"]),
            "recommended_aggregation_within_tested_read_speech": best["aggregation_method"],
            "selection_repetitions": int(best["repetitions"]),
            "mean_dir_rank1": best["mean_dir_rank1"],
            "min_dir_rank1": best["min_dir_rank1"],
            "max_dir_rank1": best["max_dir_rank1"],
            "mean_evaluation_fpir": best["mean_fpir"],
            "mean_known_wrong_name_rate": best["mean_known_wrong_name_rate"],
            "scope_warning": "comparison is prompted/read Common Voice, not Beaker far-field enrollment",
        })
    comparison.sort(key=lambda row: (
        bool(float(row["known_wrong_name_rate"]) > float(config["known_wrong_name_rate_cap"]) or float(row["evaluation_fpir"]) > primary),
        max(0.0, float(row["known_wrong_name_rate"]) - float(config["known_wrong_name_rate_cap"])) + max(0.0, float(row["evaluation_fpir"]) - primary),
        -float(row["dir_rank1"]),
        float(row["known_wrong_name_rate"]),
        float(row["evaluation_fpir"]),
        float(row["embedding_rtf_observed"]),
    ))
    for rank, row in enumerate(comparison, start=1):
        row["safety_first_rank"] = rank
    gallery_summary = _aggregate_rows(
        all_gallery,
        ("backend", "dataset", "gallery_size", "fpir_target"),
        ("dir_rank1", "fpir", "known_wrong_name_rate", "known_rejection_rate", "score_threshold", "margin_threshold"),
    )
    enrollment_summary = _aggregate_rows(
        all_enrollment,
        ("backend", "dataset", "enrollment_count", "aggregation_method", "fpir_target"),
        ("dir_rank1", "fpir", "known_wrong_name_rate", "known_rejection_rate"),
    )
    _write_csv(output_root / "model_comparison.csv", comparison)
    _write_csv(output_root / "enrollment_recommendations.csv", mode_rows)
    _write_csv(output_root / "gallery_scale_summary.csv", gallery_summary)
    _write_csv(output_root / "enrollment_mode_summary.csv", enrollment_summary)
    _write_csv(output_root / "session_summary.csv", all_sessions)
    _write_csv(output_root / "session_trajectory_summary.csv", _trajectory_summary(all_trajectories))
    _write_csv(output_root / "hubness_summary.csv", hub_rows)
    (output_root / "METRIC_GUIDE.md").write_text(_metric_guide(), encoding="utf-8", newline="\n")
    (output_root / "REPORT.md").write_text(
        _report(comparison, mode_rows, gallery_summary, all_sessions, _trajectory_summary(all_trajectories), hub_rows),
        encoding="utf-8", newline="\n",
    )
    result = {
        "schema_version": "speaker-embedding-deployment-analysis.v1",
        "status": "COMPLETE",
        "best_safety_first_backend": comparison[0]["backend"],
        "ranking_basis": "meet held-out FPIR and wrong-name safety constraints, then highest DIR@rank1; violations, wrong names, FPIR, and observed RTF break ties",
        "primary_dataset": "common_voice_60plus",
        "primary_gallery_size": 272,
        "primary_fpir_target": primary,
        "backends": [row["backend"] for row in comparison],
        "pairwise_eer_used_as_deployment_threshold": False,
        "degraded_stage10_used_for_robustness_claims": False,
        "limitations": [
            "Common Voice and CMU Arctic are prompted/read speech, not Beaker device recordings.",
            "Session accumulation is a deterministic cross-utterance simulation, not an end-to-end diarization test.",
            "The known Stage-10 degraded-audio provenance issue excludes that condition from robustness claims.",
            "Sub-utterance causal-prefix inference belongs to the separately frozen enrollment-duration protocol.",
        ],
    }
    write_json_atomic(output_root / "analysis_summary.json", result)
    return result


def _aggregate_rows(
    rows: Sequence[Mapping[str, object]], keys: Sequence[str], metrics: Sequence[str]
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row[key]) for key in keys)].append(row)
    result = []
    for identity, values in sorted(grouped.items()):
        item: dict[str, object] = dict(zip(keys, identity, strict=True))
        item["repetitions"] = len(values)
        for metric in metrics:
            numbers = [float(value[metric]) for value in values]
            item[f"mean_{metric}"] = sum(numbers) / len(numbers)
            item[f"min_{metric}"] = min(numbers)
            item[f"max_{metric}"] = max(numbers)
        result.append(item)
    return result


def _trajectory_summary(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["backend"]), str(row["dataset"]), str(row["partition"]))].append(row)
    result = []
    for (backend, dataset, partition), values in sorted(grouped.items()):
        def present(key: str) -> list[float]:
            return [float(value[key]) for value in values if str(value.get(key, "")) not in {"", "None"}]
        first_correct = present("first_correct_turn")
        stable = present("stable_correct_turn")
        first_false = present("first_false_identification_turn")
        result.append({
            "backend": backend, "dataset": dataset, "partition": partition, "speaker_sessions": len(values),
            "identified_sessions": len(first_correct) if partition == "known" else None,
            "median_first_correct_turn": _median(first_correct),
            "median_stable_correct_turn": _median(stable),
            "sessions_with_false_identification": len(first_false) if partition == "unknown" else None,
            "median_first_false_identification_turn": _median(first_false),
            "mean_label_flips": sum(float(value["label_flip_count"]) for value in values) / len(values),
            "premature_false_attribution_rate": sum(str(value["premature_false_attribution"]).lower() == "true" for value in values) / len(values) if partition == "known" else None,
            "two_confirmation_wrong_name_session_rate": sum(str(value["two_confirmation_wrong_name_ever"]).lower() == "true" for value in values) / len(values),
        })
    return result


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _metric_guide() -> str:
    return """# Speaker embedding deployment metric guide

- **FPIR (false positive identification rate):** fraction of truly unknown probes that receive any enrolled person's name. This is the primary stranger-rejection safety metric; lower is better.
- **DIR@rank-1 / TPIR:** fraction of known probes that are both accepted and assigned the correct enrolled identity. Higher is better.
- **FNIR:** one minus DIR@rank-1. It includes safe rejections and wrong identities, so inspect its components.
- **Known wrong-name rate:** fraction of known probes accepted as the wrong enrolled person. This is more harmful than showing `Unknown` and is ranked first here.
- **Known rejection rate:** fraction of known probes left `Unknown`; usually recoverable with more audio.
- **Closed-set Top-1:** nearest identity accuracy when rejection is disabled. It is diagnostic, not a safe production metric.
- **Score threshold:** minimum top-1 cosine score selected from calibration data only.
- **Top-1 minus Top-2 margin:** separation between the best and runner-up identities. Requiring a margin suppresses ambiguous names.
- **EER:** pairwise verification point where false accepts equal false rejects. It compares embedding separability but is not the deployment threshold for a multi-person gallery.
- **Hubness:** concentration of false assignments on a few enrolled identities. Large top-hub share or Gini means some templates act as impostor magnets.
- **Speaker-cluster bootstrap interval:** uncertainty estimated by resampling speakers, preserving correlation among one speaker's clips.
- **Embedding RTF:** extraction seconds divided by audio seconds. Below 1.0 means faster than real time in the observed offline run; concurrent-run timing is not a clean device benchmark.
"""


def _report(
    rows: Sequence[Mapping[str, object]],
    modes: Sequence[Mapping[str, object]],
    gallery: Sequence[Mapping[str, object]],
    sessions: Sequence[Mapping[str, object]],
    trajectories: Sequence[Mapping[str, object]],
    hubs: Sequence[Mapping[str, object]],
) -> str:
    winner = rows[0]
    lines = [
        "# Speaker embedding deployment evaluation",
        "",
        "## Main finding",
        "",
        f"The safety-first ranking selects **{winner['backend']}** on the 272-person Common Voice gallery at the calibration target FPIR of {100*float(winner['fpir_target']):.1f}%.",
        f"Its held-out DIR@rank-1 is {100*float(winner['dir_rank1']):.2f}%, held-out FPIR is {100*float(winner['evaluation_fpir']):.2f}%, and known wrong-name rate is {100*float(winner['known_wrong_name_rate']):.2f}%.",
        "This is a research recommendation for the tested read-speech panels, not a final Beaker-device release threshold.",
        "",
        "## Model comparison",
        "",
        "| Rank | Model | DIR@1 | FPIR | Wrong known name | Known rejected | Observed RTF |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['safety_first_rank']} | {row['backend']} | {100*float(row['dir_rank1']):.2f}% | {100*float(row['evaluation_fpir']):.2f}% | {100*float(row['known_wrong_name_rate']):.2f}% | {100*float(row['known_rejection_rate']):.2f}% | {float(row['embedding_rtf_observed']):.3f} |"
        )
    lines.extend(["", "## Why EER was not used as the product gate", ""])
    for row in rows:
        lines.append(
            f"- **{row['backend']}**: pairwise EER {100*float(row['pairwise_eer_diagnostic']):.2f}%; using that old threshold rejected only {100*float(row['unknown_rejection_at_old_pairwise_eer_threshold']):.2f}% of unknown probes. The gallery-calibrated 1% policy rejects {100*(1-float(row['evaluation_fpir'])):.2f}%."
        )
    lines.extend(["", "## Full-gallery safety/utility trade-off", "", "| Model | FPIR target | Held-out FPIR | DIR@1 | Wrong known name | Known rejected |", "|---|---:|---:|---:|---:|---:|"])
    for row in rows:
        backend_rows = [
            value for value in gallery
            if value["backend"] == row["backend"] and value["dataset"] == "common_voice_60plus"
            and int(float(value["gallery_size"])) == 272
        ]
        for value in sorted(backend_rows, key=lambda item: float(item["fpir_target"])):
            lines.append(
                f"| {row['backend']} | {100*float(value['fpir_target']):.1f}% | {100*float(value['mean_fpir']):.2f}% | {100*float(value['mean_dir_rank1']):.2f}% | {100*float(value['mean_known_wrong_name_rate']):.2f}% | {100*float(value['mean_known_rejection_rate']):.2f}% |"
            )
    lines.extend(["", "## Enrollment evidence", "", "| Model | Best tested stable recipe | Mean DIR@1 | Mean FPIR | Selection range |", "|---|---|---:|---:|---:|"])
    for value in modes:
        lines.append(
            f"| {value['backend']} | {value['recommended_enrollment_count_within_tested_read_speech']} clips; {value['recommended_aggregation_within_tested_read_speech']} | {100*float(value['mean_dir_rank1']):.2f}% | {100*float(value['mean_evaluation_fpir']):.2f}% | {100*float(value['min_dir_rank1']):.2f}–{100*float(value['max_dir_rank1']):.2f}% |"
        )
    lines.extend(["", "All recommendations average the five predeclared enrollment selections; no recommendation is chosen from a lucky held-out repetition."])
    lines.extend(["", "## Multi-turn accumulation simulation", "", "| Model | Turn 1 known correct | Turn 2 | Turn 3 | Turn 5 | Turn 5 unknown false-ID |", "|---|---:|---:|---:|---:|---:|"])
    for row in rows:
        known = {int(value["turn"]): value for value in sessions if value["backend"] == row["backend"] and value["dataset"] == "common_voice_60plus" and value["partition"] == "known"}
        unknown = {int(value["turn"]): value for value in sessions if value["backend"] == row["backend"] and value["dataset"] == "common_voice_60plus" and value["partition"] == "unknown"}
        lines.append(
            f"| {row['backend']} | {100*float(known[1]['correct_known_acceptance']):.2f}% | {100*float(known[2]['correct_known_acceptance']):.2f}% | {100*float(known[3]['correct_known_acceptance']):.2f}% | {100*float(known[5]['correct_known_acceptance']):.2f}% | {100*float(unknown[5]['unknown_false_identification']):.2f}% |"
        )
    lines.extend(["", "Accumulation is useful evidence for retroactive naming, but it is not a causal latency measurement: each turn is a complete independent utterance."])
    lines.extend(["", "A two-consecutive-decision confirmation rule was also replayed as an exploratory hysteresis guard:", ""])
    for row in rows:
        known = next(value for value in trajectories if value["backend"] == row["backend"] and value["dataset"] == "common_voice_60plus" and value["partition"] == "known")
        unknown = next(value for value in trajectories if value["backend"] == row["backend"] and value["dataset"] == "common_voice_60plus" and value["partition"] == "unknown")
        lines.append(
            f"- **{row['backend']}**: median first/stable correct turn {known['median_first_correct_turn']}/{known['median_stable_correct_turn']}; premature wrong-name sessions {100*float(known['premature_false_attribution_rate']):.2f}%; two-confirmation wrong-name sessions {100*float(known['two_confirmation_wrong_name_session_rate']):.2f}%; unknown sessions ever falsely named after confirmation {100*float(unknown['two_confirmation_wrong_name_session_rate']):.2f}%."
        )
    lines.extend(["", "## Hubness", ""])
    for row in rows:
        hub = next(value for value in hubs if value["backend"] == row["backend"])
        share = hub.get("largest_hub_share")
        share_text = "none" if share in (None, "") else f"{100*float(share):.1f}%"
        lines.append(
            f"- **{row['backend']}**: {int(hub['false_known_assignments'])} unknown probes were falsely named at the 1% policy; the largest identity received {share_text} of them. Inspect and quarantine hub templates during enrollment QA."
        )
    lines.extend([
        "", "## Product guidance", "",
        "1. Render transcript text immediately; attach or revise the speaker name asynchronously.",
        "2. Start every turn with a generic speaker label and reveal a name only after both the score and margin gates pass.",
        "3. Optimize in this order: wrong known name, identification latency, then time labeled Unknown.",
        "4. Capture five prompted phrases. Store all five normalized templates plus an aggregate; the tested best aggregation differs by model, so bind it to the selected backend.",
        "5. Run enrollment QC before saving: speech sufficiency, clipping/noise, pairwise template cohesion, and leave-one-out outlier detection. Recapture a bad phrase instead of weakening the global rejection gate.",
        "6. Use calibration thresholds tied to model identity, gallery size, enrollment recipe, and acoustic domain. Do not copy an EER threshold or another model's number.",
        "7. Do not auto-adapt a user's template from uncertain live predictions. Any adaptation needs a separately consented and validated policy.",
        "8. For Beaker enrollment, use phonetic variety, normal device distance, and the production microphone path; confirm quality before saving.",
        "9. If a name is not stable by the conservative window, keep `Unknown` rather than forcing a likely identity.",
        "10. Do not let repeated unknown speech automatically become more trusted: the exploratory accumulation replay increased false identification for some models. Use expiry/decay and re-apply both safety gates.",
        "", "## Scope", "",
        "The study uses Common Voice for broad open-set/gallery evidence and clean CMU Arctic as a second read-speech panel. It intentionally excludes the invalid Stage-10 degraded condition from robustness claims. Session accumulation and two-confirmation hysteresis are engineering simulations over complete utterances; end-to-end Speaker Label Error Rate and true causal latency require diarization-aligned Beaker recordings.",
    ])
    return "\n".join(lines) + "\n"
