"""Deterministic event identities and ordered JSONL sinks."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Callable, Mapping, Sequence
import uuid

from .models import CONTRACT_SCHEMA_VERSION, ComponentRuntimeIdentity


class EventOrderingError(RuntimeError):
    """Raised when a caller attempts to write a non-monotonic event."""


class EventFactory:
    """Own one session's sequence, IDs, and common envelope fields."""

    def __init__(
        self,
        *,
        session_id: str,
        pipeline_id: str,
        protocol_version: str,
        stream_id: str,
        recording_id: str | None,
        source_clock: Mapping[str, object],
        monotonic_ns: Callable[[], int] = time.perf_counter_ns,
        utc_now: Callable[[], datetime] | None = None,
    ) -> None:
        self.session_id = session_id
        self.pipeline_id = pipeline_id
        self.protocol_version = protocol_version
        self.stream_id = stream_id
        self.recording_id = recording_id
        self.source_clock = dict(source_clock)
        self.monotonic_ns = monotonic_ns
        self.utc_now = utc_now or (lambda: datetime.now(timezone.utc))
        self._sequence = 0
        self._lock = threading.Lock()
        self._namespace = uuid.uuid5(uuid.NAMESPACE_URL, f"just-peachy:{session_id}")

    @property
    def next_sequence(self) -> int:
        with self._lock:
            return self._sequence + 1

    def create(
        self,
        *,
        contract_type: str,
        event_type: str,
        component_identity: ComponentRuntimeIdentity | Mapping[str, object],
        payload: Mapping[str, object],
        capture_timestamps: Mapping[str, object] | None = None,
        event_reason: str = "runtime_update",
        detail: str | None = None,
        causation_event_id: str | None = None,
        causal_event_ids: Sequence[str] = (),
        correlation_id: str | None = None,
        utterance_id: str | None = None,
        processing_started_monotonic_ns: int | None = None,
        processing_ended_monotonic_ns: int | None = None,
        backend_latency_ms: float | None = None,
    ) -> dict[str, object]:
        with self._lock:
            self._sequence += 1
            sequence = self._sequence
            emitted = int(self.monotonic_ns())
            wall = self.utc_now()
        if wall.tzinfo is None:
            wall = wall.replace(tzinfo=timezone.utc)
        emitted_utc = (
            wall.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
        event_id = f"evt_{uuid.uuid5(self._namespace, f'{sequence}:{event_type}').hex}"
        identity = (
            component_identity.to_contract()
            if isinstance(component_identity, ComponentRuntimeIdentity)
            else dict(component_identity)
        )
        capture = dict(capture_timestamps or {})
        complete_capture = {
            "sample_start_index": capture.get("sample_start_index"),
            "sample_end_index": capture.get("sample_end_index"),
            "audio_start_sec": capture.get("audio_start_sec"),
            "audio_end_sec": capture.get("audio_end_sec"),
            "capture_start_monotonic_ns": capture.get("capture_start_monotonic_ns"),
            "capture_end_monotonic_ns": capture.get("capture_end_monotonic_ns"),
            "capture_start_utc": capture.get("capture_start_utc"),
            "capture_end_utc": capture.get("capture_end_utc"),
            "discontinuity_before": bool(capture.get("discontinuity_before", False)),
            "dropped_sample_count_before": int(
                capture.get("dropped_sample_count_before", 0)
            ),
        }
        event: dict[str, object] = {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "contract_type": contract_type,
            "event_id": event_id,
            "event_type": event_type,
            "event_sequence": sequence,
            "session_id": self.session_id,
            "pipeline_id": self.pipeline_id,
            "protocol_version": self.protocol_version,
            "stream_id": self.stream_id,
            "recording_id": self.recording_id,
            "utterance_id": utterance_id,
            "correlation_id": correlation_id or self.session_id,
            "causation_event_id": causation_event_id,
            "source_clock": dict(self.source_clock),
            "capture_timestamps": complete_capture,
            "processing_timestamps": {
                "processing_started_monotonic_ns": processing_started_monotonic_ns,
                "processing_ended_monotonic_ns": processing_ended_monotonic_ns,
                "emitted_monotonic_ns": emitted,
                "emitted_at_utc": emitted_utc,
                "backend_latency_ms": backend_latency_ms,
            },
            "component_identity": identity,
            "event_reason": {
                "code": event_reason,
                "detail": detail,
                "causal_event_ids": list(dict.fromkeys(causal_event_ids)),
            },
        }
        event.update(deepcopy(dict(payload)))
        return event


class OrderedJsonlEventSink:
    """Thread-safe append-only sink that rejects sequence/time regression."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path).resolve() if path is not None else None
        self._events: list[dict[str, object]] = []
        self._last_sequence = 0
        self._last_emitted_ns = -1
        self._pending: dict[int, dict[str, object]] = {}
        self._lock = threading.Lock()
        self._handle = None
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self.path.open("w", encoding="utf-8", newline="\n")

    def emit(self, event: Mapping[str, object]) -> None:
        row = deepcopy(dict(event))
        sequence = int(row.get("event_sequence", -1))
        with self._lock:
            if sequence <= self._last_sequence or sequence in self._pending:
                raise EventOrderingError(
                    f"event_sequence is duplicate or regressive: {sequence}"
                )
            self._pending[sequence] = row
            while self._last_sequence + 1 in self._pending:
                next_row = self._pending.pop(self._last_sequence + 1)
                processing = next_row.get("processing_timestamps")
                next_emitted_ns = (
                    int(processing.get("emitted_monotonic_ns", -1))
                    if isinstance(processing, Mapping)
                    else -1
                )
                if next_emitted_ns < self._last_emitted_ns:
                    raise EventOrderingError("emitted monotonic time regressed")
                self._events.append(next_row)
                self._last_sequence += 1
                self._last_emitted_ns = next_emitted_ns
                if self._handle is not None:
                    self._handle.write(
                        json.dumps(next_row, sort_keys=True, separators=(",", ":"))
                        + "\n"
                    )
            if self._handle is not None:
                self._handle.flush()

    def events(self) -> tuple[Mapping[str, object], ...]:
        with self._lock:
            return tuple(deepcopy(self._events))

    def close(self) -> None:
        with self._lock:
            if self._pending:
                missing = self._last_sequence + 1
                raise EventOrderingError(
                    f"cannot close event sink with a sequence gap at {missing}"
                )
            if self._handle is not None:
                self._handle.flush()
                self._handle.close()
                self._handle = None


class MemoryEventSink(OrderedJsonlEventSink):
    def __init__(self) -> None:
        super().__init__(None)
