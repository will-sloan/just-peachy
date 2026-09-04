"""Small model-free recovery checks used by Prompt-7 hardening."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from app.full_pipeline.workers import (
    PersistentWorker,
    WorkerExitedError,
    WorkerSpec,
)
from app.full_pipeline_demo.session import CoalescingUpdateBuffer


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=(
            "worker-recovery",
            "slow-consumer",
            "controlled-virtual-loopback",
        ),
    )
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--duration-sec", type=float)
    parser.add_argument("--session-id")
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--runtime-root", type=Path)
    parser.add_argument("--export-root", type=Path)
    parser.add_argument("--enrollment-root", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.action == "worker-recovery":
        value = _worker_recovery(args.pipeline_id)
    elif args.action == "slow-consumer":
        value = _slow_consumer(args.pipeline_id)
    else:
        required = {
            "input": args.input,
            "duration_sec": args.duration_sec,
            "session_id": args.session_id,
            "results_root": args.results_root,
            "runtime_root": args.runtime_root,
            "export_root": args.export_root,
            "enrollment_root": args.enrollment_root,
        }
        missing = [key for key, item in required.items() if item is None]
        if missing:
            parser.error("controlled-virtual-loopback requires: " + ", ".join(missing))
        value = _controlled_virtual_loopback(
            pipeline_id=args.pipeline_id,
            input_path=args.input,
            duration_sec=float(args.duration_sec),
            session_id=str(args.session_id),
            results_root=args.results_root,
            runtime_root=args.runtime_root,
            export_root=args.export_root,
            enrollment_root=args.enrollment_root,
        )
    output.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value["status"] == "PASS" else 1


def _worker_recovery(pipeline_id: str) -> dict[str, object]:
    spec = WorkerSpec(
        worker_id=f"prompt7-recovery-{pipeline_id}",
        kind="test",
        component_id="protocol_test",
        environment_profile="current",
        startup_timeout_sec=10.0,
        request_timeout_sec=5.0,
        shutdown_timeout_sec=2.0,
        restart_limit=1,
        command_override=(
            sys.executable,
            "-u",
            "-m",
            "app.full_pipeline.worker_main",
            "--worker-id",
            f"prompt7-recovery-{pipeline_id}",
            "--kind",
            "test",
            "--component",
            "protocol_test",
        ),
    )
    worker = PersistentWorker(spec)
    exited = False
    try:
        first = worker.start()
        try:
            worker.call("crash", retry_on_worker_failure=False)
        except WorkerExitedError:
            exited = True
        replacement = worker.restart()
        health = worker.health()
        passed = (
            exited
            and first.get("component_id") == "protocol_test"
            and replacement.get("component_id") == "protocol_test"
            and health.get("status") == "HEALTHY"
            and worker.restart_count >= 1
        )
        return {
            "schema_version": "full-pipeline-production-worker-recovery.v1",
            "status": "PASS" if passed else "FAIL",
            "pipeline_id": pipeline_id,
            "initial_worker_exit_observed": exited,
            "restart_count": worker.restart_count,
            "replacement_health": health,
            "model_inference_run": False,
            "shared_worker_recovery_mechanism": True,
        }
    finally:
        worker.shutdown()


def _slow_consumer(pipeline_id: str) -> dict[str, object]:
    buffer = CoalescingUpdateBuffer(maximum_items=4)
    buffer.push({"kind": "status", "status": {"state": "running"}})
    for sequence in range(1, 101):
        buffer.push(
            {
                "kind": "event",
                "event": {
                    "event_sequence": sequence,
                    "contract_type": "AnonymousSpeakerEvent",
                },
            }
        )
    result = buffer.drain()
    passed = (
        int(result.get("dropped_ui_updates") or 0) > 0
        and result.get("requires_event_resync") is True
        and len(result.get("updates") or []) <= 4
    )
    return {
        "schema_version": "full-pipeline-production-slow-consumer.v1",
        "status": "PASS" if passed else "FAIL",
        "pipeline_id": pipeline_id,
        "bounded_queue": True,
        "durable_event_resync_requested": result.get("requires_event_resync"),
        "dropped_ui_updates": result.get("dropped_ui_updates"),
        "retained_update_count": len(result.get("updates") or []),
        "model_inference_run": False,
    }


def _controlled_virtual_loopback(
    *,
    pipeline_id: str,
    input_path: Path,
    duration_sec: float,
    session_id: str,
    results_root: Path,
    runtime_root: Path,
    export_root: Path,
    enrollment_root: Path,
) -> dict[str, object]:
    """Exercise the common live-session API with a deterministic WAV source.

    This is intentionally called a *virtual* loopback. It proves live-session
    lifecycle, queue/UI/export integration reproducibly, but makes no claim
    about an operating-system loopback device or a physical microphone.
    """

    source = input_path.resolve(strict=True)
    if duration_sec <= 0:
        raise ValueError("duration_sec must be positive")
    from app.full_pipeline.audio import DurationLimitedAudioSource, FileAudioSource
    from app.full_pipeline.factory import _build
    from app.full_pipeline_demo.session import DemoSessionManager, TERMINAL_STATES
    from app.full_pipeline_evaluation.io import sha256_file

    def virtual_microphone_builder(**kwargs: object) -> object:
        virtual_source = DurationLimitedAudioSource(
            FileAudioSource(source, frame_duration_ms=100, pace=1.0),
            float(kwargs["duration_sec"]),
        )
        return _build(
            pipeline_id=str(kwargs["pipeline_id"]),
            source=virtual_source,
            recording_id="prompt7_controlled_virtual_loopback",
            output_root=Path(str(kwargs["output_root"])),
            enrollment_root=Path(str(kwargs["enrollment_root"])),
            session_id=str(kwargs["session_id"]),
            queue_policy="drop_oldest",
            telemetry_enabled=bool(kwargs.get("telemetry_enabled", True)),
            cache_root=None,
            worker_pool=None,
            lazy_worker_start=False,
            worker_warmup_audio_path=None,
            asr_stream_trace_root=None,
            asr_stream_trace_enabled=False,
            evaluation_measurement_mode=None,
            asr_trace_source_path=None,
            asr_trace_duration_sec=float(kwargs["duration_sec"]),
            decision_policy_registry_path=None,
            gallery_requested_size=None,
            realized_gallery_size=None,
        )

    manager = DemoSessionManager(
        results_root=results_root,
        enrollment_root=enrollment_root,
        microphone_builder=virtual_microphone_builder,
    )
    status: dict[str, object]
    export: dict[str, object] | None = None
    try:
        status = manager.start_microphone(
            pipeline_id=pipeline_id,
            duration_sec=duration_sec,
            device="prompt7-controlled-virtual-loopback",
            source_sample_rate_hz=16000,
            source_channels=1,
            telemetry_enabled=True,
            record_input_audio=False,
            session_id=session_id,
            output_root=runtime_root,
        )
        while str(status.get("state")) not in TERMINAL_STATES:
            status = manager.join(session_id, timeout=0.5)
            time.sleep(0.05)
        status = manager.join(session_id, timeout=30)
        if str(status.get("state")) == "completed":
            export = manager.export(
                export_root,
                session_id=session_id,
                include_input_audio=False,
            )
    finally:
        manager.shutdown(timeout_per_session=30)
    final_status = manager.status(session_id)
    passed = (
        str(final_status.get("state")) == "completed"
        and final_status.get("source_kind") == "microphone"
        and final_status.get("thread_alive") is False
        and isinstance(export, dict)
    )
    return {
        "schema_version": "full-pipeline-controlled-virtual-loopback.v1",
        "status": "PASS" if passed else "FAIL",
        "pipeline_id": pipeline_id,
        "source_mode": "controlled_virtual_loopback",
        "source_wav_path": str(source),
        "source_wav_sha256": sha256_file(source),
        "requested_duration_sec": duration_sec,
        "common_live_api_exercised": "DemoSessionManager.start_microphone",
        "runtime_transport": "deterministic_wav_virtual_microphone_source",
        "live_queue_policy": "drop_oldest",
        "physical_microphone_claimed": False,
        "os_loopback_device_claimed": False,
        "file_simulation_claimed": False,
        "session_status": final_status,
        "session_export": export,
        "graceful_shutdown_observed": final_status.get("thread_alive") is False,
        "implicit_downloads_allowed": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
