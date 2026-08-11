"""Measure identical real Evaluation Tool runs on CPU and CUDA.

The subprocesses use the ordinary ``run_evaluation.py full`` lifecycle. This
wrapper adds process-tree and NVML sampling, verifies identical selected records,
and writes a machine-readable qualification comparison. It never downloads a
model or changes a frozen campaign.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import socket
import subprocess
import sys
import time
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.campaign_exchange.common import atomic_write_json  # noqa: E402
from app.inference_pipeline.metrics.asr_metrics import aggregate_cer  # noqa: E402
from app.resource_telemetry.sampler import ResourceSampler  # noqa: E402
from app.utils.json_utils import read_jsonl  # noqa: E402


class CudaQualificationError(RuntimeError):
    """Raised when a measured evaluator case fails or selects different audio."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-recordings", type=int, default=5)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=TOOL_ROOT / "artifacts" / "gpu_qualification" / "comparison",
    )
    parser.add_argument("--sampling-interval-sec", type=float, default=0.25)
    return parser


def run_qualification(
    *,
    max_recordings: int,
    output_root: Path,
    sampling_interval_sec: float,
) -> dict[str, object]:
    if max_recordings < 1:
        raise CudaQualificationError("max recordings must be positive")
    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    cases = (
        (
            "cpu_float32",
            REPOSITORY_ROOT / ".venv" / "Scripts" / "python.exe",
            TOOL_ROOT / "configs" / "inference" / "live_mic_whisper_base.yaml",
            None,
        ),
        (
            "cuda_float32",
            REPOSITORY_ROOT
            / ".stage8-envs"
            / "core-cuda"
            / "Scripts"
            / "python.exe",
            TOOL_ROOT / "configs" / "inference" / "whisper_base_cuda_float32.yaml",
            "0",
        ),
        (
            "cuda_float16",
            REPOSITORY_ROOT
            / ".stage8-envs"
            / "core-cuda"
            / "Scripts"
            / "python.exe",
            TOOL_ROOT / "configs" / "inference" / "whisper_base_cuda_float16.yaml",
            "0",
        ),
    )
    results = [
        _run_case(
            name=name,
            python=python,
            config=config,
            gpu_index=gpu_index,
            max_recordings=max_recordings,
            output_root=root,
            interval_sec=sampling_interval_sec,
        )
        for name, python, config, gpu_index in cases
    ]
    selections = [result["selection_identity"] for result in results]
    if not all(selection == selections[0] for selection in selections[1:]):
        raise CudaQualificationError("CPU and CUDA runs did not select identical audio")
    transcripts = {
        str(result["case"]): result["transcripts"] for result in results
    }
    cpu = results[0]
    for result in results[1:]:
        result["speedup_vs_cpu_total"] = _ratio(
            float(cpu["total_elapsed_sec"]), float(result["total_elapsed_sec"])
        )
        result["speedup_vs_cpu_inference"] = _ratio(
            float(cpu["asr_inference_sec"]), float(result["asr_inference_sec"])
        )
        result["transcripts_identical_to_cpu"] = (
            result["transcripts"] == cpu["transcripts"]
        )
    comparison = {
        "schema_version": "whisper-base-cuda-qualification.v1",
        "scope": {
            "dataset": "cmu_arctic",
            "selected_item_count": max_recordings,
            "augmentation": "none",
            "beam_size": 1,
            "model": "whisper_base",
            "implicit_model_downloads": False,
            "sampling_interval_sec": sampling_interval_sec,
        },
        "host": socket.gethostname(),
        "selection_identity": selections[0],
        "cases": results,
        "transcript_comparison": transcripts,
        "limitations": [
            "NVML GPU utilization, temperature, and power are device-wide and may include unrelated desktop applications.",
            "This bounded qualification is not a replacement for component canary, small, or standard scientific gates.",
        ],
    }
    atomic_write_json(root / "whisper_base_cuda_qualification.json", comparison)
    return comparison


def _run_case(
    *,
    name: str,
    python: Path,
    config: Path,
    gpu_index: str | None,
    max_recordings: int,
    output_root: Path,
    interval_sec: float,
) -> dict[str, object]:
    if not python.is_file():
        raise FileNotFoundError(python)
    runs_root = output_root / "runs"
    command = [
        str(python),
        str(TOOL_ROOT / "run_evaluation.py"),
        "full",
        "--dataset",
        "cmu_arctic",
        "--max-recordings",
        str(max_recordings),
        "--runner",
        "configured",
        "--inference-config",
        str(config),
        "--augmentation",
        "none",
        "--run-name",
        f"whisper_base_{name}_qualification",
        "--runs-root",
        str(runs_root),
    ]
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=TOOL_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    sampler = ResourceSampler(
        campaign_id="qualification",
        scenario_id=name,
        attempt=1,
        worker_id="machine_a",
        host=socket.gethostname(),
        root_pid=process.pid,
        disk_path=output_root,
        gpu_index=gpu_index,
        interval_sec=interval_sec,
    )
    sampler.start()
    stdout, stderr = process.communicate()
    sampler.stop()
    elapsed = time.perf_counter() - started
    (output_root / f"{name}.stdout.log").write_text(stdout, encoding="utf-8")
    (output_root / f"{name}.stderr.log").write_text(stderr, encoding="utf-8")
    if process.returncode != 0:
        raise CudaQualificationError(
            f"{name} evaluator exited {process.returncode}; inspect {name}.stderr.log"
        )
    run_dir = _run_directory(stdout)
    runner = _json_mapping(run_dir / "predictions" / "runner_summary.json")
    predictions = list(read_jsonl(run_dir / "predictions" / "utterances.jsonl"))
    failures = list(read_jsonl(run_dir / "predictions" / "failures.jsonl"))
    diagnostics = list(read_jsonl(run_dir / "predictions" / "diagnostics.jsonl"))
    selection = list(read_jsonl(run_dir / "dataset_selection_records.jsonl"))
    metrics = _json_mapping(run_dir / "metrics" / "aggregate_metrics.json")
    if int(runner["written_count"]) != max_recordings or failures:
        raise CudaQualificationError(
            f"{name} did not produce {max_recordings} successful predictions"
        )
    backend = [
        _mapping(_mapping(row.get("diagnostics"), "diagnostics").get("asr_backend_runtime"), "ASR runtime")
        for row in diagnostics
    ]
    audio_seconds = sum(float(row.get("duration_sec") or 0.0) for row in selection)
    inference_seconds = sum(float(row.get("inference_sec") or 0.0) for row in backend)
    pipeline_seconds = sum(
        float(
            _mapping(
                _mapping(row.get("diagnostics"), "diagnostics").get("runtime_stats"),
                "pipeline runtime",
            ).get("total_sec")
            or 0.0
        )
        for row in diagnostics
    )
    samples = list(sampler.samples)
    return {
        "case": name,
        "python": str(python),
        "inference_config": str(config.relative_to(TOOL_ROOT).as_posix()),
        "run_dir": str(run_dir),
        "total_elapsed_sec": elapsed,
        "audio_duration_sec": audio_seconds,
        "asr_inference_sec": inference_seconds,
        "pipeline_total_sec": pipeline_seconds,
        "asr_realtime_factor": _ratio(inference_seconds, audio_seconds),
        "pipeline_realtime_factor": _ratio(pipeline_seconds, audio_seconds),
        "throughput_audio_sec_per_wall_sec": _ratio(audio_seconds, elapsed),
        "model_load_sec": max(float(row.get("load_sec") or 0.0) for row in backend),
        "device": backend[-1].get("device"),
        "dtype": backend[-1].get("dtype"),
        "peak_allocated_vram_mb": max(
            (float(row.get("peak_gpu_memory_mb") or 0.0) for row in backend),
            default=0.0,
        ),
        "peak_reserved_vram_mb": max(
            (float(row.get("peak_gpu_memory_reserved_mb") or 0.0) for row in backend),
            default=0.0,
        ),
        "telemetry": {
            "sample_count": len(samples),
            "peak_process_rss_bytes": _maximum(samples, "process_rss_bytes"),
            "peak_process_vram_bytes": _maximum(samples, "gpu_peak_vram_bytes"),
            "mean_gpu_utilization_percent": _mean(samples, "gpu_utilization_percent"),
            "p95_gpu_utilization_percent": _percentile(samples, "gpu_utilization_percent", 0.95),
            "peak_gpu_utilization_percent": _maximum(samples, "gpu_utilization_percent"),
            "peak_system_ram_percent": _maximum(samples, "system_ram_percent"),
            "peak_gpu_temperature_c": _maximum(samples, "gpu_temperature_c"),
            "peak_gpu_power_w": _maximum(samples, "gpu_power_w"),
            "warnings": list(sampler.warnings),
        },
        "prediction_count": len(predictions),
        "failure_count": len(failures),
        "missing_count": int(runner.get("attempted_count") or 0)
        - int(runner.get("written_count") or 0),
        "wer": metrics.get("aggregate_wer"),
        "cer": aggregate_cer(selection, predictions),
        "transcripts": [
            {
                "recording_id": row["recording_id"],
                "utt_id": row["utt_id"],
                "text": row["text"],
            }
            for row in predictions
        ],
        "selection_identity": [
            {
                "recording_id": row["recording_id"],
                "source_recording_id": row.get("source_recording_id"),
                "utt_id": row["utt_id"],
                "start_sec": row.get("start_sec"),
                "end_sec": row.get("end_sec"),
            }
            for row in selection
        ],
    }


def _run_directory(stdout: str) -> Path:
    for line in stdout.splitlines():
        if line.startswith("Run folder:"):
            path = Path(line.split(":", 1)[1].strip())
            if path.is_dir():
                return path
    raise CudaQualificationError("evaluator output did not identify its run folder")


def _numbers(rows: Sequence[Mapping[str, object]], field: str) -> list[float]:
    return [float(row[field]) for row in rows if row.get(field) is not None]


def _maximum(rows: Sequence[Mapping[str, object]], field: str) -> float | None:
    values = _numbers(rows, field)
    return max(values) if values else None


def _mean(rows: Sequence[Mapping[str, object]], field: str) -> float | None:
    values = _numbers(rows, field)
    return sum(values) / len(values) if values else None


def _percentile(
    rows: Sequence[Mapping[str, object]], field: str, fraction: float
) -> float | None:
    values = sorted(_numbers(rows, field))
    if not values:
        return None
    index = min(len(values) - 1, max(0, math.ceil(fraction * len(values)) - 1))
    return values[index]


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _json_mapping(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CudaQualificationError(f"{label} must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_qualification(
        max_recordings=args.max_recordings,
        output_root=args.output_root,
        sampling_interval_sec=args.sampling_interval_sec,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
