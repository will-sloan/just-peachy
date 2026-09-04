"""Prompt-4-only worker reuse and exact native-ASR stream replay.

The normal interactive runtime remains cold-started and owns its workers.  This
module adds opt-in evaluation helpers: one worker pool owned by an accuracy job
and a checksum-bound trace of the *native streaming adapter interactions* for
one source recording and one ASR configuration.  Replaying an ASR trace still
feeds each partial/final update back at the same normalized-audio call horizon;
it is not a batch transcript shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import time
from typing import Mapping
import uuid

import numpy as np
import soundfile as sf

from app.full_pipeline.cache import canonical_sha256
from app.full_pipeline.models import NormalizedAudioFrame
from app.full_pipeline.workers import PersistentWorker, WorkerSpec


ASR_STREAM_TRACE_SCHEMA_VERSION = "full-pipeline-native-asr-stream-trace.v2"
ASR_STREAM_TRACE_IDENTITY_SCHEMA_VERSION = (
    "full-pipeline-native-asr-stream-trace-identity.v2"
)


def sha256_file(path: Path) -> str:
    """Hash a source without reading a potentially long recording at once."""

    digest = hashlib.sha256()
    with Path(path).resolve().open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_asr_stream_trace_identity(
    *,
    source_audio_path: Path,
    selection: object,
    duration_sec: float | None,
) -> dict[str, object]:
    """Return the complete result-affecting identity for a native ASR trace."""

    source_audio_path = Path(source_audio_path).resolve()
    source_info = sf.info(str(source_audio_path))
    source_frame_count = int(source_info.frames)
    source_sample_rate_hz = int(source_info.samplerate)
    if source_frame_count < 0 or source_sample_rate_hz < 1:
        raise ValueError(f"invalid source-audio metadata: {source_audio_path}")
    if duration_sec is not None and (
        not math.isfinite(float(duration_sec)) or float(duration_sec) <= 0
    ):
        raise ValueError("duration_sec must be finite and positive")
    duration_limited_frame_count = (
        source_frame_count
        if duration_sec is None
        else min(source_frame_count, round(float(duration_sec) * source_sample_rate_hz))
    )
    asr = dict(selection.asr)  # type: ignore[attr-defined]
    model_asset = dict(asr["model_asset"])
    evaluation_root = Path(__file__).resolve().parents[2]
    code_paths = {
        "shared_trace_adapter": Path(__file__).resolve(),
        "normalizer": evaluation_root / "app/full_pipeline/audio.py",
        "coordinator_adapter": evaluation_root
        / "app/full_pipeline/runtime_components.py",
        "native_worker": evaluation_root / "app/full_pipeline/worker_main.py",
        "stream_contract": evaluation_root / "app/full_pipeline/asr.py",
        "backend_adapter": evaluation_root / str(asr["implementation_path"]),
    }
    return {
        "schema_version": ASR_STREAM_TRACE_IDENTITY_SCHEMA_VERSION,
        "source_audio_sha256": sha256_file(source_audio_path),
        "source_audio_contract": {
            "decoder_id": "soundfile.SoundFile.v1",
            "source_frame_count": source_frame_count,
            "source_sample_rate_hz": source_sample_rate_hz,
            "source_channel_count": int(source_info.channels),
            "expected_source_sample_start": 0,
            "expected_source_sample_end": duration_limited_frame_count,
        },
        "source_duration_limit_sec": (
            None if duration_sec is None else float(duration_sec)
        ),
        "normalization": {
            "policy_id": "full_pipeline_audio_normalization.v1",
            "sample_rate_hz": 16_000,
            "channels": 1,
            "file_source_frame_duration_ms": 100,
            "implementation_sha256": sha256_file(code_paths["normalizer"]),
        },
        "native_stream": {
            "component_id": str(asr["component_id"]),
            "config_sha256": str(asr["config_sha256"]).lower(),
            "model_asset_id": str(model_asset["asset_id"]),
            "model_asset_sha256": str(model_asset["installed_tree_sha256"]).lower(),
            "runtime_config_sha256": str(
                selection.runtime_config_sha256  # type: ignore[attr-defined]
            ).lower(),
            "adapter_policy_id": "full_pipeline_native_sherpa_session.v1",
            "requirements_sha256": str(asr["requirements_sha256"]).lower(),
            "package_identity": str(asr["package_identity"]),
            "result_affecting_code_sha256s": {
                key: sha256_file(path) for key, path in sorted(code_paths.items())
            },
            "partial_final_reset_order_preserved": True,
        },
    }


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.Lock] = {}


def _key_lock(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


@dataclass
class ASRStreamTraceStore:
    """Atomic, content-addressed storage for complete native ASR sessions."""

    root: Path
    replace_attempts: int = 40

    def __post_init__(self) -> None:
        self.root = Path(self.root).expanduser().resolve()
        if self.replace_attempts < 1:
            raise ValueError("replace_attempts must be positive")

    @staticmethod
    def key(identity: Mapping[str, object]) -> str:
        return canonical_sha256(dict(identity))

    def path_for(self, key: str) -> Path:
        _require_sha256(key, "ASR trace key")
        return self.root / key[:2] / f"{key}.json"

    def acquire(self, key: str) -> threading.Lock:
        _require_sha256(key, "ASR trace key")
        lock = _key_lock(key)
        lock.acquire()
        return lock

    def load(
        self, key: str, identity: Mapping[str, object]
    ) -> dict[str, object] | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError(f"ASR trace is not an object: {path}")
        if value.get("schema_version") != ASR_STREAM_TRACE_SCHEMA_VERSION:
            raise ValueError(f"unsupported ASR stream trace schema: {path}")
        if value.get("trace_key_sha256") != key:
            raise ValueError(f"ASR stream trace key mismatch: {path}")
        expected_identity = dict(identity)
        if value.get("identity") != expected_identity:
            raise ValueError(f"ASR stream trace identity mismatch: {path}")
        trace = value.get("trace")
        if not isinstance(trace, Mapping):
            raise ValueError(f"ASR stream trace payload is missing: {path}")
        if canonical_sha256(trace) != value.get("trace_sha256"):
            raise ValueError(f"ASR stream trace checksum mismatch: {path}")
        _validate_complete_trace(identity, trace, context=str(path))
        return dict(trace)

    def publish(
        self,
        key: str,
        identity: Mapping[str, object],
        trace: Mapping[str, object],
    ) -> Path:
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(trace)
        _validate_complete_trace(identity, payload, context="trace publication")
        entry = {
            "schema_version": ASR_STREAM_TRACE_SCHEMA_VERSION,
            "trace_key_sha256": key,
            "identity": dict(identity),
            "trace_sha256": canonical_sha256(payload),
            "trace": payload,
        }
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(entry, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        last_error: PermissionError | None = None
        try:
            for attempt in range(self.replace_attempts):
                try:
                    os.replace(temporary, path)
                    return path
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(min(0.5, 0.01 * (attempt + 1)))
            assert last_error is not None
            raise last_error
        finally:
            temporary.unlink(missing_ok=True)


class ASRStreamTraceAdapter:
    """Record or replay one exact sequence of native ASR interactions.

    The per-key lock is retained from ``start`` through terminal finalization.
    Therefore two accuracy threads racing on the same ASR/source identity have
    one primary producer and one checksum-validated replay consumer.
    """

    def __init__(
        self,
        delegate: object,
        *,
        store: ASRStreamTraceStore,
        identity: Mapping[str, object],
        usage_mode: str,
    ) -> None:
        if usage_mode != "accuracy":
            raise ValueError(
                "native ASR stream traces are accuracy-only and must be disabled "
                "for resource measurement"
            )
        self.delegate = delegate
        self.backend_id = str(delegate.backend_id)  # type: ignore[attr-defined]
        self.worker = getattr(delegate, "worker", None)
        self.store = store
        self.identity = dict(identity)
        self._expected_source_sample_horizon = _expected_source_sample_horizon(
            self.identity
        )
        self.trace_key_sha256 = store.key(self.identity)
        self._lock: threading.Lock | None = None
        self._interactions: list[dict[str, object]] = []
        self._cursor = 0
        self._state = "created"
        self._session_id: str | None = None
        self._producer_session_id: str | None = None
        self._execution_origin: str | None = None
        self._trace_sha256: str | None = None
        self._worker_started = False
        self._published = False
        self._terminal_completeness: dict[str, object] | None = None

    def start(self, session_id: str) -> None:
        if self._state != "created":
            raise RuntimeError("ASR stream trace adapter may only be started once")
        self._lock = self.store.acquire(self.trace_key_sha256)
        self._session_id = str(session_id)
        try:
            cached = self.store.load(self.trace_key_sha256, self.identity)
            if cached is not None:
                raw = cached.get("interactions")
                if not isinstance(raw, list):
                    raise ValueError("ASR stream trace interactions are missing")
                self._interactions = [dict(row) for row in raw]
                self._producer_session_id = str(cached.get("producer_session_id") or "")
                self._execution_origin = "accuracy_replayed"
                self._trace_sha256 = canonical_sha256(cached)
                self._terminal_completeness = dict(
                    cached["terminal_completeness"]  # type: ignore[arg-type]
                )
            else:
                self.delegate.start(session_id)  # type: ignore[attr-defined]
                self._worker_started = True
                self._producer_session_id = str(session_id)
                self._execution_origin = "primary_computed"
            self._state = "running"
        except BaseException:
            self._release_lock()
            raise

    def accept_audio(
        self, frame: NormalizedAudioFrame
    ) -> tuple[Mapping[str, object], ...]:
        self._require_running()
        request = _frame_request(frame)
        if self._execution_origin == "accuracy_replayed":
            return self._replay("accept_audio", request)
        updates = tuple(self.delegate.accept_audio(frame))  # type: ignore[attr-defined]
        self._record("accept_audio", request, updates)
        return updates

    def finalize(self, reason: str) -> tuple[Mapping[str, object], ...]:
        if self._state != "running":
            return ()
        request = {"reason": str(reason)}
        terminal = reason == "input_finished"
        if self._execution_origin == "accuracy_replayed":
            try:
                updates = self._replay("finalize", request)
                if terminal and self._cursor != len(self._interactions):
                    raise ValueError(
                        "ASR stream trace has trailing interactions after terminal finalize"
                    )
                return updates
            finally:
                if terminal:
                    self._state = "finalized"
                    self._release_lock()
        try:
            updates = tuple(self.delegate.finalize(reason))  # type: ignore[attr-defined]
            self._record("finalize", request, updates)
            if terminal:
                completeness = _terminal_completeness(
                    self._interactions,
                    expected_horizon=self._expected_source_sample_horizon,
                )
                self._terminal_completeness = completeness
                if completeness["complete"] is True:
                    trace = {
                        "complete": True,
                        "terminal_reason": str(reason),
                        "terminal_completeness": completeness,
                        "producer_session_id": self._producer_session_id,
                        "interaction_count": len(self._interactions),
                        "interactions": self._interactions,
                        "source_audio_horizons": [
                            dict(row["request"])
                            for row in self._interactions
                            if row["operation"] == "accept_audio"
                        ],
                        "native_processing_latency_preserved": True,
                        "session_scoped_fields_rebound_on_replay": True,
                    }
                    self.store.publish(self.trace_key_sha256, self.identity, trace)
                    self._trace_sha256 = canonical_sha256(trace)
                    self._published = True
            return updates
        finally:
            if terminal:
                self._state = "finalized"
                self._release_lock()

    def reset(self, reason: str) -> tuple[Mapping[str, object], ...]:
        self._require_running()
        request = {"reason": str(reason)}
        if self._execution_origin == "accuracy_replayed":
            return self._replay("reset", request)
        updates = tuple(self.delegate.reset(reason))  # type: ignore[attr-defined]
        self._record("reset", request, updates)
        return updates

    def status(self) -> Mapping[str, object]:
        delegate_status = dict(self.delegate.status())  # type: ignore[attr-defined]
        return {
            **delegate_status,
            "state": self._state,
            "shared_execution": {
                "schema_version": ASR_STREAM_TRACE_SCHEMA_VERSION,
                "trace_key_sha256": self.trace_key_sha256,
                "trace_sha256": self._trace_sha256,
                "execution_origin": self._execution_origin,
                "worker_started": self._worker_started,
                "interaction_cursor": self._cursor,
                "interaction_count": len(self._interactions),
                "trace_published": self._published,
                "terminal_completeness": self._terminal_completeness,
                "recorded_source_audio_horizons_preserved": True,
                "native_processing_latency_preserved": True,
                "session_scoped_fields_rebound_on_replay": True,
                "resource_measurement_eligible": False,
            },
        }

    def close(self) -> None:
        try:
            self.delegate.close()  # type: ignore[attr-defined]
        finally:
            self._state = "closed"
            self._release_lock()

    def _record(
        self,
        operation: str,
        request: Mapping[str, object],
        updates: tuple[Mapping[str, object], ...],
    ) -> None:
        self._interactions.append(
            {
                "sequence": len(self._interactions),
                "operation": operation,
                "request": dict(request),
                "updates": [dict(row) for row in updates],
            }
        )

    def _replay(
        self, operation: str, request: Mapping[str, object]
    ) -> tuple[Mapping[str, object], ...]:
        if self._cursor >= len(self._interactions):
            raise ValueError(f"ASR stream trace ended before {operation}")
        row = self._interactions[self._cursor]
        if row.get("sequence") != self._cursor:
            raise ValueError("ASR stream trace sequence is not contiguous")
        if row.get("operation") != operation or row.get("request") != dict(request):
            raise ValueError(
                f"ASR stream trace interaction mismatch at {self._cursor}: "
                f"expected {operation} {dict(request)}"
            )
        raw_updates = row.get("updates")
        if not isinstance(raw_updates, list):
            raise ValueError("ASR stream trace update rows are invalid")
        self._cursor += 1
        return tuple(self._rebind_session(dict(value)) for value in raw_updates)

    def _rebind_session(self, row: dict[str, object]) -> dict[str, object]:
        session_id = self._session_id
        if not session_id:
            raise RuntimeError("ASR replay lacks its consumer session identity")
        if "session_id" in row:
            row["session_id"] = session_id
        if "hypothesis_id" in row:
            utterance_index = row.get("utterance_index")
            if utterance_index is not None:
                row["hypothesis_id"] = f"{session_id}:asr:{utterance_index}"
            else:
                original = str(row["hypothesis_id"])
                producer = self._producer_session_id or ""
                row["hypothesis_id"] = (
                    session_id + original[len(producer) :]
                    if producer and original.startswith(producer)
                    else original
                )
        return row

    def _require_running(self) -> None:
        if self._state != "running":
            raise RuntimeError("ASR stream trace adapter is not running")

    def _release_lock(self) -> None:
        lock, self._lock = self._lock, None
        if lock is not None:
            lock.release()


def _frame_request(frame: NormalizedAudioFrame) -> dict[str, object]:
    samples = np.ascontiguousarray(frame.samples, dtype=np.float32)
    return {
        "sample_rate_hz": int(frame.sample_rate_hz),
        "normalized_sample_start": int(frame.sample_start),
        "normalized_sample_end": int(frame.sample_end),
        "normalized_start_sec": float(frame.audio_start_sec),
        "normalized_end_sec": float(frame.audio_end_sec),
        "source_sample_rate_hz": int(frame.source_sample_rate_hz),
        "source_sample_start": int(frame.source_sample_start),
        "source_sample_end": int(frame.source_sample_end),
        "source_start_sec": float(frame.source_audio_start_sec),
        "source_end_sec": float(frame.source_audio_end_sec),
        "source_clock_id": str(frame.source_clock_id),
        "source_clock_type": str(frame.source_clock_type),
        "normalized_samples_sha256": hashlib.sha256(samples.tobytes()).hexdigest(),
    }


def _expected_source_sample_horizon(
    identity: Mapping[str, object],
) -> tuple[int, int]:
    contract = identity.get("source_audio_contract")
    if not isinstance(contract, Mapping):
        raise ValueError("ASR stream trace identity lacks a source-audio contract")
    start = contract.get("expected_source_sample_start")
    end = contract.get("expected_source_sample_end")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or isinstance(end, bool)
        or not isinstance(end, int)
        or start < 0
        or end < start
    ):
        raise ValueError("ASR stream trace identity has an invalid source horizon")
    return start, end


def _terminal_completeness(
    interactions: list[dict[str, object]],
    *,
    expected_horizon: tuple[int, int],
) -> dict[str, object]:
    expected_start, expected_end = expected_horizon
    cursor = expected_start
    accepted_frame_count = 0
    failure_reason: str | None = None
    for row in interactions:
        if row.get("operation") != "accept_audio":
            continue
        request = row.get("request")
        if not isinstance(request, Mapping):
            failure_reason = "accept_audio_request_missing"
            break
        start = request.get("source_sample_start")
        end = request.get("source_sample_end")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
        ):
            failure_reason = "source_horizon_invalid"
            break
        if start != cursor:
            failure_reason = "source_horizon_not_contiguous"
            break
        if end <= start or end > expected_end:
            failure_reason = "source_horizon_out_of_bounds"
            break
        cursor = end
        accepted_frame_count += 1
    if failure_reason is None and cursor != expected_end:
        failure_reason = "source_horizon_incomplete"
    complete = failure_reason is None
    return {
        "schema_version": "full-pipeline-asr-terminal-completeness.v1",
        "complete": complete,
        "expected_source_sample_start": expected_start,
        "expected_source_sample_end": expected_end,
        "accepted_source_sample_end": cursor,
        "accepted_frame_count": accepted_frame_count,
        "contiguous_from_source_start": failure_reason
        not in {
            "accept_audio_request_missing",
            "source_horizon_invalid",
            "source_horizon_not_contiguous",
        },
        "failure_reason": failure_reason,
    }


def _validate_complete_trace(
    identity: Mapping[str, object],
    trace: Mapping[str, object],
    *,
    context: str,
) -> None:
    if (
        trace.get("complete") is not True
        or trace.get("terminal_reason") != "input_finished"
    ):
        raise ValueError(f"ASR stream trace is incomplete: {context}")
    interactions = trace.get("interactions")
    if not isinstance(interactions, list) or not all(
        isinstance(row, Mapping) for row in interactions
    ):
        raise ValueError(f"ASR stream trace interactions are invalid: {context}")
    if trace.get("interaction_count") != len(interactions):
        raise ValueError(f"ASR stream trace interaction count mismatch: {context}")
    terminal_interaction = interactions[-1] if interactions else None
    if (
        not isinstance(terminal_interaction, Mapping)
        or terminal_interaction.get("operation") != "finalize"
        or terminal_interaction.get("request") != {"reason": "input_finished"}
    ):
        raise ValueError(f"ASR stream trace lacks its terminal interaction: {context}")
    recomputed = _terminal_completeness(
        [dict(row) for row in interactions],
        expected_horizon=_expected_source_sample_horizon(identity),
    )
    if recomputed["complete"] is not True:
        raise ValueError(f"ASR stream trace source horizon is incomplete: {context}")
    recorded = trace.get("terminal_completeness")
    if not isinstance(recorded, Mapping) or dict(recorded) != recomputed:
        raise ValueError(
            f"ASR stream trace terminal-completeness proof mismatch: {context}"
        )


@dataclass
class SharedWorkerPool:
    """Job-owned workers shared sequentially across case runtimes."""

    pool_id: str
    _workers: dict[tuple[str, str, str, str, str, str], PersistentWorker] = field(
        default_factory=dict, init=False, repr=False
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _closed: bool = field(default=False, init=False, repr=False)

    def acquire(self, spec: WorkerSpec) -> "SharedWorkerLease":
        key = (
            spec.kind,
            spec.component_id,
            spec.environment_profile,
            spec.expected_declared_identity_sha256 or "",
            _warmup_semantic_identity(spec),
            spec.pool_partition_id or "",
        )
        with self._lock:
            if self._closed:
                raise RuntimeError("shared worker pool is closed")
            worker = self._workers.get(key)
            if worker is None:
                worker = PersistentWorker(spec)
                self._workers[key] = worker
            return SharedWorkerLease(worker=worker, pool_id=self.pool_id)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema_version": "full-pipeline-shared-worker-pool.v1",
                "pool_id": self.pool_id,
                "closed": self._closed,
                "workers": [
                    self._workers[key].status() for key in sorted(self._workers)
                ],
            }

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            for key in reversed(sorted(self._workers)):
                self._workers[key].shutdown()
            self._closed = True


@dataclass
class SharedWorkerLease:
    """PersistentWorker-compatible lease whose shutdown preserves the process."""

    worker: PersistentWorker
    pool_id: str
    _asr_session_open: bool = field(default=False, init=False, repr=False)

    @property
    def spec(self) -> WorkerSpec:
        return self.worker.spec

    def start(self) -> dict[str, object]:
        return self.worker.start()

    def call(
        self,
        operation: str,
        payload: Mapping[str, object] | None = None,
        *,
        timeout_sec: float | None = None,
        retry_on_worker_failure: bool = True,
    ) -> dict[str, object]:
        result = self.worker.call(
            operation,
            payload,
            timeout_sec=timeout_sec,
            retry_on_worker_failure=retry_on_worker_failure,
        )
        if self.spec.kind == "native_sherpa_asr":
            if operation in {"start_session", "warmup"}:
                self._asr_session_open = True
            elif operation == "finalize":
                self._asr_session_open = False
        return result

    def reset(self) -> dict[str, object]:
        return self.worker.reset()

    def status(self) -> dict[str, object]:
        return {**self.worker.status(), "shared_worker_pool_id": self.pool_id}

    def shutdown(self) -> None:
        # The lease must leave a stateful ASR decoder at a clean session
        # boundary, but process ownership remains with SharedWorkerPool.
        if self.spec.kind == "native_sherpa_asr" and self._asr_session_open:
            try:
                self.worker.call(
                    "finalize",
                    {"reason": "pooled_lease_release"},
                    retry_on_worker_failure=False,
                )
            finally:
                self._asr_session_open = False


def _require_sha256(value: object, field_name: str) -> str:
    digest = str(value).lower()
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError(f"{field_name} must be a SHA-256 digest")
    return digest


def _warmup_semantic_identity(spec: WorkerSpec) -> str:
    if spec.warmup_request is None:
        return "no_warmup"
    # Per-case paths and session labels do not change the deterministic warmup
    # operation. Audio/config hashes and all other parameters remain bound.
    ignored = {"audio_path", "recording_id", "session_id"}
    return canonical_sha256(
        {
            key: value
            for key, value in dict(spec.warmup_request).items()
            if key not in ignored
        }
    )


__all__ = [
    "ASRStreamTraceAdapter",
    "ASRStreamTraceStore",
    "ASR_STREAM_TRACE_SCHEMA_VERSION",
    "SharedWorkerLease",
    "SharedWorkerPool",
    "build_asr_stream_trace_identity",
]
