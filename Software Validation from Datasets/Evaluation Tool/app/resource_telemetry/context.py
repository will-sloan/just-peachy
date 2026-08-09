"""Opt-in component spans with no-op behavior outside telemetry sessions."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Callable, Iterator, Mapping
import uuid

from app.resource_telemetry.contracts import COMPONENT_SPANS_SCHEMA_VERSION
from app.resource_telemetry.cuda_timing import CudaTimer, TorchCudaTimer


SPAN_PATH_ENV = "EVALUATION_TELEMETRY_SPAN_PATH"
ACTIVE_PATH_ENV = "EVALUATION_TELEMETRY_ACTIVE_PATH"
CONTEXT_ENV = "EVALUATION_TELEMETRY_CONTEXT"
CUDA_TIMING_ENV = "EVALUATION_TELEMETRY_CUDA_TIMING"
REGISTRY_ENV = "EVALUATION_ARTIFACT_REGISTRY_VERSION"

_ACTIVE_RECORDER: ContextVar["SpanRecorder | None"] = ContextVar(
    "evaluation_active_telemetry_recorder", default=None
)
_SPAN_STACK: ContextVar[tuple[tuple[str, str], ...]] = ContextVar(
    "evaluation_telemetry_span_stack", default=()
)


class SpanRecorder:
    """Append completed component spans and expose the currently active span."""

    def __init__(
        self,
        span_path: Path,
        active_state_path: Path,
        context: Mapping[str, object],
        *,
        cuda_timing: bool = False,
        wall_clock: Callable[[], datetime] | None = None,
        monotonic_ns: Callable[[], int] | None = None,
        cuda_timer_factory: Callable[[], CudaTimer] | None = None,
    ) -> None:
        self.span_path = span_path.resolve()
        self.active_state_path = active_state_path.resolve()
        self.context = {
            "campaign_id": str(context.get("campaign_id") or ""),
            "scenario_id": str(context.get("scenario_id") or ""),
            "attempt": int(context.get("attempt") or 0),
            "worker_id": str(context.get("worker_id") or ""),
            "host": str(context.get("host") or ""),
        }
        self.cuda_timing = bool(cuda_timing)
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.monotonic_ns = monotonic_ns or time.perf_counter_ns
        self.cuda_timer_factory = cuda_timer_factory or TorchCudaTimer
        self._write_lock = threading.Lock()
        self._warnings: list[str] = []
        self.span_path.parent.mkdir(parents=True, exist_ok=True)
        self.active_state_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def span(
        self,
        name: str,
        *,
        phase: str = "component",
        identifiers: Mapping[str, object] | None = None,
        cuda: bool = False,
    ) -> Iterator[None]:
        span_id = uuid.uuid4().hex[:16]
        stack = _SPAN_STACK.get()
        parent_span_id = stack[-1][0] if stack else None
        token = _SPAN_STACK.set((*stack, (span_id, str(name))))
        started_wall = _utc_text(self.wall_clock())
        started_ns = int(self.monotonic_ns())
        cuda_timer: CudaTimer | None = None
        cuda_reason: str | None = "CUDA timing not requested for this span"
        if cuda and self.cuda_timing:
            try:
                cuda_timer = self.cuda_timer_factory()
                cuda_reason = cuda_timer.reason
                cuda_timer.start()
            except Exception as exc:  # measurement must never break inference
                cuda_timer = None
                cuda_reason = f"CUDA timing failed: {type(exc).__name__}"
        elif cuda:
            cuda_reason = "CUDA timing disabled for this telemetry session"
        try:
            self._write_active(name, (*stack, (span_id, str(name))))
        except Exception as exc:  # measurement must never block pipeline work
            self._warnings.append(f"active-state write failed: {type(exc).__name__}")
        status = "ok"
        error_type: str | None = None
        try:
            yield
        except BaseException as exc:
            status = "error"
            error_type = type(exc).__name__
            raise
        finally:
            try:
                cuda_elapsed_ms = cuda_timer.stop() if cuda_timer is not None else None
            except Exception as exc:  # measurement must never mask pipeline output
                cuda_elapsed_ms = None
                cuda_reason = f"CUDA timing finalization failed: {type(exc).__name__}"
            ended_ns = int(self.monotonic_ns())
            row: dict[str, object] = {
                "schema_version": COMPONENT_SPANS_SCHEMA_VERSION,
                **self.context,
                "pid": os.getpid(),
                "thread_id": threading.get_ident(),
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "name": str(name),
                "phase": str(phase),
                "start_timestamp_utc": started_wall,
                "start_monotonic_ns": started_ns,
                "end_monotonic_ns": ended_ns,
                "duration_ns": max(0, ended_ns - started_ns),
                "status": status,
                "error_type": error_type,
                "cuda_timing_requested": bool(cuda),
                "cuda_timing_available": bool(cuda_timer and cuda_timer.available),
                "cuda_elapsed_ms": cuda_elapsed_ms,
                "cuda_availability_reason": (
                    None if cuda_timer is not None and cuda_timer.available else cuda_reason
                ),
            }
            for key in ("recording_id", "utt_id", "segment_index"):
                value = identifiers.get(key) if isinstance(identifiers, Mapping) else None
                row[key] = None if value is None else (int(value) if key == "segment_index" else str(value))
            try:
                self._append(row)
            except Exception as exc:  # measurement must never mask pipeline output
                self._warnings.append(f"span write failed: {type(exc).__name__}")
            _SPAN_STACK.reset(token)
            try:
                self._write_active(stack[-1][1] if stack else None, stack)
            except Exception as exc:  # measurement must never mask pipeline output
                self._warnings.append(f"active-state write failed: {type(exc).__name__}")

    def close(self) -> None:
        try:
            self._write_active(None, ())
        except Exception as exc:  # measurement must never mask pipeline output
            self._warnings.append(f"active-state close failed: {type(exc).__name__}")

    def _append(self, row: Mapping[str, object]) -> None:
        payload = json.dumps(dict(row), sort_keys=True, ensure_ascii=False) + "\n"
        with self._write_lock:
            with self.span_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

    def _write_active(
        self,
        name: str | None,
        stack: tuple[tuple[str, str], ...],
    ) -> None:
        payload = {
            "active_component": name,
            "span_depth": len(stack),
            "pid": os.getpid(),
        }
        temporary = self.active_state_path.with_name(
            f".{self.active_state_path.name}.tmp-{uuid.uuid4().hex}"
        )
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.active_state_path)
        finally:
            temporary.unlink(missing_ok=True)


@contextmanager
def activate_recorder(recorder: SpanRecorder | None) -> Iterator[SpanRecorder | None]:
    """Activate a recorder in the current execution context."""

    if recorder is None:
        with nullcontext(None) as value:
            yield value
        return
    token = _ACTIVE_RECORDER.set(recorder)
    try:
        yield recorder
    finally:
        _ACTIVE_RECORDER.reset(token)
        recorder.close()


def telemetry_span(
    name: str,
    *,
    phase: str = "component",
    identifiers: Mapping[str, object] | None = None,
    cuda: bool = False,
):
    """Return an active span context, or a zero-cost semantic no-op."""

    recorder = _ACTIVE_RECORDER.get()
    if recorder is None:
        return nullcontext()
    return recorder.span(name, phase=phase, identifiers=identifiers, cuda=cuda)


def recorder_from_environment() -> SpanRecorder | None:
    """Build the child-process recorder declared by the campaign executor."""

    span_path = os.environ.get(SPAN_PATH_ENV)
    active_path = os.environ.get(ACTIVE_PATH_ENV)
    raw_context = os.environ.get(CONTEXT_ENV)
    if not span_path or not active_path or not raw_context:
        return None
    try:
        context = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid telemetry process context") from exc
    if not isinstance(context, Mapping):
        raise ValueError("telemetry process context must be a mapping")
    return SpanRecorder(
        Path(span_path),
        Path(active_path),
        context,
        cuda_timing=os.environ.get(CUDA_TIMING_ENV, "0") == "1",
    )


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
