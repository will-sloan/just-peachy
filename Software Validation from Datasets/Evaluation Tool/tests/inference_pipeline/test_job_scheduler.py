from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from app.inference_pipeline.runtime.gpu import GpuDevice, GpuSample
from app.inference_pipeline.runtime.job_scheduler import (
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    STATUS_TIMED_OUT,
    JobSpec,
    SchedulerConfig,
    load_runtime_profile,
    run_jobs,
    write_parallel_execution_report,
)
from app.prediction_io.schema import UTTERANCE_REQUIRED_FIELDS
from scripts.run_parallel_sweep import build_fake_jobs, load_parallel_sweep_config


TOOL_ROOT = Path(__file__).resolve().parents[2]


class FakeGpuTelemetryProvider:
    def __init__(self) -> None:
        self.calls = 0

    def devices(self):
        return (
            GpuDevice(index="0", name="Fake RTX 3080", total_vram_mb=10240, uuid="gpu-0"),
            GpuDevice(index="1", name="Fake RTX 3090", total_vram_mb=24576, uuid="gpu-1"),
        )

    def snapshot(self):
        self.calls += 1
        return (
            GpuSample(
                index="0",
                timestamp_sec=float(self.calls),
                name="Fake RTX 3080",
                total_vram_mb=10240,
                used_vram_mb=2048 + self.calls,
                utilization_percent=30 + self.calls,
            ),
            GpuSample(
                index="1",
                timestamp_sec=float(self.calls),
                name="Fake RTX 3090",
                total_vram_mb=24576,
                used_vram_mb=4096 + self.calls,
                utilization_percent=40 + self.calls,
            ),
        )


def marker_job(job_id: str) -> JobSpec:
    script = (
        "import json, os, pathlib; "
        "run_dir = pathlib.Path(os.environ['JP_RUN_DIR']); "
        "run_dir.mkdir(parents=True, exist_ok=True); "
        "(run_dir / 'marker.json').write_text("
        "json.dumps({"
        "'job_id': os.environ.get('JP_JOB_ID'), "
        "'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES'), "
        "'run_dir': str(run_dir)"
        "}, sort_keys=True), encoding='utf-8')"
    )
    return JobSpec(
        job_id=job_id,
        command=(sys.executable, "-c", script),
        audio_duration_sec=60.0,
        config_snapshot={"test_job": job_id},
    )


def scheduler_config(tmp_path: Path, *, serial: bool = False) -> SchedulerConfig:
    return SchedulerConfig(
        run_id="unit_parallel",
        output_root=tmp_path / "parallel",
        max_workers=2,
        serial=serial,
        timeout_sec=5,
        retry_count=0,
        gpu_ids=("0", "1"),
        telemetry_poll_interval_sec=0.01,
    )


def test_parallel_jobs_get_unique_run_dirs_and_cuda_assignments(tmp_path: Path) -> None:
    result = run_jobs(
        [marker_job("alpha"), marker_job("beta")],
        scheduler_config(tmp_path),
        telemetry_provider=FakeGpuTelemetryProvider(),
    )

    assert [job.status for job in result.jobs] == [STATUS_SUCCEEDED, STATUS_SUCCEEDED]
    assert len({job.run_dir for job in result.jobs}) == 2
    assert [job.assigned_cuda_device for job in result.jobs] == ["0", "1"]
    for job in result.jobs:
        payload = json.loads((job.run_dir / "marker.json").read_text(encoding="utf-8"))
        assert payload["job_id"] == job.job_id
        assert payload["cuda_visible_devices"] == job.assigned_cuda_device
        assert job.config_snapshot_path.exists()
        assert job.gpu.peak_memory_mb is not None
    assert result.throughput_audio_hours_per_wall_hour is not None
    assert (result.config.output_root / "parallel_scheduler_result.json").exists()
    assert (result.config.output_root / "parallel_scheduler_jobs.csv").exists()


def test_serial_fallback_uses_one_effective_worker(tmp_path: Path) -> None:
    result = run_jobs(
        [marker_job("one"), marker_job("two")],
        scheduler_config(tmp_path, serial=True),
        telemetry_provider=FakeGpuTelemetryProvider(),
    )

    assert result.config.serial is True
    assert result.config.effective_max_workers == 1
    assert [job.status for job in result.jobs] == [STATUS_SUCCEEDED, STATUS_SUCCEEDED]


def test_scheduler_reports_timeout_and_failure_without_losing_results(tmp_path: Path) -> None:
    sleep_job = JobSpec(
        job_id="timeout",
        command=(sys.executable, "-c", "import time; time.sleep(1.0)"),
        timeout_sec=0.05,
    )
    failure_job = JobSpec(
        job_id="failure",
        command=(sys.executable, "-c", "import sys; sys.exit(7)"),
    )
    config = SchedulerConfig(
        run_id="unit_failures",
        output_root=tmp_path / "parallel",
        max_workers=2,
        timeout_sec=5,
        gpu_ids=("0",),
        telemetry_poll_interval_sec=0.01,
    )

    result = run_jobs(
        [sleep_job, failure_job],
        config,
        telemetry_provider=FakeGpuTelemetryProvider(),
    )

    assert [job.status for job in result.jobs] == [STATUS_TIMED_OUT, STATUS_FAILED]
    assert result.failure_rate == pytest.approx(1.0)
    assert result.jobs[0].failure_message is not None
    assert "timed out" in result.jobs[0].failure_message
    assert result.jobs[1].returncode == 7


def test_parallel_execution_report_includes_runtime_recommendations(tmp_path: Path) -> None:
    result = run_jobs(
        [marker_job("alpha"), marker_job("beta")],
        scheduler_config(tmp_path),
        telemetry_provider=FakeGpuTelemetryProvider(),
    )
    profile = {
        "gpu_name": "Fake RTX 3090",
        "recommended_concurrency": 2,
        "recommendation_notes": "Use two workers for this fake profile.",
    }
    report_path = write_parallel_execution_report(
        tmp_path / "reports" / "runtime" / "parallel_execution_unit.md",
        result,
        runtime_profiles=[profile],
        test_commands=["python -m pytest tests/inference_pipeline/test_job_scheduler.py"],
        smoke_commands=["python scripts/run_parallel_sweep.py --dry-run-fake-jobs"],
    )

    text = report_path.read_text(encoding="utf-8")
    assert "Recommended Concurrency" in text
    assert "Fake RTX 3090" in text
    assert "Throughput audio hours" in text
    assert "CUDA_VISIBLE_DEVICES" in text


def test_parallel_sweep_config_loads_and_fake_jobs_are_valid() -> None:
    sweep = load_parallel_sweep_config(TOOL_ROOT / "configs" / "sweeps" / "parallel_asr_eval.yaml")
    fake_jobs = build_fake_jobs(2)

    assert sweep.sweep_name == "parallel_asr_eval"
    assert len(sweep.jobs) == 2
    assert sweep.jobs[0].command[0] == sys.executable
    assert "{run_dir}" in sweep.jobs[0].command[-1]
    assert [job.job_id for job in fake_jobs] == ["fake_job_1", "fake_job_2"]


def test_runtime_profiles_load_and_prediction_contract_is_unchanged() -> None:
    rtx3080 = load_runtime_profile(TOOL_ROOT / "configs" / "runtime" / "rtx3080.yaml")
    rtx3090 = load_runtime_profile(TOOL_ROOT / "configs" / "runtime" / "rtx3090.yaml")

    assert rtx3080["recommended_concurrency"] == 1
    assert rtx3090["recommended_concurrency"] == 2
    assert UTTERANCE_REQUIRED_FIELDS == (
        "recording_id",
        "utt_id",
        "start_sec",
        "end_sec",
        "speaker_label",
        "text",
    )
