"""Scientific analysis and plots for completed enrollment-duration configurations."""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from typing import Mapping, Sequence

import numpy as np

from app.speaker_enrollment.evaluation import validate_configuration_result
from app.speaker_enrollment.protocol import SpeakerEnrollmentError, load_config, load_protocol_tables


def analyze_results(
    protocol_root: Path,
    result_base: Path,
    output_root: Path,
    backends: Sequence[str],
    *,
    bootstrap_repetitions: int | None = None,
) -> dict[str, object]:
    config = load_config(protocol_root / "selection_config.yaml")
    repetitions = int(bootstrap_repetitions or config["metrics"]["bootstrap_repetitions"])
    seed = int(config["metrics"]["bootstrap_seed"])
    cohort = {row["speaker_key"]: row for row in load_protocol_tables(protocol_root)["cohort"]}
    configuration_rows: list[dict[str, object]] = []
    all_speaker_rows: list[dict[str, object]] = []
    completed_roots: list[Path] = []
    for backend in backends:
        backend_root = result_base.resolve() / backend
        for path in sorted(backend_root.glob("phase_*/*/configuration_result.json")):
            root = path.parent
            validate_configuration_result(root, protocol_root=protocol_root)
            result = _read_json(path)
            decisions = _read_csv(root / "probe_decisions.csv")
            speaker_rows = _read_csv(root / "speaker_results.csv")
            bootstrap = _bootstrap_decisions(
                decisions,
                seed=seed + len(configuration_rows) * 997,
                repetitions=repetitions,
            )
            bootstrap.update(
                _bootstrap_score_trials(
                    root / "score_trials.npz",
                    threshold=float(result["operating_threshold"]),
                    seed=seed + len(configuration_rows) * 997 + 313,
                    repetitions=repetitions,
                )
            )
            flat = _flatten_configuration(result, speaker_rows, bootstrap)
            configuration_rows.append(flat)
            for row in speaker_rows:
                metadata = cohort.get(row["speaker_key"], {})
                all_speaker_rows.append(
                    {
                        "backend": backend,
                        "configuration_id": result["configuration"]["configuration_id"],
                        "phase": result["configuration"]["phase"],
                        "enrollment_basis": result["configuration"]["enrollment_basis"],
                        "enrollment_count": result["configuration"].get("enrollment_count", ""),
                        "enrollment_target_audio_sec": result["configuration"].get("enrollment_target_audio_sec", ""),
                        "aggregation_method": result["configuration"]["aggregation_method"],
                        "probe_duration_label": result["configuration"]["probe_duration_label"],
                        **row,
                        "age_category": metadata.get("age_category", ""),
                        "gender": metadata.get("gender", ""),
                        "accent": metadata.get("accent", ""),
                    }
                )
            completed_roots.append(root)
    if not configuration_rows:
        raise SpeakerEnrollmentError("no completed enrollment-study configurations were found")
    output = output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    configuration_rows.sort(key=lambda row: (str(row["backend"]), str(row["phase"]), str(row["configuration_id"])))
    _write_csv(output / "configuration_results.csv", configuration_rows)
    _write_csv(output / "speaker_results.csv", all_speaker_rows)
    enrollment_curve = _curve(
        [row for row in configuration_rows if row["phase"] in {"EnrollmentCount", "EnrollmentDuration"}],
        ["backend", "phase", "enrollment_basis", "enrollment_count", "enrollment_target_audio_sec", "aggregation_method", "probe_duration_label"],
    )
    duration_curve = _curve(
        [row for row in configuration_rows if row["phase"] in {"ProbeDuration", "JointFrontier"}],
        ["backend", "phase", "reference_configuration_id", "aggregation_method", "probe_target_audio_sec"],
    )
    aggregation = _curve(
        [row for row in configuration_rows if row["phase"] == "Aggregation"],
        ["backend", "enrollment_count", "aggregation_method", "probe_duration_label"],
    )
    frontier = [row for row in configuration_rows if row["phase"] == "JointFrontier"]
    reliability = _reliability_rows(configuration_rows)
    _write_csv(output / "enrollment_curve.csv", enrollment_curve)
    _write_csv(output / "duration_curve.csv", duration_curve)
    _write_csv(output / "aggregation_comparison.csv", aggregation)
    _write_csv(output / "joint_frontier.csv", frontier)
    _write_csv(output / "reliability_summary.csv", reliability)
    _write_csv(output / "quality_loss_vs_reference.csv", _quality_loss(configuration_rows))
    _write_csv(output / "marginal_gain.csv", _marginal_gains(enrollment_curve))
    _write_csv(output / "speaker_diagnostics.csv", _speaker_diagnostics(all_speaker_rows))
    _write_csv(output / "enrollment_selection_variance.csv", _enrollment_selection_variance(all_speaker_rows))
    _write_csv(output / "subgroup_results.csv", _subgroup_results(all_speaker_rows))
    plot_files = _plots(output / "plots", enrollment_curve, duration_curve, aggregation, frontier)
    report = _report(configuration_rows, enrollment_curve, duration_curve, frontier, repetitions)
    (output / "report.md").write_text(report, encoding="utf-8", newline="\n")
    manifest = {
        "schema_version": "speaker-enrollment-analysis-manifest.v1",
        "protocol_id": _read_json(protocol_root / "protocol_summary.json")["protocol_id"],
        "backends": list(backends),
        "completed_configurations": len(configuration_rows),
        "bootstrap": {
            "cluster": "speaker",
            "seed": seed,
            "repetitions": repetitions,
            "confidence_level": float(config["metrics"]["confidence_level"]),
            "eer_and_fixed_far_method": "speaker-cluster bootstrap with 2001 fixed cosine-score bins",
        },
        "automatic_product_decision": False,
        "joint_frontier_present": bool(frontier),
        "score_extraction_rerun": False,
        "plots": plot_files,
        "source_result_roots": [str(path) for path in completed_roots],
    }
    _write_json(output / "analysis_manifest.json", manifest)
    _write_inventory(output)
    return manifest


def _flatten_configuration(
    result: Mapping[str, object],
    speaker_rows: Sequence[Mapping[str, str]],
    bootstrap: Mapping[str, Mapping[str, float]],
) -> dict[str, object]:
    configuration = result["configuration"]
    metrics = result["metrics"]
    tar_fixed = result["tar_at_fixed_far"]
    enrollment_audio = [float(row["enrollment_audio_sec"]) for row in speaker_rows if row.get("enrollment_audio_sec")]
    values = {
        "backend": result["backend_id"],
        "backend_identity_hash": result["backend_identity_hash"],
        "configuration_id": configuration["configuration_id"],
        "configuration_identity_hash": result["configuration_identity_hash"],
        "phase": configuration["phase"],
        "reference_configuration_id": configuration.get("reference_configuration_id", ""),
        "enrollment_basis": configuration["enrollment_basis"],
        "enrollment_count": configuration.get("enrollment_count", ""),
        "enrollment_target_audio_sec": configuration.get("enrollment_target_audio_sec", ""),
        "mean_actual_enrollment_audio_sec": statistics.mean(enrollment_audio) if enrollment_audio else "",
        "aggregation_method": configuration["aggregation_method"],
        "repetition": configuration["repetition"],
        "probe_duration_label": configuration["probe_duration_label"],
        "probe_target_audio_sec": configuration.get("probe_target_audio_sec", ""),
        "operating_threshold": result["operating_threshold"],
        "eer": _nested(result.get("evaluation_eer_oracle_diagnostic"), "eer"),
        "far": metrics.get("far"),
        "frr": metrics.get("frr"),
        "tar": metrics.get("tar"),
        "tar_far_1": _nested(tar_fixed.get("0.01"), "tar"),
        "tar_far_5": _nested(tar_fixed.get("0.05"), "tar"),
        "verification_accuracy": _metric_value(metrics, "verification_accuracy"),
        "top1_accuracy": _metric_value(metrics, "top1_identification"),
        "top3_accuracy": _metric_value(metrics, "top3_identification"),
        "top5_accuracy": _metric_value(metrics, "top5_identification"),
        "known_open_set_accuracy": _metric_value(metrics, "known_open_set_correct"),
        "unknown_rejection": _metric_value(metrics, "unknown_rejection"),
        "false_known_rate": _metric_value(metrics, "false_known_attribution"),
        "false_unknown_rate": _metric_value(metrics, "known_false_unknown"),
        "valid_rate": _metric_value(metrics, "valid_probe_rate"),
        "technically_invalid_probes": result["extraction"]["technically_invalid_probes"],
        "failed_probes": result["extraction"]["failed_probes"],
        "nan_or_inf_scores": result["extraction"]["nan_or_inf_scores"],
        "stored_templates_per_speaker": result["representation_cost"]["stored_templates_per_speaker"],
        "storage_bytes_per_speaker_float32": result["representation_cost"]["estimated_bytes_per_speaker_float32"],
        "estimated_cosine_comparisons": result["representation_cost"]["estimated_cosine_comparisons"],
        "enrollment_aggregation_runtime_sec": result["representation_cost"]["enrollment_aggregation_runtime_sec"],
        "probe_scoring_runtime_sec": result["representation_cost"]["probe_scoring_runtime_sec"],
    }
    for metric, interval in bootstrap.items():
        values[f"{metric}_ci_lower"] = interval["lower"]
        values[f"{metric}_ci_upper"] = interval["upper"]
    return values


def _bootstrap_decisions(
    decisions: Sequence[Mapping[str, str]],
    *,
    seed: int,
    repetitions: int,
) -> dict[str, dict[str, float]]:
    grouped: dict[tuple[str, str], list[Mapping[str, str]]] = defaultdict(list)
    for row in decisions:
        grouped[(row["true_partition"], row["true_speaker_key"])].append(row)
    known = sorted(key for key in grouped if key[0] == "known")
    unknown = sorted(key for key in grouped if key[0] == "unknown")
    rng = random.Random(seed)
    samples: dict[str, list[float]] = defaultdict(list)
    for _ in range(max(1, repetitions)):
        selected = [rng.choice(known) for _ in known] + [rng.choice(unknown) for _ in unknown]
        rows = [row for key in selected for row in grouped[key]]
        known_rows = [row for row in rows if row["true_partition"] == "known"]
        unknown_rows = [row for row in rows if row["true_partition"] == "unknown"]
        samples["top1_accuracy"].append(_bool_mean(known_rows, "top1_correct"))
        samples["known_open_set_accuracy"].append(_bool_mean(known_rows, "correct"))
        samples["unknown_rejection"].append(_bool_mean(unknown_rows, "correct"))
        samples["false_known_rate"].append(_bool_mean(unknown_rows, "false_known_attribution"))
        samples["false_unknown_rate"].append(_bool_mean(known_rows, "false_unknown"))
        samples["valid_rate"].append(_mean([row["status"] == "ok" for row in rows]))
    return {
        metric: {"lower": _quantile(sorted(values), 0.025), "upper": _quantile(sorted(values), 0.975)}
        for metric, values in samples.items()
    }


def _bootstrap_score_trials(
    path: Path,
    *,
    threshold: float,
    seed: int,
    repetitions: int,
) -> dict[str, dict[str, float]]:
    """Cluster-bootstrap verification metrics with a deterministic score histogram."""

    with np.load(path, allow_pickle=False) as bundle:
        evaluation = bundle["split"].astype(str) == "evaluation"
        scores = bundle["score"][evaluation].astype(np.float64)
        targets = bundle["is_target"][evaluation].astype(bool)
        speaker_index = bundle["speaker_index"][evaluation].astype(np.int64)
    speakers = np.unique(speaker_index)
    if not len(speakers) or not targets.any() or targets.all():
        return {}
    remap = {int(value): index for index, value in enumerate(speakers.tolist())}
    local = np.asarray([remap[int(value)] for value in speaker_index], dtype=np.int64)
    bins = 2001
    score_bins = np.clip(((scores + 1.0) * (bins - 1) / 2.0).astype(np.int64), 0, bins - 1)
    positive_hist = np.zeros((len(speakers), bins), dtype=np.int32)
    negative_hist = np.zeros((len(speakers), bins), dtype=np.int32)
    np.add.at(positive_hist, (local[targets], score_bins[targets]), 1)
    np.add.at(negative_hist, (local[~targets], score_bins[~targets]), 1)
    actual_accept = scores >= threshold
    per_speaker = {
        "correct": np.bincount(local, weights=(actual_accept == targets).astype(np.float64), minlength=len(speakers)),
        "total": np.bincount(local, minlength=len(speakers)).astype(np.float64),
        "positive": np.bincount(local[targets], minlength=len(speakers)).astype(np.float64),
        "negative": np.bincount(local[~targets], minlength=len(speakers)).astype(np.float64),
        "true_accept": np.bincount(local[targets], weights=actual_accept[targets].astype(np.float64), minlength=len(speakers)),
        "false_accept": np.bincount(local[~targets], weights=actual_accept[~targets].astype(np.float64), minlength=len(speakers)),
    }
    rng = np.random.default_rng(seed)
    sampled_metrics: dict[str, list[float]] = defaultdict(list)
    for _ in range(max(1, repetitions)):
        sampled = rng.integers(0, len(speakers), size=len(speakers))
        weights = np.bincount(sampled, minlength=len(speakers)).astype(np.float64)
        positives = float(weights @ per_speaker["positive"])
        negatives = float(weights @ per_speaker["negative"])
        total = float(weights @ per_speaker["total"])
        if positives <= 0 or negatives <= 0 or total <= 0:
            continue
        true_accept = float(weights @ per_speaker["true_accept"])
        false_accept = float(weights @ per_speaker["false_accept"])
        sampled_metrics["verification_accuracy"].append(float(weights @ per_speaker["correct"]) / total)
        sampled_metrics["far"].append(false_accept / negatives)
        sampled_metrics["frr"].append(1.0 - true_accept / positives)
        sampled_metrics["tar"].append(true_accept / positives)
        pos = weights @ positive_hist
        neg = weights @ negative_hist
        pos_accept = np.cumsum(pos[::-1])
        neg_accept = np.cumsum(neg[::-1])
        far = neg_accept / negatives
        frr = 1.0 - pos_accept / positives
        tar = pos_accept / positives
        index = int(np.argmin(np.abs(far - frr)))
        sampled_metrics["eer"].append(float((far[index] + frr[index]) / 2.0))
        for target_far, name in ((0.01, "tar_far_1"), (0.05, "tar_far_5")):
            eligible = np.flatnonzero(far <= target_far)
            sampled_metrics[name].append(float(np.max(tar[eligible])) if eligible.size else float("nan"))
    result = {}
    for metric, values in sampled_metrics.items():
        finite = sorted(value for value in values if math.isfinite(value))
        if finite:
            result[metric] = {"lower": _quantile(finite, 0.025), "upper": _quantile(finite, 0.975)}
    return result


def _curve(rows: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)
    metrics = [
        "eer",
        "far",
        "frr",
        "tar_far_1",
        "tar_far_5",
        "verification_accuracy",
        "top1_accuracy",
        "known_open_set_accuracy",
        "unknown_rejection",
        "false_known_rate",
        "false_unknown_rate",
        "valid_rate",
    ]
    result = []
    for key_values, group in sorted(grouped.items()):
        output = {key: value for key, value in zip(keys, key_values, strict=True)}
        output["configuration_count"] = len(group)
        for metric in metrics:
            values = [_float_or_none(row.get(metric)) for row in group]
            finite = [value for value in values if value is not None]
            output[metric] = statistics.mean(finite) if finite else ""
            output[f"{metric}_between_configuration_sd"] = statistics.pstdev(finite) if len(finite) > 1 else 0.0 if finite else ""
        result.append(output)
    return result


def _reliability_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    fields = [
        "backend",
        "configuration_id",
        "phase",
        "eer",
        "eer_ci_lower",
        "eer_ci_upper",
        "verification_accuracy",
        "verification_accuracy_ci_lower",
        "verification_accuracy_ci_upper",
        "far",
        "far_ci_lower",
        "far_ci_upper",
        "frr",
        "frr_ci_lower",
        "frr_ci_upper",
        "tar_far_1",
        "tar_far_1_ci_lower",
        "tar_far_1_ci_upper",
        "tar_far_5",
        "tar_far_5_ci_lower",
        "tar_far_5_ci_upper",
        "top1_accuracy",
        "top1_accuracy_ci_lower",
        "top1_accuracy_ci_upper",
        "known_open_set_accuracy",
        "known_open_set_accuracy_ci_lower",
        "known_open_set_accuracy_ci_upper",
        "unknown_rejection",
        "unknown_rejection_ci_lower",
        "unknown_rejection_ci_upper",
        "false_known_rate",
        "false_known_rate_ci_lower",
        "false_known_rate_ci_upper",
        "false_unknown_rate",
        "false_unknown_rate_ci_lower",
        "false_unknown_rate_ci_upper",
        "valid_rate",
        "valid_rate_ci_lower",
        "valid_rate_ci_upper",
    ]
    return [{field: row.get(field, "") for field in fields} for row in rows]


def _quality_loss(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    result = []
    for backend in sorted({str(row["backend"]) for row in rows}):
        candidates = [
            row for row in rows
            if row["backend"] == backend
            and row["phase"] == "EnrollmentCount"
            and str(row["enrollment_count"]) == "5"
            and str(row["repetition"]) == "0"
        ]
        if not candidates:
            continue
        reference = candidates[0]
        for row in [value for value in rows if value["backend"] == backend]:
            result.append(
                {
                    "backend": backend,
                    "configuration_id": row["configuration_id"],
                    "reference_configuration_id": reference["configuration_id"],
                    "enrollment_count": row["enrollment_count"],
                    "enrollment_audio_sec": row["enrollment_target_audio_sec"] or row["mean_actual_enrollment_audio_sec"],
                    "probe_audio_sec": row["probe_target_audio_sec"],
                    "top1_delta": _difference(row, reference, "top1_accuracy"),
                    "tar_far_1_delta": _difference(row, reference, "tar_far_1"),
                    "unknown_rejection_delta": _difference(row, reference, "unknown_rejection"),
                    "false_known_delta": _difference(row, reference, "false_known_rate"),
                    "valid_rate_delta": _difference(row, reference, "valid_rate"),
                    "noninferiority_margin_applied": False,
                }
            )
    return result


def _marginal_gains(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    result = []
    for backend in sorted({str(row["backend"]) for row in rows}):
        for phase, x_field in (("EnrollmentCount", "enrollment_count"), ("EnrollmentDuration", "enrollment_target_audio_sec")):
            group = [
                row for row in rows
                if str(row["backend"]) == backend and str(row["phase"]) == phase and _float_or_none(row.get(x_field)) is not None
            ]
            ordered = sorted(group, key=lambda row: float(row[x_field]))
            for left, right in zip(ordered, ordered[1:]):
                result.append(
                    {
                        "backend": backend,
                        "phase": phase,
                        "x_field": x_field,
                        "from_value": left[x_field],
                        "to_value": right[x_field],
                        "top1_gain": _difference(right, left, "top1_accuracy"),
                        "tar_far_1_gain": _difference(right, left, "tar_far_1"),
                        "unknown_rejection_gain": _difference(right, left, "unknown_rejection"),
                        "false_known_change": _difference(right, left, "false_known_rate"),
                        "valid_rate_gain": _difference(right, left, "valid_rate"),
                    }
                )
    return result


def _speaker_diagnostics(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["backend"]), str(row["speaker_key"]))].append(row)
    result = []
    for (backend, speaker), group in sorted(grouped.items()):
        probes = sum(int(row["probe_count"]) for row in group)
        correct = sum(int(row["correct_count"]) for row in group)
        false_known = sum(int(row["false_known_count"]) for row in group)
        false_unknown = sum(int(row["false_unknown_count"]) for row in group)
        config_rates = [int(row["correct_count"]) / int(row["probe_count"]) for row in group if int(row["probe_count"])]
        result.append(
            {
                "backend": backend,
                "speaker_key": speaker,
                "partition": group[0]["partition"],
                "configuration_count": len(group),
                "probe_count": probes,
                "correct_rate": correct / probes if probes else "",
                "false_known_count": false_known,
                "false_unknown_count": false_unknown,
                "configuration_accuracy_sd": statistics.pstdev(config_rates) if len(config_rates) > 1 else 0.0,
                "age_category": group[0].get("age_category", ""),
                "gender": group[0].get("gender", ""),
                "accent": group[0].get("accent", ""),
            }
        )
    return result


def _enrollment_selection_variance(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if row["partition"] != "known" or row["phase"] not in {"EnrollmentCount", "EnrollmentDuration", "Aggregation"}:
            continue
        key = tuple(
            str(row.get(field, ""))
            for field in (
                "backend",
                "phase",
                "speaker_key",
                "enrollment_basis",
                "enrollment_count",
                "enrollment_target_audio_sec",
                "aggregation_method",
            )
        )
        grouped[key].append(row)
    fields = (
        "backend",
        "phase",
        "speaker_key",
        "enrollment_basis",
        "enrollment_count",
        "enrollment_target_audio_sec",
        "aggregation_method",
    )
    result = []
    for key, group in sorted(grouped.items()):
        rates = [int(row["correct_count"]) / int(row["probe_count"]) for row in group if int(row["probe_count"])]
        result.append(
            {
                **{field: value for field, value in zip(fields, key, strict=True)},
                "selection_repetitions": len(group),
                "mean_correct_rate": statistics.mean(rates) if rates else "",
                "correct_rate_sd_across_selections": statistics.pstdev(rates) if len(rates) > 1 else 0.0 if rates else "",
                "centroid_cosine_variance_available": False,
                "metric_variance_available": bool(rates),
            }
        )
    return result


def _subgroup_results(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    result = []
    for field in ("age_category", "gender", "accent"):
        backend_speakers: dict[str, dict[str, bool]] = defaultdict(dict)
        for row in rows:
            backend_speakers[str(row["backend"])][str(row["speaker_key"])] = not bool(str(row.get(field, "")).strip())
        grouped: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
        for row in rows:
            value = str(row.get(field, "")).strip()
            grouped[(str(row["backend"]), value or "MISSING")].append(row)
        for (backend, value), group in sorted(grouped.items()):
            speakers = {str(row["speaker_key"]) for row in group}
            probes = sum(int(row["probe_count"]) for row in group)
            correct = sum(int(row["correct_count"]) for row in group)
            result.append(
                {
                    "backend": backend,
                    "subgroup_field": field,
                    "subgroup_value": value,
                    "speaker_count": len(speakers),
                    "trial_count": probes,
                    "descriptive_correct_rate": correct / probes if probes else "",
                    "missing_data": value == "MISSING",
                    "field_missing_speaker_rate": (
                        sum(backend_speakers[backend].values()) / len(backend_speakers[backend])
                        if backend_speakers[backend]
                        else ""
                    ),
                    "inferential_claim": False,
                }
            )
    return result


def _plots(
    root: Path,
    enrollment: Sequence[Mapping[str, object]],
    duration: Sequence[Mapping[str, object]],
    aggregation: Sequence[Mapping[str, object]],
    frontier: Sequence[Mapping[str, object]],
) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    root.mkdir(parents=True, exist_ok=True)
    outputs = []

    def line_plot(rows: Sequence[Mapping[str, object]], x_field: str, y_field: str, name: str, title: str) -> None:
        usable = [row for row in rows if _float_or_none(row.get(x_field)) is not None and _float_or_none(row.get(y_field)) is not None]
        if not usable:
            return
        fig, ax = plt.subplots(figsize=(7.5, 4.8))
        groups: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for row in usable:
            groups[str(row.get("backend", "backend"))].append(row)
        for label, group in groups.items():
            ordered = sorted(group, key=lambda row: float(row[x_field]))
            ax.plot([float(row[x_field]) for row in ordered], [float(row[y_field]) for row in ordered], marker="o", label=label)
        ax.set_xlabel(x_field.replace("_", " "))
        ax.set_ylabel(y_field.replace("_", " "))
        ax.set_title(title)
        ax.grid(alpha=0.25)
        ax.legend()
        fig.tight_layout()
        path = root / name
        fig.savefig(path, dpi=160)
        plt.close(fig)
        outputs.append(path.name)

    count_rows = [row for row in enrollment if row.get("phase") == "EnrollmentCount"]
    budget_rows = [row for row in enrollment if row.get("phase") == "EnrollmentDuration"]
    line_plot(count_rows, "enrollment_count", "top1_accuracy", "enrollment_count_top1.png", "Enrollment utterances vs top-1 identification")
    line_plot(budget_rows, "enrollment_target_audio_sec", "top1_accuracy", "enrollment_duration_top1.png", "Enrollment audio vs top-1 identification")
    line_plot(duration, "probe_target_audio_sec", "false_known_rate", "probe_duration_false_known.png", "False-known attribution vs live duration")
    line_plot(duration, "probe_target_audio_sec", "known_open_set_accuracy", "probe_duration_known_identification.png", "Known-speaker identification vs live duration")
    if aggregation:
        fig, ax = plt.subplots(figsize=(8.0, 4.8))
        labels = [f"{row['backend']}\nN={row['enrollment_count']}\n{row['aggregation_method']}" for row in aggregation]
        values = [float(row["top1_accuracy"]) for row in aggregation]
        ax.bar(range(len(values)), values)
        ax.set_xticks(range(len(values)), labels, rotation=45, ha="right", fontsize=7)
        ax.set_ylabel("top-1 accuracy")
        ax.set_title("Matched enrollment aggregation comparison")
        fig.tight_layout()
        path = root / "aggregation_comparison.png"
        fig.savefig(path, dpi=160)
        plt.close(fig)
        outputs.append(path.name)
    if frontier:
        line_plot(frontier, "probe_target_audio_sec", "false_known_rate", "joint_frontier_false_known.png", "Selected joint frontier: false-known rate")
        for backend in sorted({str(row["backend"]) for row in frontier}):
            rows = [row for row in frontier if str(row["backend"]) == backend]
            references = sorted({str(row["reference_configuration_id"]) for row in rows})
            durations = sorted({float(row["probe_target_audio_sec"]) for row in rows})
            if not references or not durations:
                continue
            matrix = np.full((len(references), len(durations)), np.nan)
            for row in rows:
                matrix[references.index(str(row["reference_configuration_id"])), durations.index(float(row["probe_target_audio_sec"]))] = float(row["false_known_rate"])
            fig, ax = plt.subplots(figsize=(7.5, max(3.5, 0.45 * len(references))))
            image = ax.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0, cmap="magma_r")
            ax.set_xticks(range(len(durations)), [str(value) for value in durations])
            ax.set_yticks(range(len(references)), references, fontsize=7)
            ax.set_xlabel("probe audio seconds")
            ax.set_ylabel("selected enrollment configuration")
            ax.set_title(f"Joint frontier false-known rate — {backend}")
            fig.colorbar(image, ax=ax, label="false-known rate")
            fig.tight_layout()
            safe_backend = "".join(char if char.isalnum() or char in "-_" else "_" for char in backend)
            path = root / f"joint_frontier_false_known_heatmap_{safe_backend}.png"
            fig.savefig(path, dpi=160)
            plt.close(fig)
            outputs.append(path.name)
    return outputs


def _report(
    configurations: Sequence[Mapping[str, object]],
    enrollment: Sequence[Mapping[str, object]],
    duration: Sequence[Mapping[str, object]],
    frontier: Sequence[Mapping[str, object]],
    repetitions: int,
) -> str:
    phases = defaultdict(int)
    for row in configurations:
        phases[str(row["phase"])] += 1
    lines = [
        "# Speaker enrollment and live-duration analysis",
        "",
        "This report summarizes completed configurations only. It makes no automatic product decision and applies no unsupplied non-inferiority margin.",
        "",
        f"- Backends: {', '.join(sorted({str(row['backend']) for row in configurations}))}",
        f"- Completed configurations: {len(configurations)}",
        f"- Speaker-cluster bootstrap: {repetitions} repetitions, seed family rooted at 3800, 95% intervals",
        f"- Completed phase counts: {dict(sorted(phases.items()))}",
        "- Speech style: prompted/read Common Voice speech",
        "- Duration label: available waveform audio, not exact voiced-speech time",
        "",
        "## Interpretation boundary",
        "",
        "Inspect the enrollment, duration, aggregation, reliability, subgroup, and quality-loss tables before authoring a decision gate. Short-probe false-known attribution and valid-output rate must be considered alongside top-1 identification. Tiny age/accent subgroups are descriptive only.",
        "",
        f"Joint-frontier results present: {'YES' if frontier else 'NO — an operator decision gate is still required after earlier phases.'}",
        "",
    ]
    return "\n".join(lines)


def _write_inventory(root: Path) -> None:
    rows = []
    for path in sorted(value for value in root.rglob("*") if value.is_file() and value.name != "RESULT_FILE_INVENTORY.csv"):
        rows.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    _write_csv(root / "RESULT_FILE_INVENTORY.csv", rows)


def _bool_mean(rows: Sequence[Mapping[str, str]], field: str) -> float:
    return _mean([_as_bool(row[field]) for row in rows])


def _mean(values: Sequence[bool | float]) -> float:
    return sum(float(value) for value in values) / len(values) if values else float("nan")


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        return float("nan")
    position = (len(values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    weight = position - lower
    return float(values[lower]) * (1.0 - weight) + float(values[upper]) * weight


def _metric_value(metrics: Mapping[str, object], key: str) -> object:
    value = metrics.get(key)
    return value.get("value") if isinstance(value, Mapping) else ""


def _nested(value: object, key: str) -> object:
    return value.get(key, "") if isinstance(value, Mapping) else ""


def _difference(row: Mapping[str, object], reference: Mapping[str, object], key: str) -> object:
    left = _float_or_none(row.get(key))
    right = _float_or_none(reference.get(key))
    return left - right if left is not None and right is not None else ""


def _float_or_none(value: object) -> float | None:
    if value in {None, ""}:
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _as_bool(value: object) -> bool:
    return value is True or str(value).strip().lower() == "true"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SpeakerEnrollmentError(f"JSON object required: {path}")
    return {str(key): item for key, item in value.items()}


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
