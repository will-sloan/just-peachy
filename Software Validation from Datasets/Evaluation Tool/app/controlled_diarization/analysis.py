"""Automated analysis and compact collection for controlled diarization results."""

from __future__ import annotations

from collections import defaultdict
import csv
import io
import json
import math
from pathlib import Path
import random
import shutil
import statistics
import subprocess
from typing import Iterable, Mapping, Sequence

from app.controlled_diarization.contracts import (
    DEFAULT_BENCHMARK_ROOT,
    DEFAULT_CONFIG_PATH,
    TOOL_ROOT,
    ControlledDiarizationError,
    default_generated_root,
    default_result_root,
    default_summary_root,
    load_config,
    load_pipeline_registry,
    sha256_file,
)
from app.controlled_diarization.runner import validate_result
from app.diarization_evaluation.artifacts import (
    write_checksum_manifest,
    write_json_atomic,
    write_text_atomic,
)


def analyze_results(
    *,
    pipelines: Sequence[str],
    tiers: Sequence[str] = ("development", "evaluation"),
    config_path: Path = DEFAULT_CONFIG_PATH,
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    result_root: Path | None = None,
    output_root: Path | None = None,
) -> dict[str, object]:
    """Validate existing results and generate all predeclared analysis tables."""

    config = load_config(config_path)
    registry = load_pipeline_registry(config)
    unknown = sorted(set(pipelines) - set(registry))
    if unknown:
        raise ControlledDiarizationError(f"unknown pipelines: {unknown}")
    benchmark = benchmark_root.resolve()
    results = (result_root or default_result_root()).resolve()
    output = (output_root or (results / "analysis")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    planned: list[dict[str, object]] = []
    recording_rows: list[dict[str, object]] = []
    reliability_rows: list[dict[str, object]] = []
    for tier in tiers:
        cases = _read_jsonl(benchmark / tier / "case_manifest.jsonl")
        for pipeline_id in pipelines:
            counts = defaultdict(int)
            for case in cases:
                if (
                    registry[pipeline_id].kind == "oracle_turn_clustering"
                    and case["overlap_profile"] != "none"
                ):
                    counts["excluded_diagnostic_ineligible"] += 1
                    planned.append(
                        {
                            "tier": tier,
                            "pipeline_id": pipeline_id,
                            "case_id": case["case_id"],
                            "status": "excluded_diagnostic_ineligible",
                        }
                    )
                    continue
                root = results / tier / pipeline_id / str(case["case_id"])
                status = "missing"
                if root.is_dir():
                    try:
                        validate_result(root)
                        status = "valid"
                        recording_rows.append(_recording_row(root, case))
                    except Exception:
                        status = "partial_or_invalid"
                counts[status] += 1
                planned.append(
                    {
                        "tier": tier,
                        "pipeline_id": pipeline_id,
                        "case_id": case["case_id"],
                        "status": status,
                    }
                )
            failed_root = results / "_failed" / tier / pipeline_id
            failed_attempts = (
                len([path for path in failed_root.iterdir() if path.is_dir()])
                if failed_root.is_dir()
                else 0
            )
            reliability_rows.append(
                {
                    "tier": tier,
                    "pipeline_id": pipeline_id,
                    "planned": len(cases),
                    "valid": counts["valid"],
                    "missing": counts["missing"],
                    "partial_or_invalid": counts["partial_or_invalid"],
                    "excluded_diagnostic_ineligible": counts[
                        "excluded_diagnostic_ineligible"
                    ],
                    "failed_attempts": failed_attempts,
                    "valid_rate": counts["valid"] / len(cases) if cases else 0.0,
                }
            )

    overall_rows = _aggregate(recording_rows, ("tier", "pipeline_id"))
    factor_rows = []
    for dimensions in (
        ("tier", "pipeline_id", "speaker_count"),
        ("tier", "pipeline_id", "turn_cadence"),
        ("tier", "pipeline_id", "overlap_profile"),
        ("tier", "pipeline_id", "speaker_count", "overlap_profile"),
        ("tier", "pipeline_id", "speaker_count", "turn_cadence"),
        ("tier", "pipeline_id", "turn_cadence", "overlap_profile"),
    ):
        factor_rows.extend(_aggregate(recording_rows, dimensions))
    speaker_count_rows = _aggregate(recording_rows, ("tier", "pipeline_id", "speaker_count"))
    overlap_rows = _aggregate(recording_rows, ("tier", "pipeline_id", "overlap_profile"))
    cadence_rows = _aggregate(recording_rows, ("tier", "pipeline_id", "turn_cadence"))
    fragmentation_rows = [
        {
            key: row.get(key)
            for key in (
                "tier",
                "pipeline_id",
                "case_id",
                "speaker_count",
                "predicted_speaker_count",
                "mean_clusters_per_reference_speaker",
                "split_reference_speaker_count",
                "mean_reference_speakers_per_cluster",
                "merged_predicted_cluster_count",
                "cluster_purity",
                "reference_speaker_coverage",
            )
        }
        for row in recording_rows
    ]
    merge_rows = [
        {
            key: row.get(key)
            for key in (
                "tier",
                "pipeline_id",
                "case_id",
                "speaker_count",
                "predicted_speaker_count",
                "mean_reference_speakers_per_cluster",
                "merged_predicted_cluster_count",
                "cluster_purity",
                "reference_speaker_coverage",
            )
        }
        for row in recording_rows
    ]
    single_speaker_rows = _single_speaker_controls(recording_rows)
    reentry_rows = [
        {
            "tier": row["tier"],
            "pipeline_id": row["pipeline_id"],
            "case_id": row["case_id"],
            **observation,
        }
        for row in recording_rows
        for observation in row.get("reentry_observations", [])
    ]
    resource_rows = [
        {
            key: row.get(key)
            for key in (
                "tier",
                "pipeline_id",
                "case_id",
                "environment_profile",
                "hostname",
                "audio_duration_sec",
                "audio_loading_sec",
                "inference_sec",
                "total_wall_sec",
                "real_time_factor",
            )
        }
        for row in recording_rows
    ]
    oracle_rows = [row for row in recording_rows if row.get("diagnostic_only")]
    comparisons = _paired_comparisons(recording_rows, config)

    _write_csv(output / "overall_results.csv", overall_rows)
    _write_csv(output / "recording_results.csv", _flatten_recording_rows(recording_rows))
    _write_csv(output / "factor_results.csv", factor_rows)
    _write_csv(output / "speaker_count_results.csv", speaker_count_rows)
    _write_csv(output / "overlap_results.csv", overlap_rows)
    _write_csv(output / "turn_cadence_results.csv", cadence_rows)
    _write_csv(output / "fragmentation_results.csv", fragmentation_rows)
    _write_csv(output / "merge_results.csv", merge_rows)
    _write_csv(output / "single_speaker_controls.csv", single_speaker_rows)
    _write_csv(output / "reentry_results.csv", reentry_rows)
    _write_csv(output / "resource_results.csv", resource_rows)
    _write_csv(output / "reliability_summary.csv", reliability_rows)
    _write_csv(output / "oracle_turn_results.csv", _flatten_recording_rows(oracle_rows))
    _write_csv(output / "paired_comparisons.csv", comparisons)
    _write_interaction_plots(output, factor_rows)
    protocol_summary = json.loads(
        (benchmark / "protocol_summary.json").read_text(encoding="utf-8")
    )
    benchmark_id = protocol_summary.get("benchmark_id") or protocol_summary.get("protocol_id")
    if not benchmark_id:
        raise ControlledDiarizationError("protocol summary lacks benchmark_id/protocol_id")
    manifest = {
        "schema_version": "controlled-diarization-analysis-manifest.v1",
        "benchmark_id": benchmark_id,
        "pipelines": list(pipelines),
        "tiers": list(tiers),
        "planned_units": len(planned),
        "valid_results": len(recording_rows),
        "analysis_seed": int(config["scoring"]["bootstrap_seed"]),
        "bootstrap_repetitions": int(config["scoring"]["bootstrap_repetitions"]),
        "anonymous_scoring": True,
        "development_and_evaluation_pooled": False,
        "oracle_results_in_primary_ranking": False,
        "planned_status": planned,
        "artifacts": [
            "overall_results.csv",
            "recording_results.csv",
            "factor_results.csv",
            "speaker_count_results.csv",
            "overlap_results.csv",
            "turn_cadence_results.csv",
            "fragmentation_results.csv",
            "merge_results.csv",
            "single_speaker_controls.csv",
            "reentry_results.csv",
            "resource_results.csv",
            "reliability_summary.csv",
            "oracle_turn_results.csv",
            "paired_comparisons.csv",
            "report.md",
        ],
    }
    write_json_atomic(output / "analysis_manifest.json", manifest)
    write_text_atomic(output / "report.md", _report(manifest, overall_rows, reliability_rows))
    write_checksum_manifest(output)
    return manifest


def collect_research_package(
    *,
    pipelines: Sequence[str],
    tiers: Sequence[str] = ("development", "evaluation"),
    benchmark_root: Path = DEFAULT_BENCHMARK_ROOT,
    generated_root: Path | None = None,
    result_root: Path | None = None,
    analysis_root: Path | None = None,
    output_root: Path | None = None,
) -> dict[str, object]:
    """Collect compact manifests/results while intentionally excluding generated audio."""

    benchmark = benchmark_root.resolve()
    generated = (generated_root or default_generated_root()).resolve()
    results = (result_root or default_result_root()).resolve()
    analysis = (analysis_root or (results / "analysis")).resolve()
    git_sha = _git_sha()
    destination = (
        output_root
        or default_summary_root() / f"controlled_diarization_v1_{git_sha[:12]}"
    ).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, object]] = []

    metadata_names = (
        "benchmark_config.yaml",
        "protocol_summary.json",
        "source_audit.json",
        "source_speaker_inventory.csv",
        "source_clip_inventory.csv",
        "speaker_appearance_counts.csv",
        "speaker_pair_cooccurrence.csv",
        "validation_report.json",
        "protected_evaluation_assets.json",
    )
    for name in metadata_names:
        _copy_file(benchmark / name, destination / "benchmark" / name, copied)
    for tier in tiers:
        _copy_file(
            benchmark / tier / "case_manifest.jsonl",
            destination / "benchmark" / tier / "case_manifest.jsonl",
            copied,
        )
        for reference in sorted((benchmark / tier / "references").glob("*")):
            _copy_file(
                reference,
                destination / "benchmark" / tier / "references" / reference.name,
                copied,
            )
    if analysis.is_dir():
        for path in sorted(analysis.iterdir()):
            if path.is_file():
                _copy_file(path, destination / "analysis" / path.name, copied)
    run_summary: list[dict[str, object]] = []
    for tier in tiers:
        cases = _read_jsonl(benchmark / tier / "case_manifest.jsonl")
        for pipeline in pipelines:
            for case in cases:
                root = results / tier / pipeline / str(case["case_id"])
                if not root.is_dir():
                    continue
                try:
                    validate_result(root)
                except Exception:
                    continue
                for relative in (
                    "run.json",
                    "resolved_pipeline_identity.json",
                    "predictions/segments.rttm",
                    "metrics/summary.json",
                    "report/scenario_report.md",
                ):
                    _copy_file(
                        root / relative,
                        destination / "results" / tier / pipeline / str(case["case_id"]) / relative,
                        copied,
                    )
                metrics = json.loads((root / "metrics" / "summary.json").read_text(encoding="utf-8"))
                strict = metrics["primary_strict"]
                run_summary.append(
                    {
                        "tier": tier,
                        "pipeline_id": pipeline,
                        "case_id": case["case_id"],
                        "scenario_id": json.loads((root / "run.json").read_text(encoding="utf-8"))[
                            "scenario_id"
                        ],
                        "der": strict.get("der"),
                        "jer": strict.get("jer"),
                        "result_path": str(root),
                    }
                )
    # Audio is represented by exact external path and hashes, never copied.
    for tier in tiers:
        for case in _read_jsonl(benchmark / tier / "case_manifest.jsonl"):
            path = generated / str(case["audio_logical_path"])
            copied.append(
                {
                    "kind": "external_generated_audio_not_copied",
                    "source_path": str(path),
                    "package_path": "",
                    "bytes": path.stat().st_size if path.is_file() else None,
                    "sha256": case["audio_sha256"],
                }
            )
    _write_csv(destination / "RUN_SUMMARY.csv", run_summary)
    write_text_atomic(
        destination / "RUN_PROVENANCE.txt",
        "\n".join(
            (
                f"GIT_SHA={git_sha}",
                f"BENCHMARK_ROOT={benchmark}",
                f"GENERATED_AUDIO_ROOT={generated}",
                f"RESULT_ROOT={results}",
                f"PIPELINES={','.join(pipelines)}",
                f"TIERS={','.join(tiers)}",
                "GENERATED_AUDIO_COPIED=NO",
            )
        )
        + "\n",
    )
    _write_csv(destination / "RESULT_FILE_INVENTORY.csv", copied)
    write_checksum_manifest(destination)
    return {
        "schema_version": "controlled-diarization-collection.v1",
        "output_root": str(destination),
        "copied_files": sum(row["kind"] == "copied" for row in copied),
        "external_audio_references": sum(
            row["kind"] == "external_generated_audio_not_copied" for row in copied
        ),
        "run_rows": len(run_summary),
    }


def _recording_row(root: Path, case: Mapping[str, object]) -> dict[str, object]:
    run = json.loads((root / "run.json").read_text(encoding="utf-8"))
    metrics = json.loads((root / "metrics" / "summary.json").read_text(encoding="utf-8"))
    strict = metrics["primary_strict"]
    practical = metrics["practical_boundary_tolerant"]
    count = metrics["speaker_count"]
    fragmentation = metrics["fragmentation"]
    merging = metrics["merging"]
    timing = run["timing"]
    environment = run["environment"]
    overlap = metrics.get("overlap_specific") or {}
    return {
        "tier": run["tier"],
        "pipeline_id": run["pipeline_id"],
        "case_id": run["case_id"],
        "scenario_id": run["scenario_id"],
        "speaker_count": int(case["speaker_count"]),
        "turn_cadence": case["turn_cadence"],
        "overlap_profile": case["overlap_profile"],
        "replicate": case["replicate"],
        "control_kind": case["control_kind"],
        "diagnostic_only": bool(run["diagnostic_only"]),
        "speaker_count_mode": run["speaker_count_mode"],
        "metrics_emitted": bool(strict.get("metrics_emitted")),
        "der": strict.get("der"),
        "jer": strict.get("jer"),
        "missed_speech_sec": strict.get("missed_speech_sec"),
        "false_alarm_sec": strict.get("false_alarm_sec"),
        "speaker_confusion_sec": strict.get("speaker_confusion_sec"),
        "reference_speaker_time_sec": strict.get("reference_speaker_time_sec"),
        "non_overlap_der": (strict.get("modes") or {}).get("overlap_excluded", {}).get("der"),
        "practical_der": practical.get("der"),
        "overlap_der": overlap.get("der"),
        "reference_speaker_count": count["reference"],
        "predicted_speaker_count": count["predicted"],
        "speaker_count_signed_error": count["signed_error"],
        "speaker_count_absolute_error": count["absolute_error"],
        "speaker_count_exact": count["exact"],
        "mean_clusters_per_reference_speaker": fragmentation[
            "mean_clusters_per_reference_speaker"
        ],
        "split_reference_speaker_count": fragmentation["split_reference_speaker_count"],
        "mean_reference_speakers_per_cluster": merging[
            "mean_reference_speakers_per_cluster"
        ],
        "merged_predicted_cluster_count": merging["merged_predicted_cluster_count"],
        "cluster_purity": metrics.get("cluster_purity"),
        "reference_speaker_coverage": metrics.get("reference_speaker_coverage"),
        "speaker_reentry_consistency": metrics.get("speaker_reentry_consistency"),
        "reentry_observations": metrics.get("reentry_observations", []),
        "boundary_f1_250ms": metrics["turn_boundary"]["0.25"]["f1"],
        "boundary_f1_500ms": metrics["turn_boundary"]["0.5"]["f1"],
        "audio_duration_sec": timing["audio_duration_sec"],
        "audio_loading_sec": timing["audio_loading_sec"],
        "inference_sec": timing["diarization_inference_sec"],
        "total_wall_sec": timing["total_wall_sec"],
        "real_time_factor": timing["real_time_factor"],
        "environment_profile": environment["environment_profile"],
        "hostname": environment["hostname"],
        "result_path": str(root),
    }


def _aggregate(
    rows: Sequence[Mapping[str, object]], dimensions: Sequence[str]
) -> list[dict[str, object]]:
    groups: dict[tuple[object, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if row.get("diagnostic_only"):
            continue
        groups[tuple(row.get(key) for key in dimensions)].append(row)
    output = []
    for values, group in sorted(groups.items(), key=lambda item: tuple(str(v) for v in item[0])):
        valid = [row for row in group if row.get("metrics_emitted")]
        denominator = sum(float(row["reference_speaker_time_sec"]) for row in valid)
        miss = sum(float(row["missed_speech_sec"]) for row in valid)
        false_alarm = sum(float(row["false_alarm_sec"]) for row in valid)
        confusion = sum(float(row["speaker_confusion_sec"]) for row in valid)
        ders = [float(row["der"]) for row in valid]
        ci_low, ci_high = _bootstrap_ci(ders, seed=3800)
        value = {key: item for key, item in zip(dimensions, values, strict=True)}
        value.update(
            {
                "grouping": " x ".join(dimensions[2:]) if len(dimensions) > 2 else "overall",
                "planned_or_observed_results": len(group),
                "valid_results": len(valid),
                "valid_rate": len(valid) / len(group) if group else 0.0,
                "der": (miss + false_alarm + confusion) / denominator if denominator else None,
                "mean_recording_der": statistics.fmean(ders) if ders else None,
                "der_bootstrap_ci95_low": ci_low,
                "der_bootstrap_ci95_high": ci_high,
                "mean_jer": _mean(row.get("jer") for row in valid),
                "missed_speech_sec": miss if valid else None,
                "false_alarm_sec": false_alarm if valid else None,
                "speaker_confusion_sec": confusion if valid else None,
                "reference_speaker_time_sec": denominator if valid else None,
                "speaker_count_mae": _mean(
                    row.get("speaker_count_absolute_error") for row in valid
                ),
                "speaker_count_exact_accuracy": _mean(
                    float(bool(row.get("speaker_count_exact"))) for row in valid
                ),
                "mean_fragmentation": _mean(
                    row.get("mean_clusters_per_reference_speaker") for row in valid
                ),
                "mean_merge": _mean(
                    row.get("mean_reference_speakers_per_cluster") for row in valid
                ),
                "mean_reentry_consistency": _mean(
                    row.get("speaker_reentry_consistency") for row in valid
                ),
                "mean_real_time_factor": _mean(row.get("real_time_factor") for row in valid),
            }
        )
        output.append(value)
    return output


def _paired_comparisons(
    rows: Sequence[Mapping[str, object]], config: Mapping[str, object]
) -> list[dict[str, object]]:
    output = []
    pipelines = sorted({str(row["pipeline_id"]) for row in rows if not row["diagnostic_only"]})
    by_pipeline = {
        pipeline: {
            (str(row["tier"]), str(row["case_id"])): row
            for row in rows
            if row["pipeline_id"] == pipeline and row.get("metrics_emitted")
        }
        for pipeline in pipelines
    }
    for index, baseline in enumerate(pipelines):
        for candidate in pipelines[index + 1 :]:
            shared = sorted(set(by_pipeline[baseline]) & set(by_pipeline[candidate]))
            deltas = [
                float(by_pipeline[candidate][key]["der"])
                - float(by_pipeline[baseline][key]["der"])
                for key in shared
            ]
            low, high = _bootstrap_ci(
                deltas,
                seed=int(config["scoring"]["bootstrap_seed"]),
                repetitions=int(config["scoring"]["bootstrap_repetitions"]),
            )
            output.append(
                {
                    "baseline_pipeline": baseline,
                    "candidate_pipeline": candidate,
                    "shared_recordings": len(shared),
                    "mean_paired_der_change": statistics.fmean(deltas) if deltas else None,
                    "bootstrap_ci95_low": low,
                    "bootstrap_ci95_high": high,
                    "bootstrap_unit": "recording",
                    "seed": int(config["scoring"]["bootstrap_seed"]),
                }
            )
    return output


def _single_speaker_controls(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        if int(row.get("speaker_count") or 0) == 1 and not row.get("diagnostic_only"):
            groups[(str(row["tier"]), str(row["pipeline_id"]))].append(row)
    output = []
    for (tier, pipeline_id), group in sorted(groups.items()):
        valid = [row for row in group if row.get("metrics_emitted")]
        output.append(
            {
                "tier": tier,
                "pipeline_id": pipeline_id,
                "recordings": len(group),
                "valid_results": len(valid),
                "mean_predicted_speakers": _mean(
                    row.get("predicted_speaker_count") for row in valid
                ),
                "exact_one_speaker_rate": _mean(
                    float(int(row.get("predicted_speaker_count") or 0) == 1)
                    for row in valid
                ),
                "fragmentation_rate": _mean(
                    float(int(row.get("split_reference_speaker_count") or 0) > 0)
                    for row in valid
                ),
                "mean_der": _mean(row.get("der") for row in valid),
            }
        )
    return output


def _bootstrap_ci(
    values: Sequence[float], *, seed: int, repetitions: int = 2000
) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return float(values[0]), float(values[0])
    randomizer = random.Random(seed)
    estimates = sorted(
        statistics.fmean(randomizer.choice(values) for _ in values)
        for _ in range(repetitions)
    )
    return estimates[round(0.025 * (repetitions - 1))], estimates[round(0.975 * (repetitions - 1))]


def _write_interaction_plots(
    output: Path, factor_rows: Sequence[Mapping[str, object]]
) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    specifications = (
        ("speaker_count", "overlap_profile", "der_by_speaker_count_and_overlap.png"),
        ("speaker_count", "turn_cadence", "der_by_speaker_count_and_cadence.png"),
        ("turn_cadence", "overlap_profile", "der_by_cadence_and_overlap.png"),
    )
    for x, series, filename in specifications:
        eligible = [
            row
            for row in factor_rows
            if row.get(x) is not None
            and row.get(series) is not None
            and row.get("der") is not None
            and row.get("tier") == "evaluation"
        ]
        if not eligible:
            continue
        figure, axis = plt.subplots(figsize=(8, 5))
        for label in sorted({f"{row['pipeline_id']} | {row[series]}" for row in eligible}):
            pipeline, value = label.split(" | ", 1)
            points = [
                row
                for row in eligible
                if row["pipeline_id"] == pipeline and str(row[series]) == value
            ]
            points.sort(key=lambda row: str(row[x]))
            axis.plot([str(row[x]) for row in points], [float(row["der"]) for row in points], marker="o", label=label)
        axis.set_xlabel(x.replace("_", " "))
        axis.set_ylabel("DER (strict, overlap included)")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=7)
        figure.tight_layout()
        figure.savefig(output / filename, dpi=150)
        plt.close(figure)


def _flatten_recording_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [
        {key: value for key, value in row.items() if key != "reentry_observations"}
        for row in rows
    ]


def _report(
    manifest: Mapping[str, object],
    overall: Sequence[Mapping[str, object]],
    reliability: Sequence[Mapping[str, object]],
) -> str:
    lines = [
        "# Controlled diarization analysis",
        "",
        f"Benchmark: `{manifest['benchmark_id']}`",
        "",
        "Development and evaluation are reported separately. Oracle-turn and oracle-count diagnostics are excluded from primary summaries. No scalar composite ranking is calculated.",
        "",
        "## Reliability",
        "",
        "| Tier | Pipeline | Valid | Missing | Partial | Valid rate |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in reliability:
        lines.append(
            f"| {row['tier']} | {row['pipeline_id']} | {row['valid']} | {row['missing']} | "
            f"{row['partial_or_invalid']} | {float(row['valid_rate']):.3f} |"
        )
    lines.extend(
        (
            "",
            "## Primary summaries",
            "",
            "| Tier | Pipeline | DER | JER | Count MAE | RTF |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        )
    )
    for row in overall:
        lines.append(
            f"| {row['tier']} | {row['pipeline_id']} | {_fmt(row.get('der'))} | "
            f"{_fmt(row.get('mean_jer'))} | {_fmt(row.get('speaker_count_mae'))} | "
            f"{_fmt(row.get('mean_real_time_factor'))} |"
        )
    lines.extend(
        (
            "",
            "Interpret DER beside missed speech, false alarm, speaker confusion, count error, fragmentation, merging, re-entry consistency, reliability, runtime, memory availability, integration complexity, and licence constraints.",
            "",
        )
    )
    return "\n".join(lines)


def _fmt(value: object) -> str:
    return "—" if value is None else f"{float(value):.4f}"


def _mean(values: Iterable[object]) -> float | None:
    usable = [float(value) for value in values if value is not None]
    return statistics.fmean(usable) if usable else None


def _copy_file(source: Path, destination: Path, inventory: list[dict[str, object]]) -> None:
    if not source.is_file():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    inventory.append(
        {
            "kind": "copied",
            "source_path": str(source),
            "package_path": destination.as_posix(),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        write_text_atomic(path, "")
        return
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: (
                    json.dumps(row.get(field), sort_keys=True)
                    if isinstance(row.get(field), (dict, list))
                    else row.get(field)
                )
                for field in fields
            }
        )
    write_text_atomic(path, stream.getvalue())


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=TOOL_ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()
