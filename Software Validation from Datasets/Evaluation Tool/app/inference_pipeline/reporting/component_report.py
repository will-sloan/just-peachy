"""Reusable report generation for inference pipeline component runs."""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from app.inference_pipeline.metrics.asr_metrics import (
    asr_primary_recommendation,
    asr_summary_from_aggregate,
)
from app.inference_pipeline.metrics.runtime_metrics import (
    extract_model_versions_from_diagnostics,
    runtime_primary_recommendation,
    summarize_runtime_diagnostics,
)
from app.inference_pipeline.metrics.speaker_metrics import (
    extract_speaker_decisions_from_diagnostics,
    speaker_primary_recommendation,
    summarize_speaker_decisions,
)
from app.utils.json_utils import read_json, read_jsonl, write_json


TOOL_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORTS_ROOT = TOOL_ROOT / "reports"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
CONFIG_FILENAMES = (
    "run_config.yaml",
    "config_snapshot.yaml",
    "asr_config_snapshot.yaml",
    "benchmark_run_config.yaml",
)
REQUIRED_SECTION_HEADINGS = (
    "Report Metadata",
    "Dataset Selection",
    "Configuration Snapshot",
    "Model Versions",
    "Metrics Summary",
    "Validation Scores",
    "Recommendation",
    "Artifacts",
)
REPORT_INDEX_COLUMNS = (
    "run_id",
    "component_type",
    "report_markdown_path",
    "summary_csv_path",
    "metrics_json_path",
    "primary_recommendation",
    "report_completeness_score",
    "reproducibility_score",
    "comparison_readiness_score",
    "generated_at",
    "git_commit",
)
COMPONENT_LABELS = {
    "asr": "ASR Report",
    "vad": "VAD Report",
    "segmentation": "Segmentation Report",
    "speaker_embedding": "Speaker Embedding Report",
    "speaker_matching": "Speaker Matching Report",
    "enrollment": "Enrollment Report",
    "enrollment_prompts": "Enrollment Prompt Report",
    "runtime": "Runtime Report",
    "end_to_end": "End-to-End Pipeline Report",
}
COMPONENT_ALIASES = {
    "e2e": "end_to_end",
    "end-to-end": "end_to_end",
    "end_to_end_pipeline": "end_to_end",
    "speaker-matching": "speaker_matching",
    "speaker-embedding": "speaker_embedding",
    "enrollment-prompts": "enrollment_prompts",
}


@dataclass(frozen=True)
class ReportMetadata:
    """Standard metadata block included in every reusable report."""

    run_id: str
    git_commit: str
    config_path: str
    dataset_selection: Mapping[str, object]
    model_versions: Mapping[str, object]
    hardware: Mapping[str, object]
    date: str
    config_snapshot: Mapping[str, object] | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "git_commit": self.git_commit,
            "config_path": self.config_path,
            "dataset_selection": dict(self.dataset_selection),
            "model_versions": dict(self.model_versions),
            "hardware": dict(self.hardware),
            "date": self.date,
            "config_snapshot": dict(self.config_snapshot or {}),
        }


@dataclass(frozen=True)
class GeneratedReportArtifacts:
    """Paths written by one report generation call."""

    markdown_path: Path
    csv_path: Path
    json_path: Path
    index_path: Path
    validation: Mapping[str, object]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "markdown_path": self.markdown_path.as_posix(),
            "csv_path": self.csv_path.as_posix(),
            "json_path": self.json_path.as_posix(),
            "index_path": self.index_path.as_posix(),
            "validation": dict(self.validation),
        }


def generate_report_from_run(
    run_dir: Path | str,
    *,
    component_type: str = "end_to_end",
    reports_root: Path | str | None = None,
    output_dir: Path | str | None = None,
    primary_recommendation: str | None = None,
    git_commit: str | None = None,
    generated_at: str | None = None,
) -> GeneratedReportArtifacts:
    """Generate markdown, CSV, JSON, and index entries from an existing run."""

    source_run_dir = Path(run_dir).resolve()
    if not source_run_dir.exists():
        raise FileNotFoundError(f"Run directory does not exist: {source_run_dir}")
    if not source_run_dir.is_dir():
        raise NotADirectoryError(f"Expected run directory: {source_run_dir}")

    component_key = normalize_component_type(component_type)
    root = Path(reports_root).resolve() if reports_root is not None else DEFAULT_REPORTS_ROOT
    destination = (
        Path(output_dir).resolve()
        if output_dir is not None
        else root / "component_reports" / component_key
    )
    destination.mkdir(parents=True, exist_ok=True)

    metrics = collect_report_metrics(source_run_dir, component_type=component_key)
    metadata = build_report_metadata(
        source_run_dir,
        metrics=metrics,
        git_commit=git_commit,
        generated_at=generated_at,
    )
    recommendation = primary_recommendation or primary_recommendation_for(
        component_key,
        metrics,
    )
    summary_rows = summary_rows_for(component_key, metrics)

    report_stem = f"{component_key}_report_{source_run_dir.name}"
    markdown_path = destination / f"{report_stem}.md"
    csv_path = destination / f"{report_stem}.csv"
    json_path = destination / f"{report_stem}.json"
    index_path = root / "report_index.csv"

    initial_markdown = render_markdown_report(
        component_key,
        metadata=metadata,
        metrics=metrics,
        summary_rows=summary_rows,
        primary_recommendation=recommendation,
        artifacts={
            "source_run_dir": display_path(source_run_dir),
            "markdown": display_path(markdown_path),
            "csv": display_path(csv_path),
            "json": display_path(json_path),
            "report_index": display_path(index_path),
        },
        validation={},
    )
    validation = validate_report_contents(
        initial_markdown,
        metadata=metadata,
        summary_rows=summary_rows,
        planned_markdown_path=markdown_path,
        planned_csv_path=csv_path,
        planned_json_path=json_path,
    )
    markdown = render_markdown_report(
        component_key,
        metadata=metadata,
        metrics=metrics,
        summary_rows=summary_rows,
        primary_recommendation=recommendation,
        artifacts={
            "source_run_dir": display_path(source_run_dir),
            "markdown": display_path(markdown_path),
            "csv": display_path(csv_path),
            "json": display_path(json_path),
            "report_index": display_path(index_path),
        },
        validation=validation,
    )

    markdown_path.write_text(markdown, encoding="utf-8")
    write_csv_summary(csv_path, component_key, metadata.run_id, summary_rows)
    write_json(
        json_path,
        {
            "component_type": component_key,
            "metadata": metadata.to_jsonable(),
            "metrics": json_safe(metrics),
            "summary_rows": json_safe(summary_rows),
            "validation": dict(validation),
            "primary_recommendation": recommendation,
            "artifacts": {
                "source_run_dir": display_path(source_run_dir),
                "markdown": display_path(markdown_path),
                "csv": display_path(csv_path),
                "json": display_path(json_path),
                "report_index": display_path(index_path),
            },
        },
    )
    update_report_index(
        index_path,
        {
            "run_id": metadata.run_id,
            "component_type": component_key,
            "report_markdown_path": display_path(markdown_path, root),
            "summary_csv_path": display_path(csv_path, root),
            "metrics_json_path": display_path(json_path, root),
            "primary_recommendation": recommendation,
            "report_completeness_score": _format_score(
                validation.get("report_completeness_score")
            ),
            "reproducibility_score": _format_score(validation.get("reproducibility_score")),
            "comparison_readiness_score": _format_score(
                validation.get("comparison_readiness_score")
            ),
            "generated_at": metadata.date,
            "git_commit": metadata.git_commit,
        },
    )
    return GeneratedReportArtifacts(
        markdown_path=markdown_path,
        csv_path=csv_path,
        json_path=json_path,
        index_path=index_path,
        validation=validation,
    )


def collect_report_metrics(
    run_dir: Path,
    *,
    component_type: str,
) -> dict[str, object]:
    """Collect report metrics from existing run artifacts."""

    aggregate_metrics = _read_json_mapping(run_dir / "metrics" / "aggregate_metrics.json")
    benchmark_result = _read_json_mapping(run_dir / "benchmark_result.json")
    runner_summary = _read_json_mapping(run_dir / "predictions" / "runner_summary.json")
    diagnostics_rows = _read_jsonl_mappings(run_dir / "predictions" / "diagnostics.jsonl")
    speaker_decisions = extract_speaker_decisions_from_diagnostics(diagnostics_rows)
    runtime_metrics = summarize_runtime_diagnostics(diagnostics_rows)
    speaker_metrics = summarize_speaker_decisions(speaker_decisions)

    metrics: dict[str, object] = {
        "component_type": component_type,
        "aggregate_metrics": aggregate_metrics,
        "asr_metrics": _asr_metrics(aggregate_metrics, benchmark_result),
        "speaker_metrics": _speaker_metrics(aggregate_metrics, speaker_metrics),
        "runtime_metrics": runtime_metrics,
        "benchmark_result": benchmark_result,
        "runner_summary": runner_summary,
        "artifact_counts": _artifact_counts(run_dir),
        "diagnostics_row_count": len(diagnostics_rows),
    }
    return metrics


def build_report_metadata(
    run_dir: Path,
    *,
    metrics: Mapping[str, object],
    git_commit: str | None = None,
    generated_at: str | None = None,
) -> ReportMetadata:
    """Build the standard report metadata block from a run directory."""

    config_path, config_snapshot = _load_config_snapshots(run_dir)
    diagnostics_rows = _read_jsonl_mappings(run_dir / "predictions" / "diagnostics.jsonl")
    model_versions = _model_versions(
        config_snapshot,
        diagnostics_rows,
        metrics.get("benchmark_result"),
    )
    runtime = metrics.get("runtime_metrics")
    runtime_mapping = runtime if isinstance(runtime, Mapping) else {}
    return ReportMetadata(
        run_id=run_dir.name,
        git_commit=git_commit or current_git_commit(),
        config_path=display_path(config_path) if config_path is not None else "not found",
        dataset_selection=_dataset_selection(run_dir, config_snapshot),
        model_versions=model_versions,
        hardware=_hardware_summary(runtime_mapping),
        date=generated_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        config_snapshot=config_snapshot,
    )


def render_markdown_report(
    component_type: str,
    *,
    metadata: ReportMetadata,
    metrics: Mapping[str, object],
    summary_rows: Sequence[Mapping[str, object]],
    primary_recommendation: str,
    artifacts: Mapping[str, object],
    validation: Mapping[str, object],
) -> str:
    """Render a component report using a reusable template."""

    component_key = normalize_component_type(component_type)
    template = template_path_for_component(component_key).read_text(encoding="utf-8")
    context = {
        "title": COMPONENT_LABELS[component_key],
        "component_type": component_key,
        "metadata_block": _metadata_block(metadata),
        "dataset_selection_block": json_block(metadata.dataset_selection),
        "config_snapshot_block": json_block(metadata.config_snapshot or {}),
        "model_versions_block": json_block(metadata.model_versions),
        "metrics_block": _metrics_block(metrics, summary_rows),
        "validation_block": _validation_block(validation),
        "primary_recommendation": primary_recommendation,
        "artifacts_block": _artifacts_block(artifacts),
    }
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered.rstrip() + "\n"


def validate_report_contents(
    markdown: str,
    *,
    metadata: ReportMetadata,
    summary_rows: Sequence[Mapping[str, object]],
    planned_markdown_path: Path,
    planned_csv_path: Path,
    planned_json_path: Path,
) -> dict[str, object]:
    """Score report completeness, reproducibility, and comparison readiness."""

    present_sections = [
        heading
        for heading in REQUIRED_SECTION_HEADINGS
        if f"## {heading}" in markdown
    ]
    reproducibility_checks = {
        "git_commit_present": metadata.git_commit not in {"", "unknown"},
        "config_path_present": metadata.config_path not in {"", "not found"},
        "config_snapshot_present": bool(metadata.config_snapshot),
        "dataset_selection_present": bool(metadata.dataset_selection),
        "model_versions_present": bool(metadata.model_versions),
    }
    comparison_checks = {
        "markdown_output_planned": planned_markdown_path.suffix == ".md",
        "csv_output_planned": planned_csv_path.suffix == ".csv",
        "json_output_planned": planned_json_path.suffix == ".json",
        "summary_rows_present": bool(summary_rows),
    }
    return {
        "report_completeness_score": _ratio(
            len(present_sections),
            len(REQUIRED_SECTION_HEADINGS),
        ),
        "reproducibility_score": _ratio(
            sum(1 for value in reproducibility_checks.values() if value),
            len(reproducibility_checks),
        ),
        "comparison_readiness_score": _ratio(
            sum(1 for value in comparison_checks.values() if value),
            len(comparison_checks),
        ),
        "required_sections_present": present_sections,
        "required_sections_missing": [
            heading
            for heading in REQUIRED_SECTION_HEADINGS
            if heading not in present_sections
        ],
        "reproducibility_checks": reproducibility_checks,
        "comparison_checks": comparison_checks,
    }


def summary_rows_for(
    component_type: str,
    metrics: Mapping[str, object],
) -> list[dict[str, object]]:
    """Build machine-readable summary rows for CSV output."""

    component_key = normalize_component_type(component_type)
    rows: list[dict[str, object]] = []
    selected_groups = _metric_groups_for(component_key, metrics)
    for source, group in selected_groups:
        if not isinstance(group, Mapping):
            continue
        for key, value in sorted(group.items()):
            if isinstance(value, Mapping):
                for nested_key, nested_value in sorted(value.items()):
                    _append_summary_row(rows, f"{key}.{nested_key}", nested_value, source)
            elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
                _append_summary_row(rows, key, value, source)
            else:
                _append_summary_row(rows, key, value, source)
    return rows


def primary_recommendation_for(
    component_type: str,
    metrics: Mapping[str, object],
) -> str:
    """Return a primary recommendation for the report index."""

    component_key = normalize_component_type(component_type)
    if component_key == "runtime":
        runtime = metrics.get("runtime_metrics")
        return runtime_primary_recommendation(runtime if isinstance(runtime, Mapping) else {})
    if component_key == "speaker_matching":
        speaker = metrics.get("speaker_metrics")
        return speaker_primary_recommendation(speaker if isinstance(speaker, Mapping) else {})
    if component_key == "asr":
        asr = metrics.get("asr_metrics")
        return asr_primary_recommendation(asr if isinstance(asr, Mapping) else {})
    if component_key == "end_to_end":
        aggregate = metrics.get("aggregate_metrics")
        speaker = metrics.get("speaker_metrics")
        runtime = metrics.get("runtime_metrics")
        aggregate_map = aggregate if isinstance(aggregate, Mapping) else {}
        speaker_map = speaker if isinstance(speaker, Mapping) else {}
        runtime_map = runtime if isinstance(runtime, Mapping) else {}
        if aggregate_map.get("missing_predictions") not in {None, 0, "0"}:
            return "Resolve missing predictions before comparing end-to-end runs."
        speaker_accuracy = _optional_float(aggregate_map.get("speaker_label_accuracy"))
        if speaker_accuracy is not None and speaker_accuracy < 0.50:
            return speaker_primary_recommendation({**speaker_map, **aggregate_map})
        rtf = _optional_float(runtime_map.get("realtime_factor_mean"))
        if rtf is not None and rtf > 1.0:
            return runtime_primary_recommendation(runtime_map)
        return asr_primary_recommendation(aggregate_map)
    return "Use this component report for reproducible comparison against later runs."


def template_path_for_component(component_type: str) -> Path:
    """Return the Markdown template path for a component type."""

    component_key = normalize_component_type(component_type)
    path = TEMPLATE_DIR / f"{component_key}.md"
    if not path.exists():
        raise FileNotFoundError(f"Missing report template for {component_key}: {path}")
    return path


def write_csv_summary(
    path: Path,
    component_type: str,
    run_id: str,
    rows: Sequence[Mapping[str, object]],
) -> Path:
    """Write a CSV metric summary table."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ("component_type", "run_id", "metric", "value", "source")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "component_type": component_type,
                    "run_id": run_id,
                    "metric": row.get("metric"),
                    "value": _csv_value(row.get("value")),
                    "source": row.get("source"),
                }
            )
    return path


def update_report_index(path: Path, row: Mapping[str, object]) -> Path:
    """Create or update the reusable report index CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_index_rows(path)
    identity = (
        str(row.get("run_id")),
        str(row.get("component_type")),
        str(row.get("report_markdown_path")),
    )
    kept = [
        item
        for item in existing
        if (
            str(item.get("run_id")),
            str(item.get("component_type")),
            str(item.get("report_markdown_path")),
        )
        != identity
    ]
    kept.append({column: str(row.get(column, "")) for column in REPORT_INDEX_COLUMNS})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_INDEX_COLUMNS)
        writer.writeheader()
        writer.writerows(kept)
    return path


def normalize_component_type(component_type: str) -> str:
    normalized = component_type.strip().lower().replace(" ", "_")
    normalized = COMPONENT_ALIASES.get(normalized, normalized)
    if normalized not in COMPONENT_LABELS:
        allowed = ", ".join(sorted(COMPONENT_LABELS))
        raise ValueError(f"Unknown component_type {component_type!r}; expected one of: {allowed}")
    return normalized


def current_git_commit() -> str:
    """Return the current git commit hash when available."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=TOOL_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    commit = result.stdout.strip()
    return commit or "unknown"


def json_safe(value: object) -> object:
    """Return a JSON-safe representation for report payloads."""

    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [json_safe(item) for item in value]
    return value


def display_path(path: Path, base: Path | None = None) -> str:
    """Return a stable, human-readable path."""

    selected_base = base or TOOL_ROOT
    try:
        return path.resolve().relative_to(selected_base.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def json_block(value: object) -> str:
    return "```json\n" + json.dumps(json_safe(value), indent=2, sort_keys=True) + "\n```"


def _metric_groups_for(
    component_type: str,
    metrics: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    aggregate = metrics.get("aggregate_metrics")
    asr = metrics.get("asr_metrics")
    speaker = metrics.get("speaker_metrics")
    runtime = metrics.get("runtime_metrics")
    benchmark = metrics.get("benchmark_result")
    runner = metrics.get("runner_summary")
    artifacts = metrics.get("artifact_counts")
    if component_type == "asr":
        return (("asr", asr), ("benchmark", benchmark), ("runtime", runtime), ("artifacts", artifacts))
    if component_type == "speaker_matching":
        return (("speaker", speaker), ("aggregate", aggregate), ("runtime", runtime))
    if component_type == "runtime":
        return (("runtime", runtime), ("runner", runner), ("artifacts", artifacts))
    if component_type == "end_to_end":
        return (
            ("aggregate", aggregate),
            ("asr", asr),
            ("speaker", speaker),
            ("runtime", runtime),
            ("runner", runner),
            ("artifacts", artifacts),
        )
    return (("aggregate", aggregate), ("runtime", runtime), ("artifacts", artifacts))


def _append_summary_row(
    rows: list[dict[str, object]],
    metric: str,
    value: object,
    source: str,
) -> None:
    if value is None:
        return
    rows.append({"metric": metric, "value": json_safe(value), "source": source})


def _asr_metrics(
    aggregate_metrics: Mapping[str, object],
    benchmark_result: Mapping[str, object],
) -> dict[str, object]:
    benchmark_metrics = benchmark_result.get("metrics")
    if isinstance(benchmark_metrics, Mapping):
        return {str(key): value for key, value in benchmark_metrics.items()}
    return asr_summary_from_aggregate(aggregate_metrics)


def _speaker_metrics(
    aggregate_metrics: Mapping[str, object],
    diagnostics_speaker_metrics: Mapping[str, object],
) -> dict[str, object]:
    result = dict(diagnostics_speaker_metrics)
    for key in (
        "speaker_label_accuracy",
        "speaker_label_matches",
        "speaker_label_scored",
        "segment_speaker_summary",
    ):
        if key in aggregate_metrics:
            result[key] = aggregate_metrics[key]
    return result


def _artifact_counts(run_dir: Path) -> dict[str, object]:
    counts: dict[str, object] = {}
    for subdir in ("predictions", "metrics", "plots", "report"):
        path = run_dir / subdir
        counts[f"{subdir}_file_count"] = _file_count(path)
    counts["has_utterance_predictions"] = (run_dir / "predictions" / "utterances.jsonl").exists()
    counts["has_aggregate_metrics"] = (run_dir / "metrics" / "aggregate_metrics.json").exists()
    counts["has_per_recording_metrics"] = (run_dir / "metrics" / "per_recording_metrics.csv").exists()
    return counts


def _file_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.rglob("*") if item.is_file())


def _load_config_snapshots(run_dir: Path) -> tuple[Path | None, dict[str, object]]:
    snapshots: dict[str, object] = {}
    first_path: Path | None = None
    seen: set[Path] = set()
    for base in (run_dir, run_dir.parent):
        for filename in CONFIG_FILENAMES:
            path = base / filename
            if path in seen or not path.exists():
                continue
            seen.add(path)
            data = _read_yaml_mapping(path)
            if data:
                if first_path is None:
                    first_path = path
                snapshots[display_path(path, run_dir)] = data
    return first_path, snapshots


def _dataset_selection(
    run_dir: Path,
    config_snapshot: Mapping[str, object] | None,
) -> dict[str, object]:
    selection = _read_json_mapping(run_dir / "dataset_selection.json")
    if selection:
        selection = dict(selection)
    else:
        selection = _dataset_selection_from_config(config_snapshot or {})
    records_path = run_dir / "dataset_selection_records.jsonl"
    source_records_path = run_dir / "dataset_selection_source_records.jsonl"
    if records_path.exists():
        selection["records_manifest"] = records_path.name
        selection["selected_evaluation_items"] = _jsonl_count(records_path)
    if source_records_path.exists():
        selection["source_records_manifest"] = source_records_path.name
        selection["selected_source_records"] = _jsonl_count(source_records_path)
    return selection


def _dataset_selection_from_config(config_snapshot: Mapping[str, object]) -> dict[str, object]:
    for snapshot in config_snapshot.values():
        if not isinstance(snapshot, Mapping):
            continue
        result: dict[str, object] = {}
        dataset = snapshot.get("dataset")
        selection = snapshot.get("selection")
        if isinstance(dataset, Mapping):
            result["dataset"] = dict(dataset)
        if isinstance(selection, Mapping):
            result["selection"] = dict(selection)
        if result:
            return result
    return {}


def _model_versions(
    config_snapshot: Mapping[str, object] | None,
    diagnostics_rows: Sequence[Mapping[str, object]],
    benchmark_result: object,
) -> dict[str, object]:
    versions: dict[str, object] = {}
    versions.update(_model_versions_from_config(config_snapshot or {}))
    versions.update(extract_model_versions_from_diagnostics(diagnostics_rows))
    if isinstance(benchmark_result, Mapping):
        if benchmark_result.get("model_id") is not None:
            versions["benchmark_model_id"] = benchmark_result["model_id"]
        if benchmark_result.get("label") is not None:
            versions["benchmark_model_label"] = benchmark_result["label"]
    return versions


def _model_versions_from_config(config_snapshot: Mapping[str, object]) -> dict[str, object]:
    versions: dict[str, object] = {}
    for snapshot in config_snapshot.values():
        if not isinstance(snapshot, Mapping):
            continue
        components = snapshot.get("components")
        if isinstance(components, Mapping):
            for slot, component in components.items():
                if isinstance(component, Mapping):
                    versions[str(slot)] = _component_identifier(component)
        asr = snapshot.get("asr")
        if isinstance(asr, Mapping):
            if asr.get("benchmark_model_id") is not None:
                versions["asr_benchmark_model_id"] = asr["benchmark_model_id"]
            component = asr.get("component")
            if isinstance(component, Mapping):
                versions["asr"] = _component_identifier(component)
        runner = snapshot.get("runner")
        if isinstance(runner, Mapping) and runner.get("name") is not None:
            versions["runner"] = runner["name"]
        if snapshot.get("id") is not None:
            versions["config_model_id"] = snapshot["id"]
        if snapshot.get("label") is not None:
            versions["config_model_label"] = snapshot["label"]
    return versions


def _component_identifier(component: Mapping[str, object]) -> dict[str, object]:
    params = component.get("params")
    params_mapping = params if isinstance(params, Mapping) else {}
    return {
        "name": component.get("name"),
        "adapter": component.get("adapter"),
        "enabled": component.get("enabled"),
        "model_name": params_mapping.get("model_name"),
        "model_size": params_mapping.get("model_size"),
        "model_family": params_mapping.get("model_family"),
    }


def _hardware_summary(runtime_metrics: Mapping[str, object]) -> dict[str, object]:
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "device": runtime_metrics.get("device"),
    }


def _metadata_block(metadata: ReportMetadata) -> str:
    return "\n".join(
        [
            f"- Run id: `{metadata.run_id}`",
            f"- Git commit: `{metadata.git_commit}`",
            f"- Config path: `{metadata.config_path}`",
            f"- Date: `{metadata.date}`",
            f"- Hardware platform: `{metadata.hardware.get('platform')}`",
            f"- Runtime device: `{metadata.hardware.get('device') or 'n/a'}`",
        ]
    )


def _metrics_block(
    metrics: Mapping[str, object],
    summary_rows: Sequence[Mapping[str, object]],
) -> str:
    lines = [
        f"- Machine-readable summary rows: `{len(summary_rows)}`",
        f"- Diagnostics rows: `{metrics.get('diagnostics_row_count', 0)}`",
        "",
    ]
    for source, group in _metric_groups_for(str(metrics.get("component_type")), metrics):
        if not isinstance(group, Mapping) or not group:
            continue
        lines.extend([f"### {source.replace('_', ' ').title()}", ""])
        lines.append(json_block(group))
        lines.append("")
    return "\n".join(lines).rstrip()


def _validation_block(validation: Mapping[str, object]) -> str:
    if not validation:
        return "- Validation scores pending."
    return "\n".join(
        [
            f"- Report completeness score: `{_format_score(validation.get('report_completeness_score'))}`",
            f"- Reproducibility score: `{_format_score(validation.get('reproducibility_score'))}`",
            f"- Comparison readiness score: `{_format_score(validation.get('comparison_readiness_score'))}`",
            f"- Required sections missing: `{validation.get('required_sections_missing') or []}`",
        ]
    )


def _artifacts_block(artifacts: Mapping[str, object]) -> str:
    return "\n".join(
        f"- {str(key).replace('_', ' ').title()}: `{value}`"
        for key, value in artifacts.items()
    )


def _read_json_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = read_json(path)
    return dict(value) if isinstance(value, Mapping) else {}


def _read_jsonl_mappings(path: Path) -> tuple[Mapping[str, object], ...]:
    if not path.exists():
        return ()
    return tuple(read_jsonl(path))


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data) if isinstance(data, Mapping) else {}


def _jsonl_count(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _read_index_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _csv_value(value: object) -> str:
    if isinstance(value, Mapping) or (
        isinstance(value, Sequence)
        and not isinstance(value, str | bytes | bytearray)
    ):
        return json.dumps(json_safe(value), sort_keys=True)
    return "" if value is None else str(value)


def _format_score(value: object) -> str:
    numeric = _optional_float(value)
    return "n/a" if numeric is None else f"{numeric:.4f}"


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate reusable component reports.")
    parser.add_argument("--run-dir", required=True, type=Path, help="Existing run directory.")
    parser.add_argument(
        "--component",
        default="end_to_end",
        help="Component report type, e.g. asr, speaker_matching, runtime, end-to-end.",
    )
    parser.add_argument(
        "--reports-root",
        type=Path,
        default=DEFAULT_REPORTS_ROOT,
        help="Reports root containing report_index.csv.",
    )
    parser.add_argument("--output-dir", type=Path, default=None, help="Optional output directory.")
    parser.add_argument("--primary-recommendation", default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    artifacts = generate_report_from_run(
        args.run_dir,
        component_type=args.component,
        reports_root=args.reports_root,
        output_dir=args.output_dir,
        primary_recommendation=args.primary_recommendation,
    )
    print(f"Markdown report: {artifacts.markdown_path}")
    print(f"CSV summary: {artifacts.csv_path}")
    print(f"JSON metrics: {artifacts.json_path}")
    print(f"Report index: {artifacts.index_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI boundary
    raise SystemExit(main())
