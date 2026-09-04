"""Measure frozen H2 event-emission to Tk presentation latency.

The benchmark is engineering evidence, not a scientific selection input.  It
uses the real durable JSONL cursor, coalescing update buffer, asynchronous UI
poller, state projector, and Tk render methods, while deliberately replacing
neural inference and physical audio capture with a controlled event source.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))
DEFAULT_WORKSPACE = TOOL_ROOT / "automated_runs/h2_complete_product_pipeline_v17"
DEFAULT_OUTPUT = (
    DEFAULT_WORKSPACE / "engineering_validation/ui_event_latency_receipt.json"
)
SCHEMA_VERSION = "h2-ui-event-latency-receipt.v1"
BENCHMARK_ID = "H2_DURABLE_EVENT_TO_TK_RENDER_CONTROLLED_V1"
SOURCE_FILES = (
    TOOL_ROOT / "app/full_pipeline/events.py",
    TOOL_ROOT / "app/full_pipeline_demo/session.py",
    TOOL_ROOT / "app/full_pipeline_demo/state.py",
    TOOL_ROOT / "app/full_pipeline_demo/ui.py",
)
DEFAULT_PHASE_OFFSETS_MS = (0, 20, 40, 60, 80)


class UiLatencyBenchmarkError(RuntimeError):
    """The controlled UI benchmark could not produce trustworthy evidence."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0.0 <= percentile <= 100.0:
        raise ValueError("percentile must be in [0, 100]")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_latencies(values: Sequence[float]) -> dict[str, float | int | str]:
    """Return a deterministic descriptive summary for millisecond samples."""

    rows = [float(value) for value in values]
    if not rows or any(not math.isfinite(value) or value < 0.0 for value in rows):
        raise ValueError("latencies must be finite non-negative values")
    return {
        "sample_count": len(rows),
        "unit": "milliseconds",
        "minimum_ms": min(rows),
        "mean_ms": statistics.fmean(rows),
        "median_ms": statistics.median(rows),
        "p50_ms": _percentile(rows, 50.0),
        "p95_ms": _percentile(rows, 95.0),
        "p99_ms": _percentile(rows, 99.0),
        "maximum_ms": max(rows),
        "population_standard_deviation_ms": statistics.pstdev(rows),
    }


def _logical_source_hashes() -> dict[str, str]:
    missing = [path for path in SOURCE_FILES if not path.is_file()]
    if missing:
        raise UiLatencyBenchmarkError(
            "required frozen UI source is missing: " + ", ".join(map(str, missing))
        )
    return {
        path.relative_to(TOOL_ROOT).as_posix(): _sha256_file(path)
        for path in SOURCE_FILES
    }


def _pump_tk(root: object, duration_ms: int) -> None:
    deadline = time.perf_counter() + max(0, duration_ms) / 1000.0
    while time.perf_counter() < deadline:
        root.update()  # type: ignore[attr-defined]
        time.sleep(0.001)


def measure_ui_latency(
    *,
    working_root: Path,
    sample_count: int = 100,
    warmup_count: int = 10,
    timeout_sec: float = 5.0,
    phase_offsets_ms: Sequence[int] = DEFAULT_PHASE_OFFSETS_MS,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Measure the real durable-event-to-hidden-Tk presentation path."""

    if sample_count < 1 or warmup_count < 0:
        raise ValueError("sample_count must be positive and warmup_count non-negative")
    offsets = tuple(int(value) for value in phase_offsets_ms)
    if not offsets or any(value < 0 for value in offsets):
        raise ValueError("phase offsets must contain non-negative milliseconds")
    if timeout_sec <= 0.0:
        raise ValueError("timeout_sec must be positive")

    try:
        import tkinter as tk
    except ImportError as exc:  # pragma: no cover - platform packaging failure
        raise UiLatencyBenchmarkError("Tkinter is unavailable") from exc

    from app.full_pipeline.events import EventFactory, OrderedJsonlEventSink
    from app.full_pipeline.factory import MATRIX_PATH, RUNTIME_CONFIG_PATH
    from app.full_pipeline.matrix import FullPipelineMatrix
    from app.full_pipeline_demo.h2_ux import H2_DEFAULT_PRODUCT_MODE
    from app.full_pipeline_demo.presets import PresetCatalog
    from app.full_pipeline_demo.session import (
        DemoSessionManager,
        JsonlEventCursor,
        _ManagedSession,
    )
    from app.full_pipeline_demo.state import DemoViewState
    from app.full_pipeline_demo.ui import FullPipelineDemoApp, POLL_INTERVAL_MS

    class EmptyEnrollmentService:
        @staticmethod
        def list() -> tuple[object, ...]:
            return ()

    destination = Path(working_root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    session_id = "h2_ui_latency_controlled"
    pipeline_id = "fullpipe_v1_ag_dr_ir"
    session_root = destination / "session"
    event_path = session_root / "events/events.jsonl"
    event_path.parent.mkdir(parents=True, exist_ok=True)

    manager = DemoSessionManager(results_root=destination / "manager")
    record = _ManagedSession(
        session_id=session_id,
        source_kind="controlled_durable_event",
        pipeline_id=pipeline_id,
        product_mode=H2_DEFAULT_PRODUCT_MODE,
        output_root=session_root,
        builder=lambda **_kwargs: None,
        builder_kwargs={},
        pipeline_identity={"pipeline_id": pipeline_id},
        scientific_runtime_configuration={
            "status": "FROZEN",
            "final_scientific_validation": False,
        },
        state="running",
        started_at_utc=_utc_now(),
    )
    record.ui_cursor = JsonlEventCursor(event_path)
    record.event_cursor = JsonlEventCursor(event_path)
    with manager._lock:  # Controlled fixture for the exact manager polling path.
        manager._sessions[session_id] = record
        manager._active_session_id = session_id

    root = None
    sink = None
    app = None
    try:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            raise UiLatencyBenchmarkError(f"Tk cannot initialize: {exc}") from exc
        root.withdraw()
        tk_patchlevel = str(root.tk.call("info", "patchlevel"))
        catalog = PresetCatalog(FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH))
        app = FullPipelineDemoApp(
            root,
            catalog=catalog,
            session_manager=manager,
            enrollment_service=EmptyEnrollmentService(),  # type: ignore[arg-type]
            device_enumerator=lambda: (),
        )
        app._active_session_id = session_id
        app._session_started_monotonic = time.monotonic()
        app.view_state = DemoViewState(
            session_id=session_id,
            pipeline_id=pipeline_id,
            product_mode=H2_DEFAULT_PRODUCT_MODE,
            scientific_config_status="FROZEN_SCIENTIFIC_CONFIGURATION",
            processing_state="running",
        )
        app._render_state()
        _pump_tk(root, 150)

        factory = EventFactory(
            session_id=session_id,
            pipeline_id=pipeline_id,
            protocol_version="full-speech-pipeline-contracts.v1",
            stream_id="controlled_ui_latency_stream",
            recording_id=None,
            source_clock={
                "clock_id": "controlled_ui_latency_clock",
                "sample_rate_hz": 16000,
                "channels": 1,
            },
        )
        sink = OrderedJsonlEventSink(event_path)
        emitted_by_sequence: dict[int, int] = {}
        render_by_sequence: dict[int, dict[str, object]] = {}
        original_render = app._render_state

        def observed_render() -> None:
            original_render()
            sequence = app.view_state.last_event_sequence
            if sequence not in emitted_by_sequence or sequence in render_by_sequence:
                return
            root.update_idletasks()
            cluster_id = "ui_latency_cluster"
            roster_values = tuple(str(value) for value in app.roster_tree.item(cluster_id, "values"))
            expected_event_text = f"#{sequence} IdentityLabelEvent"
            render_by_sequence[sequence] = {
                "render_completed_monotonic_ns": time.perf_counter_ns(),
                "last_event_widget_value": app.metric_last_event.get(),
                "last_event_widget_verified": app.metric_last_event.get()
                == expected_event_text,
                "roster_widget_verified": bool(roster_values)
                and roster_values[0] == f"Controlled Speaker {sequence}",
            }

        app._render_state = observed_render  # type: ignore[method-assign]
        all_samples: list[dict[str, object]] = []
        total_count = warmup_count + sample_count
        for ordinal in range(total_count):
            phase_offset = offsets[ordinal % len(offsets)]
            _pump_tk(root, phase_offset)
            event = factory.create(
                contract_type="IdentityLabelEvent",
                event_type="identity_label",
                component_identity={
                    "component_name": "identity_policy",
                    "backend_id": "controlled_no_inference",
                    "model_id": "none",
                    "model_sha256": None,
                },
                payload={
                    "anonymous_speaker_id": "ui_latency_cluster",
                    "speaker_label": {
                        "speaker_id": "controlled_speaker",
                        "display_label": f"Controlled Speaker {factory.next_sequence}",
                    },
                    "identity_state": "confirmed",
                    "roster_state": "active",
                },
                capture_timestamps={
                    "audio_start_sec": float(ordinal),
                    "audio_end_sec": float(ordinal) + 0.5,
                },
                event_reason="controlled_ui_latency_measurement",
            )
            sequence = int(event["event_sequence"])
            processing = event.get("processing_timestamps")
            if not isinstance(processing, Mapping):
                raise UiLatencyBenchmarkError("event lacks processing timestamps")
            emitted_ns = int(processing["emitted_monotonic_ns"])
            emitted_by_sequence[sequence] = emitted_ns
            sink.emit(event)
            deadline = time.perf_counter() + timeout_sec
            while sequence not in render_by_sequence and time.perf_counter() < deadline:
                root.update()
                time.sleep(0.001)
            if sequence not in render_by_sequence:
                raise UiLatencyBenchmarkError(
                    f"UI did not render event sequence {sequence} within {timeout_sec}s"
                )
            observation = render_by_sequence[sequence]
            rendered_ns = int(observation["render_completed_monotonic_ns"])
            if not observation["last_event_widget_verified"] or not observation[
                "roster_widget_verified"
            ]:
                raise UiLatencyBenchmarkError(
                    f"Tk widget verification failed for event sequence {sequence}"
                )
            if ordinal >= warmup_count:
                all_samples.append(
                    {
                        "sample_index": ordinal - warmup_count + 1,
                        "event_sequence": sequence,
                        "injection_phase_offset_ms": phase_offset,
                        "emitted_monotonic_ns": emitted_ns,
                        "render_completed_monotonic_ns": rendered_ns,
                        "latency_ms": (rendered_ns - emitted_ns) / 1_000_000.0,
                        **observation,
                    }
                )
        metadata = {
            "tk_patchlevel": tk_patchlevel,
            "configured_poll_interval_ms": POLL_INTERVAL_MS,
            "phase_offsets_ms": list(offsets),
            "durable_event_path_exercised": True,
            "coalescing_update_buffer_exercised": True,
            "background_task_runner_exercised": True,
            "tk_widget_render_verified": True,
        }
        return all_samples, metadata
    finally:
        if sink is not None:
            sink.close()
        if app is not None:
            app._closing = True
            app.tasks.close()
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass


def build_receipt(
    *,
    samples: Sequence[Mapping[str, object]],
    benchmark_metadata: Mapping[str, object],
    runtime_identity: Mapping[str, object],
    runtime_identity_file_sha256: str,
    warmup_count: int,
    timeout_sec: float,
) -> dict[str, object]:
    latency_values = [float(row["latency_ms"]) for row in samples]
    receipt: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "VALID",
        "benchmark_id": BENCHMARK_ID,
        "recorded_at_utc": _utc_now(),
        "evidence_class": "CONTROLLED_ENGINEERING_UI_PRESENTATION_LATENCY",
        "scientific_selection_or_policy_changed": False,
        "neural_inference_executed": False,
        "physical_microphone_or_display_performance_claimed": False,
        "scope": {
            "start": "EventFactory processing_timestamps.emitted_monotonic_ns",
            "end": "Tk widgets updated and update_idletasks completed",
            "included": [
                "ordered durable JSONL event write and flush",
                "JsonlEventCursor read",
                "CoalescingUpdateBuffer",
                "BackgroundTaskRunner worker-to-Tk handoff",
                "DemoViewState projection",
                "FullPipelineDemoApp Tk widget update",
            ],
            "excluded": [
                "audio capture",
                "neural inference",
                "backend compute latency",
                "operating-system display compositor and physical panel scanout",
            ],
        },
        "runtime_binding": {
            "schema_version": runtime_identity.get("schema_version"),
            "frozen_runtime_identity_sha256": runtime_identity.get("identity_sha256"),
            "frozen_runtime_identity_file_sha256": runtime_identity_file_sha256,
            "current_runtime_identity_sha256": runtime_identity.get("identity_sha256"),
            "exact_source_file_sha256": _logical_source_hashes(),
        },
        "protocol": {
            "sample_count": len(samples),
            "warmup_count": int(warmup_count),
            "per_event_timeout_sec": float(timeout_sec),
            "phase_offsets_ms": list(benchmark_metadata["phase_offsets_ms"]),
            "configured_poll_interval_ms": int(
                benchmark_metadata["configured_poll_interval_ms"]
            ),
            "one_event_in_flight_at_a_time": True,
            "monotonic_clock_shared_by_emitter_and_ui": True,
        },
        "environment": {
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "tk_patchlevel": benchmark_metadata["tk_patchlevel"],
            "logical_cpu_count": os.cpu_count(),
        },
        "path_coverage": {
            key: benchmark_metadata[key]
            for key in (
                "durable_event_path_exercised",
                "coalescing_update_buffer_exercised",
                "background_task_runner_exercised",
                "tk_widget_render_verified",
            )
        },
        "metrics": summarize_latencies(latency_values),
        "samples": [dict(row) for row in samples],
    }
    receipt["receipt_sha256"] = _sha256_bytes(_canonical_bytes(receipt))
    return receipt


def validate_receipt(
    value: Mapping[str, object],
    *,
    expected_runtime_identity_sha256: str | None = None,
) -> dict[str, object]:
    """Validate signature, measurements, widget proof, and runtime binding."""

    receipt = dict(value)
    signature = receipt.pop("receipt_sha256", None)
    if signature != _sha256_bytes(_canonical_bytes(receipt)):
        raise ValueError("UI latency receipt signature differs")
    if (
        receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("status") != "VALID"
        or receipt.get("benchmark_id") != BENCHMARK_ID
        or receipt.get("scientific_selection_or_policy_changed") is not False
        or receipt.get("neural_inference_executed") is not False
        or receipt.get("physical_microphone_or_display_performance_claimed") is not False
    ):
        raise ValueError("UI latency receipt schema/status/firewall differs")
    runtime = receipt.get("runtime_binding")
    if not isinstance(runtime, Mapping):
        raise ValueError("UI latency runtime binding is missing")
    runtime_sha = str(runtime.get("frozen_runtime_identity_sha256") or "")
    if len(runtime_sha) != 64 or (
        expected_runtime_identity_sha256 is not None
        and runtime_sha != expected_runtime_identity_sha256
    ):
        raise ValueError("UI latency frozen runtime identity differs")
    source_hashes = runtime.get("exact_source_file_sha256")
    if not isinstance(source_hashes, Mapping) or set(map(str, source_hashes)) != {
        path.relative_to(TOOL_ROOT).as_posix() for path in SOURCE_FILES
    }:
        raise ValueError("UI latency exact source inventory differs")
    samples = receipt.get("samples")
    protocol = receipt.get("protocol")
    path_coverage = receipt.get("path_coverage")
    if not isinstance(samples, list) or not isinstance(protocol, Mapping):
        raise ValueError("UI latency samples/protocol are missing")
    if int(protocol.get("sample_count") or 0) != len(samples) or not samples:
        raise ValueError("UI latency sample count differs")
    if not isinstance(path_coverage, Mapping) or any(
        path_coverage.get(key) is not True
        for key in (
            "durable_event_path_exercised",
            "coalescing_update_buffer_exercised",
            "background_task_runner_exercised",
            "tk_widget_render_verified",
        )
    ):
        raise ValueError("UI latency path coverage is incomplete")
    sequences: list[int] = []
    latencies: list[float] = []
    for row in samples:
        if not isinstance(row, Mapping):
            raise ValueError("UI latency sample is not an object")
        emitted = int(row.get("emitted_monotonic_ns") or 0)
        rendered = int(row.get("render_completed_monotonic_ns") or 0)
        latency = float(row.get("latency_ms") or -1.0)
        if (
            emitted <= 0
            or rendered < emitted
            or not math.isfinite(latency)
            or latency < 0.0
            or not math.isclose(
                latency, (rendered - emitted) / 1_000_000.0, abs_tol=1e-12
            )
            or row.get("last_event_widget_verified") is not True
            or row.get("roster_widget_verified") is not True
        ):
            raise ValueError("UI latency sample timing/widget proof differs")
        sequences.append(int(row.get("event_sequence") or 0))
        latencies.append(latency)
    if sequences != sorted(set(sequences)) or any(value <= 0 for value in sequences):
        raise ValueError("UI latency event sequences are not strictly increasing")
    expected_metrics = summarize_latencies(latencies)
    metrics = receipt.get("metrics")
    if not isinstance(metrics, Mapping):
        raise ValueError("UI latency metrics are missing")
    for key, expected in expected_metrics.items():
        observed = metrics.get(key)
        if isinstance(expected, float):
            if observed is None or not math.isclose(
                float(observed), expected, rel_tol=0.0, abs_tol=1e-12
            ):
                raise ValueError(f"UI latency metric differs: {key}")
        elif observed != expected:
            raise ValueError(f"UI latency metric differs: {key}")
    return {**receipt, "receipt_sha256": signature}


def run_benchmark(
    *,
    workspace: Path = DEFAULT_WORKSPACE,
    output: Path = DEFAULT_OUTPUT,
    sample_count: int = 100,
    warmup_count: int = 10,
    timeout_sec: float = 5.0,
) -> dict[str, object]:
    """Validate the frozen identity, measure, sign, publish, and revalidate."""

    from app.h2_product_program.execution import runtime_implementation_identity

    workspace = Path(workspace).resolve()
    output = Path(output).resolve()
    if workspace.drive.casefold() != "c:" or output.drive.casefold() != "c:":
        raise UiLatencyBenchmarkError("workspace and output must remain on C:")
    runtime_path = workspace / "runtime_implementation_identity.json"
    if not runtime_path.is_file():
        raise UiLatencyBenchmarkError(f"frozen runtime identity is missing: {runtime_path}")
    frozen = json.loads(runtime_path.read_text(encoding="utf-8"))
    if not isinstance(frozen, dict):
        raise UiLatencyBenchmarkError("frozen runtime identity must be an object")
    current = runtime_implementation_identity()
    if current != frozen:
        raise UiLatencyBenchmarkError(
            "current result-affecting source differs from the frozen runtime identity"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ui_latency_", dir=output.parent) as name:
        samples, metadata = measure_ui_latency(
            working_root=Path(name),
            sample_count=sample_count,
            warmup_count=warmup_count,
            timeout_sec=timeout_sec,
        )
    receipt = build_receipt(
        samples=samples,
        benchmark_metadata=metadata,
        runtime_identity=frozen,
        runtime_identity_file_sha256=_sha256_file(runtime_path),
        warmup_count=warmup_count,
        timeout_sec=timeout_sec,
    )
    validate_receipt(
        receipt,
        expected_runtime_identity_sha256=str(frozen["identity_sha256"]),
    )
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("wb") as stream:
            stream.write(_canonical_bytes(receipt) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    published = json.loads(output.read_text(encoding="utf-8"))
    validate_receipt(
        published,
        expected_runtime_identity_sha256=str(frozen["identity_sha256"]),
    )
    return published


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--timeout-sec", type=float, default=5.0)
    parser.add_argument(
        "--validate",
        type=Path,
        help="validate an existing signed receipt instead of running Tk",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.validate is not None:
        value = json.loads(args.validate.resolve().read_text(encoding="utf-8"))
        validated = validate_receipt(value)
        print(
            json.dumps(
                {
                    "status": "VALID",
                    "path": str(args.validate.resolve()),
                    "receipt_sha256": validated["receipt_sha256"],
                    "metrics": validated["metrics"],
                },
                indent=2,
            )
        )
        return 0
    receipt = run_benchmark(
        workspace=args.workspace,
        output=args.output,
        sample_count=args.samples,
        warmup_count=args.warmup,
        timeout_sec=args.timeout_sec,
    )
    print(
        json.dumps(
            {
                "status": "VALID",
                "path": str(Path(args.output).resolve()),
                "receipt_sha256": receipt["receipt_sha256"],
                "metrics": receipt["metrics"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
