from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import shutil
import sys

import pyarrow.parquet as pq
import pytest

from app.artifact_contracts.atomic import ScenarioArtifactStore
from app.artifact_contracts.registry import (
    ARTIFACT_REGISTRY_VERSION,
    LATEST_ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
    registry_for_scenario,
)
from app.artifact_contracts.schemas import validate_artifact
from app.artifact_contracts.completion import validate_scenario_completion
from app.benchmark_contracts.scenario import finalize_scenario
from app.campaign_executor.executor import CampaignExecutor
from app.campaign_executor.planner import plan_campaign
from app.model_runner.simulated import FakeModelRunner
from app.resource_telemetry.context import SpanRecorder, activate_recorder, telemetry_span
from app.resource_telemetry.providers import (
    GpuSnapshot,
    NvmlGpuProvider,
    PsutilSystemProvider,
    SystemSnapshot,
)
from app.resource_telemetry.sampler import ResourceSampler
from app.resource_telemetry.session import ScenarioTelemetrySession
from app.resource_telemetry.validation import validate_spans


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage2"
FIXED_UTC = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, monotonic_values: list[int]) -> None:
        self.values = iter(monotonic_values)
        self.wall_calls = 0

    def monotonic_ns(self) -> int:
        return next(self.values)

    def utc_now(self) -> datetime:
        value = FIXED_UTC + timedelta(seconds=self.wall_calls)
        self.wall_calls += 1
        return value


class FakeSystemProvider:
    def __init__(self, pids: tuple[int, ...] = (101, 102)) -> None:
        self.pids = pids
        self.calls = 0

    def snapshot(self, root_pid: int, disk_path: Path) -> SystemSnapshot:
        _ = disk_path
        self.calls += 1
        return SystemSnapshot(
            process_tree_pids=(root_pid, *self.pids),
            process_cpu_percent=10.0 + self.calls,
            system_cpu_percent=25.0,
            process_rss_bytes=1000 * self.calls,
            process_vms_bytes=2000 * self.calls,
            system_ram_total_bytes=16_000,
            system_ram_available_bytes=8_000,
            system_ram_used_bytes=8_000,
            system_ram_percent=50.0,
            process_disk_read_bytes=100,
            process_disk_write_bytes=200,
            system_disk_read_bytes=300,
            system_disk_write_bytes=400,
            disk_free_bytes=1_000_000,
        )

    def availability(self):
        return {
            "process_cpu_percent": {"available": True, "source": "fake", "reason": None},
            "process_rss_bytes": {"available": True, "source": "fake", "reason": None},
        }


class FakeGpuProvider:
    def __init__(self, vram_values: tuple[int, ...] = (100, 250, 150)) -> None:
        self.vram_values = vram_values
        self.calls = 0

    def snapshot(self, gpu_index: str | None, process_tree_pids) -> GpuSnapshot:
        _ = process_tree_pids
        value = self.vram_values[min(self.calls, len(self.vram_values) - 1)]
        self.calls += 1
        return GpuSnapshot(
            gpu_index=gpu_index or "0",
            gpu_uuid="GPU-FAKE",
            gpu_utilization_percent=50.0,
            gpu_memory_utilization_percent=20.0,
            gpu_vram_bytes=value,
            gpu_total_vram_bytes=1000,
            gpu_temperature_c=60.0,
            gpu_power_w=120.0,
            gpu_power_limit_w=300.0,
        )

    def availability(self):
        return {
            "gpu_uuid": {"available": True, "source": "fake", "reason": None},
            "gpu_vram_bytes": {"available": True, "source": "fake", "reason": None},
            "gpu_temperature_c": {"available": True, "source": "fake", "reason": None},
        }


def _sampler(
    tmp_path: Path,
    *,
    clock: FakeClock,
    system=None,
    gpu=None,
    active_state_path: Path | None = None,
) -> ResourceSampler:
    return ResourceSampler(
        campaign_id="campaign_stage5test",
        scenario_id="scenario_0123456789ab",
        attempt=1,
        worker_id="worker_test",
        host="test-host",
        root_pid=100,
        disk_path=tmp_path,
        active_state_path=active_state_path,
        interval_sec=1.0,
        system_provider=system or FakeSystemProvider(),
        gpu_provider=gpu or FakeGpuProvider(),
        clock=clock,
    )


def test_latest_registry_is_additive_and_v1_remains_frozen() -> None:
    v1 = ArtifactRegistry.load()
    v2 = ArtifactRegistry.load_version("artifact-registry.v2")
    latest = ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION)
    assert v1.schema_version == ARTIFACT_REGISTRY_VERSION
    assert v1.get("resource_usage").schema_version == "resource-usage.v1"
    assert v2.get("resource_usage").schema_version == "resource-usage.v2"
    assert {"component_spans", "resource_summary", "resource_availability"}.issubset(
        {artifact.artifact_id for artifact in v2.artifacts}
    )
    assert latest.get("streaming_diagnostics").schema_version == (
        "streaming-diagnostics-row.v1"
    )


def test_injectable_clock_sampling_gap_process_tree_and_peak(tmp_path: Path) -> None:
    active = tmp_path / "active.json"
    active.write_text('{"active_component":"asr_inference"}\n', encoding="utf-8")
    sampler = _sampler(
        tmp_path,
        clock=FakeClock([0, 2_000_000_000, 3_000_000_000]),
        active_state_path=active,
    )
    first = sampler.sample_once()
    second = sampler.sample_once()
    third = sampler.sample_once()
    assert first["process_tree_pids"] == [100, 101, 102]
    assert first["active_component"] == "asr_inference"
    assert second["sampling_gap"] is True
    assert third["gpu_peak_vram_bytes"] == 250
    assert any("sampling gap" in warning for warning in sampler.warnings)


def test_missing_nvml_is_explicit_and_does_not_affect_cpu_provider() -> None:
    class MissingNvml:
        def nvmlInit(self):
            raise RuntimeError("driver absent")

    gpu = NvmlGpuProvider(module=MissingNvml())
    snapshot = gpu.snapshot("0", [os.getpid()])
    assert snapshot.gpu_uuid is None
    assert "NVML initialization failed" in str(snapshot.availability_reason)
    assert all(not item["available"] and item["reason"] for item in gpu.availability().values())


def test_nested_spans_preserve_parentage_and_cuda_unavailability(tmp_path: Path) -> None:
    recorder = SpanRecorder(
        tmp_path / "raw.jsonl",
        tmp_path / "active.json",
        {
            "campaign_id": "campaign_stage5test",
            "scenario_id": "scenario_0123456789ab",
            "attempt": 1,
            "worker_id": "worker_test",
            "host": "test-host",
        },
        monotonic_ns=iter([100, 110, 120, 130]).__next__,
        wall_clock=lambda: FIXED_UTC,
    )
    with activate_recorder(recorder):
        with telemetry_span("outer"):
            with telemetry_span("inner", cuda=True):
                pass
    rows = [json.loads(line) for line in (tmp_path / "raw.jsonl").read_text(encoding="utf-8").splitlines()]
    inner, outer = rows
    assert inner["parent_span_id"] == outer["span_id"]
    assert inner["cuda_timing_available"] is False
    assert validate_spans(rows, scenario_id="scenario_0123456789ab") == ()


def test_span_io_failure_cannot_change_pipeline_control_flow(tmp_path: Path) -> None:
    class BrokenRecorder(SpanRecorder):
        def _append(self, row):
            _ = row
            raise OSError("simulated span disk failure")

        def _write_active(self, name, stack):
            _ = (name, stack)
            raise OSError("simulated active-state disk failure")

    recorder = BrokenRecorder(
        tmp_path / "raw.jsonl",
        tmp_path / "active.json",
        {
            "campaign_id": "campaign_stage5test",
            "scenario_id": "scenario_0123456789ab",
            "attempt": 1,
            "worker_id": "worker_test",
            "host": "test-host",
        },
    )
    completed = False
    with activate_recorder(recorder):
        with telemetry_span("asr_inference"):
            completed = True
    assert completed is True


def test_crossing_span_overlap_is_reported_without_rejecting_parallelism() -> None:
    base = {
        "schema_version": "component-spans.v1",
        "campaign_id": "campaign_stage5test",
        "scenario_id": "scenario_0123456789ab",
        "attempt": 1,
        "worker_id": "worker_test",
        "host": "test-host",
        "pid": 1,
        "thread_id": 1,
        "parent_span_id": None,
        "phase": "component",
        "start_timestamp_utc": "2026-08-08T12:00:00Z",
        "status": "ok",
        "error_type": None,
        "cuda_timing_requested": False,
        "cuda_timing_available": False,
        "cuda_elapsed_ms": None,
        "cuda_availability_reason": "not requested",
        "recording_id": None,
        "utt_id": None,
        "segment_index": None,
    }
    rows = [
        {**base, "span_id": "a", "name": "a", "start_monotonic_ns": 0, "end_monotonic_ns": 20, "duration_ns": 20},
        {**base, "span_id": "b", "name": "b", "start_monotonic_ns": 10, "end_monotonic_ns": 30, "duration_ns": 20},
    ]
    warnings = validate_spans(rows)
    assert len(warnings) == 1
    assert "crossing spans" in warnings[0]


def test_real_cpu_telemetry_smoke_without_nvidia_tooling(tmp_path: Path) -> None:
    provider = PsutilSystemProvider()
    snapshot = provider.snapshot(os.getpid(), tmp_path)
    assert os.getpid() in snapshot.process_tree_pids
    assert snapshot.process_rss_bytes is not None and snapshot.process_rss_bytes > 0
    assert snapshot.system_ram_total_bytes is not None
    assert snapshot.disk_free_bytes is not None


def test_session_publishes_typed_atomic_artifacts_and_reconciles_summary(tmp_path: Path) -> None:
    scenario = json.loads((FIXTURES / "golden_scenario.json").read_text(encoding="utf-8"))
    scenario_id = str(scenario["scenario_id"])
    scenario_hash = str(scenario["scenario_hash"])
    scenario_root = tmp_path / scenario_id
    scenario_root.mkdir()
    store = ScenarioArtifactStore(scenario_root, scenario_id)
    store.publish_json("resolved_scenario.json", scenario)
    store.publish_yaml(
        "run_config.yaml",
        {
            "schema_version": "run-config.v1",
            "artifact_registry_version": ARTIFACT_REGISTRY_VERSION,
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "settings": {"output_root": "scenarios/current"},
        },
    )
    session = ScenarioTelemetrySession(
        campaign_id="campaign_stage5test",
        scenario_id=scenario_id,
        scenario_hash=scenario_hash,
        attempt=1,
        worker_id="worker_test",
        host="test-host",
        root_pid=os.getpid(),
        disk_path=tmp_path,
        staging_root=tmp_path / "raw",
        interval_sec=100.0,
        system_provider=FakeSystemProvider(),
        gpu_provider=FakeGpuProvider(),
    )
    session.start()
    summary = session.publish(scenario_root)
    registry = registry_for_scenario(scenario_root)
    assert registry.schema_version == LATEST_ARTIFACT_REGISTRY_VERSION
    table = pq.read_table(scenario_root / "resource_logs" / "resource_usage.parquet")
    assert summary["sample_count"] == table.num_rows
    assert summary["resources"]["gpu_peak_vram_bytes"]["max"] == 250.0
    for artifact_id in (
        "resource_usage", "component_spans", "resource_summary", "resource_availability"
    ):
        definition = registry.get(artifact_id)
        validate_artifact(
            scenario_root / definition.path,
            definition,
            scenario_id=scenario_id,
            scenario_hash=scenario_hash,
        )
    checksum_text = (scenario_root / "checksums.json").read_text(encoding="utf-8")
    assert "resource_logs/resource_summary.json" in checksum_text
    assert str(tmp_path) not in (scenario_root / "resource_logs" / "resource_summary.json").read_text(encoding="utf-8")


def test_telemetry_does_not_change_prediction_content(tmp_path: Path) -> None:
    record = {
        "recording_id": "rec-1",
        "utt_id": "utt-1",
        "reference_text": "the same deterministic prediction",
        "audio_path_resolved": str(tmp_path / "unused.wav"),
        "audio_path_project_relative": "unused.wav",
        "_selection_index": 0,
    }
    logger = logging.getLogger("stage5-prediction-invariance")

    def run(root: Path, recorder: SpanRecorder | None) -> bytes:
        config = {
            "project_root": str(tmp_path),
            "run_dir": str(root),
            "augmentation": {
                "mode": "none",
                "conditions": [{"condition_id": "clean", "mode": "none"}],
            },
        }
        with activate_recorder(recorder):
            FakeModelRunner("noisy").run_batch([record], root / "predictions", config, logger)
        return (root / "predictions" / "utterances.jsonl").read_bytes()

    baseline = run(tmp_path / "baseline", None)
    recorder = SpanRecorder(
        tmp_path / "telemetry" / "spans.jsonl",
        tmp_path / "telemetry" / "active.json",
        {
            "campaign_id": "campaign_stage5test",
            "scenario_id": "scenario_0123456789ab",
            "attempt": 1,
            "worker_id": "worker_test",
            "host": "test-host",
        },
    )
    instrumented = run(tmp_path / "instrumented", recorder)
    assert instrumented == baseline


def test_campaign_executor_publishes_telemetry_without_parallel_gpu_jobs(tmp_path: Path) -> None:
    source = json.loads((FIXTURES / "golden_scenario_source.json").read_text(encoding="utf-8"))
    identity = json.loads((FIXTURES / "golden_manifest_identity.json").read_text(encoding="utf-8"))
    source["benchmark_manifest"] = {**identity, "path": "golden_manifest.parquet"}
    scenario = finalize_scenario(source)
    scenario["artifact_contract"] = {
        "schema_version": "scenario-artifact-requirements.v1",
        "scenario_type": "synthetic_executor",
        "capabilities": [],
    }
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir()
    shutil.copy2(FIXTURES / "golden_manifest.parquet", catalog_root / "golden_manifest.parquet")
    catalog = catalog_root / "resolved_scenarios.jsonl"
    catalog.write_text(json.dumps(scenario, sort_keys=True) + "\n", encoding="utf-8")
    plan = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=tmp_path / "automated_runs",
        campaign_id="campaign_stage5exec",
        registry=ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION),
    )

    def command(_lease, scenario_root: Path):
        return [
            sys.executable,
            "-m",
            "app.campaign_executor.synthetic_worker",
            "--scenario-root",
            str(scenario_root),
            "--behavior",
            "success",
        ]

    result = CampaignExecutor(
        plan.campaign_root,
        project_root=Path(__file__).resolve().parents[3],
        worker_id="worker_stage5",
        command_builder=command,
        minimum_free_disk_bytes=0,
        stop_poll_seconds=0.01,
        telemetry_enabled=True,
        telemetry_interval_sec=0.01,
        telemetry_system_provider=FakeSystemProvider(),
        telemetry_gpu_provider=FakeGpuProvider(),
    ).run(max_scenarios=1)
    scenario_root = plan.campaign_root / "scenarios" / str(scenario["scenario_id"])
    assert result.succeeded == 1
    assert (scenario_root / "resource_logs" / "resource_usage.parquet").is_file()
    assert (scenario_root / "resource_logs" / "component_spans.jsonl").is_file()
    assert validate_scenario_completion(scenario_root).complete


@pytest.mark.skipif(
    not pytest.importorskip("torch").cuda.is_available(),
    reason="CUDA is not available on this test host",
)
def test_real_cuda_event_timing_smoke_when_available(tmp_path: Path) -> None:
    import torch

    recorder = SpanRecorder(
        tmp_path / "cuda.jsonl",
        tmp_path / "active.json",
        {
            "campaign_id": "campaign_stage5test",
            "scenario_id": "scenario_0123456789ab",
            "attempt": 1,
            "worker_id": "worker_test",
            "host": "test-host",
        },
        cuda_timing=True,
    )
    with activate_recorder(recorder):
        with telemetry_span("asr_inference", phase="warm_inference", cuda=True):
            value = torch.ones((64, 64), device="cuda")
            _ = value @ value
    row = json.loads((tmp_path / "cuda.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["cuda_timing_available"] is True
    assert row["cuda_elapsed_ms"] is not None and row["cuda_elapsed_ms"] >= 0
