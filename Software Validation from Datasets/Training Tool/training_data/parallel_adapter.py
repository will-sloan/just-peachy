"""Optional isolated-process adapter orchestration for a qualified RTX 3090."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from training_data.adapter_research import EXPERIMENTS, atomic_json, default_paths, read_json


REQUIRED_BENCHMARK_METRICS = {
    "serial_optimizer_updates_per_second",
    "parallel_optimizer_updates_per_second",
    "serial_audio_seconds_per_second",
    "parallel_audio_seconds_per_second",
    "per_process_step_time_seconds",
    "per_process_peak_vram_gib",
    "total_gpu_memory_gib",
    "gpu_utilization_percent",
    "cpu_utilization_percent",
    "disk_or_dataloader_contention_observed",
    "finite_losses",
    "backbone_freeze_verified",
    "checkpoint_integrity_verified",
    "oom_observed",
    "status_or_file_collision_observed",
}


class ParallelError(RuntimeError):
    pass


def gate_path() -> Path:
    return default_paths().roots.runs / "parallel_qualification" / "rtx3090_parallel_gate.json"


def status_root(experiment_id: str) -> Path:
    return (
        default_paths().roots.runs
        / "parallel_status"
        / experiment_id.lower().replace("-", "_")
    )


def benchmark_protocol() -> dict[str, Any]:
    return {
        "schema_version": "rtx3090-parallel-adapter-benchmark-protocol.v1",
        "gpu": "NVIDIA RTX 3090 24 GB",
        "representative_jobs": ["O-AGE", "O-AGE-ROBUST"],
        "bounded_optimizer_steps_per_process": 250,
        "comparison": ["one independent process", "two independent processes"],
        "required_metrics": sorted(REQUIRED_BENCHMARK_METRICS),
        "minimum_aggregate_throughput_improvement": 0.25,
        "acceptance_requires": [
            "meaningful VRAM margin",
            "unchanged frozen scientific recipe",
            "no OOM or instability",
            "no status/checkpoint collision",
            "finite losses and verified backbone freeze",
            "checkpoint integrity",
        ],
        "gate_path": str(gate_path()),
        "note": "Record measured receiver results; this command does not fabricate measurements.",
    }


def record_benchmark(path: Path) -> dict[str, Any]:
    metrics = read_json(path)
    missing = sorted(REQUIRED_BENCHMARK_METRICS - set(metrics))
    if missing:
        raise ParallelError("Missing benchmark metrics: " + ", ".join(missing))
    serial = float(metrics["serial_optimizer_updates_per_second"])
    parallel = float(metrics["parallel_optimizer_updates_per_second"])
    improvement = parallel / serial - 1.0 if serial > 0 else -1.0
    accepted = bool(
        improvement >= 0.25
        and metrics["finite_losses"]
        and metrics["backbone_freeze_verified"]
        and metrics["checkpoint_integrity_verified"]
        and not metrics["oom_observed"]
        and not metrics["status_or_file_collision_observed"]
        and not metrics["disk_or_dataloader_contention_observed"]
        and float(metrics["total_gpu_memory_gib"]) < 23.0
    )
    gate = {
        "schema_version": "rtx3090-parallel-adapter-gate.v1",
        "accepted": accepted,
        "max_parallel_adapter_jobs": 2 if accepted else 1,
        "aggregate_optimizer_throughput_improvement": improvement,
        "metrics": metrics,
    }
    atomic_json(gate_path(), gate)
    return gate


def status() -> dict[str, Any]:
    rows = []
    for experiment_id, *_ in EXPERIMENTS:
        path = status_root(experiment_id) / "queue_status.json"
        rows.append(
            {
                "experiment_id": experiment_id,
                "status_path": str(path),
                "status": read_json(path) if path.is_file() else None,
            }
        )
    return {"schema_version": "parallel-adapter-status.v1", "jobs": rows}


def run_jobs(experiment_ids: list[str], *, maximum: int, dry_run: bool) -> dict[str, Any]:
    known = {item[0] for item in EXPERIMENTS}
    if not experiment_ids or any(item not in known for item in experiment_ids):
        raise ParallelError("Supply one or more exact Original experiment IDs")
    if maximum not in {1, 2}:
        raise ParallelError("MAX_PARALLEL_ADAPTER_JOBS must be 1 or 2")
    if maximum == 2:
        gate = read_json(gate_path()) if gate_path().is_file() else {}
        if not gate.get("accepted") or gate.get("max_parallel_adapter_jobs") != 2:
            raise ParallelError("Parallel=2 is blocked until the RTX 3090 benchmark gate passes")
    commands = []
    for experiment_id in experiment_ids:
        commands.append(
            {
                "experiment_id": experiment_id,
                "command": [
                    sys.executable,
                    "-m",
                    "training_data.adapter_research",
                    "run-one",
                    "--experiment-id",
                    experiment_id,
                ],
                "status_root": str(status_root(experiment_id)),
            }
        )
    plan = {
        "schema_version": "parallel-adapter-run-plan.v1",
        "max_parallel_adapter_jobs": maximum,
        "dry_run": dry_run,
        "independent_processes": True,
        "commands": commands,
        "gpu_large_evaluation_concurrent": False,
    }
    if dry_run:
        return plan
    pending = list(commands)
    active: list[tuple[subprocess.Popen[bytes], dict[str, Any]]] = []
    failures: list[str] = []
    while pending or active:
        while pending and len(active) < maximum:
            item = pending.pop(0)
            environment = dict(os.environ)
            environment["JP_ADAPTER_STATUS_ROOT"] = item["status_root"]
            active.append(
                (subprocess.Popen(item["command"], env=environment), item)
            )
        for process, item in list(active):
            code = process.poll()
            if code is None:
                continue
            active.remove((process, item))
            if code != 0:
                failures.append(item["experiment_id"])
        if active:
            time.sleep(0.5)
    if failures:
        raise ParallelError("Adapter processes failed: " + ", ".join(failures))
    return plan


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("benchmark-protocol", "record-benchmark", "run", "status"))
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--experiment-id", action="append", default=[])
    parser.add_argument("--max-parallel", type=int, choices=(1, 2), default=1)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if args.action == "benchmark-protocol":
            result = benchmark_protocol()
        elif args.action == "record-benchmark":
            if not args.metrics:
                raise ParallelError("--metrics is required")
            result = record_benchmark(args.metrics)
        elif args.action == "status":
            result = status()
        else:
            result = run_jobs(
                args.experiment_id, maximum=args.max_parallel, dry_run=not args.apply
            )
    except (ParallelError, FileNotFoundError, KeyError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
