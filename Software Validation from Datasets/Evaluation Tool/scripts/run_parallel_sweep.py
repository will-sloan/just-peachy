"""Run an isolated parallel sweep using the M15 subprocess scheduler."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.runtime.gpu import NvidiaSmiTelemetryProvider, available_gpu_indices
from app.inference_pipeline.runtime.job_scheduler import (
    JobSpec,
    SchedulerConfig,
    load_runtime_profile,
    run_jobs,
    write_parallel_execution_report,
)
from app.utils.run_artifacts import read_yaml


@dataclass(frozen=True)
class ParallelSweepConfig:
    """Parsed parallel sweep configuration."""

    sweep_name: str
    default_run_id: str
    scheduler: Mapping[str, object]
    jobs: tuple[JobSpec, ...]
    notes: str | None = None


def load_parallel_sweep_config(path: Path) -> ParallelSweepConfig:
    """Load a parallel sweep YAML file."""

    data = read_yaml(path)
    scheduler = _mapping_or_empty(data.get("scheduler"))
    job_entries = data.get("jobs")
    if not isinstance(job_entries, Sequence) or isinstance(job_entries, str | bytes | bytearray):
        raise ValueError("parallel sweep config requires a jobs list")
    jobs = tuple(
        _job_from_mapping(_mapping_or_empty(entry), tool_root=TOOL_ROOT, project_root=PROJECT_ROOT)
        for entry in job_entries
    )
    return ParallelSweepConfig(
        sweep_name=str(data.get("sweep_name") or path.stem),
        default_run_id=str(data.get("run_id") or path.stem),
        scheduler=scheduler,
        jobs=jobs,
        notes=str(data.get("notes")) if data.get("notes") is not None else None,
    )


def build_fake_jobs(count: int, *, sleep_sec: float = 0.05) -> tuple[JobSpec, ...]:
    """Build tiny subprocess jobs for dry scheduler smoke checks."""

    script = (
        "import json, os, pathlib, time; "
        "run_dir = pathlib.Path(os.environ['JP_RUN_DIR']); "
        "run_dir.mkdir(parents=True, exist_ok=True); "
        "time.sleep(float(os.environ.get('JP_FAKE_SLEEP_SEC', '0.05'))); "
        "(run_dir / 'fake_job.json').write_text("
        "json.dumps({"
        "'job_id': os.environ.get('JP_JOB_ID'), "
        "'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'), "
        "'run_dir': str(run_dir)"
        "}, sort_keys=True), encoding='utf-8')"
    )
    return tuple(
        JobSpec(
            job_id=f"fake_job_{index + 1}",
            command=(sys.executable, "-c", script),
            env={"JP_FAKE_SLEEP_SEC": str(sleep_sec)},
            audio_duration_sec=30.0,
            config_snapshot={"kind": "m15_fake_job"},
        )
        for index in range(count)
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    sweep_path = _resolve_tool_path(args.sweep_config)
    sweep = load_parallel_sweep_config(sweep_path)
    run_id = args.run_id or sweep.default_run_id or f"parallel_{int(time.time())}"
    output_root = _resolve_tool_path(args.output_root) / run_id
    scheduler_mapping = sweep.scheduler
    gpu_ids = _gpu_ids(args, scheduler_mapping)
    jobs = (
        build_fake_jobs(args.fake_job_count, sleep_sec=args.fake_sleep_sec)
        if args.dry_run_fake_jobs
        else sweep.jobs
    )
    scheduler_config = SchedulerConfig(
        run_id=run_id,
        output_root=output_root,
        max_workers=args.max_workers or int(scheduler_mapping.get("max_workers") or 1),
        serial=args.serial or bool(scheduler_mapping.get("serial", False)),
        timeout_sec=args.timeout_sec or _optional_float(scheduler_mapping.get("timeout_sec")),
        retry_count=args.retry_count if args.retry_count is not None else int(scheduler_mapping.get("retry_count") or 0),
        gpu_ids=gpu_ids,
        telemetry_poll_interval_sec=(
            args.telemetry_poll_interval_sec
            or _optional_float(scheduler_mapping.get("telemetry_poll_interval_sec"))
            or 1.0
        ),
        serial_baseline_wall_sec=_optional_float(scheduler_mapping.get("serial_baseline_wall_sec")),
    )
    provider = NvidiaSmiTelemetryProvider()
    result = run_jobs(jobs, scheduler_config, telemetry_provider=provider)
    runtime_profiles = _runtime_profiles()
    report_path = _resolve_tool_path(args.report_path) if args.report_path else (
        TOOL_ROOT / "reports" / "runtime" / f"parallel_execution_{run_id}.md"
    )
    blockers = []
    if not available_gpu_indices(provider):
        blockers.append(
            "Real GPU telemetry was unavailable in this environment; dry/fake jobs can still validate scheduler isolation."
        )
    incomplete = []
    if args.dry_run_fake_jobs:
        incomplete.append("Smoke check used fake subprocess jobs, not production ASR or speaker embedding models.")
    write_parallel_execution_report(
        report_path,
        result,
        runtime_profiles=runtime_profiles,
        smoke_commands=[_smoke_command_summary(args, run_id)],
        blockers=blockers,
        incomplete=incomplete,
    )
    print(f"Scheduler result: {output_root / 'parallel_scheduler_result.json'}")
    print(f"Runtime report: {report_path}")
    print(f"Failure rate: {result.failure_rate:.4f}")
    return 0 if all(job.succeeded for job in result.jobs) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a parallel evaluation sweep.")
    parser.add_argument(
        "--sweep-config",
        type=Path,
        default=Path("configs/sweeps/parallel_asr_eval.yaml"),
        help="Parallel sweep YAML path, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--run-id", default=None)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("runs/parallel_sweeps"),
        help="Output root, absolute or Evaluation Tool relative.",
    )
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--timeout-sec", type=float, default=None)
    parser.add_argument("--retry-count", type=int, default=None)
    parser.add_argument("--telemetry-poll-interval-sec", type=float, default=None)
    parser.add_argument("--gpu-ids", default=None, help="Comma-separated CUDA device ids.")
    parser.add_argument("--serial", action="store_true", help="Run jobs one at a time.")
    parser.add_argument(
        "--dry-run-fake-jobs",
        action="store_true",
        help="Ignore configured jobs and run tiny subprocess smoke jobs.",
    )
    parser.add_argument("--fake-job-count", type=int, default=2)
    parser.add_argument("--fake-sleep-sec", type=float, default=0.05)
    return parser


def _job_from_mapping(
    mapping: Mapping[str, object],
    *,
    tool_root: Path,
    project_root: Path,
) -> JobSpec:
    command = mapping.get("command")
    if not isinstance(command, Sequence) or isinstance(command, str | bytes | bytearray):
        raise ValueError("job command must be a list")
    context = {
        "python": sys.executable,
        "tool_root": tool_root.as_posix(),
        "project_root": project_root.as_posix(),
        "job_id": "{job_id}",
        "run_dir": "{run_dir}",
        "cuda_visible_devices": "{cuda_visible_devices}",
    }
    normalized = {
        **mapping,
        "command": [str(part).format(**context) for part in command],
        "cwd": (
            Path(str(mapping.get("cwd")).format(**context))
            if mapping.get("cwd") is not None
            else tool_root
        ),
    }
    return JobSpec.from_mapping(normalized)


def _runtime_profiles() -> tuple[dict[str, object], ...]:
    profiles: list[dict[str, object]] = []
    for name in ("rtx3080.yaml", "rtx3090.yaml"):
        path = TOOL_ROOT / "configs" / "runtime" / name
        if path.exists():
            profiles.append(load_runtime_profile(path))
    return tuple(profiles)


def _gpu_ids(args: argparse.Namespace, scheduler: Mapping[str, object]) -> tuple[str, ...]:
    if args.gpu_ids:
        return tuple(item.strip() for item in args.gpu_ids.split(",") if item.strip())
    configured = scheduler.get("gpu_ids")
    if isinstance(configured, Sequence) and not isinstance(configured, str | bytes | bytearray):
        return tuple(str(item) for item in configured)
    if str(configured).lower() == "auto":
        return available_gpu_indices()
    return ()


def _resolve_tool_path(path: Path) -> Path:
    return path.resolve() if path.is_absolute() else (TOOL_ROOT / path).resolve()


def _mapping_or_empty(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _smoke_command_summary(args: argparse.Namespace, run_id: str) -> str:
    parts = [
        sys.executable,
        "scripts/run_parallel_sweep.py",
        "--run-id",
        run_id,
    ]
    if args.gpu_ids:
        parts.extend(["--gpu-ids", args.gpu_ids])
    if args.max_workers is not None:
        parts.extend(["--max-workers", str(args.max_workers)])
    if args.timeout_sec is not None:
        parts.extend(["--timeout-sec", str(args.timeout_sec)])
    if args.telemetry_poll_interval_sec is not None:
        parts.extend(["--telemetry-poll-interval-sec", str(args.telemetry_poll_interval_sec)])
    if args.dry_run_fake_jobs:
        parts.append("--dry-run-fake-jobs")
        parts.extend(["--fake-job-count", str(args.fake_job_count)])
        parts.extend(["--fake-sleep-sec", str(args.fake_sleep_sec)])
    if args.serial:
        parts.append("--serial")
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
