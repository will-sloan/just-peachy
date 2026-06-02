"""Subprocess-based scheduler for isolated parallel evaluation jobs."""

from __future__ import annotations

import csv
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.inference_pipeline.runtime.gpu import (
    GpuDevice,
    GpuJobSummary,
    GpuTelemetryMonitor,
    GpuTelemetryProvider,
    NvidiaSmiTelemetryProvider,
)
from app.utils.json_utils import write_json
from app.utils.run_artifacts import ensure_run_subdirs, write_yaml


STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class JobSpec:
    """One isolated subprocess job."""

    job_id: str
    command: tuple[str, ...]
    run_dir: Path | None = None
    cwd: Path | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    timeout_sec: float | None = None
    max_retries: int | None = None
    audio_duration_sec: float | None = None
    config_snapshot: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "JobSpec":
        command = mapping.get("command")
        if not isinstance(command, Sequence) or isinstance(command, str | bytes | bytearray):
            raise ValueError("job command must be a list of command arguments")
        return cls(
            job_id=str(mapping.get("job_id") or mapping.get("id") or "").strip(),
            command=tuple(str(item) for item in command),
            run_dir=_optional_path(mapping.get("run_dir")),
            cwd=_optional_path(mapping.get("cwd")),
            env=_string_mapping(mapping.get("env")),
            timeout_sec=_optional_float(mapping.get("timeout_sec")),
            max_retries=_optional_int(mapping.get("max_retries")),
            audio_duration_sec=_optional_float(mapping.get("audio_duration_sec")),
            config_snapshot=_mapping_or_empty(mapping.get("config_snapshot")),
        )


@dataclass(frozen=True)
class SchedulerConfig:
    """Scheduler settings for one parallel run."""

    run_id: str
    output_root: Path
    max_workers: int = 1
    serial: bool = False
    timeout_sec: float | None = None
    retry_count: int = 0
    gpu_ids: tuple[str, ...] = ()
    telemetry_poll_interval_sec: float = 1.0
    serial_baseline_wall_sec: float | None = None

    @property
    def effective_max_workers(self) -> int:
        if self.serial:
            return 1
        return max(1, int(self.max_workers))

    def to_jsonable(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "output_root": self.output_root.as_posix(),
            "max_workers": self.max_workers,
            "effective_max_workers": self.effective_max_workers,
            "serial": self.serial,
            "timeout_sec": self.timeout_sec,
            "retry_count": self.retry_count,
            "gpu_ids": list(self.gpu_ids),
            "telemetry_poll_interval_sec": self.telemetry_poll_interval_sec,
            "serial_baseline_wall_sec": self.serial_baseline_wall_sec,
        }


@dataclass(frozen=True)
class JobResult:
    """Result from one isolated subprocess job."""

    job_id: str
    status: str
    run_dir: Path
    config_snapshot_path: Path
    command: tuple[str, ...]
    cwd: Path | None
    assigned_cuda_device: str | None
    attempts: int
    duration_sec: float
    returncode: int | None
    stdout_path: Path
    stderr_path: Path
    failure_message: str | None
    gpu: GpuJobSummary
    audio_duration_sec: float | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == STATUS_SUCCEEDED

    def to_jsonable(self, *, root: Path | None = None) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "run_dir": _display_path(self.run_dir, root),
            "config_snapshot_path": _display_path(self.config_snapshot_path, root),
            "command": list(self.command),
            "cwd": self.cwd.as_posix() if self.cwd is not None else None,
            "assigned_cuda_device": self.assigned_cuda_device,
            "attempts": self.attempts,
            "duration_sec": self.duration_sec,
            "returncode": self.returncode,
            "stdout_path": _display_path(self.stdout_path, root),
            "stderr_path": _display_path(self.stderr_path, root),
            "failure_message": self.failure_message,
            "gpu": self.gpu.to_jsonable(),
            "audio_duration_sec": self.audio_duration_sec,
        }


@dataclass(frozen=True)
class SchedulerResult:
    """Aggregate scheduler result."""

    run_id: str
    started_at: str
    wall_duration_sec: float
    config: SchedulerConfig
    jobs: tuple[JobResult, ...]
    gpu_devices: tuple[GpuDevice, ...]
    telemetry_available: bool

    @property
    def failure_rate(self) -> float:
        if not self.jobs:
            return 0.0
        failures = sum(1 for job in self.jobs if not job.succeeded)
        return failures / len(self.jobs)

    @property
    def throughput_audio_hours_per_wall_hour(self) -> float | None:
        audio_seconds = sum(
            job.audio_duration_sec or 0.0
            for job in self.jobs
            if job.succeeded
        )
        if audio_seconds <= 0 or self.wall_duration_sec <= 0:
            return None
        return (audio_seconds / 3600.0) / (self.wall_duration_sec / 3600.0)

    @property
    def speedup_vs_serial_baseline(self) -> float | None:
        baseline = self.config.serial_baseline_wall_sec
        if baseline is None or baseline <= 0 or self.wall_duration_sec <= 0:
            return None
        return baseline / self.wall_duration_sec

    @property
    def min_memory_headroom_percent(self) -> float | None:
        values = [
            job.gpu.memory_headroom_percent
            for job in self.jobs
            if job.gpu.memory_headroom_percent is not None
        ]
        return min(values) if values else None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "wall_duration_sec": self.wall_duration_sec,
            "config": self.config.to_jsonable(),
            "jobs": [job.to_jsonable(root=self.config.output_root) for job in self.jobs],
            "gpu_devices": [device.to_jsonable() for device in self.gpu_devices],
            "telemetry_available": self.telemetry_available,
            "failure_rate": self.failure_rate,
            "throughput_audio_hours_per_wall_hour": self.throughput_audio_hours_per_wall_hour,
            "speedup_vs_serial_baseline": self.speedup_vs_serial_baseline,
            "min_memory_headroom_percent": self.min_memory_headroom_percent,
        }


def run_jobs(
    jobs: Sequence[JobSpec],
    config: SchedulerConfig,
    *,
    telemetry_provider: GpuTelemetryProvider | None = None,
) -> SchedulerResult:
    """Run jobs with one subprocess per job and isolated run directories."""

    provider = telemetry_provider or NvidiaSmiTelemetryProvider()
    gpu_devices = provider.devices()
    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    wall_started = time.perf_counter()
    prepared = [
        _prepare_job(job, config, index)
        for index, job in enumerate(jobs)
    ]

    if config.serial:
        results = [
            _run_prepared_job(prepared_job, config, provider)
            for prepared_job in prepared
        ]
    else:
        results_by_id: dict[str, JobResult] = {}
        with ThreadPoolExecutor(max_workers=config.effective_max_workers) as executor:
            future_by_id = {
                executor.submit(_run_prepared_job, prepared_job, config, provider): prepared_job.job.job_id
                for prepared_job in prepared
            }
            for future in as_completed(future_by_id):
                results_by_id[future_by_id[future]] = future.result()
        results = [results_by_id[prepared_job.job.job_id] for prepared_job in prepared]

    result = SchedulerResult(
        run_id=config.run_id,
        started_at=started_at,
        wall_duration_sec=time.perf_counter() - wall_started,
        config=config,
        jobs=tuple(results),
        gpu_devices=gpu_devices,
        telemetry_available=bool(gpu_devices),
    )
    config.output_root.mkdir(parents=True, exist_ok=True)
    write_json(config.output_root / "parallel_scheduler_result.json", result.to_jsonable())
    write_csv_result(config.output_root / "parallel_scheduler_jobs.csv", result)
    return result


def write_csv_result(path: Path, result: SchedulerResult) -> Path:
    """Write per-job scheduler results to CSV."""

    columns = (
        "job_id",
        "status",
        "run_dir",
        "assigned_cuda_device",
        "gpu_name",
        "total_vram_mb",
        "peak_memory_mb",
        "average_utilization_percent",
        "memory_headroom_percent",
        "attempts",
        "duration_sec",
        "returncode",
        "failure_message",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for job in result.jobs:
            writer.writerow(
                {
                    "job_id": job.job_id,
                    "status": job.status,
                    "run_dir": _display_path(job.run_dir, result.config.output_root),
                    "assigned_cuda_device": job.assigned_cuda_device,
                    "gpu_name": job.gpu.gpu_name,
                    "total_vram_mb": job.gpu.total_vram_mb,
                    "peak_memory_mb": job.gpu.peak_memory_mb,
                    "average_utilization_percent": job.gpu.average_utilization_percent,
                    "memory_headroom_percent": job.gpu.memory_headroom_percent,
                    "attempts": job.attempts,
                    "duration_sec": job.duration_sec,
                    "returncode": job.returncode,
                    "failure_message": job.failure_message,
                }
            )
    return path


def write_parallel_execution_report(
    path: Path,
    result: SchedulerResult,
    *,
    runtime_profiles: Sequence[Mapping[str, object]] = (),
    test_commands: Sequence[str] = (),
    smoke_commands: Sequence[str] = (),
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the required M15 runtime report artifact."""

    lines = [
        "# Parallel Execution Runtime Report",
        "",
        "## Milestone",
        "",
        "M15 - Parallel Batch Execution and GPU Scheduling",
        "",
        "## Scheduler Configuration",
        "",
        f"- Run id: `{result.run_id}`",
        f"- Serial fallback mode: `{result.config.serial}`",
        f"- Max workers requested: `{result.config.max_workers}`",
        f"- Effective max workers: `{result.config.effective_max_workers}`",
        f"- Timeout sec: `{_fmt(result.config.timeout_sec)}`",
        f"- Retry count: `{result.config.retry_count}`",
        f"- GPU ids: `{list(result.config.gpu_ids)}`",
        f"- Wall duration sec: `{_fmt(result.wall_duration_sec)}`",
        "",
        "## Jobs Launched",
        "",
        "| job | status | cuda device | duration sec | attempts | run folder | failure |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for job in result.jobs:
        lines.append(
            "| "
            f"`{job.job_id}` | "
            f"{job.status} | "
            f"`{job.assigned_cuda_device or 'cpu/unassigned'}` | "
            f"{_fmt(job.duration_sec)} | "
            f"{job.attempts} | "
            f"`{_display_path(job.run_dir, result.config.output_root)}` | "
            f"{_escape_table(job.failure_message or '')} |"
        )
    lines.extend(
        [
            "",
            "## GPU Assignments And Memory",
            "",
            "| job | GPU name | VRAM MB | peak MB | avg utilization | memory headroom | telemetry |",
            "| --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for job in result.jobs:
        lines.append(
            "| "
            f"`{job.job_id}` | "
            f"{_escape_table(job.gpu.gpu_name or 'unavailable')} | "
            f"{_fmt(job.gpu.total_vram_mb)} | "
            f"{_fmt(job.gpu.peak_memory_mb)} | "
            f"{_fmt(job.gpu.average_utilization_percent)} | "
            f"{_fmt(job.gpu.memory_headroom_percent)} | "
            f"{job.gpu.telemetry_available} |"
        )
    lines.extend(
        [
            "",
            "## Validation Metrics",
            "",
            f"- Throughput audio hours per wall-clock hour: `{_fmt(result.throughput_audio_hours_per_wall_hour)}`",
            f"- Failure rate under parallel load: `{_fmt(result.failure_rate)}`",
            f"- GPU memory headroom percent: `{_fmt(result.min_memory_headroom_percent)}`",
            f"- Speedup vs serial baseline: `{_fmt(result.speedup_vs_serial_baseline)}`",
        ]
    )
    if result.speedup_vs_serial_baseline is None:
        lines.append("- Speedup note: serial baseline was not measured for this run.")

    lines.extend(["", "## Recommended Concurrency", ""])
    for profile in runtime_profiles:
        lines.extend(_profile_recommendation_lines(profile))
    if not runtime_profiles:
        lines.append("- Runtime profiles were not supplied.")

    lines.extend(["", "## Commands", ""])
    if test_commands or smoke_commands:
        lines.extend(f"- `{command}`" for command in test_commands)
        lines.extend(f"- `{command}`" for command in smoke_commands)
    else:
        lines.append("- No commands recorded.")

    lines.extend(["", "## Reproducibility", ""])
    lines.append("- Each job received an isolated run folder and `parallel_job_config.yaml` snapshot.")
    lines.append("- Each subprocess received explicit `CUDA_VISIBLE_DEVICES` when a GPU id was assigned.")
    lines.append("- The scheduler did not modify `app/model_runner/external_stub.py` or `predictions/utterances.jsonl`.")

    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- {blocker}" for blocker in blockers) if blockers else lines.append("- None known.")

    lines.extend(["", "## Incomplete", ""])
    lines.extend(f"- {item}" for item in incomplete) if incomplete else lines.append("- None known.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def load_runtime_profile(path: Path) -> dict[str, object]:
    """Load an RTX runtime profile YAML file."""

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, Mapping):
        raise ValueError(f"Expected runtime profile mapping in {path}")
    return dict(data)


@dataclass(frozen=True)
class _PreparedJob:
    job: JobSpec
    run_dir: Path
    config_snapshot_path: Path
    assigned_cuda_device: str | None


def _prepare_job(job: JobSpec, config: SchedulerConfig, index: int) -> _PreparedJob:
    if not job.job_id:
        raise ValueError("job_id must be non-empty")
    run_dir = job.run_dir or _unique_run_dir(config.output_root / "jobs", job.job_id)
    ensure_run_subdirs(run_dir)
    assigned = _assigned_device(config.gpu_ids, index)
    snapshot_path = run_dir / "parallel_job_config.yaml"
    write_yaml(
        snapshot_path,
        {
            "job_id": job.job_id,
            "command": list(job.command),
            "cwd": job.cwd.as_posix() if job.cwd else None,
            "env": dict(job.env),
            "assigned_cuda_device": assigned,
            "timeout_sec": job.timeout_sec or config.timeout_sec,
            "max_retries": job.max_retries if job.max_retries is not None else config.retry_count,
            "audio_duration_sec": job.audio_duration_sec,
            "config_snapshot": dict(job.config_snapshot),
        },
    )
    return _PreparedJob(
        job=job,
        run_dir=run_dir,
        config_snapshot_path=snapshot_path,
        assigned_cuda_device=assigned,
    )


def _run_prepared_job(
    prepared: _PreparedJob,
    config: SchedulerConfig,
    provider: GpuTelemetryProvider,
) -> JobResult:
    job_started = time.perf_counter()
    attempts_allowed = (prepared.job.max_retries if prepared.job.max_retries is not None else config.retry_count) + 1
    timeout_sec = prepared.job.timeout_sec if prepared.job.timeout_sec is not None else config.timeout_sec
    last_status = STATUS_FAILED
    last_returncode: int | None = None
    last_failure: str | None = None
    last_stdout = prepared.run_dir / "logs" / "stdout_attempt_1.txt"
    last_stderr = prepared.run_dir / "logs" / "stderr_attempt_1.txt"
    gpu_summary = GpuJobSummary(
        assigned_cuda_device=prepared.assigned_cuda_device,
        gpu_name=None,
        total_vram_mb=None,
        peak_memory_mb=None,
        average_utilization_percent=None,
        memory_headroom_percent=None,
        sample_count=0,
        telemetry_available=False,
    )

    for attempt in range(1, attempts_allowed + 1):
        last_stdout = prepared.run_dir / "logs" / f"stdout_attempt_{attempt}.txt"
        last_stderr = prepared.run_dir / "logs" / f"stderr_attempt_{attempt}.txt"
        command = _format_command(prepared.job.command, prepared)
        env = _job_env(prepared.job, prepared)
        monitor = GpuTelemetryMonitor(
            provider,
            gpu_indices=(prepared.assigned_cuda_device,) if prepared.assigned_cuda_device else (),
            poll_interval_sec=config.telemetry_poll_interval_sec,
        )
        monitor.start()
        try:
            completed = subprocess.run(
                command,
                cwd=prepared.job.cwd,
                env=env,
                timeout=timeout_sec,
                capture_output=True,
                text=True,
            )
            last_returncode = completed.returncode
            last_stdout.write_text(completed.stdout or "", encoding="utf-8")
            last_stderr.write_text(completed.stderr or "", encoding="utf-8")
            if completed.returncode == 0:
                last_status = STATUS_SUCCEEDED
                last_failure = None
                gpu_summary = monitor.summary(prepared.assigned_cuda_device)
                break
            last_status = STATUS_FAILED
            last_failure = f"return code {completed.returncode}"
        except subprocess.TimeoutExpired as exc:
            last_returncode = None
            last_status = STATUS_TIMED_OUT
            last_failure = f"timed out after {timeout_sec} sec"
            last_stdout.write_text(_timeout_output(exc.stdout), encoding="utf-8")
            last_stderr.write_text(_timeout_output(exc.stderr), encoding="utf-8")
        finally:
            monitor.stop()
            gpu_summary = monitor.summary(prepared.assigned_cuda_device)

        if attempt < attempts_allowed:
            continue

    return JobResult(
        job_id=prepared.job.job_id,
        status=last_status,
        run_dir=prepared.run_dir,
        config_snapshot_path=prepared.config_snapshot_path,
        command=_format_command(prepared.job.command, prepared),
        cwd=prepared.job.cwd,
        assigned_cuda_device=prepared.assigned_cuda_device,
        attempts=attempt,
        duration_sec=time.perf_counter() - job_started,
        returncode=last_returncode,
        stdout_path=last_stdout,
        stderr_path=last_stderr,
        failure_message=last_failure,
        gpu=gpu_summary,
        audio_duration_sec=prepared.job.audio_duration_sec,
    )


def _job_env(job: JobSpec, prepared: _PreparedJob) -> dict[str, str]:
    env = dict(os.environ)
    env.update({str(key): str(value) for key, value in job.env.items()})
    if prepared.assigned_cuda_device is not None:
        env["CUDA_VISIBLE_DEVICES"] = prepared.assigned_cuda_device
    env["JP_RUN_DIR"] = prepared.run_dir.as_posix()
    env["JP_JOB_ID"] = job.job_id
    return env


def _format_command(command: Sequence[str], prepared: _PreparedJob) -> tuple[str, ...]:
    replacements = {
        "{job_id}": prepared.job.job_id,
        "{run_dir}": prepared.run_dir.as_posix(),
        "{cuda_visible_devices}": prepared.assigned_cuda_device or "",
    }
    formatted: list[str] = []
    for part in command:
        text = str(part)
        for token, value in replacements.items():
            text = text.replace(token, value)
        formatted.append(text)
    return tuple(formatted)


def _assigned_device(gpu_ids: Sequence[str], index: int) -> str | None:
    if not gpu_ids:
        return None
    return str(gpu_ids[index % len(gpu_ids)])


def _unique_run_dir(root: Path, job_id: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    safe = _safe_name(job_id)
    candidate = root / safe
    if not candidate.exists():
        return candidate
    suffix = 2
    while True:
        next_candidate = root / f"{safe}_{suffix}"
        if not next_candidate.exists():
            return next_candidate
        suffix += 1


def _profile_recommendation_lines(profile: Mapping[str, object]) -> list[str]:
    name = profile.get("gpu_name") or profile.get("name") or "GPU"
    concurrency = profile.get("recommended_concurrency")
    rationale = profile.get("recommendation_notes") or "No rationale supplied."
    return [
        f"- {name}: recommended concurrency `{concurrency}`.",
        f"  {rationale}",
    ]


def _timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _optional_path(value: object) -> Path | None:
    if value in (None, ""):
        return None
    return Path(str(value))


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _string_mapping(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _mapping_or_empty(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)
    return safe.strip("._-") or "job"


def _display_path(path: Path, root: Path | None = None) -> str:
    if root is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _fmt(value: object) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _escape_table(value: str) -> str:
    return str(value).replace("|", "\\|")
