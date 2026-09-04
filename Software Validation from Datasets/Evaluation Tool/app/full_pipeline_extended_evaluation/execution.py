"""Real execution adapters for the bounded Prompt-6 controller.

No inference is implemented here. Scored cases delegate to the Prompt-3
worker, and stateful cases delegate to the common Prompt-1 runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Mapping

import numpy as np
import soundfile as sf

from app.augmentation.audio import (
    add_noise_at_snr,
    convolve_with_rir,
    load_rir,
    mono,
    peak_protect,
    read_audio,
    resample_audio,
)
from app.full_pipeline.factory import build_file_runtime
from app.full_pipeline.product_modes import H2RuntimeTuning
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    installed_tool_path_candidates,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_evaluation.scorers import score_resources
from app.full_pipeline_evaluation.store import EvaluationJobSpec
from app.full_pipeline_evaluation.worker import _model_bytes, execute_evaluation_job
from app.utils.paths import resolve_data_path_from_logical

from . import DEFAULT_SHARED_CACHE, RELIABILITY_FAULTS, TOOL_ROOT, scope_fields
from .io import ExtendedEvaluationError, ensure_c_drive, read_jsonl


Progress = Callable[..., None]
StopRequested = Callable[[], bool]


def materialize_hardening_inputs(
    plan: Mapping[str, object], *, workspace_root: Path
) -> dict[str, object]:
    """Build outcome-independent C:-only WAVs required by Prompt 7."""

    raw = plan.get("hardening_input_plan")
    if not isinstance(raw, Mapping):
        raise ExtendedEvaluationError("Prompt-6 plan lacks hardening inputs")
    long_raw = raw.get("long_input")
    long_streams_raw = raw.get("long_stream_inputs")
    samples_raw = raw.get("enrollment_samples")
    if (
        not isinstance(long_raw, Mapping)
        or not isinstance(long_streams_raw, list)
        or len(long_streams_raw) != 2
        or not isinstance(samples_raw, list)
    ):
        raise ExtendedEvaluationError("hardening input plan is incomplete")
    long_source = _resolve_audio(
        str(long_raw.get("source_logical_path") or ""),
        expected_sha256=long_raw.get("source_sha256"),
    )
    long_destination = ensure_c_drive(
        str(long_raw.get("destination_path") or ""), label="hardening long WAV"
    )
    _write_repeated_wav(
        long_source,
        long_destination,
        duration_sec=float(long_raw.get("target_duration_sec") or 0.0),
    )
    inputs = [
        {
            "input_id": str(long_raw["input_id"]),
            "path": str(long_destination),
            "sha256": sha256_file(long_destination),
            "duration_sec": _audio_duration(long_destination),
            "roles": list(long_raw.get("roles") or []),
            "capture_method": long_raw.get("capture_method"),
            "source_evidence": {
                "source_case_id": long_raw.get("source_case_id"),
                "source_path": str(long_source),
                "source_sha256": sha256_file(long_source),
            },
        }
    ]
    for raw_stream in long_streams_raw:
        if not isinstance(raw_stream, Mapping):
            raise ExtendedEvaluationError("long-stream input plan is invalid")
        source = _resolve_audio(
            str(raw_stream.get("source_logical_path") or ""),
            expected_sha256=raw_stream.get("source_sha256"),
        )
        destination = ensure_c_drive(
            str(raw_stream.get("destination_path") or ""),
            label="Prompt-6 long-stream WAV",
        )
        _write_repeated_wav(
            source,
            destination,
            duration_sec=float(raw_stream.get("target_duration_sec") or 0.0),
        )
        provenance = raw_stream.get("source_provenance")
        if not isinstance(provenance, Mapping):
            raise ExtendedEvaluationError("long-stream provenance is absent")
        inputs.append(
            {
                "input_id": str(raw_stream["input_id"]),
                "path": str(destination),
                "sha256": sha256_file(destination),
                "duration_sec": _audio_duration(destination),
                "roles": list(raw_stream.get("roles") or []),
                "capture_method": raw_stream.get("capture_method"),
                "source_evidence": {
                    **dict(provenance),
                    "source_path": str(source),
                    "resolved_source_sha256": sha256_file(source),
                },
            }
        )
    for raw_sample in samples_raw:
        if not isinstance(raw_sample, Mapping):
            raise ExtendedEvaluationError("hardening enrollment sample is invalid")
        source = _resolve_audio(
            str(raw_sample.get("source_logical_path") or ""),
            expected_sha256=raw_sample.get("source_sha256"),
        )
        destination = ensure_c_drive(
            str(raw_sample.get("destination_path") or ""),
            label="hardening enrollment WAV",
        )
        _transcode_wav(source, destination)
        inputs.append(
            {
                "input_id": str(raw_sample["input_id"]),
                "path": str(destination),
                "sha256": sha256_file(destination),
                "duration_sec": _audio_duration(destination),
                "roles": list(raw_sample.get("roles") or []),
                "capture_method": raw_sample.get("capture_method"),
                "source_evidence": {
                    "enrolled_id": raw_sample.get("enrolled_id"),
                    "source_path": str(source),
                    "source_sha256": sha256_file(source),
                    "declared_source_duration_sec": raw_sample.get(
                        "source_duration_sec"
                    ),
                },
            }
        )
    manifest = {
        "schema_version": "full-pipeline-hardening-input-manifest.v1",
        **scope_fields(),
        "outcome_independent": True,
        "inputs": inputs,
        "raw_dataset_audio_copied_into_report_package": False,
        "model_inference_used_to_select_inputs": False,
    }
    _validate_hardening_manifest(manifest)
    destination = ensure_c_drive(
        Path(workspace_root) / "hardening_input_manifest.json",
        label="hardening input manifest",
    )
    write_json_atomic(destination, manifest)
    return manifest


def execute_scored(
    record: Mapping[str, object],
    *,
    output_root: Path,
    progress: Progress,
    stop_requested: StopRequested,
    decision_policy_registry_path: Path | None,
) -> Mapping[str, object]:
    spec = EvaluationJobSpec.from_jsonable(record["spec"])  # type: ignore[arg-type]
    raw_cases = record.get("cases")
    if not isinstance(raw_cases, list):
        raise ExtendedEvaluationError(f"scored job {spec.job_id} has no cases")
    cases = [dict(row) for row in raw_cases if isinstance(row, Mapping)]
    if record.get("panel_id") == "noise_rir":
        cases = [_materialize_augmented_case(row) for row in cases]
    runtime_pace = float(record.get("runtime_pace") or 0.0)
    if runtime_pace > 0:
        # Passing a wrapper deliberately disables Prompt-3's cached ASR trace
        # path: these bounded cases exercise native Sherpa streaming state.
        def runtime_builder(**kwargs: object) -> object:
            kwargs["pace"] = runtime_pace
            kwargs["asr_stream_trace_enabled"] = False
            kwargs["asr_stream_trace_root"] = None
            return build_file_runtime(**kwargs)  # type: ignore[arg-type]

    else:
        runtime_builder = build_file_runtime
    return execute_evaluation_job(
        spec,
        cases,
        output_root,
        progress,
        stop_requested,
        runtime_builder=runtime_builder,
        decision_policy_registry_path=decision_policy_registry_path,
    )


def execute_custom(
    record: Mapping[str, object],
    *,
    output_root: Path,
    workspace_root: Path,
    progress: Progress,
    stop_requested: StopRequested,
    decision_policy_registry_path: Path | None,
) -> Mapping[str, object]:
    spec = EvaluationJobSpec.from_jsonable(record["spec"])  # type: ignore[arg-type]
    output_root.mkdir(parents=True, exist_ok=True)
    hardening = json.loads(
        (Path(workspace_root) / "hardening_input_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    _validate_hardening_manifest(hardening)
    long_input = next(
        Path(str(row["path"]))
        for row in hardening["inputs"]
        if "soak" in row.get("roles", [])
    )
    engine = str(record.get("engine") or "")
    progress(
        completed_cases=0,
        completed_audio_sec=0.0,
        current_case_id=spec.case_ids[0],
        latest_activity=f"starting {engine}",
    )
    started = time.monotonic()
    if engine == "reliability_runtime":
        result = _run_reliability(
            record,
            spec=spec,
            input_path=long_input,
            output_root=output_root / "runtime",
            stop_requested=stop_requested,
            decision_policy_registry_path=decision_policy_registry_path,
        )
    elif engine == "long_stream_runtime":
        stream_input_id = str(record.get("long_stream_input_id") or "")
        stream_entry = next(
            (
                row
                for row in hardening["inputs"]
                if isinstance(row, Mapping) and row.get("input_id") == stream_input_id
            ),
            None,
        )
        if not isinstance(stream_entry, Mapping):
            raise ExtendedEvaluationError(
                f"long-stream input is absent from hardening manifest: {stream_input_id}"
            )
        stream_input = Path(str(stream_entry["path"]))
        result = _run_common_runtime(
            spec,
            input_path=stream_input,
            output_root=output_root / "runtime",
            duration_sec=float(record.get("target_duration_sec") or 1800.0),
            pace=float(record.get("runtime_pace") or 0.0),
            enrollment_root=output_root / "enrollment_empty",
            decision_policy_registry_path=decision_policy_registry_path,
            source_case=record.get("source_case"),
            stop_requested=stop_requested,
        )
        result = {
            "schema_version": "full-pipeline-extended-long-session-result.v1",
            "panel_id": "long_session",
            "expected_duration_sec": float(record.get("target_duration_sec") or 1800.0),
            "runtime_pace": float(record.get("runtime_pace") or 0.0),
            "source_provenance": dict(record.get("source_provenance") or {}),
            "input_id": stream_input_id,
            "input_path": str(stream_input),
            "input_sha256": sha256_file(stream_input),
            "input_duration_sec": _audio_duration(stream_input),
            **_runtime_summary(result, output_root / "runtime"),
        }
    elif engine == "serial_resource_runtime":
        cache_bytes_before = _directory_bytes(DEFAULT_SHARED_CACHE)
        lifecycle: dict[str, float] = {}
        result = _run_common_runtime(
            spec,
            input_path=long_input,
            output_root=output_root / "runtime",
            duration_sec=360.0,
            pace=1.0,
            enrollment_root=output_root / "enrollment_empty",
            decision_policy_registry_path=decision_policy_registry_path,
            source_case=record.get("source_case"),
            stop_requested=stop_requested,
            lifecycle=lifecycle,
        )
        cache_bytes_after = _directory_bytes(DEFAULT_SHARED_CACHE)
        result = _resource_result(
            result,
            output_root / "runtime",
            wall_sec=time.monotonic() - started,
            warmup_sec=60.0,
            measured_sec=300.0,
            startup_sec=lifecycle.get("runtime_construction_sec"),
            model_bytes=_model_bytes(matrix().resolve(spec.pipeline_id)),
            cache_bytes_before=cache_bytes_before,
            cache_bytes_after=cache_bytes_after,
        )
    else:
        raise ExtendedEvaluationError(f"unknown custom execution engine: {engine}")
    elapsed = time.monotonic() - started
    terminal = str(result.get("harness_status") or result.get("completion_state") or "")
    state = "stopped" if stop_requested() else "complete"
    if terminal in {"FAIL", "UNEXPECTED_FAILURE", "failed"}:
        state = "failed"
    payload = {
        **scope_fields(),
        "job_id": spec.job_id,
        "pipeline_id": spec.pipeline_id,
        "engine": engine,
        "elapsed_wall_sec": elapsed,
        "state": state,
        "result": result,
    }
    write_json_atomic(output_root / "result.json", payload)
    checksums = checksum_map(output_root, exclude=("checksums.json",))
    write_json_atomic(
        output_root / "checksums.json",
        {
            "schema_version": "full-pipeline-extended-custom-checksums.v1",
            **scope_fields(),
            "entries": checksums,
        },
    )
    completed = 0 if state == "stopped" else 1
    progress(
        completed_cases=completed,
        completed_audio_sec=spec.audio_duration_sec if completed else 0.0,
        current_case_id=spec.case_ids[0],
        latest_activity=f"{state} {engine}",
        rolling_rtf=(
            elapsed / spec.audio_duration_sec if spec.audio_duration_sec else None
        ),
    )
    return {
        "state": state,
        "completed_cases": completed,
        "completed_audio_sec": spec.audio_duration_sec if completed else 0.0,
        "error": result.get("error") if state == "failed" else None,
    }


def _run_common_runtime(
    spec: EvaluationJobSpec,
    *,
    input_path: Path,
    output_root: Path,
    duration_sec: float,
    pace: float,
    enrollment_root: Path,
    decision_policy_registry_path: Path | None,
    source_case: object,
    stop_requested: StopRequested,
    lifecycle: dict[str, float] | None = None,
    runtime_tuning: H2RuntimeTuning | Mapping[str, object] | None = None,
    product_mode: str | None = None,
    runtime_builder: Callable[..., object] | None = None,
    status_observations: list[dict[str, object]] | None = None,
) -> Mapping[str, object]:
    case = dict(source_case) if isinstance(source_case, Mapping) else {}
    gallery_size = int(case.get("gallery_size") or 0)
    construction_started = time.monotonic()
    builder = runtime_builder or build_file_runtime
    runtime = builder(
        pipeline_id=spec.pipeline_id,
        input_path=input_path,
        output_root=output_root,
        enrollment_root=enrollment_root,
        session_id=f"{spec.job_id}_session",
        pace=pace,
        duration_sec=duration_sec,
        telemetry_enabled=True,
        cache_root=DEFAULT_SHARED_CACHE,
        decision_policy_registry_path=decision_policy_registry_path,
        gallery_requested_size=case.get("gallery_requested_size"),
        realized_gallery_size=gallery_size,
        product_mode=product_mode,
        runtime_tuning=runtime_tuning,
    )
    construction_sec = time.monotonic() - construction_started
    if lifecycle is not None:
        lifecycle["runtime_construction_sec"] = construction_sec
    run_started = time.monotonic()
    result = _run_with_stop(
        runtime,
        stop_requested=stop_requested,
        status_observations=status_observations,
    )
    if lifecycle is not None:
        lifecycle["runtime_run_sec"] = time.monotonic() - run_started
    return result


def _run_reliability(
    record: Mapping[str, object],
    *,
    spec: EvaluationJobSpec,
    input_path: Path,
    output_root: Path,
    stop_requested: StopRequested,
    decision_policy_registry_path: Path | None,
    runtime_tuning: H2RuntimeTuning | Mapping[str, object] | None = None,
    product_mode: str | None = None,
    runtime_builder: Callable[..., object] | None = None,
    status_observations: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    fault = str(record.get("fault_id") or "")
    if fault not in RELIABILITY_FAULTS:
        raise ExtendedEvaluationError(f"unknown reliability fault: {fault}")
    duration = float(record.get("target_duration_sec") or 30.0)
    enrollment_root = output_root / "enrollment"
    enrollment_root.mkdir(parents=True, exist_ok=True)
    input_for_run = input_path
    if fault == "silence":
        input_for_run = output_root / "fixtures/silence.wav"
        _write_silence(input_for_run, duration)
    elif fault == "sample_rate_mismatch":
        input_for_run = output_root / "fixtures/sample_rate_8000.wav"
        _write_rate_variant(input_path, input_for_run, rate=8000, duration_sec=duration)
    elif fault == "file_end":
        input_for_run = output_root / "fixtures/short_file_end.wav"
        _write_audio_excerpt(
            input_path,
            input_for_run,
            duration_sec=min(5.0, duration / 2.0),
        )
    corrupt_profile: Path | None = None
    if fault == "corrupted_enrollment_profile":
        from app.full_pipeline_evaluation.planning import matrix

        backend = str(matrix().resolve(spec.pipeline_id).identity["backend_id"])
        corrupt_profile = enrollment_root / "profiles/corrupted.json"
        corrupt_profile.parent.mkdir(parents=True, exist_ok=True)
        corrupt_profile.write_text(
            json.dumps(
                {
                    "schema_version": "corrupted-profile.v0",
                    "backend_id": backend,
                    "state": "active",
                }
            )
            + "\n",
            encoding="utf-8",
        )
    case = record.get("source_case")
    case_map = dict(case) if isinstance(case, Mapping) else {}
    gallery_size = int(case_map.get("gallery_size") or 0)
    builder = runtime_builder or build_file_runtime

    def construct(
        root: Path,
        session_suffix: str,
        *,
        pace: float = 0.0,
        run_duration_sec: float | None = None,
    ) -> object:
        return builder(
            pipeline_id=spec.pipeline_id,
            input_path=input_for_run,
            output_root=root,
            enrollment_root=enrollment_root,
            session_id=f"{spec.job_id}_{session_suffix}",
            pace=pace,
            duration_sec=run_duration_sec or duration,
            telemetry_enabled=True,
            cache_root=DEFAULT_SHARED_CACHE,
            decision_policy_registry_path=decision_policy_registry_path,
            gallery_requested_size=case_map.get("gallery_requested_size"),
            realized_gallery_size=gallery_size,
            product_mode=product_mode,
            runtime_tuning=runtime_tuning,
        )

    device_inventory: list[object] = []
    if fault == "microphone_device_selection":
        try:
            from app.full_pipeline_demo.devices import enumerate_input_devices

            device_inventory = [
                {
                    "index": item.index,
                    "name": item.name,
                    "sample_rate_hz": item.sample_rate_hz,
                    "maximum_input_channels": item.maximum_input_channels,
                    "host_api": item.host_api,
                }
                for item in enumerate_input_devices()
            ]
        except Exception as exc:
            device_inventory = [{"status": "unavailable", "reason": str(exc)}]
        return _reliability_result(
            fault,
            duration,
            status="UNSUPPORTED",
            reason=(
                "physical microphone selection is not reproducibly injectable "
                "from the controlled prerecorded loopback harness"
            ),
            device_inventory=device_inventory,
            injection={"demo_device_enumeration_attempted": True},
        )
    if fault == "device_reconnect":
        return _reliability_result(
            fault,
            duration,
            status="UNSUPPORTED",
            reason=(
                "no deterministic hardware disconnect/reconnect injection hook is "
                "available to the common runtime"
            ),
            injection={"fault_injected": False},
        )

    results: list[Mapping[str, object]] = []
    session_roots: list[Path] = []
    injected: dict[str, object] = {"fault_injected": True}
    assertions: list[dict[str, object]] = []
    harness_exception: BaseException | None = None
    try:
        if fault == "repeated_sessions":
            for index in range(2):
                root = output_root / f"session_{index + 1}"
                session_roots.append(root)
                runtime = construct(root, f"s{index + 1}")
                results.append(
                    _run_with_stop(
                        runtime,
                        stop_requested=stop_requested,
                        status_observations=status_observations,
                    )
                )
            injected["restart_boundary_exercised"] = True
        elif fault in {"sudden_stop", "worker_restart"}:
            root = output_root / "session"
            session_roots.append(root)
            runtime = construct(root, "injected", pace=1.0)
            holder: dict[str, Mapping[str, object]] = {}
            failures: list[BaseException] = []

            def run() -> None:
                try:
                    holder["result"] = runtime.run()  # type: ignore[attr-defined]
                except BaseException as exc:
                    failures.append(exc)

            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            _wait_running(runtime, timeout_sec=20.0)
            time.sleep(5.0)
            if fault == "sudden_stop":
                runtime.request_stop()  # type: ignore[attr-defined]
                injected["request_stop_called"] = True
            else:
                worker = getattr(getattr(runtime, "asr", None), "worker", None)
                if worker is None or not callable(getattr(worker, "restart", None)):
                    runtime.request_stop()  # type: ignore[attr-defined]
                    thread.join(timeout=10.0)
                    return _reliability_result(
                        fault,
                        duration,
                        status="UNSUPPORTED",
                        reason="ASR worker restart hook is unavailable",
                        injection={"fault_injected": False},
                    )
                injected["worker_restart_result"] = worker.restart()
                injected["worker_restart_count"] = getattr(
                    worker, "restart_count", None
                )
                health = getattr(worker, "health", None)
                injected["worker_health_after_restart"] = (
                    health() if callable(health) else None
                )
            thread.join(timeout=duration + 60.0)
            if thread.is_alive():
                runtime.request_stop()  # type: ignore[attr-defined]
                raise RuntimeError("fault-injection runtime did not terminate")
            if failures:
                raise failures[0]
            if "result" not in holder:
                raise RuntimeError("fault-injection runtime returned no result")
            results.append(holder["result"])
        else:
            root = output_root / "session"
            session_roots.append(root)
            run_pace = 1.0 if fault in {"continuous_session", "file_end"} else 0.0
            runtime = construct(
                root,
                "single",
                pace=run_pace,
            )
            run_started = time.monotonic()
            results.append(
                _run_with_stop(
                    runtime,
                    stop_requested=stop_requested,
                    status_observations=status_observations,
                )
            )
            injected["runtime_wall_sec"] = time.monotonic() - run_started
    except Exception as exc:
        harness_exception = exc
        results.append({"completion_state": "failed", "errors": [str(exc)]})
        injected["harness_exception"] = f"{type(exc).__name__}: {exc}"

    completions = [str(row.get("completion_state") or "failed") for row in results]
    events = [row for root in session_roots for row in _runtime_events(root)]
    safe_completion = all(value in {"complete", "degraded"} for value in completions)
    no_known_identity = not any(_event_has_known_identity(row) for row in events)

    if fault == "sudden_stop":
        assertions.extend(
            (
                _assertion(
                    "stop_request_forwarded",
                    injected.get("request_stop_called") is True,
                    expected=True,
                    observed=injected.get("request_stop_called"),
                ),
                _assertion(
                    "runtime_stopped",
                    completions == ["stopped"],
                    expected=["stopped"],
                    observed=completions,
                ),
            )
        )
    elif fault == "worker_restart":
        health = injected.get("worker_health_after_restart")
        assertions.extend(
            (
                _assertion(
                    "restart_count_incremented",
                    int(injected.get("worker_restart_count") or 0) >= 1,
                    expected=">=1",
                    observed=injected.get("worker_restart_count"),
                ),
                _assertion(
                    "replacement_worker_healthy",
                    isinstance(health, Mapping)
                    and str(health.get("status") or "").upper() == "HEALTHY",
                    expected="HEALTHY",
                    observed=health,
                ),
                _assertion(
                    "runtime_survived_restart",
                    safe_completion,
                    expected="complete_or_degraded",
                    observed=completions,
                ),
            )
        )
    elif fault == "sample_rate_mismatch":
        assertions.extend(
            (
                _assertion(
                    "mismatched_rate_materialized",
                    sf.info(input_for_run).samplerate == 8000,
                    expected=8000,
                    observed=sf.info(input_for_run).samplerate,
                ),
                _assertion(
                    "runtime_handled_resampling",
                    safe_completion,
                    expected="complete_or_degraded",
                    observed=completions,
                ),
            )
        )
    elif fault == "silence":
        silence, _ = read_audio(input_for_run)
        assertions.extend(
            (
                _assertion(
                    "zero_signal_fixture",
                    float(np.max(np.abs(silence))) == 0.0,
                    expected=0.0,
                    observed=float(np.max(np.abs(silence))),
                ),
                _assertion(
                    "no_false_known_identity",
                    no_known_identity,
                    expected=True,
                    observed=not no_known_identity,
                ),
                _assertion(
                    "runtime_completed",
                    safe_completion,
                    expected="complete_or_degraded",
                    observed=completions,
                ),
            )
        )
    elif fault == "continuous_session":
        observed_wall = float(injected.get("runtime_wall_sec") or 0.0)
        assertions.extend(
            (
                _assertion(
                    "true_realtime_pacing",
                    observed_wall >= duration * 0.9,
                    expected=f">={duration * 0.9:.3f}",
                    observed=observed_wall,
                ),
                _assertion(
                    "continuous_runtime_completed",
                    safe_completion,
                    expected="complete_or_degraded",
                    observed=completions,
                ),
            )
        )
    elif fault == "queue_pressure":
        queue = _runtime_queue_evidence(session_roots[0])
        if not queue:
            return _reliability_result(
                fault,
                duration,
                status="UNSUPPORTED",
                reason="runtime queue counters were not emitted",
                completions=completions,
                injection={**injected, "unpaced_producer_used": True},
            )
        maximum = int(queue.get("maximum_observed_depth") or 0)
        blocked = float(queue.get("blocked_total_sec") or 0.0)
        injected.update({"unpaced_producer_used": True, "queue_evidence": queue})
        assertions.extend(
            (
                _assertion(
                    "queue_pressure_observed",
                    maximum > 0 or blocked > 0.0,
                    expected="maximum_depth>0_or_blocked_time>0",
                    observed={"maximum_depth": maximum, "blocked_total_sec": blocked},
                ),
                _assertion(
                    "runtime_completed_under_pressure",
                    safe_completion,
                    expected="complete_or_degraded",
                    observed=completions,
                ),
            )
        )
    elif fault == "slow_ui":
        if not events:
            return _reliability_result(
                fault,
                duration,
                status="UNSUPPORTED",
                reason="runtime emitted no durable events for UI queue injection",
                completions=completions,
                injection=injected,
            )
        from app.full_pipeline_demo.session import CoalescingUpdateBuffer

        buffer = CoalescingUpdateBuffer(maximum_items=4)
        for index in range(100):
            buffer.push({"kind": "event", "event": events[index % len(events)]})
        drain = buffer.drain()
        injected["ui_buffer_evidence"] = drain
        assertions.append(
            _assertion(
                "bounded_ui_overflow_requires_resync",
                int(drain.get("dropped_ui_updates") or 0) > 0
                and drain.get("requires_event_resync") is True,
                expected=True,
                observed=drain,
            )
        )
    elif fault == "no_enrolled_speakers":
        assertions.extend(
            (
                _assertion(
                    "empty_enrollment_root",
                    not any(enrollment_root.rglob("*.json")),
                    expected=0,
                    observed=len(list(enrollment_root.rglob("*.json"))),
                ),
                _assertion(
                    "no_known_identity_released",
                    no_known_identity,
                    expected=True,
                    observed=not no_known_identity,
                ),
                _assertion(
                    "runtime_completed",
                    safe_completion,
                    expected="complete_or_degraded",
                    observed=completions,
                ),
            )
        )
    elif fault == "corrupted_enrollment_profile":
        error_text = _runtime_error_text(results, harness_exception)
        profile_specific_failure = bool(
            error_text
            and any(
                token in error_text.casefold()
                for token in (
                    "profile",
                    "schema",
                    "enrollment",
                    "backend",
                    "checkpoint",
                )
            )
        )
        safely_ignored = safe_completion and no_known_identity
        assertions.extend(
            (
                _assertion(
                    "corrupt_profile_was_injected",
                    corrupt_profile is not None and corrupt_profile.is_file(),
                    expected=True,
                    observed=str(corrupt_profile) if corrupt_profile else None,
                ),
                _assertion(
                    "profile_rejected_or_safely_ignored",
                    profile_specific_failure or safely_ignored,
                    expected="profile_specific_rejection_or_no_known_release",
                    observed={
                        "profile_specific_failure": profile_specific_failure,
                        "safely_ignored": safely_ignored,
                        "error": error_text,
                    },
                ),
            )
        )
    elif fault == "file_end":
        source_duration = _audio_duration(input_for_run)
        assertions.extend(
            (
                _assertion(
                    "source_shorter_than_runtime_limit",
                    source_duration < duration,
                    expected=f"<{duration}",
                    observed=source_duration,
                ),
                _assertion(
                    "clean_end_of_file_completion",
                    completions == ["complete"],
                    expected=["complete"],
                    observed=completions,
                ),
            )
        )
    elif fault == "repeated_sessions":
        assertions.extend(
            (
                _assertion(
                    "two_distinct_session_roots",
                    len({str(path.resolve()) for path in session_roots}) == 2,
                    expected=2,
                    observed=[str(path) for path in session_roots],
                ),
                _assertion(
                    "both_sessions_completed",
                    len(completions) == 2 and safe_completion,
                    expected="two_complete_or_degraded",
                    observed=completions,
                ),
            )
        )

    if harness_exception is not None and fault != "corrupted_enrollment_profile":
        assertions.append(
            _assertion(
                "harness_raised_no_exception",
                False,
                expected=None,
                observed=f"{type(harness_exception).__name__}: {harness_exception}",
            )
        )
    status = (
        "PASS"
        if assertions and all(row["status"] == "PASS" for row in assertions)
        else "FAIL"
    )
    return _reliability_result(
        fault,
        duration,
        status=status,
        reason=None
        if status == "PASS"
        else "one or more injected-fault assertions failed",
        completions=completions,
        device_inventory=device_inventory,
        injection=injected,
        assertions=assertions,
    )


def _reliability_result(
    fault: str,
    duration: float,
    *,
    status: str,
    reason: str | None,
    completions: list[str] | None = None,
    device_inventory: list[object] | None = None,
    injection: Mapping[str, object] | None = None,
    assertions: list[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if status not in {"PASS", "FAIL", "UNSUPPORTED"}:
        raise ExtendedEvaluationError(f"invalid reliability status: {status}")
    return {
        "schema_version": "full-pipeline-extended-reliability-result.v2",
        "panel_id": "reliability",
        "fault_id": fault,
        "declared_test_duration_sec": duration,
        "controlled_prerecorded_loopback": True,
        "physical_human_microphone_claimed": False,
        "observed_completion_states": completions or [],
        "device_inventory": device_inventory or [],
        "injection": dict(injection or {}),
        "assertions": [dict(item) for item in assertions or []],
        "harness_status": status,
        "fault_injected": bool(dict(injection or {}).get("fault_injected")),
        "unsupported_reason": reason if status == "UNSUPPORTED" else None,
        "error": reason if status == "FAIL" else None,
    }


def _assertion(
    assertion_id: str,
    passed: bool,
    *,
    expected: object,
    observed: object,
) -> dict[str, object]:
    return {
        "assertion_id": assertion_id,
        "status": "PASS" if passed else "FAIL",
        "expected": expected,
        "observed": observed,
    }


def _runtime_events(root: Path) -> list[dict[str, object]]:
    path = root / "events/events.jsonl"
    return read_jsonl(path) if path.is_file() else []


def _event_has_known_identity(row: Mapping[str, object]) -> bool:
    if str(row.get("event_type") or "") != "identity_label":
        return False
    state = str(row.get("identity_state") or "").casefold()
    label = row.get("speaker_label")
    enrolled = (
        label.get("enrolled_speaker_id")
        if isinstance(label, Mapping)
        else row.get("enrolled_speaker_id")
    )
    return state in {"tentative", "confirmed", "known"} and bool(enrolled)


def _runtime_queue_evidence(root: Path) -> dict[str, object]:
    path = root / "metrics/runtime_metrics.json"
    if not path.is_file():
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    queue = document.get("queue")
    return dict(queue) if isinstance(queue, Mapping) else {}


def _runtime_error_text(
    results: list[Mapping[str, object]], exception: BaseException | None
) -> str:
    values: list[str] = []
    if exception is not None:
        values.append(f"{type(exception).__name__}: {exception}")
    for result in results:
        raw = result.get("errors")
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
        elif raw:
            values.append(str(raw))
    return " | ".join(values)


def _runtime_summary(result: Mapping[str, object], root: Path) -> dict[str, object]:
    events_path = root / "events/events.jsonl"
    events = read_jsonl(events_path) if events_path.is_file() else []
    event_types = [str(row.get("event_type") or "") for row in events]
    return {
        "completion_state": result.get("completion_state"),
        "event_count": len(events),
        "identity_revision_events": sum(
            "identity" in item and "revision" in item for item in event_types
        ),
        "cluster_revision_events": sum(
            "cluster" in item and "revision" in item for item in event_types
        ),
        "reset_events": sum("reset" in item for item in event_types),
        "failure_events": sum(item in {"failure", "error"} for item in event_types),
        "warnings": result.get("warnings", []),
        "errors": result.get("errors", []),
    }


def _resource_result(
    result: Mapping[str, object],
    root: Path,
    *,
    wall_sec: float,
    warmup_sec: float,
    measured_sec: float,
    startup_sec: float | None,
    model_bytes: int | None,
    cache_bytes_before: int,
    cache_bytes_after: int,
) -> dict[str, object]:
    samples_path = root / "telemetry/resource_samples.jsonl"
    samples = read_jsonl(samples_path) if samples_path.is_file() else []
    measured_samples = [
        row for row in samples if (_number(row.get("elapsed_sec")) or 0.0) >= warmup_sec
    ]
    runtime_metrics_path = root / "metrics/runtime_metrics.json"
    runtime_metrics = (
        json.loads(runtime_metrics_path.read_text(encoding="utf-8"))
        if runtime_metrics_path.is_file()
        else {}
    )
    queue = runtime_metrics.get("queue")
    queue_values = dict(queue) if isinstance(queue, Mapping) else {}
    counts = runtime_metrics.get("counts")
    count_values = dict(counts) if isinstance(counts, Mapping) else {}
    deadline_keys = [key for key in count_values if "deadline" in str(key).casefold()]
    measured_wall_sec = max(0.0, wall_sec - float(startup_sec or 0.0) - warmup_sec)
    report = score_resources(
        measured_samples,
        audio_duration_sec=measured_sec,
        wall_time_sec=measured_wall_sec,
        startup_sec=startup_sec,
        model_bytes=model_bytes,
        cache_bytes=cache_bytes_after,
        maximum_queue_depth=_optional_int(queue_values.get("maximum_observed_depth")),
        failure_count=0 if result.get("completion_state") == "complete" else 1,
        retry_count=0,
    ).to_jsonable()
    raw_metrics = report.get("metrics")
    metrics = dict(raw_metrics) if isinstance(raw_metrics, Mapping) else {}
    scalar: dict[str, object] = {}
    for metric_id, raw in metrics.items():
        if not isinstance(raw, Mapping):
            continue
        scalar[str(metric_id)] = raw.get("value")
        scalar[f"{metric_id}__status"] = raw.get("status")
        scalar[f"{metric_id}__reason"] = raw.get("reason")
    component_evidence = _measured_component_rtfs(measured_samples)
    scalar["component_rtf"] = component_evidence["value"]
    scalar["component_rtf__status"] = component_evidence["status"]
    scalar["component_rtf__reason"] = component_evidence["reason"]
    scalar["component_rtfs"] = component_evidence["component_rtfs"]
    temperature = [
        value
        for row in measured_samples
        if (value := _number(row.get("gpu_temperature_c"))) is not None
    ]
    temperature_drift = (
        temperature[-1] - temperature[0] if len(temperature) >= 2 else None
    )
    return {
        "schema_version": "full-pipeline-extended-serial-resource-result.v1",
        "panel_id": "serial_resources",
        "completion_state": result.get("completion_state"),
        "cold_start_included": True,
        "startup_measurement_definition": "build_file_runtime_wall_duration",
        "warmup_duration_sec": warmup_sec,
        "measured_duration_sec": measured_sec,
        "total_audio_duration_sec": warmup_sec + measured_sec,
        "wall_duration_sec": wall_sec,
        "measured_wall_duration_sec": measured_wall_sec,
        "total_rtf_including_startup_and_warmup": wall_sec
        / (warmup_sec + measured_sec),
        **scalar,
        "telemetry_sample_count": len(samples),
        "measured_telemetry_sample_count": len(measured_samples),
        "cache_bytes_before": cache_bytes_before,
        "cache_bytes_after": cache_bytes_after,
        "cache_growth_bytes": max(0, cache_bytes_after - cache_bytes_before),
        "dropped_frames": queue_values.get("dropped_frames"),
        "deadline_miss_count": (
            sum(int(count_values[key]) for key in deadline_keys)
            if deadline_keys
            else None
        ),
        "deadline_miss_status": (
            "computed" if deadline_keys else "unsupported_no_deadline_counter"
        ),
        "runtime_drift_status": (
            "computed_gpu_temperature_proxy"
            if temperature_drift is not None
            else "unsupported_no_temperature_series"
        ),
        "gpu_temperature_drift_c": temperature_drift,
        "energy_proxy_status": "unsupported_no_current_instrumentation",
        "beaker_power_claimed": False,
        "parallel_campaign_resource_numbers_used": False,
        "component_rtf_measurement_status": component_evidence["measurement_status"],
        "component_rtf_processing_audio_pair_count": component_evidence["pair_count"],
    }


def _measured_component_rtfs(
    samples: list[dict[str, object]],
) -> dict[str, object]:
    totals: dict[str, list[float]] = {}
    pair_count = 0
    for row in samples:
        component = str(row.get("component") or row.get("active_component") or "")
        processing = _number(row.get("processing_sec"))
        audio = _number(row.get("audio_duration_sec"))
        if (
            not component
            or processing is None
            or audio is None
            or processing < 0
            or audio <= 0
        ):
            continue
        pair_count += 1
        current = totals.setdefault(component, [0.0, 0.0])
        current[0] += processing
        current[1] += audio
    rtfs = {
        component: processing / audio
        for component, (processing, audio) in sorted(totals.items())
        if audio > 0
    }
    if not rtfs:
        return {
            "value": None,
            "status": "unsupported",
            "reason": "measured component processing/audio duration pairs absent",
            "component_rtfs": None,
            "measurement_status": "UNSUPPORTED_NO_MEASURED_PROCESSING_AUDIO_PAIRS",
            "pair_count": 0,
        }
    return {
        "value": max(rtfs.values()),
        "status": "computed",
        "reason": None,
        "component_rtfs": rtfs,
        "measurement_status": "COMPUTED_FROM_MEASURED_PROCESSING_AUDIO_PAIRS",
        "pair_count": pair_count,
    }


def _directory_bytes(root: Path) -> int:
    path = Path(root)
    if not path.is_dir():
        return 0
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            try:
                total += item.stat().st_size
            except FileNotFoundError:
                # Another checksum-bound cache producer can atomically publish
                # between enumeration and stat; the next serial sample sees it.
                continue
    return total


def _materialize_augmented_case(case: Mapping[str, object]) -> dict[str, object]:
    destination = ensure_c_drive(
        str(case.get("audio_path") or ""), label="augmented Prompt-6 WAV"
    )
    sidecar = destination.with_suffix(".materialization.json")
    recipe = {
        "source_audio_logical_path": case.get("source_audio_logical_path"),
        "source_audio_sha256": case.get("source_audio_sha256"),
        "augmentation_condition": case.get("augmentation_condition"),
        "augmentation_seed": case.get("augmentation_seed"),
    }
    recipe_sha = sha256_bytes(canonical_json_bytes(recipe))
    if destination.is_file() and sidecar.is_file():
        prior = json.loads(sidecar.read_text(encoding="utf-8"))
        if prior.get("recipe_sha256") == recipe_sha and prior.get(
            "output_sha256"
        ) == sha256_file(destination):
            return dict(case)
        raise ExtendedEvaluationError(f"augmented material differs: {destination}")
    source = _resolve_audio(
        str(case.get("source_audio_logical_path") or ""),
        expected_sha256=case.get("source_audio_sha256"),
    )
    audio, rate = read_audio(source)
    condition = case.get("augmentation_condition")
    if not isinstance(condition, Mapping):
        raise ExtendedEvaluationError("augmentation condition is absent")
    augmented = audio
    rir = condition.get("rir")
    if isinstance(rir, Mapping):
        rir_path = _resolve_audio(
            str(rir.get("relative_path") or ""), expected_sha256=rir.get("sha256")
        )
        augmented = convolve_with_rir(augmented, load_rir(rir_path, rate))
        augmented = augmented[: len(audio)]
    if condition.get("noise_type") and condition.get("snr_db") is not None:
        augmented = add_noise_at_snr(
            augmented,
            str(condition["noise_type"]),
            float(condition["snr_db"]),
            f"3800:{case.get('protocol_case_id')}:{condition.get('id')}",
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.wav")
    sf.write(temporary, peak_protect(augmented), rate, subtype="PCM_16")
    os.replace(temporary, destination)
    write_json_atomic(
        sidecar,
        {
            "schema_version": "full-pipeline-extended-augmentation-materialization.v1",
            **scope_fields(),
            "recipe": recipe,
            "recipe_sha256": recipe_sha,
            "source_path": str(source),
            "output_path": str(destination),
            "output_sha256": sha256_file(destination),
        },
    )
    return dict(case)


def _validate_hardening_manifest(value: Mapping[str, object]) -> None:
    if value.get("schema_version") != "full-pipeline-hardening-input-manifest.v1":
        raise ExtendedEvaluationError("hardening input manifest schema differs")
    for key, expected in scope_fields().items():
        if value.get(key) != expected:
            raise ExtendedEvaluationError(f"hardening input {key} differs")
    if value.get("outcome_independent") is not True:
        raise ExtendedEvaluationError("hardening inputs are outcome-dependent")
    inputs = value.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ExtendedEvaluationError("hardening input manifest is empty")
    roles: dict[str, list[float]] = {}
    enrollment_ids: set[str] = set()
    long_stream_provenance: set[str] = set()
    for raw in inputs:
        if not isinstance(raw, Mapping):
            raise ExtendedEvaluationError("hardening input entry is invalid")
        path = ensure_c_drive(
            str(raw.get("path") or ""), label="hardening WAV", must_exist=True
        )
        if path.suffix.casefold() != ".wav" or not path.is_file():
            raise ExtendedEvaluationError("hardening input must be an existing WAV")
        if raw.get("sha256") != sha256_file(path):
            raise ExtendedEvaluationError("hardening input SHA-256 differs")
        duration = float(raw.get("duration_sec") or 0.0)
        if duration <= 0:
            raise ExtendedEvaluationError("hardening input duration is not positive")
        actual_duration = _audio_duration(path)
        if abs(actual_duration - duration) > 0.05:
            raise ExtendedEvaluationError(
                "hardening input declared duration differs from WAV duration"
            )
        for role in raw.get("roles", []):
            roles.setdefault(str(role), []).append(actual_duration)
        if "enrollment_sample" in raw.get("roles", []):
            enrollment_ids.add(str(raw.get("input_id")))
        if "prompt6_long_stream" in raw.get("roles", []):
            source_evidence = raw.get("source_evidence")
            identity = (
                str(source_evidence.get("provenance_identity_sha256") or "")
                if isinstance(source_evidence, Mapping)
                else ""
            )
            if len(identity) != 64 or actual_duration + 1e-6 < 1800.0:
                raise ExtendedEvaluationError(
                    "Prompt-6 long-stream input lacks 30-minute provenance"
                )
            long_stream_provenance.add(identity)
    required = {
        "deterministic_replay": 300.0,
        "controlled_loopback": 600.0,
        "repeated_session": 120.0,
        "soak": 3600.0,
    }
    for role, minimum in required.items():
        if max(roles.get(role, [0.0])) + 1e-6 < minimum:
            raise ExtendedEvaluationError(f"hardening role {role} is below {minimum}s")
    if len(enrollment_ids) < 3:
        raise ExtendedEvaluationError("hardening inputs need three enrollment samples")
    if (
        len(roles.get("prompt6_long_stream", [])) != 2
        or len(long_stream_provenance) != 2
    ):
        raise ExtendedEvaluationError(
            "hardening inputs need two provenance-distinct Prompt-6 long streams"
        )


def _resolve_audio(raw: str, *, expected_sha256: object | None = None) -> Path:
    value = Path(raw)
    candidates = (
        *installed_tool_path_candidates(value, evaluation_root=TOOL_ROOT),
        value,
        TOOL_ROOT.parents[1] / value,
        resolve_data_path_from_logical(value),
    )
    for candidate in candidates:
        path = candidate.resolve()
        if not path.is_file():
            continue
        if (
            expected_sha256 is not None
            and sha256_file(path) != str(expected_sha256).casefold()
        ):
            raise ExtendedEvaluationError(f"source audio hash differs: {path}")
        return ensure_c_drive(path, label="source audio", must_exist=True)
    raise FileNotFoundError(raw)


def _transcode_wav(source: Path, destination: Path) -> None:
    if destination.is_file():
        if _audio_duration(destination) <= 0:
            raise ExtendedEvaluationError(f"invalid existing WAV: {destination}")
        return
    audio, rate = read_audio(source)
    normalized = resample_audio(mono(audio)[:, None], rate, 16000)[:, 0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.wav")
    sf.write(temporary, normalized, 16000, subtype="PCM_16")
    os.replace(temporary, destination)


def _write_repeated_wav(
    source: Path, destination: Path, *, duration_sec: float
) -> None:
    if duration_sec <= 0.0:
        raise ExtendedEvaluationError("repeated WAV duration must be positive")
    if destination.is_file():
        if _audio_duration(destination) + 1e-6 < duration_sec:
            raise ExtendedEvaluationError("existing repeated WAV is too short")
        return
    audio, rate = read_audio(source)
    normalized = resample_audio(mono(audio)[:, None], rate, 16000)[:, 0]
    if not len(normalized):
        raise ExtendedEvaluationError("hardening source audio is empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp.wav")
    target_frames = round(duration_sec * 16000)
    with sf.SoundFile(
        temporary,
        mode="w",
        samplerate=16000,
        channels=1,
        subtype="PCM_16",
        format="WAV",
    ) as stream:
        remaining = target_frames
        while remaining:
            chunk = normalized[: min(remaining, len(normalized))]
            stream.write(chunk)
            remaining -= len(chunk)
    os.replace(temporary, destination)


def _write_silence(path: Path, duration_sec: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(
        path,
        np.zeros(round(duration_sec * 16000), dtype=np.float32),
        16000,
        subtype="PCM_16",
    )


def _write_rate_variant(
    source: Path, destination: Path, *, rate: int, duration_sec: float
) -> None:
    audio, source_rate = read_audio(source)
    mono_audio = mono(audio)[: round(duration_sec * source_rate)]
    variant = resample_audio(mono_audio[:, None], source_rate, rate)[:, 0]
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination, variant, rate, subtype="PCM_16")


def _write_audio_excerpt(
    source: Path,
    destination: Path,
    *,
    duration_sec: float,
) -> None:
    if duration_sec <= 0.0:
        raise ExtendedEvaluationError("audio excerpt duration must be positive")
    audio, source_rate = read_audio(source)
    normalized = resample_audio(mono(audio)[:, None], source_rate, 16000)[:, 0]
    target_frames = min(len(normalized), round(duration_sec * 16000))
    if target_frames <= 0:
        raise ExtendedEvaluationError("audio excerpt source is empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    sf.write(destination, normalized[:target_frames], 16000, subtype="PCM_16")


def _audio_duration(path: Path) -> float:
    info = sf.info(path)
    return float(info.frames / info.samplerate)


def _wait_running(runtime: object, *, timeout_sec: float) -> None:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        state = str(runtime.status().get("state"))  # type: ignore[attr-defined]
        if state == "running":
            return
        if state in {"failed", "complete", "completed", "stopped"}:
            raise RuntimeError(f"runtime reached {state} before fault injection")
        time.sleep(0.1)
    raise TimeoutError("runtime did not reach running state")


def _run_with_stop(
    runtime: object,
    *,
    stop_requested: StopRequested,
    status_observations: list[dict[str, object]] | None = None,
) -> Mapping[str, object]:
    """Run a common runtime while honoring the durable controller stop flag."""

    holder: dict[str, Mapping[str, object]] = {}
    failure: list[BaseException] = []

    def run() -> None:
        try:
            value = runtime.run()  # type: ignore[attr-defined]
            if not isinstance(value, Mapping):
                raise RuntimeError("common runtime returned a non-mapping result")
            holder["result"] = value
        except BaseException as exc:  # transported back to the scheduler thread
            failure.append(exc)

    thread = threading.Thread(target=run, daemon=True, name="prompt6-common-runtime")
    thread.start()
    stop_forwarded = False
    observation_started = time.monotonic()
    while thread.is_alive():
        _observe_runtime_status(
            runtime,
            status_observations,
            elapsed_wall_sec=time.monotonic() - observation_started,
        )
        if stop_requested() and not stop_forwarded:
            runtime.request_stop()  # type: ignore[attr-defined]
            stop_forwarded = True
        thread.join(timeout=0.5)
    _observe_runtime_status(
        runtime,
        status_observations,
        elapsed_wall_sec=time.monotonic() - observation_started,
    )
    if failure:
        raise failure[0]
    if "result" not in holder:
        raise RuntimeError("common runtime terminated without a result")
    return holder["result"]


def _observe_runtime_status(
    runtime: object,
    observations: list[dict[str, object]] | None,
    *,
    elapsed_wall_sec: float,
) -> None:
    """Capture bounded-state cardinalities without changing runtime decisions."""

    if observations is None:
        return
    status = runtime.status()  # type: ignore[attr-defined]
    if not isinstance(status, Mapping):
        raise RuntimeError("common runtime status returned a non-mapping")
    bounded = status.get("bounded_session_state")
    memory = status.get("session_memory")
    observations.append(
        {
            "session_id": status.get("session_id"),
            "elapsed_wall_sec": elapsed_wall_sec,
            "source_time_sec": status.get("source_time_sec"),
            "state": status.get("state"),
            "queue_depth": status.get("queue_depth"),
            "dropped_frame_count": status.get("dropped_frame_count"),
            "bounded_session_state": (
                dict(bounded) if isinstance(bounded, Mapping) else None
            ),
            "session_memory": (
                {
                    "roster_count": len(memory.get("roster") or []),
                    "history_count": len(memory.get("history") or []),
                    "roster_bound": memory.get("roster_bound"),
                    "history_bound": memory.get("history_bound"),
                }
                if isinstance(memory, Mapping)
                else None
            ),
            "runtime_tuning_sha256": status.get("runtime_tuning_sha256"),
            "h2_product_mode": status.get("h2_product_mode"),
        }
    )


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# Public reuse points for later controllers.  They deliberately remain the
# same implementation used by Prompt 6, so reliability campaigns cannot grow
# a second inference path.
run_controlled_file_session = _run_common_runtime
run_reliability_fault = _run_reliability


__all__ = [
    "execute_custom",
    "execute_scored",
    "materialize_hardening_inputs",
    "run_controlled_file_session",
    "run_reliability_fault",
]
