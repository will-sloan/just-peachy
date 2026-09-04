"""Threaded, model-neutral session control for the common full-pipeline demo.

This module never imports a model implementation.  Default builders are loaded
from :mod:`app.full_pipeline.factory` only inside the session thread, and tests
can inject lightweight builders implementing the same runtime surface.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import threading
import traceback
from typing import Any
import uuid

from .runtime_config import (
    DemoRuntimeSelection,
    H2DemoRuntimeBinding,
    engineering_baseline_selection,
    load_h2_demo_runtime_binding,
)


TERMINAL_STATES = frozenset({"completed", "stopped", "failed"})
EVALUATION_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DEMO_RESULTS_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/demo_sessions"
)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _new_session_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"fullpipe_demo_{stamp}_{uuid.uuid4().hex[:10]}"


class EventStreamError(RuntimeError):
    """The durable event stream contained a complete but invalid record."""


class JsonlEventCursor:
    """Reconnectable byte-offset cursor over an append-only UTF-8 JSONL file.

    The cursor advances only past newline-terminated records.  A writer may
    therefore be interrupted halfway through a line without causing loss or a
    transient JSON error.  ``token()`` can be returned to a client and supplied
    to ``from_token`` after reconnecting.
    """

    def __init__(
        self,
        path: Path,
        *,
        byte_offset: int = 0,
        after_sequence: int | None = None,
        last_sequence: int | None = None,
        generation: int = 0,
    ) -> None:
        if byte_offset < 0:
            raise ValueError("byte_offset must be non-negative")
        self.path = Path(path).resolve()
        self._offset = int(byte_offset)
        self._after_sequence = after_sequence
        self._last_sequence = last_sequence
        self._generation = int(generation)
        self._lock = threading.Lock()

    @classmethod
    def from_token(
        cls, path: Path, token: Mapping[str, object]
    ) -> JsonlEventCursor:
        return cls(
            path,
            byte_offset=int(token.get("byte_offset") or 0),
            after_sequence=(
                int(token["after_sequence"])
                if token.get("after_sequence") is not None
                else None
            ),
            last_sequence=(
                int(token["last_sequence"])
                if token.get("last_sequence") is not None
                else None
            ),
            generation=int(token.get("generation") or 0),
        )

    def token(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": "full-pipeline-demo-event-cursor.v1",
                "byte_offset": self._offset,
                "after_sequence": self._after_sequence,
                "last_sequence": self._last_sequence,
                "generation": self._generation,
            }

    def read_available(self, *, limit: int = 256) -> list[dict[str, object]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._lock:
            if not self.path.is_file():
                return []
            size = self.path.stat().st_size
            if size < self._offset:
                # A session log should not truncate.  Reset safely if an
                # operator replaced it and let sequence filtering deduplicate.
                self._offset = 0
                self._last_sequence = self._after_sequence
                self._generation += 1
            rows: list[dict[str, object]] = []
            with self.path.open("rb") as stream:
                stream.seek(self._offset)
                while len(rows) < limit:
                    line_start = stream.tell()
                    payload = stream.readline()
                    if not payload:
                        break
                    if not payload.endswith(b"\n"):
                        # Do not consume a partial final line.
                        stream.seek(line_start)
                        break
                    self._offset = stream.tell()
                    try:
                        value = json.loads(payload.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                        raise EventStreamError(
                            f"invalid complete JSONL record at byte {line_start}: "
                            f"{self.path}"
                        ) from exc
                    if not isinstance(value, dict):
                        raise EventStreamError(
                            f"event record at byte {line_start} is not an object"
                        )
                    try:
                        sequence = int(value["event_sequence"])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise EventStreamError(
                            f"event record at byte {line_start} has no valid sequence"
                        ) from exc
                    if (
                        self._after_sequence is not None
                        and sequence <= self._after_sequence
                    ):
                        self._last_sequence = max(
                            sequence, self._last_sequence or sequence
                        )
                        continue
                    if self._last_sequence is not None and sequence <= self._last_sequence:
                        raise EventStreamError(
                            "event sequence is duplicate or regressive: "
                            f"{sequence} <= {self._last_sequence}"
                        )
                    self._last_sequence = sequence
                    rows.append(value)
            return rows


class CoalescingUpdateBuffer:
    """Bounded UI queue that coalesces transient snapshots.

    The durable event log remains authoritative.  Overflow is surfaced to the
    caller so it can reconnect with ``JsonlEventCursor`` rather than treating a
    lossy UI queue as scientific evidence.
    """

    def __init__(self, maximum_items: int = 256) -> None:
        if maximum_items < 4:
            raise ValueError("maximum_items must be at least 4")
        self.maximum_items = int(maximum_items)
        self._rows: deque[dict[str, object]] = deque()
        self._dropped = 0
        self._lock = threading.Lock()

    @staticmethod
    def _coalesce_key(row: Mapping[str, object]) -> str | None:
        kind = str(row.get("kind") or "")
        if kind == "status":
            return "status"
        if kind != "event":
            return None
        event = row.get("event")
        if not isinstance(event, Mapping):
            return None
        contract = str(event.get("contract_type") or "")
        if contract == "PipelineStatusEvent":
            return "event:pipeline_status"
        if contract == "ResourceTelemetryEvent":
            return "event:resource_telemetry"
        if contract == "AsrPartialEvent":
            return f"event:asr_partial:{event.get('hypothesis_id')}"
        return None

    def push(self, row: Mapping[str, object]) -> None:
        value = dict(row)
        key = self._coalesce_key(value)
        with self._lock:
            if key is not None:
                retained = deque(
                    existing
                    for existing in self._rows
                    if self._coalesce_key(existing) != key
                )
                self._rows = retained
            self._rows.append(value)
            while len(self._rows) > self.maximum_items:
                self._rows.popleft()
                self._dropped += 1

    def drain(self, *, limit: int = 256) -> dict[str, object]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._lock:
            values = [self._rows.popleft() for _ in range(min(limit, len(self._rows)))]
            dropped = self._dropped
            self._dropped = 0
            return {
                "updates": values,
                "dropped_ui_updates": dropped,
                "requires_event_resync": dropped > 0,
                "remaining_updates": len(self._rows),
            }


@dataclass
class _ManagedSession:
    session_id: str
    source_kind: str
    pipeline_id: str
    product_mode: str | None
    output_root: Path
    builder: Callable[..., Any]
    builder_kwargs: dict[str, object]
    pipeline_identity: Mapping[str, object]
    scientific_runtime_configuration: Mapping[str, object]
    input_audio_path: Path | None = None
    predecessor_session_id: str | None = None
    state: str = "queued"
    control_state: str = "running"
    created_at_utc: str = field(default_factory=_utc_now)
    started_at_utc: str | None = None
    ended_at_utc: str | None = None
    stop_requested: bool = False
    pause_requested: bool = False
    runtime: Any | None = None
    result: dict[str, object] | None = None
    failures: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    thread: threading.Thread | None = None
    joined: bool = False
    run_entered: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)
    updates: CoalescingUpdateBuffer = field(default_factory=CoalescingUpdateBuffer)
    ui_cursor: JsonlEventCursor | None = None
    event_cursor: JsonlEventCursor | None = None
    resume_gate: threading.Event = field(default_factory=threading.Event)


class DemoSessionManager:
    """Own immutable demo sessions while delegating all inference to factories."""

    def __init__(
        self,
        results_root: Path | None = None,
        *,
        enrollment_root: Path | None = None,
        file_builder: Callable[..., Any] | None = None,
        microphone_builder: Callable[..., Any] | None = None,
        pipeline_validator: Callable[[str], Mapping[str, object]] | None = None,
        maximum_ui_updates: int = 256,
        runtime_config_path: Path | None = None,
        runtime_config_expected_sha256: str | None = None,
    ) -> None:
        self.results_root = Path(results_root or DEFAULT_DEMO_RESULTS_ROOT).resolve()
        self.results_root.mkdir(parents=True, exist_ok=True)
        self.enrollment_root = (
            Path(enrollment_root).resolve() if enrollment_root is not None else None
        )
        self._file_builder = file_builder
        self._microphone_builder = microphone_builder
        self._pipeline_validator = pipeline_validator
        self._maximum_ui_updates = int(maximum_ui_updates)
        if runtime_config_expected_sha256 is not None and runtime_config_path is None:
            raise ValueError(
                "runtime_config_expected_sha256 requires runtime_config_path"
            )
        self._runtime_config_binding: H2DemoRuntimeBinding | None = (
            load_h2_demo_runtime_binding(
                runtime_config_path,
                expected_sha256=runtime_config_expected_sha256,
            )
            if runtime_config_path is not None
            else None
        )
        self._sessions: dict[str, _ManagedSession] = {}
        self._active_session_id: str | None = None
        self._lock = threading.RLock()

    @property
    def session_id(self) -> str | None:
        """Return the immutable active session ID, if one has been allocated."""

        with self._lock:
            return self._active_session_id

    @property
    def output_root(self) -> Path | None:
        """Return the active session's output root without starting a runtime."""

        with self._lock:
            record = self._active_record_locked()
            return record.output_root if record is not None else None

    @property
    def active(self) -> bool:
        """Whether the current session has a live or queued execution thread."""

        with self._lock:
            record = self._active_record_locked()
            return record is not None and not self._is_terminal_locked(record)

    @property
    def default_product_mode(self) -> str:
        """Return the binding-selected default, or the labelled baseline default."""

        if self._runtime_config_binding is not None:
            return self._runtime_config_binding.default_product_mode
        from .h2_ux import H2_DEFAULT_PRODUCT_MODE

        return H2_DEFAULT_PRODUCT_MODE

    @property
    def scientific_configuration_status(self) -> str:
        """Describe the manager's configuration claim before a session starts."""

        if self._runtime_config_binding is None:
            return "ENGINEERING_BASELINE_NOT_FINAL"
        return {
            "DEVELOPMENT_SELECTED": "DEVELOPMENT_SELECTED_NOT_FINAL",
            "FROZEN": "FROZEN_SCIENTIFIC_CONFIGURATION",
            "FINAL_VALIDATED": "FINAL_VALIDATED_SCIENTIFIC_CONFIGURATION",
        }[self._runtime_config_binding.lifecycle]

    def start_file(
        self,
        *,
        pipeline_id: str,
        input_path: Path,
        pace: float = 1.0,
        play_audio: bool = False,
        duration_sec: float | None = None,
        telemetry_enabled: bool = True,
        product_mode: str | None = None,
        session_id: str | None = None,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        return self._start_file(
            pipeline_id=pipeline_id,
            input_path=input_path,
            pace=pace,
            play_audio=play_audio,
            duration_sec=duration_sec,
            telemetry_enabled=telemetry_enabled,
            product_mode=product_mode,
            session_id=session_id,
            output_root=output_root,
            predecessor_session_id=None,
        )

    def switch_file(self, **kwargs: Any) -> dict[str, object]:
        predecessor = self._stop_active_for_switch()
        kwargs.setdefault("product_mode", None)
        return self._start_file(
            predecessor_session_id=predecessor,
            **kwargs,
        )

    def _start_file(
        self,
        *,
        pipeline_id: str,
        input_path: Path,
        pace: float,
        play_audio: bool,
        duration_sec: float | None,
        telemetry_enabled: bool,
        product_mode: str | None,
        session_id: str | None,
        output_root: Path | None,
        predecessor_session_id: str | None,
    ) -> dict[str, object]:
        source = Path(input_path).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        if pace < 0:
            raise ValueError("pace must be non-negative")
        if duration_sec is not None and duration_sec <= 0:
            raise ValueError("duration_sec must be positive when provided")
        configuration = self._resolve_runtime_configuration(
            pipeline_id, product_mode
        )
        normalized_mode = configuration.product_mode
        config_status = configuration.status_payload()
        identity = {
            **self._validate_pipeline(pipeline_id),
            "demo_scientific_runtime_configuration": config_status,
        }
        builder = self._file_builder or _default_file_builder
        kwargs: dict[str, object] = {
            "pipeline_id": pipeline_id,
            "input_path": source,
            "enrollment_root": self.enrollment_root,
            "duration_sec": duration_sec,
            "telemetry_enabled": telemetry_enabled,
            "pace": float(pace),
            "realtime": pace == 1.0,
            "play_audio": bool(play_audio),
        }
        if normalized_mode is not None:
            kwargs["product_mode"] = normalized_mode
        tuning_payload = configuration.runtime_tuning_payload()
        if tuning_payload is not None:
            kwargs["runtime_tuning"] = tuning_payload
        return self._create_session(
            source_kind="file",
            pipeline_id=pipeline_id,
            pipeline_identity=identity,
            product_mode=normalized_mode,
            builder=builder,
            builder_kwargs=kwargs,
            scientific_runtime_configuration=config_status,
            input_audio_path=source,
            session_id=session_id,
            output_root=output_root,
            predecessor_session_id=predecessor_session_id,
        )

    def start_microphone(
        self,
        *,
        pipeline_id: str,
        duration_sec: float,
        device: int | str | None = None,
        source_sample_rate_hz: int | None = None,
        source_channels: int | None = None,
        play_audio: bool = False,
        record_input_audio: bool = False,
        telemetry_enabled: bool = True,
        product_mode: str | None = None,
        session_id: str | None = None,
        output_root: Path | None = None,
    ) -> dict[str, object]:
        return self._start_microphone(
            pipeline_id=pipeline_id,
            duration_sec=duration_sec,
            device=device,
            source_sample_rate_hz=source_sample_rate_hz,
            source_channels=source_channels,
            play_audio=play_audio,
            record_input_audio=record_input_audio,
            telemetry_enabled=telemetry_enabled,
            product_mode=product_mode,
            session_id=session_id,
            output_root=output_root,
            predecessor_session_id=None,
        )

    def switch_microphone(self, **kwargs: Any) -> dict[str, object]:
        predecessor = self._stop_active_for_switch()
        kwargs.setdefault("product_mode", None)
        return self._start_microphone(
            predecessor_session_id=predecessor,
            **kwargs,
        )

    def _start_microphone(
        self,
        *,
        pipeline_id: str,
        duration_sec: float,
        device: int | str | None,
        source_sample_rate_hz: int | None,
        source_channels: int | None,
        play_audio: bool,
        record_input_audio: bool,
        telemetry_enabled: bool,
        product_mode: str | None,
        session_id: str | None,
        output_root: Path | None,
        predecessor_session_id: str | None,
    ) -> dict[str, object]:
        if duration_sec <= 0:
            raise ValueError("duration_sec must be positive")
        configuration = self._resolve_runtime_configuration(
            pipeline_id, product_mode
        )
        normalized_mode = configuration.product_mode
        config_status = configuration.status_payload()
        identity = {
            **self._validate_pipeline(pipeline_id),
            "demo_scientific_runtime_configuration": config_status,
        }
        builder = self._microphone_builder or _default_microphone_builder
        kwargs: dict[str, object] = {
            "pipeline_id": pipeline_id,
            "duration_sec": float(duration_sec),
            "enrollment_root": self.enrollment_root,
            "device": device,
            "source_sample_rate_hz": source_sample_rate_hz,
            "source_channels": source_channels,
            "telemetry_enabled": telemetry_enabled,
            "play_audio": bool(play_audio),
            "record_input_audio": bool(record_input_audio),
        }
        if normalized_mode is not None:
            kwargs["product_mode"] = normalized_mode
        tuning_payload = configuration.runtime_tuning_payload()
        if tuning_payload is not None:
            kwargs["runtime_tuning"] = tuning_payload
        return self._create_session(
            source_kind="microphone",
            pipeline_id=pipeline_id,
            pipeline_identity=identity,
            product_mode=normalized_mode,
            builder=builder,
            builder_kwargs=kwargs,
            scientific_runtime_configuration=config_status,
            input_audio_path=None,
            session_id=session_id,
            output_root=output_root,
            predecessor_session_id=predecessor_session_id,
        )

    def _create_session(
        self,
        *,
        source_kind: str,
        pipeline_id: str,
        pipeline_identity: Mapping[str, object],
        product_mode: str | None,
        builder: Callable[..., Any],
        builder_kwargs: Mapping[str, object],
        scientific_runtime_configuration: Mapping[str, object],
        input_audio_path: Path | None,
        session_id: str | None,
        output_root: Path | None,
        predecessor_session_id: str | None,
    ) -> dict[str, object]:
        identifier = session_id or _new_session_id()
        if not identifier or any(value in identifier for value in ("/", "\\", ":")):
            raise ValueError("session_id must be a non-empty portable name")
        run_root = (
            Path(output_root).resolve()
            if output_root is not None
            else self.results_root / identifier
        )
        requested_recording = bool(builder_kwargs.get("record_input_audio", False))
        with self._lock:
            if identifier in self._sessions:
                raise ValueError(f"session_id already exists: {identifier}")
            if run_root.exists():
                raise FileExistsError(
                    f"refusing to overwrite an existing session root: {run_root}"
                )
            if predecessor_session_id is None:
                active = self._active_record_locked()
                if active is not None and not self._is_terminal_locked(active):
                    raise RuntimeError(
                        "another demo session is active; use switch_file or "
                        "switch_microphone for an immutable transition"
                    )
            kwargs = dict(builder_kwargs)
            kwargs.pop("record_input_audio", None)
            recorded_input_path = (
                run_root / "input_audio/source.wav" if requested_recording else None
            )
            if recorded_input_path is not None:
                kwargs["record_audio_path"] = recorded_input_path
            kwargs["session_id"] = identifier
            kwargs["output_root"] = run_root
            _write_json_atomic(
                run_root / "manifests/demo_runtime_configuration.json",
                scientific_runtime_configuration,
            )
            record = _ManagedSession(
                session_id=identifier,
                source_kind=source_kind,
                pipeline_id=pipeline_id,
                product_mode=product_mode,
                output_root=run_root,
                builder=builder,
                builder_kwargs=kwargs,
                pipeline_identity=dict(pipeline_identity),
                scientific_runtime_configuration=dict(
                    scientific_runtime_configuration
                ),
                input_audio_path=recorded_input_path or input_audio_path,
                predecessor_session_id=predecessor_session_id,
                updates=CoalescingUpdateBuffer(self._maximum_ui_updates),
                ui_cursor=JsonlEventCursor(run_root / "events/events.jsonl"),
                event_cursor=JsonlEventCursor(run_root / "events/events.jsonl"),
            )
            record.resume_gate.set()
            self._sessions[identifier] = record
            self._active_session_id = identifier
            thread = threading.Thread(
                target=self._run_session,
                args=(record,),
                name=f"full-pipeline-demo-{identifier}",
                daemon=False,
            )
            record.thread = thread
            self._push_status_locked(record)
            thread.start()
            return self._status_locked(record)

    def _run_session(self, record: _ManagedSession) -> None:
        try:
            if record.predecessor_session_id is not None:
                predecessor = self._record(record.predecessor_session_id)
                thread = predecessor.thread
                if thread is not None:
                    thread.join()
            with record.lock:
                if record.stop_requested:
                    record.state = "stopped"
                    record.control_state = "stopped"
                    return
                record.state = "building"
                record.started_at_utc = _utc_now()
                self._push_status_locked(record)
            scientifically_bound = not bool(
                record.scientific_runtime_configuration.get(
                    "engineering_baseline", False
                )
            )
            runtime, accepted = _build_runtime(
                record.builder,
                record.builder_kwargs,
                required_keywords=(
                    ("product_mode", "runtime_tuning")
                    if scientifically_bound
                    else ()
                ),
            )
            with record.lock:
                record.runtime = runtime
                record.state = "starting"
                if bool(record.builder_kwargs.get("play_audio")) and not accepted.get(
                    "play_audio", False
                ):
                    if not _request_optional_control(
                        runtime, ("set_play_audio", "request_play_audio"), True
                    ):
                        record.warnings.append(
                            "play_audio was requested but this runtime has no "
                            "playback control"
                        )
                if record.stop_requested:
                    _request_optional_control(runtime, ("request_stop",), None)
                elif record.pause_requested:
                    record.state = "paused"
                    record.control_state = "paused"
                    record.resume_gate.clear()
                self._push_status_locked(record)
            while not record.resume_gate.wait(timeout=0.25):
                with record.lock:
                    if record.stop_requested:
                        _request_optional_control(runtime, ("request_stop",), None)
                        record.resume_gate.set()
                        break
            with record.lock:
                record.run_entered = True
                if record.state == "paused":
                    record.state = "starting"
                    record.control_state = "running"
            result = runtime.run()
            result_value = dict(result) if isinstance(result, Mapping) else {}
            with record.lock:
                record.result = result_value
                completion = str(
                    result_value.get("completion_state")
                    or result_value.get("state")
                    or ""
                ).casefold()
                if completion in {"failed", "corrupt", "incompatible"}:
                    record.state = "failed"
                elif completion in {"stopped", "incomplete"} or record.stop_requested:
                    record.state = "stopped"
                else:
                    record.state = "completed"
                record.control_state = record.state
                for value in result_value.get("errors", []) or []:
                    record.failures.append(
                        {"stage": "runtime", "type": "RuntimeError", "message": str(value)}
                    )
        except BaseException as exc:
            with record.lock:
                failure_stage = record.state
                record.state = "failed"
                record.control_state = "failed"
                record.failures.append(
                    {
                        "stage": failure_stage,
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": "".join(
                            traceback.format_exception(type(exc), exc, exc.__traceback__)
                        ),
                    }
                )
        finally:
            with record.lock:
                record.ended_at_utc = _utc_now()
                self._push_status_locked(record)

    def pause(self, session_id: str | None = None) -> dict[str, object]:
        record = self._record(self._resolve_session_id(session_id))
        with record.lock:
            if self._is_terminal_locked(record):
                return self._status_locked(record)
            record.pause_requested = True
            record.control_state = "pause_requested"
            record.resume_gate.clear()
            if record.runtime is not None and record.run_entered:
                self._apply_pause_locked(record)
            elif record.runtime is not None:
                record.state = "paused"
                record.control_state = "paused"
            self._push_status_locked(record)
            return self._status_locked(record)

    def _apply_pause_locked(self, record: _ManagedSession) -> None:
        runtime = record.runtime
        if runtime is None:
            return
        supported = _request_optional_control(runtime, ("request_pause", "pause"), None)
        if not supported:
            source = getattr(runtime, "source", None)
            supported = _request_optional_control(source, ("pause",), None)
        if supported:
            record.control_state = "paused"
        else:
            record.control_state = "pause_unsupported"
            record.warnings.append("pause is not supported by this runtime")

    def resume(self, session_id: str | None = None) -> dict[str, object]:
        record = self._record(self._resolve_session_id(session_id))
        with record.lock:
            if self._is_terminal_locked(record):
                return self._status_locked(record)
            record.pause_requested = False
            record.resume_gate.set()
            runtime = record.runtime
            supported = True
            if runtime is not None and record.run_entered:
                supported = _request_optional_control(
                    runtime, ("request_resume", "resume"), None
                )
                if not supported:
                    supported = _request_optional_control(
                        getattr(runtime, "source", None), ("resume",), None
                    )
            record.control_state = "running" if supported else "resume_unsupported"
            if not supported:
                record.warnings.append("resume is not supported by this runtime")
            self._push_status_locked(record)
            return self._status_locked(record)

    def stop(self, session_id: str | None = None) -> dict[str, object]:
        record = self._record(self._resolve_session_id(session_id))
        with record.lock:
            if self._is_terminal_locked(record):
                return self._status_locked(record)
            record.stop_requested = True
            record.control_state = "stopping"
            record.resume_gate.set()
            if record.runtime is not None:
                _request_optional_control(record.runtime, ("request_stop",), None)
            self._push_status_locked(record)
            return self._status_locked(record)

    def reset_session(
        self,
        session_id: str | None = None,
        *,
        preserve_transcript: bool = True,
    ) -> dict[str, object]:
        """Reset volatile H2 identity state without touching enrollment profiles.

        This is deliberately an explicit runtime capability.  A legacy runtime
        that cannot prove the reset is rejected instead of allowing the UI to
        imply that anonymous memory was removed when it was not.
        """

        record = self._record(self._resolve_session_id(session_id))
        with record.lock:
            result, resumed = self._run_privacy_control_locked(
                record,
                action="reset_session",
                preserve_transcript=preserve_transcript,
            )
            value = self._status_locked(record)
            value["session_control"] = {
                "action": "reset_session",
                "preserve_transcript": bool(preserve_transcript),
                "permanent_enrollment_profiles_touched": False,
                "automatically_resumed": resumed,
                "runtime_result": result,
            }
            self._push_status_locked(record)
            return value

    def clear_anonymous_memory(
        self,
        session_id: str | None = None,
        *,
        preserve_transcript: bool = True,
    ) -> dict[str, object]:
        """Clear only volatile anonymous memory through the H2 runtime."""

        record = self._record(self._resolve_session_id(session_id))
        with record.lock:
            result, resumed = self._run_privacy_control_locked(
                record,
                action="clear_anonymous_memory",
                preserve_transcript=preserve_transcript,
            )
            value = self._status_locked(record)
            value["session_control"] = {
                "action": "clear_anonymous_memory",
                "preserve_transcript": bool(preserve_transcript),
                "permanent_enrollment_profiles_touched": False,
                "automatically_resumed": resumed,
                "runtime_result": result,
            }
            self._push_status_locked(record)
            return value

    @staticmethod
    def _run_privacy_control_locked(
        record: _ManagedSession,
        *,
        action: str,
        preserve_transcript: bool,
    ) -> tuple[object | None, bool]:
        runtime = record.runtime
        if runtime is None or not record.run_entered:
            raise RuntimeError("the H2 runtime is not ready for session controls")
        automatically_paused = not record.pause_requested
        if automatically_paused:
            if not _request_optional_control(runtime, ("request_pause", "pause"), None):
                raise RuntimeError(
                    "this runtime cannot establish the pause boundary required "
                    "for an H2 privacy control"
                )
            record.control_state = "paused"
        try:
            supported, result = _invoke_optional_control(
                runtime,
                (action,),
                preserve_transcript=bool(preserve_transcript),
            )
            if not supported:
                raise RuntimeError(
                    f"this runtime does not expose the H2 {action} control"
                )
        finally:
            if automatically_paused:
                if not _request_optional_control(
                    runtime, ("request_resume", "resume"), None
                ):
                    record.control_state = "resume_unsupported"
                    record.warnings.append(
                        f"runtime did not resume after H2 {action}"
                    )
                else:
                    record.control_state = "running"
        return result, automatically_paused and record.control_state == "running"

    def join(
        self, session_id: str | None = None, timeout: float | None = None
    ) -> dict[str, object]:
        record = self._record(self._resolve_session_id(session_id))
        thread = record.thread
        if thread is not None:
            thread.join(timeout=timeout)
        with record.lock:
            record.joined = thread is None or not thread.is_alive()
            return self._status_locked(record)

    def status(self, session_id: str | None = None) -> dict[str, object]:
        record = self._record(self._resolve_session_id(session_id))
        with record.lock:
            return self._status_locked(record)

    def statuses(self) -> list[dict[str, object]]:
        with self._lock:
            identifiers = tuple(self._sessions)
        return [self.status(identifier) for identifier in identifiers]

    def open_event_cursor(
        self,
        session_id: str,
        *,
        byte_offset: int = 0,
        after_sequence: int | None = None,
        token: Mapping[str, object] | None = None,
    ) -> JsonlEventCursor:
        record = self._record(session_id)
        path = record.output_root / "events/events.jsonl"
        if token is not None:
            return JsonlEventCursor.from_token(path, token)
        return JsonlEventCursor(
            path, byte_offset=byte_offset, after_sequence=after_sequence
        )

    def poll_updates(
        self,
        session_id: str,
        *,
        event_limit: int = 256,
        update_limit: int = 256,
    ) -> dict[str, object]:
        record = self._record(session_id)
        cursor = record.ui_cursor
        if cursor is not None:
            for event in cursor.read_available(limit=event_limit):
                record.updates.push({"kind": "event", "event": event})
        with record.lock:
            record.updates.push({"kind": "status", "status": self._status_locked(record)})
        result = record.updates.drain(limit=update_limit)
        result.update(
            {
                "schema_version": "full-pipeline-demo-updates.v1",
                "session_id": session_id,
                "authoritative_event_cursor": cursor.token() if cursor else None,
            }
        )
        return result

    def poll_events(
        self,
        limit: int = 256,
        *,
        session_id: str | None = None,
    ) -> dict[str, object]:
        """Read durable events for the active run and return a reconnect token.

        This convenience cursor is independent of the bounded/coalesced UI
        queue.  A reconnecting client that owns its own token should call
        :meth:`open_event_cursor` instead.
        """

        record = self._record(self._resolve_session_id(session_id))
        cursor = record.event_cursor
        events = cursor.read_available(limit=limit) if cursor is not None else []
        return {
            "schema_version": "full-pipeline-demo-event-batch.v1",
            "session_id": record.session_id,
            "events": events,
            "cursor": cursor.token() if cursor is not None else None,
        }

    def export(
        self,
        export_root: Path,
        *,
        session_id: str | None = None,
        include_input_audio: bool = False,
    ) -> dict[str, object]:
        record = self._record(self._resolve_session_id(session_id))
        thread = record.thread
        if thread is not None:
            thread.join(timeout=0)
            if thread.is_alive():
                raise RuntimeError("export is available only after the session has joined")
        with record.lock:
            record.joined = True
            manager_status = self._status_locked(record)
            audio = record.input_audio_path if include_input_audio else None
        from .exports import export_session

        return export_session(
            record.output_root,
            export_root,
            manager_status=manager_status,
            input_audio_path=audio,
            authorize_input_audio=include_input_audio,
        )

    def shutdown(self, *, timeout_per_session: float = 10.0) -> None:
        for value in self.statuses():
            if str(value["state"]) not in TERMINAL_STATES:
                self.stop(str(value["session_id"]))
        for value in self.statuses():
            self.join(str(value["session_id"]), timeout=timeout_per_session)

    def _stop_active_for_switch(self) -> str | None:
        with self._lock:
            record = self._active_record_locked()
            if record is None:
                return None
            identifier = record.session_id
            terminal = self._is_terminal_locked(record)
        if not terminal:
            self.stop(identifier)
        return identifier

    def _validate_pipeline(self, pipeline_id: str) -> Mapping[str, object]:
        if self._pipeline_validator is not None:
            return dict(self._pipeline_validator(pipeline_id))
        from app.full_pipeline.matrix import FullPipelineMatrix

        matrix_path = (
            EVALUATION_ROOT
            / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
        )
        runtime_path = (
            EVALUATION_ROOT
            / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
        )
        selection = FullPipelineMatrix(matrix_path, runtime_path).resolve(pipeline_id)
        return {
            "pipeline_id": selection.pipeline_id,
            "pipeline_config_sha256": selection.pipeline_config_sha256,
            "protocol_version": selection.protocol_version,
            "asr_backend_id": selection.asr.get("component_id"),
            "diarization_backend_id": selection.diarization.get("pipeline_id"),
            "identity_backend_id": selection.identity.get("backend_id"),
            "hybrid_label": selection.hybrid_label,
            "frozen_hybrid_anchor": selection.frozen_hybrid_anchor,
        }

    def _resolve_runtime_configuration(
        self, pipeline_id: str, product_mode: str | None
    ) -> DemoRuntimeSelection:
        normalized_mode = _validated_product_mode(pipeline_id, product_mode)
        if self._runtime_config_binding is not None:
            return self._runtime_config_binding.select(
                pipeline_id, normalized_mode
            )
        return engineering_baseline_selection(pipeline_id, normalized_mode)

    def _record(self, session_id: str) -> _ManagedSession:
        with self._lock:
            try:
                return self._sessions[session_id]
            except KeyError as exc:
                raise KeyError(f"unknown demo session: {session_id}") from exc

    def _resolve_session_id(self, session_id: str | None) -> str:
        if session_id is not None:
            return session_id
        with self._lock:
            if self._active_session_id is None:
                raise RuntimeError("no demo session has been started")
            return self._active_session_id

    def _active_record_locked(self) -> _ManagedSession | None:
        return (
            self._sessions.get(self._active_session_id)
            if self._active_session_id is not None
            else None
        )

    @staticmethod
    def _is_terminal_locked(record: _ManagedSession) -> bool:
        return record.state in TERMINAL_STATES

    def _push_status_locked(self, record: _ManagedSession) -> None:
        record.updates.push({"kind": "status", "status": self._status_locked(record)})

    @staticmethod
    def _status_locked(record: _ManagedSession) -> dict[str, object]:
        runtime_status, status_error = _read_runtime_status(record.output_root)
        thread_alive = record.thread is not None and record.thread.is_alive()
        runtime_status = runtime_status or {}
        runtime_state = str(runtime_status.get("state") or "")
        visible_state = (
            runtime_state
            if record.state not in TERMINAL_STATES and runtime_state
            else record.state
        )
        runtime_warnings = [str(value) for value in runtime_status.get("warnings") or []]
        runtime_errors = [str(value) for value in runtime_status.get("errors") or []]
        manager_errors = [str(value.get("message") or value) for value in record.failures]
        value: dict[str, object] = {
            "schema_version": "full-pipeline-demo-session-status.v1",
            "session_id": record.session_id,
            "source_kind": record.source_kind,
            "pipeline_id": record.pipeline_id,
            "product_mode": record.product_mode,
            "pipeline_identity": dict(record.pipeline_identity),
            "scientific_runtime_configuration": dict(
                record.scientific_runtime_configuration
            ),
            "scientific_config_status": record.scientific_runtime_configuration.get(
                "status"
            ),
            "scientific_config_path": record.scientific_runtime_configuration.get(
                "source_path"
            ),
            "scientific_config_sha256": record.scientific_runtime_configuration.get(
                "source_file_sha256"
            ),
            "runtime_tuning_identity_sha256": (
                record.scientific_runtime_configuration.get(
                    "runtime_tuning_identity_sha256"
                )
            ),
            "final_scientific_validation": (
                record.scientific_runtime_configuration.get(
                    "final_scientific_validation"
                )
            ),
            "output_root": str(record.output_root),
            "state": visible_state,
            "manager_state": record.state,
            "control_state": record.control_state,
            "created_at_utc": record.created_at_utc,
            "started_at_utc": record.started_at_utc,
            "ended_at_utc": record.ended_at_utc,
            "predecessor_session_id": record.predecessor_session_id,
            "thread_alive": thread_alive,
            "joined": record.joined,
            "stop_requested": record.stop_requested,
            "pause_requested": record.pause_requested,
            "warnings": list(dict.fromkeys([*record.warnings, *runtime_warnings])),
            "errors": list(dict.fromkeys([*manager_errors, *runtime_errors])),
            "failures": [dict(value) for value in record.failures],
            "runtime_status": runtime_status or None,
            "result": dict(record.result) if record.result is not None else None,
        }
        for key in (
            "queue_depth",
            "dropped_frame_count",
            "queue_backpressure",
            "counts",
            "components",
            "recoverable",
            "elapsed_session_sec",
            "audio_processed_sec",
            "realtime_factor",
        ):
            if key in runtime_status:
                value[key] = runtime_status[key]
        if status_error is not None:
            value["runtime_status_read_error"] = status_error
        return value


def _read_runtime_status(
    output_root: Path,
) -> tuple[dict[str, object] | None, str | None]:
    path = output_root / "status.json"
    if not path.is_file():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("runtime status is not an object")
        return value, None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> None:
    """Persist the manager-side configuration identity before model loading."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    payload = (
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _build_runtime(
    builder: Callable[..., Any],
    kwargs: Mapping[str, object],
    *,
    required_keywords: Sequence[str] = (),
) -> tuple[Any, dict[str, bool]]:
    if builder is _default_file_builder:
        from app.full_pipeline.factory import build_file_runtime

        return _build_runtime(
            build_file_runtime,
            kwargs,
            required_keywords=required_keywords,
        )
    if builder is _default_microphone_builder:
        from app.full_pipeline.factory import build_microphone_runtime

        return _build_runtime(
            build_microphone_runtime,
            kwargs,
            required_keywords=required_keywords,
        )
    signature = inspect.signature(builder)
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    accepted: dict[str, bool] = {}
    filtered: dict[str, object] = {}
    for key, value in kwargs.items():
        if accepts_kwargs or key in signature.parameters:
            filtered[key] = value
            accepted[key] = True
        else:
            accepted[key] = False
    missing_required = sorted(
        key for key in required_keywords if not accepted.get(key, False)
    )
    if missing_required:
        raise RuntimeError(
            "scientifically bound demo builder does not accept exact keyword(s): "
            + ", ".join(missing_required)
        )
    pace = float(kwargs.get("pace") or 0.0)
    if not accepted.get("pace", False) and pace not in {0.0, 1.0}:
        raise RuntimeError(
            "the installed full-pipeline factory supports only unpaced or "
            "real-time file replay; explicit accelerated pace requires the "
            "Prompt-2 factory control"
        )
    return builder(**filtered), accepted


def _request_optional_control(
    target: Any | None, names: Sequence[str], value: object | None
) -> bool:
    if target is None:
        return False
    for name in names:
        method = getattr(target, name, None)
        if not callable(method):
            continue
        if value is None:
            method()
        else:
            method(value)
        return True
    return False


def _invoke_optional_control(
    target: Any | None,
    names: Sequence[str],
    **kwargs: object,
) -> tuple[bool, object | None]:
    """Invoke one optional keyword control and preserve its diagnostic result."""

    if target is None:
        return False, None
    for name in names:
        method = getattr(target, name, None)
        if callable(method):
            return True, method(**kwargs)
    return False, None


def _validated_product_mode(pipeline_id: str, product_mode: str | None) -> str | None:
    if product_mode is None:
        return None
    from .h2_ux import h2_product_mode, require_h2_pipeline_id

    require_h2_pipeline_id(pipeline_id)
    return h2_product_mode(product_mode).mode_id


def _default_file_builder(**kwargs: object) -> Any:
    raise AssertionError("default file builder must be resolved in the session thread")


def _default_microphone_builder(**kwargs: object) -> Any:
    raise AssertionError(
        "default microphone builder must be resolved in the session thread"
    )
