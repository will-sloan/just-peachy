"""Atomic, non-scientific progress reporting for speaker-protocol evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import threading
import time
from typing import Mapping

import psutil


class EvaluationProgress:
    """Write lightweight progress without participating in scientific scoring."""

    def __init__(self, root: Path, *, backend: str, workers: int) -> None:
        self.path = root.resolve() / "evaluation_progress.json"
        self.backend = backend
        self.workers = workers
        self.started_wall = datetime.now(timezone.utc)
        self.started_clock = time.perf_counter()
        self.phase_wall = self.started_wall
        self.phase_clock = self.started_clock
        self.last_write = 0.0
        self.phase_name = "STARTING"
        self.process = psutil.Process()
        self.process.cpu_percent(interval=None)
        self.update("STARTING", status="RUNNING", force=True)

    def update(
        self,
        phase: str,
        *,
        status: str = "RUNNING",
        completed: int | None = None,
        total: int | None = None,
        force: bool = False,
        details: Mapping[str, object] | None = None,
    ) -> None:
        now_clock = time.perf_counter()
        now_wall = datetime.now(timezone.utc)
        if phase != self.phase_name:
            self.phase_name = phase
            self.phase_clock = now_clock
            self.phase_wall = now_wall
            force = True
        if not force and now_clock - self.last_write < 5.0:
            return
        phase_elapsed = max(now_clock - self.phase_clock, 0.0)
        rate = completed / phase_elapsed if completed is not None and phase_elapsed > 0 else None
        remaining = (
            (total - completed) / rate
            if completed is not None and total is not None and rate and completed < total
            else None
        )
        payload = {
            "schema_version": "speaker-protocol-evaluation-progress.v1",
            "backend": self.backend,
            "phase": phase,
            "workers": self.workers,
            "math_threads_per_worker": 1,
            "pid": os.getpid(),
            "started_at": self.started_wall.isoformat(),
            "updated_at": now_wall.isoformat(),
            "elapsed_sec": now_clock - self.started_clock,
            "phase_started_at": self.phase_wall.isoformat(),
            "phase_elapsed_sec": phase_elapsed,
            "status": status,
            "bootstrap_completed": completed if phase == "BOOTSTRAP" else None,
            "bootstrap_total": total if phase == "BOOTSTRAP" else None,
            "bootstrap_percent": (
                100.0 * completed / total
                if phase == "BOOTSTRAP" and completed is not None and total
                else None
            ),
            "bootstrap_per_second": rate if phase == "BOOTSTRAP" else None,
            "estimated_remaining_sec": remaining,
            "estimated_completion_time": (
                (now_wall + timedelta(seconds=remaining)).isoformat()
                if remaining is not None
                else None
            ),
            "current_memory_mb": self.process.memory_info().rss / (1024 * 1024),
            "cpu_percent": self.process.cpu_percent(interval=None),
            **dict(details or {}),
        }
        if _write_json_atomic(self.path, payload):
            self.last_write = now_clock

    def fail(self, message: str) -> None:
        self.update("FAILED", status="FAILED", force=True, details={"error": message})


def _write_json_atomic(path: Path, value: Mapping[str, object]) -> bool:
    """Publish progress atomically without letting a Windows reader abort science."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        deadline = time.monotonic() + 2.0
        while True:
            try:
                os.replace(temporary, path)
                return True
            except OSError as exc:
                sharing_violation = isinstance(exc, PermissionError) or getattr(
                    exc, "winerror", None
                ) in {5, 32}
                if not sharing_violation:
                    raise
                if time.monotonic() >= deadline:
                    # Progress is explicitly non-scientific. A long-lived reader
                    # may miss one update, but must never terminate evaluation.
                    return False
                time.sleep(0.05)
    finally:
        temporary.unlink(missing_ok=True)
