"""Persistent isolated-environment JSONL workers for the full pipeline."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
from typing import Mapping
import uuid

WORKER_PROTOCOL = "full-pipeline-worker-jsonl.v1"
TOOL_ROOT = Path(__file__).resolve().parents[2]


class WorkerError(RuntimeError):
    """Base error for isolated runtime workers."""


class WorkerStartupError(WorkerError):
    """Worker did not become ready before its startup deadline."""


class WorkerExitedError(WorkerError):
    """Worker exited or closed its response pipe unexpectedly."""


class WorkerTimeoutError(WorkerError):
    """Worker did not answer a request before its deadline."""


class WorkerRequestError(WorkerError):
    """Worker returned a structured component failure."""


@dataclass(frozen=True)
class WorkerSpec:
    worker_id: str
    kind: str
    component_id: str
    environment_profile: str
    # A semantic role boundary for pools that intentionally reuse processes
    # across case-specific worker IDs.  ``None`` preserves the historical
    # component-level sharing contract.  Distinct non-empty partitions force
    # otherwise identical models into independent processes (for example the
    # R1 diarization-versus-identity resource ablation).
    pool_partition_id: str | None = None
    startup_timeout_sec: float = 90.0
    request_timeout_sec: float = 180.0
    shutdown_timeout_sec: float = 10.0
    restart_limit: int = 1
    expected_declared_identity_sha256: str | None = None
    warmup_request: Mapping[str, object] | None = None
    command_override: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if (
            not self.worker_id.strip()
            or not self.kind.strip()
            or not self.component_id.strip()
        ):
            raise WorkerStartupError(
                "worker_id, kind, and component_id must be non-empty"
            )
        if self.startup_timeout_sec <= 0 or self.request_timeout_sec <= 0:
            raise WorkerStartupError("worker timeouts must be positive")
        if self.shutdown_timeout_sec <= 0 or self.restart_limit < 0:
            raise WorkerStartupError("invalid shutdown timeout or restart limit")
        if self.pool_partition_id is not None and not self.pool_partition_id.strip():
            raise WorkerStartupError("pool_partition_id must be non-empty when set")
        expected = self.expected_declared_identity_sha256
        if expected is not None and (
            len(expected) != 64
            or any(
                character not in "0123456789abcdef" for character in expected.lower()
            )
        ):
            raise WorkerStartupError("expected identity must be a SHA-256 digest")

    def command(self) -> list[str]:
        if self.command_override:
            return list(self.command_override)
        from app.controlled_diarization.runner import interpreter_for_profile

        interpreter = interpreter_for_profile(self.environment_profile)
        if interpreter is None or not interpreter.is_file():
            raise WorkerStartupError(
                f"environment unavailable: {self.environment_profile}"
            )
        return [
            str(interpreter),
            "-u",
            "-m",
            "app.full_pipeline.worker_main",
            "--worker-id",
            self.worker_id,
            "--kind",
            self.kind,
            "--component",
            self.component_id,
        ]


def segmentation_worker_spec(
    *, worker_id: str = "pyannote-segmentation", **overrides: object
) -> WorkerSpec:
    return WorkerSpec(
        worker_id=worker_id,
        kind="pyannote_segmentation",
        component_id="pyannote_segmentation_3_0",
        environment_profile="credential-diarization",
        **overrides,
    )


def asr_worker_spec(
    backend_id: str, *, worker_id: str | None = None, **overrides: object
) -> WorkerSpec:
    if backend_id not in {
        "sherpa_onnx",
        "sherpa_onnx_libri_giga_zipformer_2023_06_21",
    }:
        raise WorkerStartupError(f"unsupported streaming ASR backend: {backend_id}")
    return WorkerSpec(
        worker_id=worker_id or f"asr-{backend_id}",
        kind="native_sherpa_asr",
        component_id=backend_id,
        environment_profile="onnx",
        **overrides,
    )


def embedding_worker_spec(
    backend_id: str, *, worker_id: str | None = None, **overrides: object
) -> WorkerSpec:
    # The registry/policy remains authoritative for environment selection.
    from app.speaker_protocol.contracts import eligible_embedding_backends

    eligible = eligible_embedding_backends(backend_ids={backend_id})
    if backend_id not in eligible:
        raise WorkerStartupError(f"embedding backend is not qualified: {backend_id}")
    return WorkerSpec(
        worker_id=worker_id or f"embedding-{backend_id}",
        kind="speaker_embedding",
        component_id=backend_id,
        environment_profile=str(eligible[backend_id]["environment_profile"]),
        **overrides,
    )


@dataclass
class PersistentWorker:
    """One sequential request channel with health, restart, and clean shutdown."""

    spec: WorkerSpec
    process: subprocess.Popen[str] | None = field(default=None, init=False)
    ready_identity: dict[str, object] | None = field(default=None, init=False)
    restart_count: int = field(default=0, init=False)
    _responses: queue.Queue[dict[str, object]] = field(
        default_factory=queue.Queue, init=False, repr=False
    )
    _stderr_tail: deque[str] = field(
        default_factory=lambda: deque(maxlen=80), init=False, repr=False
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock, init=False, repr=False
    )
    _sequence: int = field(default=0, init=False, repr=False)

    @property
    def pid(self) -> int | None:
        return (
            self.process.pid
            if self.process is not None and self.process.poll() is None
            else None
        )

    @property
    def running(self) -> bool:
        return self.pid is not None

    @property
    def stderr_tail(self) -> tuple[str, ...]:
        return tuple(self._stderr_tail)

    def start(self) -> dict[str, object]:
        with self._lock:
            if self.running and self.ready_identity is not None:
                return dict(self.ready_identity)
            self._launch()
            ready = self._await_message(
                timeout_sec=self.spec.startup_timeout_sec,
                expected_type="ready",
                phase="startup",
            )
            if ready.get("protocol") != WORKER_PROTOCOL:
                self._terminate()
                raise WorkerStartupError("worker protocol identity mismatch")
            identity = ready.get("identity")
            if not isinstance(identity, Mapping):
                self._terminate()
                raise WorkerStartupError("worker did not report a model identity")
            expected = self.spec.expected_declared_identity_sha256
            observed = identity.get("declared_identity_sha256")
            if expected is not None and str(observed).lower() != expected.lower():
                self._terminate()
                raise WorkerStartupError(
                    f"worker identity mismatch: expected {expected}, observed {observed}"
                )
            self.ready_identity = dict(identity)
            if self.spec.warmup_request:
                try:
                    response = self._request_locked(
                        "warmup",
                        dict(self.spec.warmup_request),
                        timeout_sec=self.spec.request_timeout_sec,
                    )
                    status = str(response.get("status") or "").lower()
                    if status not in {"ok", "running", "healthy", "pass"}:
                        raise WorkerStartupError(
                            f"worker warmup failed with status {status or 'missing'}"
                        )
                    warm_identity = response.get("identity")
                    if not isinstance(warm_identity, Mapping):
                        raise WorkerStartupError(
                            "worker warmup omitted the model identity"
                        )
                    self.ready_identity = dict(warm_identity)
                except Exception:
                    self._terminate()
                    self.ready_identity = None
                    raise
            return dict(self.ready_identity)

    def call(
        self,
        operation: str,
        payload: Mapping[str, object] | None = None,
        *,
        timeout_sec: float | None = None,
        retry_on_worker_failure: bool = True,
    ) -> dict[str, object]:
        with self._lock:
            attempts = 0
            while True:
                if not self.running:
                    self.start()
                try:
                    return self._request_locked(
                        operation,
                        dict(payload or {}),
                        timeout_sec=timeout_sec or self.spec.request_timeout_sec,
                    )
                except (WorkerExitedError, WorkerTimeoutError):
                    if (
                        not retry_on_worker_failure
                        or attempts >= self.spec.restart_limit
                    ):
                        raise
                    attempts += 1
                    self.restart_count += 1
                    self._terminate()
                    self.ready_identity = None

    def health(self) -> dict[str, object]:
        return self.call("ping", retry_on_worker_failure=True)

    def reset(self) -> dict[str, object]:
        return self.call("reset", retry_on_worker_failure=True)

    def restart(self) -> dict[str, object]:
        with self._lock:
            self._terminate()
            self.ready_identity = None
            self.restart_count += 1
            return self.start()

    def shutdown(self) -> None:
        with self._lock:
            process = self.process
            if process is None:
                return
            if process.poll() is None:
                try:
                    self._request_locked(
                        "shutdown", {}, timeout_sec=self.spec.shutdown_timeout_sec
                    )
                except WorkerError:
                    pass
            self._terminate()
            # Preserve the last successfully reported identity for final
            # provenance/status after the process has shut down.  ``start``
            # always replaces it with the identity from the new generation.

    def status(self) -> dict[str, object]:
        return {
            "worker_id": self.spec.worker_id,
            "kind": self.spec.kind,
            "component_id": self.spec.component_id,
            "environment_profile": self.spec.environment_profile,
            "pool_partition_id": self.spec.pool_partition_id,
            "pid": self.pid,
            "running": self.running,
            "restart_count": self.restart_count,
            "identity": self.ready_identity,
            "stderr_tail": list(self._stderr_tail),
        }

    def _launch(self) -> None:
        # Reader threads from a terminated generation can finish after a restart.
        # Give each generation private sinks so a late EOF/protocol row cannot be
        # injected into the replacement worker's response channel.
        responses: queue.Queue[dict[str, object]] = queue.Queue()
        stderr_tail: deque[str] = deque(maxlen=80)
        self._responses = responses
        self._stderr_tail = stderr_tail
        creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            self.spec.command(),
            cwd=TOOL_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            shell=False,
            creationflags=creation_flags,
        )
        self.process = process
        threading.Thread(
            target=self._read_stdout,
            args=(process, responses),
            name=f"{self.spec.worker_id}-stdout",
            daemon=True,
        ).start()
        threading.Thread(
            target=self._read_stderr,
            args=(process, stderr_tail),
            name=f"{self.spec.worker_id}-stderr",
            daemon=True,
        ).start()

    def _request_locked(
        self, operation: str, payload: Mapping[str, object], *, timeout_sec: float
    ) -> dict[str, object]:
        process = self.process
        if process is None or process.poll() is not None or process.stdin is None:
            raise WorkerExitedError(self._exit_message("worker is not running"))
        self._sequence += 1
        request_id = (
            f"{self.spec.worker_id}-{self._sequence:08d}-{uuid.uuid4().hex[:8]}"
        )
        request = {
            "protocol": WORKER_PROTOCOL,
            "type": "request",
            "request_id": request_id,
            "operation": operation,
            "payload": dict(payload),
        }
        try:
            process.stdin.write(json.dumps(request, sort_keys=True) + "\n")
            process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise WorkerExitedError(self._exit_message(str(exc))) from exc
        response = self._await_message(
            timeout_sec=timeout_sec,
            request_id=request_id,
            expected_type="response",
            phase=operation,
        )
        if response.get("ok") is not True:
            error = response.get("error")
            raise WorkerRequestError(
                f"{self.spec.worker_id} {operation} failed: {error}"
            )
        result = response.get("result")
        return dict(result) if isinstance(result, Mapping) else {"value": result}

    def _await_message(
        self,
        *,
        timeout_sec: float,
        expected_type: str,
        phase: str,
        request_id: str | None = None,
    ) -> dict[str, object]:
        deadline = time.monotonic() + timeout_sec
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._terminate()
                error_type = (
                    WorkerStartupError if phase == "startup" else WorkerTimeoutError
                )
                raise error_type(
                    self._exit_message(f"{phase} timed out after {timeout_sec:.3f}s")
                )
            try:
                row = self._responses.get(timeout=min(0.1, remaining))
            except queue.Empty:
                if self.process is not None and self.process.poll() is not None:
                    raise WorkerExitedError(
                        self._exit_message(f"exited during {phase}")
                    )
                continue
            if row.get("type") == "eof":
                raise WorkerExitedError(
                    self._exit_message(f"closed stdout during {phase}")
                )
            if row.get("type") == "protocol_error":
                raise WorkerExitedError(self._exit_message(str(row.get("error"))))
            if row.get("type") != expected_type:
                continue
            if request_id is not None and row.get("request_id") != request_id:
                continue
            return row

    def _read_stdout(
        self,
        process: subprocess.Popen[str],
        responses: queue.Queue[dict[str, object]],
    ) -> None:
        stream = process.stdout
        if stream is None:
            responses.put({"type": "eof"})
            return
        try:
            for line in stream:
                try:
                    value = json.loads(line)
                    if not isinstance(value, dict):
                        raise ValueError("worker row is not an object")
                    responses.put(value)
                except Exception as exc:
                    responses.put(
                        {
                            "type": "protocol_error",
                            "error": f"invalid worker JSON: {exc}",
                        }
                    )
        finally:
            responses.put({"type": "eof"})

    @staticmethod
    def _read_stderr(process: subprocess.Popen[str], stderr_tail: deque[str]) -> None:
        stream = process.stderr
        if stream is None:
            return
        for line in stream:
            stderr_tail.append(line.rstrip())

    def _terminate(self) -> None:
        process = self.process
        if process is None:
            return
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=self.spec.shutdown_timeout_sec)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=max(1.0, self.spec.shutdown_timeout_sec))
        self.process = None

    def _exit_message(self, message: str) -> str:
        process = self.process
        exit_code = process.poll() if process is not None else None
        tail = " | ".join(self._stderr_tail)
        suffix = f"; stderr={tail[-4000:]}" if tail else ""
        return f"{self.spec.worker_id}: {message}; exit_code={exit_code}{suffix}"

    def __enter__(self) -> "PersistentWorker":
        self.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.shutdown()


class WorkerSupervisor:
    """Own a set of persistent workers without mixing their environments."""

    def __init__(self, specs: tuple[WorkerSpec, ...] = ()) -> None:
        self._workers: dict[str, PersistentWorker] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: WorkerSpec) -> PersistentWorker:
        if spec.worker_id in self._workers:
            raise WorkerStartupError(f"duplicate worker_id: {spec.worker_id}")
        worker = PersistentWorker(spec)
        self._workers[spec.worker_id] = worker
        return worker

    def worker(self, worker_id: str) -> PersistentWorker:
        try:
            return self._workers[worker_id]
        except KeyError as exc:
            raise WorkerStartupError(f"unknown worker_id: {worker_id}") from exc

    def start_all(self) -> dict[str, dict[str, object]]:
        started: dict[str, dict[str, object]] = {}
        try:
            for worker_id in sorted(self._workers):
                started[worker_id] = self._workers[worker_id].start()
            return started
        except Exception:
            self.shutdown()
            raise

    def health(self) -> dict[str, dict[str, object]]:
        return {
            worker_id: self._workers[worker_id].health()
            for worker_id in sorted(self._workers)
        }

    def status(self) -> dict[str, object]:
        return {
            "schema_version": "full-pipeline-worker-supervisor-status.v1",
            "workers": [self._workers[key].status() for key in sorted(self._workers)],
        }

    def shutdown(self) -> None:
        for worker_id in reversed(sorted(self._workers)):
            self._workers[worker_id].shutdown()

    def __enter__(self) -> "WorkerSupervisor":
        self.start_all()
        return self

    def __exit__(self, *_args: object) -> None:
        self.shutdown()
