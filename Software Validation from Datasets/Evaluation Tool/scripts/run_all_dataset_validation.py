"""Run and aggregate the M16 all-dataset validation battery."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.dataset_registry.registry import (  # noqa: E402
    DatasetDefinition,
    get_dataset,
    list_datasets,
    validate_required_tables,
)
from app.prediction_io.schema import UTTERANCE_REQUIRED_FIELDS  # noqa: E402
from app.utils.json_utils import read_json, read_jsonl, write_json, write_jsonl  # noqa: E402
from app.utils.run_artifacts import ensure_run_subdirs, read_yaml, write_yaml  # noqa: E402


MILESTONE_DATASET_KEYS = (
    "cmu_arctic",
    "librispeech",
    "hifitts",
    "ami",
    "voices",
    "chime6",
)

STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_TIMED_OUT = "timed_out"
STATUS_MISSING_ARTIFACT = "missing_artifact"
STATUS_SKIPPED = "skipped"

FAILURE_ASR = "ASR"
FAILURE_VAD = "VAD"
FAILURE_SEGMENTATION = "segmentation"
FAILURE_SPEAKER_MATCHING = "speaker matching"
FAILURE_DATA = "data/artifact availability"
FAILURE_TIMEOUT_CRASH = "timeout/crash"
FAILURE_NONE = "none"


@dataclass(frozen=True)
class ValidationJobSpec:
    """One dataset/condition validation job."""

    job_id: str
    dataset: str
    label: str
    condition_id: str
    max_recordings: int | None
    subset_filters: Mapping[str, object] = field(default_factory=dict)
    augmentation: Mapping[str, object] = field(default_factory=dict)
    native_condition: bool = False
    runtime_device: str | None = None
    timeout_sec: float | None = None
    runner: str = "simulation"
    simulation_mode: str = "perfect"
    expected_audio_duration_sec: float | None = None
    config_snapshot: Mapping[str, object] = field(default_factory=dict)

    @property
    def augmentation_mode(self) -> str:
        return str(self.augmentation.get("mode") or "none")

    def to_jsonable(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "dataset": self.dataset,
            "label": self.label,
            "condition_id": self.condition_id,
            "max_recordings": self.max_recordings,
            "subset_filters": dict(self.subset_filters),
            "augmentation": dict(self.augmentation),
            "native_condition": self.native_condition,
            "runtime_device": self.runtime_device,
            "timeout_sec": self.timeout_sec,
            "runner": self.runner,
            "simulation_mode": self.simulation_mode,
            "expected_audio_duration_sec": self.expected_audio_duration_sec,
            "config_snapshot": dict(self.config_snapshot),
        }


@dataclass(frozen=True)
class ValidationSweepConfig:
    """Parsed all-dataset sweep YAML."""

    source_path: Path
    sweep_name: str
    default_run_id: str
    description: str | None
    runner: str
    simulation_mode: str
    runtime_device: str | None
    jobs: tuple[ValidationJobSpec, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "source_path": self.source_path.as_posix(),
            "sweep_name": self.sweep_name,
            "default_run_id": self.default_run_id,
            "description": self.description,
            "runner": self.runner,
            "simulation_mode": self.simulation_mode,
            "runtime_device": self.runtime_device,
            "jobs": [job.to_jsonable() for job in self.jobs],
        }


@dataclass(frozen=True)
class ValidationRunSummary:
    """Aggregated result for one generated run folder or blocked job."""

    run_id: str
    job_id: str
    dataset: str
    dataset_display_name: str
    condition_id: str
    augmentation_mode: str
    native_condition: bool
    run_dir: Path | None
    status: str
    metrics: Mapping[str, object] = field(default_factory=dict)
    group_metrics: Mapping[str, tuple[Mapping[str, object], ...]] = field(default_factory=dict)
    runtime_device: str | None = None
    blocker: str | None = None
    failure_mode: str = FAILURE_NONE
    command: tuple[str, ...] = ()
    duration_sec: float | None = None
    config_snapshot: Mapping[str, object] = field(default_factory=dict)
    model_identifiers: Mapping[str, object] = field(default_factory=dict)

    def to_jsonable(self, *, root: Path | None = None) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "job_id": self.job_id,
            "dataset": self.dataset,
            "dataset_display_name": self.dataset_display_name,
            "condition_id": self.condition_id,
            "augmentation_mode": self.augmentation_mode,
            "native_condition": self.native_condition,
            "run_dir": _display_path(self.run_dir, root),
            "status": self.status,
            "metrics": dict(self.metrics),
            "group_metrics": {
                key: [dict(row) for row in rows]
                for key, rows in self.group_metrics.items()
            },
            "runtime_device": self.runtime_device,
            "blocker": self.blocker,
            "failure_mode": self.failure_mode,
            "command": list(self.command),
            "duration_sec": self.duration_sec,
            "config_snapshot": dict(self.config_snapshot),
            "model_identifiers": dict(self.model_identifiers),
        }


@dataclass(frozen=True)
class ValidationResult:
    """Complete M16 validation aggregation."""

    run_id: str
    started_at: str
    wall_duration_sec: float
    sweep: ValidationSweepConfig
    runs: tuple[ValidationRunSummary, ...]
    dry_run_fixtures: bool = False

    @property
    def failure_rate(self) -> float:
        if not self.runs:
            return 0.0
        failed = sum(
            1
            for run in self.runs
            if run.status in {STATUS_FAILED, STATUS_TIMED_OUT, STATUS_MISSING_ARTIFACT}
        )
        return failed / len(self.runs)

    def to_jsonable(self, *, root: Path | None = None) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "wall_duration_sec": self.wall_duration_sec,
            "dry_run_fixtures": self.dry_run_fixtures,
            "failure_rate": self.failure_rate,
            "sweep": self.sweep.to_jsonable(),
            "runs": [run.to_jsonable(root=root) for run in self.runs],
            "dataset_rollups": dataset_rollups(self),
        }


def load_validation_sweep_config(path: Path) -> ValidationSweepConfig:
    """Load an all-dataset validation sweep config."""

    data = read_yaml(path)
    defaults = _mapping_or_empty(data.get("defaults"))
    dataset_entries = data.get("datasets")
    if not isinstance(dataset_entries, Sequence) or isinstance(dataset_entries, str | bytes | bytearray):
        raise ValueError("all-dataset sweep config requires a datasets list")

    runner = str(data.get("runner") or defaults.get("runner") or "simulation")
    simulation_mode = str(data.get("simulation_mode") or defaults.get("simulation_mode") or "perfect")
    runtime_device = _optional_str(data.get("runtime_device") or defaults.get("runtime_device"))
    jobs: list[ValidationJobSpec] = []
    seen_job_ids: set[str] = set()
    for entry_value in dataset_entries:
        entry = _mapping_or_empty(entry_value)
        if "key" not in entry:
            raise ValueError("dataset sweep entry is missing key")
        definition = get_dataset(str(entry["key"]))
        conditions = entry.get("conditions") or [{"id": "clean", "augmentation": entry.get("augmentation")}]
        if not isinstance(conditions, Sequence) or isinstance(conditions, str | bytes | bytearray):
            raise ValueError(f"conditions for {definition.key} must be a list")
        for condition_value in conditions:
            condition = _mapping_or_empty(condition_value)
            condition_id = str(condition.get("id") or condition.get("condition_id") or "clean")
            job_id = _safe_identifier(str(condition.get("job_id") or f"{definition.key}_{condition_id}"))
            if job_id in seen_job_ids:
                raise ValueError(f"duplicate validation job id: {job_id}")
            seen_job_ids.add(job_id)
            augmentation = {
                **_mapping_or_empty(defaults.get("augmentation")),
                **_mapping_or_empty(entry.get("augmentation")),
                **_mapping_or_empty(condition.get("augmentation")),
            }
            if "mode" not in augmentation:
                augmentation["mode"] = "none"
            subset_filters = {
                **_mapping_or_empty(defaults.get("subset_filters")),
                **_mapping_or_empty(entry.get("subset_filters")),
                **_mapping_or_empty(condition.get("subset_filters")),
            }
            max_recordings = _optional_int(
                condition.get("max_recordings", entry.get("max_recordings", defaults.get("max_recordings")))
            )
            job_runtime_device = _optional_str(
                condition.get("runtime_device", entry.get("runtime_device", runtime_device))
            )
            job_runner = str(condition.get("runner", entry.get("runner", runner)))
            job_simulation_mode = str(
                condition.get("simulation_mode", entry.get("simulation_mode", simulation_mode))
            )
            native_condition = bool(
                condition.get(
                    "native_condition",
                    entry.get("native_condition", not definition.supports_augmentation),
                )
            )
            config_snapshot = {
                "sweep_config": path.as_posix(),
                "dataset": definition.key,
                "condition_id": condition_id,
                "max_recordings": max_recordings,
                "subset_filters": subset_filters,
                "augmentation": augmentation,
                "native_condition": native_condition,
                "runner": job_runner,
                "simulation_mode": job_simulation_mode,
                "runtime_device": job_runtime_device,
            }
            jobs.append(
                ValidationJobSpec(
                    job_id=job_id,
                    dataset=definition.key,
                    label=str(entry.get("label") or definition.display_name),
                    condition_id=condition_id,
                    max_recordings=max_recordings,
                    subset_filters=subset_filters,
                    augmentation=augmentation,
                    native_condition=native_condition,
                    runtime_device=job_runtime_device,
                    timeout_sec=_optional_float(
                        condition.get("timeout_sec", entry.get("timeout_sec", defaults.get("timeout_sec")))
                    ),
                    runner=job_runner,
                    simulation_mode=job_simulation_mode,
                    expected_audio_duration_sec=_optional_float(
                        condition.get(
                            "expected_audio_duration_sec",
                            entry.get("expected_audio_duration_sec"),
                        )
                    ),
                    config_snapshot=config_snapshot,
                )
            )

    return ValidationSweepConfig(
        source_path=path,
        sweep_name=str(data.get("sweep_name") or path.stem),
        default_run_id=str(data.get("run_id") or path.stem),
        description=_optional_str(data.get("description")),
        runner=runner,
        simulation_mode=simulation_mode,
        runtime_device=runtime_device,
        jobs=tuple(jobs),
    )


def build_evaluation_command(
    job: ValidationJobSpec,
    *,
    project_root: Path,
    runs_root: Path,
) -> tuple[str, ...]:
    """Build the existing Evaluation Tool CLI command for one real validation job."""

    command: list[str] = [
        sys.executable,
        "-m",
        "app.cli.main",
        "full",
        "--project-root",
        project_root.as_posix(),
        "--dataset",
        job.dataset,
        "--runner",
        job.runner,
        "--run-name",
        job.job_id,
        "--runs-root",
        runs_root.as_posix(),
        "--augmentation",
        job.augmentation_mode,
    ]
    if job.runner == "simulation":
        command.extend(["--simulation-mode", job.simulation_mode])
    if job.max_recordings is not None:
        command.extend(["--max-recordings", str(job.max_recordings)])
    for key, value in job.subset_filters.items():
        command.extend(["--subset", f"{key}={_subset_value(value)}"])
    for noise_type in _as_sequence(job.augmentation.get("noise_type") or job.augmentation.get("noise_types")):
        command.extend(["--noise-type", str(noise_type)])
    for snr_db in _as_sequence(job.augmentation.get("snr_db") or job.augmentation.get("snr_values")):
        command.extend(["--snr-db", str(snr_db)])
    rir_paths = _as_sequence(job.augmentation.get("rir_paths") or job.augmentation.get("rir_path"))
    if rir_paths:
        command.append("--rir-paths")
        command.extend(str(path) for path in rir_paths)
    return tuple(command)


def run_validation_jobs(
    sweep: ValidationSweepConfig,
    *,
    run_id: str,
    project_root: Path,
    output_root: Path,
) -> tuple[ValidationRunSummary, ...]:
    """Run real validation jobs through the existing Evaluation Tool CLI."""

    summaries: list[ValidationRunSummary] = []
    validation_root = output_root / run_id
    logs_root = validation_root / "_validation_logs"
    logs_root.mkdir(parents=True, exist_ok=True)
    for job in sweep.jobs:
        definition = get_dataset(job.dataset)
        missing_tables = validate_required_tables(project_root, definition)
        if missing_tables:
            summaries.append(
                blocked_summary(
                    run_id=run_id,
                    job=job,
                    definition=definition,
                    status=STATUS_SKIPPED,
                    blocker="Missing normalized metadata: "
                    + ", ".join(path.as_posix() for path in missing_tables),
                    failure_mode=FAILURE_DATA,
                )
            )
            continue

        job_runs_root = validation_root / job.job_id
        command = build_evaluation_command(job, project_root=project_root, runs_root=job_runs_root)
        started = time.perf_counter()
        stdout_path = logs_root / f"{job.job_id}.stdout.txt"
        stderr_path = logs_root / f"{job.job_id}.stderr.txt"
        try:
            completed = subprocess.run(
                command,
                cwd=TOOL_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=job.timeout_sec,
                check=False,
            )
            duration = time.perf_counter() - started
            stdout_path.write_text(completed.stdout, encoding="utf-8")
            stderr_path.write_text(completed.stderr, encoding="utf-8")
            run_dir = find_generated_run_dir(job_runs_root)
            status = STATUS_SUCCEEDED if completed.returncode == 0 and run_dir is not None else STATUS_FAILED
            blocker = None
            if completed.returncode != 0:
                blocker = f"Evaluation command returned {completed.returncode}; see {stderr_path.as_posix()}"
            elif run_dir is None:
                blocker = f"Evaluation command did not create a run folder under {job_runs_root.as_posix()}"
            summaries.append(
                aggregate_run_folder(
                    run_dir,
                    job=job,
                    run_id=run_id,
                    status=status,
                    blocker=blocker,
                    command=command,
                    duration_sec=duration,
                )
                if run_dir is not None
                else blocked_summary(
                    run_id=run_id,
                    job=job,
                    definition=definition,
                    status=status,
                    blocker=blocker,
                    command=command,
                    duration_sec=duration,
                    failure_mode=FAILURE_TIMEOUT_CRASH,
                )
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.perf_counter() - started
            stdout_path.write_text(exc.stdout or "", encoding="utf-8")
            stderr_path.write_text(exc.stderr or "", encoding="utf-8")
            summaries.append(
                blocked_summary(
                    run_id=run_id,
                    job=job,
                    definition=definition,
                    status=STATUS_TIMED_OUT,
                    blocker=f"Evaluation command timed out after {job.timeout_sec} seconds",
                    command=command,
                    duration_sec=duration,
                    failure_mode=FAILURE_TIMEOUT_CRASH,
                )
            )
    return tuple(summaries)


def create_fixture_run_folders(
    output_root: Path,
    *,
    run_id: str,
    jobs: Sequence[ValidationJobSpec],
) -> tuple[Path, ...]:
    """Create tiny synthetic run folders for M16 dry smoke and tests."""

    created: list[Path] = []
    for index, job in enumerate(jobs):
        definition = get_dataset(job.dataset)
        run_dir = output_root / run_id / job.job_id / f"{run_id}_{job.job_id}"
        ensure_run_subdirs(run_dir)
        write_yaml(run_dir / "run_config.yaml", fixture_run_config(job, definition, run_id, run_dir))
        write_json(run_dir / "dataset_selection.json", fixture_dataset_selection(job, definition))
        records = fixture_selection_records(job, index)
        write_jsonl(run_dir / "dataset_selection_records.jsonl", records)
        write_jsonl(run_dir / "dataset_selection_source_records.jsonl", records)
        predictions = fixture_predictions(records, job)
        write_jsonl(run_dir / "predictions" / "utterances.jsonl", predictions)
        write_json(
            run_dir / "predictions" / "runner_summary.json",
            {
                "runner": job.runner,
                "attempted_count": len(records),
                "written_count": len(predictions),
                "failed_count": 0,
                "skipped_count": 0,
            },
        )
        write_jsonl(run_dir / "predictions" / "diagnostics.jsonl", fixture_diagnostics(records, job))
        write_json(run_dir / "metrics" / "aggregate_metrics.json", fixture_aggregate_metrics(records, predictions, index))
        write_fixture_metric_csvs(run_dir, job, records, predictions, index)
        created.append(run_dir)
    return tuple(created)


def aggregate_run_folder(
    run_dir: Path | None,
    *,
    job: ValidationJobSpec,
    run_id: str,
    status: str | None = None,
    blocker: str | None = None,
    command: Sequence[str] = (),
    duration_sec: float | None = None,
) -> ValidationRunSummary:
    """Aggregate existing Evaluation Tool artifacts for one run folder."""

    definition = get_dataset(job.dataset)
    if run_dir is None:
        return blocked_summary(
            run_id=run_id,
            job=job,
            definition=definition,
            status=status or STATUS_MISSING_ARTIFACT,
            blocker=blocker or "Run folder was not available",
            command=command,
            duration_sec=duration_sec,
            failure_mode=FAILURE_DATA,
        )

    config = _read_yaml_mapping(run_dir / "run_config.yaml")
    aggregate = _read_json_mapping(run_dir / "metrics" / "aggregate_metrics.json")
    selection = _read_json_mapping(run_dir / "dataset_selection.json")
    diagnostics_metrics, diagnostics_models = collect_diagnostics_metrics(run_dir / "predictions" / "diagnostics.jsonl")
    derived_metrics = {
        **aggregate,
        **derived_metrics_from_run(run_dir),
        **diagnostics_metrics,
    }
    if selection:
        derived_metrics.setdefault("selected_evaluation_items", selection.get("selected_evaluation_items"))
        derived_metrics.setdefault("missing_audio_count", selection.get("missing_audio_count"))

    effective_status = status or (STATUS_SUCCEEDED if aggregate else STATUS_MISSING_ARTIFACT)
    effective_blocker = blocker
    if effective_status == STATUS_MISSING_ARTIFACT and effective_blocker is None:
        effective_blocker = f"Missing aggregate metrics in {run_dir.as_posix()}"
    failure_mode = classify_failure_mode(effective_status, derived_metrics, effective_blocker)
    model_identifiers = collect_model_identifiers(config, diagnostics_models)
    return ValidationRunSummary(
        run_id=run_id,
        job_id=job.job_id,
        dataset=job.dataset,
        dataset_display_name=definition.display_name,
        condition_id=job.condition_id,
        augmentation_mode=job.augmentation_mode,
        native_condition=job.native_condition,
        run_dir=run_dir,
        status=effective_status,
        metrics=derived_metrics,
        group_metrics=collect_group_metric_rows(run_dir / "metrics"),
        runtime_device=_optional_str(derived_metrics.get("runtime_device") or job.runtime_device),
        blocker=effective_blocker,
        failure_mode=failure_mode,
        command=tuple(command),
        duration_sec=duration_sec,
        config_snapshot=config or dict(job.config_snapshot),
        model_identifiers=model_identifiers,
    )


def blocked_summary(
    *,
    run_id: str,
    job: ValidationJobSpec,
    definition: DatasetDefinition,
    status: str,
    blocker: str | None,
    failure_mode: str,
    command: Sequence[str] = (),
    duration_sec: float | None = None,
) -> ValidationRunSummary:
    return ValidationRunSummary(
        run_id=run_id,
        job_id=job.job_id,
        dataset=job.dataset,
        dataset_display_name=definition.display_name,
        condition_id=job.condition_id,
        augmentation_mode=job.augmentation_mode,
        native_condition=job.native_condition,
        run_dir=None,
        status=status,
        metrics={},
        group_metrics={},
        runtime_device=job.runtime_device,
        blocker=blocker,
        failure_mode=failure_mode,
        command=tuple(command),
        duration_sec=duration_sec,
        config_snapshot=dict(job.config_snapshot),
    )


def dataset_rollups(result: ValidationResult) -> list[dict[str, object]]:
    """Return comparison-ready one-row-per-dataset rollups."""

    rows: list[dict[str, object]] = []
    for key in MILESTONE_DATASET_KEYS:
        definition = get_dataset(key)
        runs = [run for run in result.runs if run.dataset == key]
        statuses = [run.status for run in runs]
        metrics = [run.metrics for run in runs]
        rows.append(
            {
                "dataset": key,
                "dataset_display_name": definition.display_name,
                "attempted_runs": len(runs),
                "succeeded_runs": statuses.count(STATUS_SUCCEEDED),
                "failed_runs": statuses.count(STATUS_FAILED) + statuses.count(STATUS_MISSING_ARTIFACT),
                "timed_out_runs": statuses.count(STATUS_TIMED_OUT),
                "skipped_runs": statuses.count(STATUS_SKIPPED),
                "wer": _weighted_rate(metrics, "errors", "reference_words", "aggregate_wer"),
                "cer": _mean_metric(metrics, "cer"),
                "speaker_label_accuracy": _mean_metric(metrics, "speaker_label_accuracy"),
                "false_known_rate": _mean_metric(metrics, "false_known_rate"),
                "unknown_rate": _mean_metric(metrics, "unknown_rate"),
                "missing_prediction_count": _sum_metric(metrics, "missing_prediction_count", "missing_predictions"),
                "missing_prediction_rate": _mean_metric(metrics, "missing_prediction_rate"),
                "crash_timeout_rate": _crash_timeout_rate(runs),
                "realtime_factor": _mean_metric(metrics, "realtime_factor_mean", "realtime_factor"),
                "memory_peak_mb": _max_metric(metrics, "memory_peak_mb"),
                "stutter_repetition_rate": _mean_metric(metrics, "stutter_repetition_rate"),
                "failure_modes": ", ".join(
                    sorted({run.failure_mode for run in runs if run.failure_mode != FAILURE_NONE})
                )
                or FAILURE_NONE,
            }
        )
    return rows


def write_validation_outputs(result: ValidationResult, report_path: Path) -> tuple[Path, Path]:
    """Write JSON and CSV outputs beside the markdown report."""

    json_path = report_path.with_suffix(".json")
    csv_path = report_path.with_suffix(".csv")
    write_json(json_path, result.to_jsonable(root=TOOL_ROOT))
    rows = dataset_rollups(result)
    columns = (
        "dataset",
        "dataset_display_name",
        "attempted_runs",
        "succeeded_runs",
        "failed_runs",
        "timed_out_runs",
        "skipped_runs",
        "wer",
        "cer",
        "speaker_label_accuracy",
        "false_known_rate",
        "unknown_rate",
        "missing_prediction_count",
        "missing_prediction_rate",
        "crash_timeout_rate",
        "realtime_factor",
        "memory_peak_mb",
        "stutter_repetition_rate",
        "failure_modes",
    )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def write_validation_report(
    path: Path,
    result: ValidationResult,
    *,
    test_commands: Sequence[str] = (),
    smoke_commands: Sequence[str] = (),
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the required M16 validation report artifact."""

    json_path, csv_path = write_validation_outputs(result, path)
    rollups = dataset_rollups(result)
    lines = [
        "# All-Dataset Validation Report",
        "",
        "## Milestone",
        "",
        "M16 - All-Dataset and All-Augmentation Validation Battery",
        "",
        "## Sweep Config Used",
        "",
        f"- Run id: `{result.run_id}`",
        f"- Sweep: `{result.sweep.sweep_name}`",
        f"- Config path: `{_display_path(result.sweep.source_path, TOOL_ROOT)}`",
        f"- Dry fixture mode: `{result.dry_run_fixtures}`",
        f"- Started at: `{result.started_at}`",
        f"- Wall duration seconds: `{result.wall_duration_sec:.3f}`",
        f"- Machine-readable JSON: `{_display_path(json_path, TOOL_ROOT)}`",
        f"- Machine-readable CSV: `{_display_path(csv_path, TOOL_ROOT)}`",
        "",
        "## Datasets Attempted",
        "",
    ]
    for key in MILESTONE_DATASET_KEYS:
        attempted = [run for run in result.runs if run.dataset == key]
        lines.append(f"- {get_dataset(key).display_name} (`{key}`): {len(attempted)} job(s)")

    lines.extend(
        [
            "",
            "## Dataset Availability And Blockers",
            "",
        ]
    )
    blocker_rows = [run for run in result.runs if run.blocker]
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    if blocker_rows:
        for run in blocker_rows:
            lines.append(f"- `{run.job_id}`: {run.blocker}")
    if not blockers and not blocker_rows:
        lines.append("- No dataset availability blockers were recorded for this run.")

    lines.extend(
        [
            "",
            "## Generated Run Folders",
            "",
        ]
    )
    for run in result.runs:
        run_dir = _display_path(run.run_dir, TOOL_ROOT) if run.run_dir else "n/a"
        lines.append(f"- `{run.job_id}` ({run.status}): `{run_dir}`")

    lines.extend(
        [
            "",
            "## Cross-Dataset Comparison",
            "",
            "| Dataset | Runs | WER | CER | Speaker accuracy | Missing rate | Crash/timeout rate | RTF | Memory MB | Failure modes |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for row in rollups:
        lines.append(
            "| {dataset} | {runs} | {wer} | {cer} | {speaker} | {missing} | {crash} | {rtf} | {memory} | {modes} |".format(
                dataset=row["dataset"],
                runs=row["attempted_runs"],
                wer=_fmt_metric(row["wer"]),
                cer=_fmt_metric(row["cer"]),
                speaker=_fmt_metric(row["speaker_label_accuracy"]),
                missing=_fmt_metric(row["missing_prediction_rate"]),
                crash=_fmt_metric(row["crash_timeout_rate"]),
                rtf=_fmt_metric(row["realtime_factor"]),
                memory=_fmt_metric(row["memory_peak_mb"]),
                modes=row["failure_modes"],
            )
        )

    lines.extend(
        [
            "",
            "## Augmentation And Native-Condition Breakdown",
            "",
            "| Job | Dataset | Condition | Augmentation | Native condition | SNR | Noise | Status | WER | Missing rate | Device |",
            "| --- | --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | --- |",
        ]
    )
    for run in result.runs:
        metrics = run.metrics
        lines.append(
            "| {job} | {dataset} | {condition} | {mode} | {native} | {snr} | {noise} | {status} | {wer} | {missing} | {device} |".format(
                job=run.job_id,
                dataset=run.dataset,
                condition=run.condition_id,
                mode=run.augmentation_mode,
                native=run.native_condition,
                snr=_fmt_metric(metrics.get("snr_db")),
                noise=metrics.get("noise_type") or "n/a",
                status=run.status,
                wer=_fmt_metric(metrics.get("aggregate_wer")),
                missing=_fmt_metric(metrics.get("missing_prediction_rate")),
                device=run.runtime_device or "n/a",
            )
        )

    lines.extend([""])
    for key in MILESTONE_DATASET_KEYS:
        definition = get_dataset(key)
        runs = [run for run in result.runs if run.dataset == key]
        lines.extend([f"## {definition.display_name} (`{key}`)", ""])
        if not runs:
            lines.append("No run was generated for this dataset.")
            lines.append("")
            continue
        for run in runs:
            lines.extend(
                [
                    f"### {run.condition_id}",
                    "",
                    f"- Status: `{run.status}`",
                    f"- Run folder: `{_display_path(run.run_dir, TOOL_ROOT) if run.run_dir else 'n/a'}`",
                    f"- Failure mode: `{run.failure_mode}`",
                    f"- WER: `{_fmt_metric(run.metrics.get('aggregate_wer'))}`",
                    f"- CER: `{_fmt_metric(run.metrics.get('cer'))}`",
                    f"- Speaker label accuracy: `{_fmt_metric(run.metrics.get('speaker_label_accuracy'))}`",
                    f"- Missing predictions: `{_fmt_metric(run.metrics.get('missing_prediction_count') or run.metrics.get('missing_predictions'))}`",
                    f"- Missing prediction rate: `{_fmt_metric(run.metrics.get('missing_prediction_rate'))}`",
                    f"- Runtime device: `{run.runtime_device or 'n/a'}`",
                    f"- Realtime factor: `{_fmt_metric(run.metrics.get('realtime_factor_mean') or run.metrics.get('realtime_factor'))}`",
                    f"- Memory peak MB: `{_fmt_metric(run.metrics.get('memory_peak_mb'))}`",
                    f"- Stutter/repetition rate: `{_fmt_metric(run.metrics.get('stutter_repetition_rate'))}`",
                ]
            )
            if run.model_identifiers:
                lines.append(f"- Model identifiers: `{json.dumps(run.model_identifiers, sort_keys=True)}`")
            if run.blocker:
                lines.append(f"- Blocker: {run.blocker}")
            lines.append("")

    lines.extend(
        [
            "## Failure-Mode Classification",
            "",
            "| Job | Status | Failure mode | Blocker |",
            "| --- | --- | --- | --- |",
        ]
    )
    for run in result.runs:
        lines.append(
            f"| {run.job_id} | {run.status} | {run.failure_mode} | {run.blocker or 'n/a'} |"
        )

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
        ]
    )
    for recommendation in recommendations_for_result(result):
        lines.append(f"- {recommendation}")

    lines.extend(["", "## Exact Commands", ""])
    if test_commands:
        lines.append("### Tests")
        lines.append("")
        for command in test_commands:
            lines.append(f"- `{command}`")
    if smoke_commands:
        lines.append("")
        lines.append("### Smoke Checks")
        lines.append("")
        for command in smoke_commands:
            lines.append(f"- `{command}`")
    if not test_commands and not smoke_commands:
        lines.append("- No test or smoke commands were recorded.")

    lines.extend(["", "## Incomplete Or Blocked", ""])
    all_incomplete = list(incomplete)
    if result.dry_run_fixtures:
        all_incomplete.append("Dry fixture mode validates sweep parsing, aggregation, and reporting only; full real dataset/model execution was not performed.")
    if all_incomplete:
        for item in all_incomplete:
            lines.append(f"- {item}")
    else:
        lines.append("- No incomplete items were recorded.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def write_milestone_summary(
    path: Path,
    *,
    validation_report_path: Path,
    test_commands: Sequence[str],
    smoke_commands: Sequence[str],
    blockers: Sequence[str],
) -> Path:
    """Write the high-level M16 milestone summary outside the Evaluation Tool."""

    lines = [
        "# M16 All-Dataset Validation Battery Summary",
        "",
        "## What Changed",
        "",
        "- Added all-dataset smoke and robustness sweep configs.",
        "- Added an all-dataset validation script that can run existing Evaluation Tool jobs or generate dry fixture run folders.",
        "- Added aggregation and report generation for per-dataset, per-condition, failure-mode, runtime, missing prediction, and speaker metrics.",
        "",
        "## Files Added Or Updated",
        "",
        "- `Evaluation Tool/configs/sweeps/all_datasets_smoke.yaml`",
        "- `Evaluation Tool/configs/sweeps/all_datasets_robustness.yaml`",
        "- `Evaluation Tool/scripts/run_all_dataset_validation.py`",
        "- `Evaluation Tool/tests/inference_pipeline/test_all_dataset_validation.py`",
        "- `Evaluation Tool/reports/validation/all_dataset_validation_<run_id>.md` plus JSON/CSV companions",
        "- `Evaluation Tool/runs/all_dataset_validation/<run_id>/` dry or real generated run folders",
        "- `milestone/reports/M16_all_dataset_validation_report.md`",
        "",
        "## Validation Report",
        "",
        f"- `{validation_report_path.as_posix()}`",
        "",
        "## Tests And Smoke Checks",
        "",
    ]
    for command in test_commands:
        lines.append(f"- `{command}`")
    for command in smoke_commands:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Remaining Incomplete Or Blocked", ""])
    if blockers:
        for blocker in blockers:
            lines.append(f"- {blocker}")
    else:
        lines.append("- Full real all-dataset execution still depends on local normalized metadata, raw audio, and model assets; dry fixture coverage was used where those assets were not required.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    wall_started = time.perf_counter()
    sweep_path = _resolve_tool_path(args.sweep_config)
    sweep = load_validation_sweep_config(sweep_path)
    run_id = args.run_id or sweep.default_run_id or f"m16_{int(time.time())}"
    output_root = _resolve_tool_path(args.output_root)
    project_root = args.project_root.resolve() if args.project_root else PROJECT_ROOT
    report_path = (
        _resolve_tool_path(args.report_path)
        if args.report_path
        else TOOL_ROOT / "reports" / "validation" / f"all_dataset_validation_{run_id}.md"
    )
    blockers: list[str] = []
    incomplete: list[str] = []

    if args.dry_run_fixtures:
        run_dirs = create_fixture_run_folders(output_root, run_id=run_id, jobs=sweep.jobs)
        summaries = tuple(
            aggregate_run_folder(
                run_dir,
                job=job,
                run_id=run_id,
                status=STATUS_SUCCEEDED,
                command=(),
            )
            for run_dir, job in zip(run_dirs, sweep.jobs, strict=True)
        )
        blockers.append("Full real all-dataset execution was not attempted in dry fixture mode.")
    else:
        summaries = run_validation_jobs(
            sweep,
            run_id=run_id,
            project_root=project_root,
            output_root=output_root,
        )

    result = ValidationResult(
        run_id=run_id,
        started_at=started,
        wall_duration_sec=time.perf_counter() - wall_started,
        sweep=sweep,
        runs=summaries,
        dry_run_fixtures=args.dry_run_fixtures,
    )
    smoke_commands = list(args.smoke_command or [])
    if not smoke_commands:
        smoke_commands.append(command_summary(args, run_id))
    test_commands = list(args.test_command or [])
    write_validation_report(
        report_path,
        result,
        test_commands=test_commands,
        smoke_commands=smoke_commands,
        blockers=blockers,
        incomplete=incomplete,
    )
    if args.milestone_summary_path:
        write_milestone_summary(
            _resolve_project_path(args.milestone_summary_path),
            validation_report_path=report_path,
            test_commands=test_commands,
            smoke_commands=smoke_commands,
            blockers=[*blockers, *incomplete],
        )
    print(f"Validation report: {report_path}")
    print(f"Validation JSON: {report_path.with_suffix('.json')}")
    print(f"Validation CSV: {report_path.with_suffix('.csv')}")
    print(f"Failure rate: {result.failure_rate:.4f}")
    return 0 if all(run.status in {STATUS_SUCCEEDED, STATUS_SKIPPED} for run in summaries) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the M16 all-dataset validation battery.")
    parser.add_argument(
        "--sweep-config",
        type=Path,
        default=Path("configs/sweeps/all_datasets_smoke.yaml"),
        help="Sweep YAML path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root. Defaults to the parent of Evaluation Tool.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("runs/all_dataset_validation"),
        help="Output root, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument(
        "--dry-run-fixtures",
        action="store_true",
        help="Create tiny synthetic run folders instead of invoking real dataset/model jobs.",
    )
    parser.add_argument("--test-command", action="append", default=[])
    parser.add_argument("--smoke-command", action="append", default=[])
    parser.add_argument("--milestone-summary-path", type=Path, default=None)
    return parser


def fixture_run_config(
    job: ValidationJobSpec,
    definition: DatasetDefinition,
    run_id: str,
    run_dir: Path,
) -> dict[str, object]:
    return {
        "command": "m16_fixture",
        "run_id": run_id,
        "run_dir": run_dir.as_posix(),
        "dataset": {
            "key": definition.key,
            "name": definition.display_name,
            "dataset_id": definition.dataset_id,
            "normalized_metadata_dir": definition.normalized_metadata_dir.as_posix(),
        },
        "selection": {
            "subset_filters": dict(job.subset_filters),
            "max_recordings": job.max_recordings,
            "selected_source_recordings": 2,
            "selected_recordings": 2,
            "total_source_duration_sec": 4.0,
            "total_evaluation_duration_sec": 4.0,
        },
        "augmentation": {
            "mode": job.augmentation_mode,
            "condition_id": job.condition_id,
            "conditions": [
                {
                    "condition_id": job.condition_id,
                    **dict(job.augmentation),
                }
            ],
            "native_condition": job.native_condition,
        },
        "runner": {
            "name": job.runner,
            "simulation_mode": job.simulation_mode if job.runner == "simulation" else None,
        },
        "components": {
            "asr": {
                "name": "fixture_asr",
                "enabled": True,
                "params": {"model_name": "m16-fixture-asr@1"},
            },
            "speaker_matching": {
                "name": "fixture_speaker_matching",
                "enabled": True,
                "params": {"model_name": "m16-fixture-speaker@1"},
            },
        },
        "runtime": {
            "device": job.runtime_device or "cpu",
        },
        "prediction_contract": {
            "minimum_file": "predictions/utterances.jsonl",
            "required_fields": list(UTTERANCE_REQUIRED_FIELDS),
        },
        "m16_validation_job": job.to_jsonable(),
    }


def fixture_dataset_selection(job: ValidationJobSpec, definition: DatasetDefinition) -> dict[str, object]:
    return {
        "dataset_key": definition.key,
        "dataset_name": definition.display_name,
        "selected_source_recordings": 2,
        "selected_evaluation_items": 2,
        "missing_audio_count": 0,
        "subset_filters": dict(job.subset_filters),
        "records_manifest": "dataset_selection_records.jsonl",
        "condition_id": job.condition_id,
    }


def fixture_selection_records(job: ValidationJobSpec, index: int) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for row_index in range(2):
        start_sec = float(row_index * 2)
        end_sec = start_sec + 2.0
        records.append(
            {
                "dataset": job.dataset,
                "dataset_id": job.dataset,
                "recording_id": f"{job.dataset}_{job.condition_id}_rec_{row_index + 1}",
                "utt_id": f"{job.dataset}_{job.condition_id}_utt_{row_index + 1}",
                "source_recording_id": f"{job.dataset}_source_{row_index + 1}",
                "start_sec": start_sec,
                "end_sec": end_sec,
                "duration_sec": 2.0,
                "speaker_label": "speaker_a" if row_index == 0 else "speaker_b",
                "reference_text": "hello validation battery" if row_index == 0 else "robust speech check",
                "audio_exists": True,
                "audio_path_project_relative": f"fixture_audio/{job.dataset}_{row_index + 1}.wav",
                "inference_audio_path": f"fixture_audio/{job.dataset}_{job.condition_id}_{row_index + 1}.wav",
                "augmentation_condition_id": job.condition_id,
                "augmentation_mode": job.augmentation_mode,
                "noise_type": job.augmentation.get("noise_type"),
                "snr_db": job.augmentation.get("snr_db"),
                "runtime_device": job.runtime_device or "cpu",
                "fixture_metric_offset": index,
            }
        )
    return records


def fixture_predictions(
    records: Sequence[Mapping[str, object]],
    job: ValidationJobSpec,
) -> list[dict[str, object]]:
    predictions: list[dict[str, object]] = []
    for row_index, record in enumerate(records):
        predictions.append(
            {
                "recording_id": str(record["recording_id"]),
                "utt_id": str(record["utt_id"]),
                "start_sec": record["start_sec"],
                "end_sec": record["end_sec"],
                "speaker_label": record["speaker_label"] if row_index == 0 else "Unknown",
                "text": record["reference_text"] if row_index == 0 else "robust robust speech check",
                "augmentation_condition_id": job.condition_id,
            }
        )
    return predictions


def fixture_diagnostics(
    records: Sequence[Mapping[str, object]],
    job: ValidationJobSpec,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record in records:
        rows.append(
            {
                "recording_id": record["recording_id"],
                "utt_id": record["utt_id"],
                "start_sec": record["start_sec"],
                "end_sec": record["end_sec"],
                "speaker_label": record["speaker_label"],
                "diagnostics": {
                    "runtime_stats": {
                        "device": job.runtime_device or "cpu",
                        "audio_duration_sec": 2.0,
                        "total_sec": 0.5,
                        "realtime_factor": 0.25,
                        "memory_peak_mb": 256.0,
                        "model_versions": {
                            "asr": "m16-fixture-asr@1",
                            "speaker_matching": "m16-fixture-speaker@1",
                        },
                    }
                },
                "warnings": [],
                "errors": [],
            }
        )
    return rows


def fixture_aggregate_metrics(
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    index: int,
) -> dict[str, object]:
    reference_words = sum(len(str(record["reference_text"]).split()) for record in records)
    errors = 1 + (index % 2)
    selected = len(records)
    speaker_scored = len(predictions)
    speaker_matches = 1
    return {
        "selected_recordings": selected,
        "selected_recording_count": selected,
        "prediction_rows": len(predictions),
        "processed_predictions": len(predictions),
        "processed_prediction_count": len(predictions),
        "missing_predictions": 0,
        "missing_prediction_count": 0,
        "missing_prediction_rate": 0.0,
        "audio_missing": 0,
        "total_duration_sec": 4.0,
        "scored_duration_sec": 4.0,
        "reference_words": reference_words,
        "hypothesis_words": reference_words + 1,
        "errors": errors,
        "substitutions": errors,
        "deletions": 0,
        "insertions": 1,
        "aggregate_wer": errors / reference_words if reference_words else 0.0,
        "mean_recording_wer": errors / reference_words if reference_words else 0.0,
        "cer": None,
        "speaker_label_scored": speaker_scored,
        "speaker_label_matches": speaker_matches,
        "speaker_label_accuracy": speaker_matches / speaker_scored if speaker_scored else None,
    }


def write_fixture_metric_csvs(
    run_dir: Path,
    job: ValidationJobSpec,
    records: Sequence[Mapping[str, object]],
    predictions: Sequence[Mapping[str, object]],
    index: int,
) -> None:
    aggregate = fixture_aggregate_metrics(records, predictions, index)
    rows = []
    for record, prediction in zip(records, predictions, strict=True):
        rows.append(
            {
                "recording_id": record["recording_id"],
                "utt_id": record["utt_id"],
                "speaker_label": record["speaker_label"],
                "predicted_speaker_label": prediction["speaker_label"],
                "speaker_label_scored": True,
                "speaker_label_match": record["speaker_label"] == prediction["speaker_label"],
                "reference_text": record["reference_text"],
                "hypothesis_text": prediction["text"],
                "transcript_scored": True,
                "wer": aggregate["aggregate_wer"],
                "errors": aggregate["errors"],
                "reference_words": len(str(record["reference_text"]).split()),
                "hypothesis_words": len(str(prediction["text"]).split()),
                "duration_sec": record["duration_sec"],
                "missing_prediction": False,
                "audio_exists": True,
                "augmentation_condition_id": job.condition_id,
                "augmentation_mode": job.augmentation_mode,
                "noise_type": job.augmentation.get("noise_type"),
                "snr_db": job.augmentation.get("snr_db"),
                "runtime_device": job.runtime_device or "cpu",
            }
        )
    _write_csv(run_dir / "metrics" / "per_recording_metrics.csv", rows)
    group_row = {
        "augmentation_condition_id": job.condition_id,
        "file_count": len(rows),
        "recordings": len(rows),
        "processed_predictions": len(rows),
        "missing_predictions": 0,
        "total_duration_sec": 4.0,
        "reference_words": aggregate["reference_words"],
        "errors": aggregate["errors"],
        "aggregate_wer": aggregate["aggregate_wer"],
        "speaker_label_accuracy": aggregate["speaker_label_accuracy"],
    }
    _write_csv(run_dir / "metrics" / "augmentation_condition_id_metrics.csv", [group_row])
    if job.augmentation.get("noise_type"):
        _write_csv(
            run_dir / "metrics" / "noise_type_metrics.csv",
            [{**group_row, "noise_type": job.augmentation.get("noise_type")}],
        )
    if job.augmentation.get("snr_db") is not None:
        _write_csv(
            run_dir / "metrics" / "snr_db_metrics.csv",
            [{**group_row, "snr_db": job.augmentation.get("snr_db")}],
        )
    _write_csv(
        run_dir / "metrics" / "runtime_device_metrics.csv",
        [{**group_row, "runtime_device": job.runtime_device or "cpu"}],
    )


def derived_metrics_from_run(run_dir: Path) -> dict[str, object]:
    per_recording = run_dir / "metrics" / "per_recording_metrics.csv"
    predictions = run_dir / "predictions" / "utterances.jsonl"
    derived: dict[str, object] = {}
    if per_recording.exists():
        rows = _read_csv_rows(per_recording)
        derived.update(speaker_rates_from_metric_rows(rows))
        if rows:
            for key in ("augmentation_condition_id", "augmentation_mode", "snr_db", "noise_type", "runtime_device"):
                values = [row.get(key) for row in rows if row.get(key) not in (None, "")]
                if values:
                    derived[key] = values[0]
    if predictions.exists():
        derived["stutter_repetition_rate"] = stutter_repetition_rate(predictions)
    return derived


def collect_diagnostics_metrics(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    if not path.exists():
        return {}, {}
    realtime_factors: list[float] = []
    total_sec_values: list[float] = []
    audio_sec_values: list[float] = []
    memory_values: list[float] = []
    devices: list[str] = []
    model_versions: dict[str, object] = {}
    for row in read_jsonl(path):
        diagnostics = row.get("diagnostics")
        if not isinstance(diagnostics, Mapping):
            continue
        stats = diagnostics.get("runtime_stats")
        if not isinstance(stats, Mapping):
            continue
        _append_float(realtime_factors, stats.get("realtime_factor"))
        _append_float(total_sec_values, stats.get("total_sec"))
        _append_float(audio_sec_values, stats.get("audio_duration_sec"))
        _append_float(memory_values, stats.get("memory_peak_mb") or stats.get("peak_memory_mb"))
        device = _optional_str(stats.get("device"))
        if device:
            devices.append(device)
        versions = stats.get("model_versions")
        if isinstance(versions, Mapping):
            model_versions.update({str(key): value for key, value in versions.items()})
    metrics: dict[str, object] = {}
    if realtime_factors:
        metrics["realtime_factor_mean"] = sum(realtime_factors) / len(realtime_factors)
    if total_sec_values:
        metrics["runtime_total_sec"] = sum(total_sec_values)
    if audio_sec_values:
        metrics["runtime_audio_duration_sec"] = sum(audio_sec_values)
    if memory_values:
        metrics["memory_peak_mb"] = max(memory_values)
    if devices:
        metrics["runtime_device"] = devices[0]
    return metrics, model_versions


def collect_group_metric_rows(metrics_dir: Path) -> dict[str, tuple[Mapping[str, object], ...]]:
    groups: dict[str, tuple[Mapping[str, object], ...]] = {}
    if not metrics_dir.exists():
        return groups
    for path in sorted(metrics_dir.glob("*_metrics.csv")):
        if path.name in {"per_recording_metrics.csv", "segment_speaker_metrics.csv"}:
            continue
        key = path.stem.removesuffix("_metrics")
        groups[key] = tuple(_read_csv_rows(path))
    return groups


def collect_model_identifiers(
    config: Mapping[str, object],
    diagnostics_versions: Mapping[str, object],
) -> dict[str, object]:
    identifiers: dict[str, object] = {}
    runner = config.get("runner")
    if isinstance(runner, Mapping):
        identifiers["runner"] = runner.get("name")
    components = config.get("components")
    if isinstance(components, Mapping):
        for component_name, component_value in components.items():
            if not isinstance(component_value, Mapping):
                continue
            params = component_value.get("params")
            model_name = params.get("model_name") if isinstance(params, Mapping) else None
            identifiers[str(component_name)] = model_name or component_value.get("name")
    identifiers.update({str(key): value for key, value in diagnostics_versions.items()})
    return {key: value for key, value in identifiers.items() if value not in (None, "")}


def speaker_rates_from_metric_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    scored = 0
    unknown = 0
    false_known = 0
    for row in rows:
        if _truthy(row.get("missing_prediction")):
            continue
        pred = _optional_str(row.get("predicted_speaker_label"))
        ref = _optional_str(row.get("speaker_label"))
        if pred is None and ref is None:
            continue
        scored += 1
        pred_unknown = _is_unknown_label(pred)
        ref_unknown = _is_unknown_label(ref)
        if pred_unknown:
            unknown += 1
        if not pred_unknown and ref_unknown:
            false_known += 1
    return {
        "unknown_rate": unknown / scored if scored else None,
        "false_known_rate": false_known / scored if scored else None,
    }


def stutter_repetition_rate(path: Path) -> float | None:
    total_tokens = 0
    repeated_tokens = 0
    for row in read_jsonl(path):
        tokens = str(row.get("text") or "").lower().split()
        total_tokens += len(tokens)
        repeated_tokens += sum(1 for left, right in zip(tokens, tokens[1:]) if left == right)
    if total_tokens == 0:
        return None
    return repeated_tokens / total_tokens


def classify_failure_mode(
    status: str,
    metrics: Mapping[str, object],
    blocker: str | None,
) -> str:
    if status in {STATUS_TIMED_OUT, STATUS_FAILED}:
        return FAILURE_TIMEOUT_CRASH
    if status in {STATUS_MISSING_ARTIFACT, STATUS_SKIPPED}:
        return FAILURE_DATA
    blocker_text = (blocker or "").lower()
    if any(word in blocker_text for word in ("metadata", "audio", "artifact", "dataset")):
        return FAILURE_DATA
    if "vad" in blocker_text:
        return FAILURE_VAD
    if "segment" in blocker_text:
        return FAILURE_SEGMENTATION
    if "speaker" in blocker_text:
        return FAILURE_SPEAKER_MATCHING
    if "asr" in blocker_text:
        return FAILURE_ASR
    vad_error_rate = _optional_float(metrics.get("vad_error_rate") or metrics.get("vad_miss_rate"))
    if vad_error_rate is not None and vad_error_rate >= 0.5:
        return FAILURE_VAD
    missing_rate = _optional_float(metrics.get("missing_prediction_rate"))
    if missing_rate is not None and missing_rate >= 0.5:
        return FAILURE_ASR
    segment_summary = metrics.get("segment_speaker_summary")
    if isinstance(segment_summary, Mapping):
        coverage = _optional_float(segment_summary.get("overlap_coverage"))
        if coverage is not None and coverage < 0.5:
            return FAILURE_SEGMENTATION
    speaker_accuracy = _optional_float(metrics.get("speaker_label_accuracy"))
    unknown_rate = _optional_float(metrics.get("unknown_rate"))
    if speaker_accuracy is not None and speaker_accuracy < 0.5:
        return FAILURE_SPEAKER_MATCHING
    if unknown_rate is not None and unknown_rate > 0.5:
        return FAILURE_SPEAKER_MATCHING
    wer = _optional_float(metrics.get("aggregate_wer"))
    if wer is not None and wer > 0.5:
        return FAILURE_ASR
    return FAILURE_NONE


def recommendations_for_result(result: ValidationResult) -> list[str]:
    modes = {run.failure_mode for run in result.runs if run.failure_mode != FAILURE_NONE}
    recommendations: list[str] = []
    if FAILURE_DATA in modes:
        recommendations.append("Resolve missing normalized metadata, raw audio, or generated artifacts before treating cross-dataset metrics as final.")
    if FAILURE_ASR in modes:
        recommendations.append("Prioritize ASR robustness on the datasets or augmentation conditions with high WER or missing predictions.")
    if FAILURE_SPEAKER_MATCHING in modes:
        recommendations.append("Revisit speaker matching thresholds and enrollment coverage for runs with low speaker accuracy or high Unknown rate.")
    if FAILURE_SEGMENTATION in modes:
        recommendations.append("Inspect VAD and segmentation boundaries where overlap coverage is low before changing downstream speaker matching.")
    if FAILURE_TIMEOUT_CRASH in modes:
        recommendations.append("Reduce per-run max_recordings or timeout pressure, then rerun the affected validation jobs.")
    if result.dry_run_fixtures:
        recommendations.append("Run the same sweep without --dry-run-fixtures once all six dataset assets and model dependencies are available.")
    if not recommendations:
        recommendations.append("Use the robustness sweep to expand from smoke coverage to noisy and native-condition validation.")
    return recommendations


def find_generated_run_dir(runs_root: Path) -> Path | None:
    if not runs_root.exists():
        return None
    candidates = [path for path in runs_root.iterdir() if path.is_dir() and (path / "run_config.yaml").exists()]
    if not candidates:
        nested = [path for path in runs_root.rglob("run_config.yaml")]
        candidates = [path.parent for path in nested]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def supported_dataset_keys() -> tuple[str, ...]:
    return tuple(definition.key for definition in list_datasets())


def command_summary(args: argparse.Namespace, run_id: str) -> str:
    parts = [
        sys.executable,
        "scripts/run_all_dataset_validation.py",
        "--run-id",
        run_id,
        "--sweep-config",
        str(args.sweep_config),
    ]
    if args.dry_run_fixtures:
        parts.append("--dry-run-fixtures")
    if args.output_root != Path("runs/all_dataset_validation"):
        parts.extend(["--output-root", str(args.output_root)])
    if args.report_path is not None:
        parts.extend(["--report-path", str(args.report_path)])
    return " ".join(parts)


def _resolve_tool_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    if path.exists():
        return path.resolve()
    return (TOOL_ROOT / path).resolve()


def _resolve_project_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    if path.exists():
        return path.resolve()
    return (PROJECT_ROOT / path).resolve()


def _read_yaml_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return read_yaml(path)


def _read_json_mapping(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    value = read_json(path)
    return dict(value) if isinstance(value, Mapping) else {}


def _read_csv_rows(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(str(key))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in columns})
    return path


def _append_float(values: list[float], value: object) -> None:
    parsed = _optional_float(value)
    if parsed is not None:
        values.append(parsed)


def _mapping_or_empty(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    parsed = _optional_float(value)
    return int(parsed) if parsed is not None else None


def _optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _as_sequence(value: object) -> tuple[object, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(value)
    return (value,)


def _subset_value(value: object) -> str:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return ",".join(str(item) for item in value)
    return str(value)


def _safe_identifier(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
    return safe.strip("._-") or "validation_job"


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _is_unknown_label(value: object) -> bool:
    text = str(value or "").strip().lower()
    return text in {"", "unknown", "unk", "none", "null"}


def _display_path(path: Path | None, root: Path | None) -> str | None:
    if path is None:
        return None
    if root is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _weighted_rate(
    metrics: Sequence[Mapping[str, object]],
    numerator_key: str,
    denominator_key: str,
    fallback_key: str,
) -> float | None:
    numerator = 0.0
    denominator = 0.0
    for row in metrics:
        row_num = _optional_float(row.get(numerator_key))
        row_den = _optional_float(row.get(denominator_key))
        if row_num is not None and row_den is not None:
            numerator += row_num
            denominator += row_den
    if denominator > 0:
        return numerator / denominator
    return _mean_metric(metrics, fallback_key)


def _mean_metric(metrics: Sequence[Mapping[str, object]], *keys: str) -> float | None:
    values: list[float] = []
    for row in metrics:
        for key in keys:
            value = _optional_float(row.get(key))
            if value is not None:
                values.append(value)
                break
    if not values:
        return None
    return sum(values) / len(values)


def _sum_metric(metrics: Sequence[Mapping[str, object]], *keys: str) -> float | None:
    total = 0.0
    found = False
    for row in metrics:
        for key in keys:
            value = _optional_float(row.get(key))
            if value is not None:
                total += value
                found = True
                break
    return total if found else None


def _max_metric(metrics: Sequence[Mapping[str, object]], key: str) -> float | None:
    values = [_optional_float(row.get(key)) for row in metrics]
    clean = [value for value in values if value is not None]
    return max(clean) if clean else None


def _crash_timeout_rate(runs: Sequence[ValidationRunSummary]) -> float:
    if not runs:
        return 0.0
    failed = sum(1 for run in runs if run.status in {STATUS_FAILED, STATUS_TIMED_OUT})
    return failed / len(runs)


def _fmt_metric(value: object) -> str:
    parsed = _optional_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
