"""Periodic Prompt-7 progress, percentage, ETA, and controller logging."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from typing import Mapping

from app.full_pipeline_evaluation.io import read_json, write_json_atomic

from . import scope_fields
from .controller import Layout, layout, status


def publish_progress(root: Path | str) -> dict[str, object]:
    paths = layout(root)
    paths.root.mkdir(parents=True, exist_ok=True)
    current = status(workspace_root=paths.root)
    planned = int(current.get("planned_task_count") or 0)
    terminal = int(current.get("terminal_task_count") or 0)
    percentage, phase = _percentage(paths, planned=planned, terminal=terminal)
    eta = _eta(paths, planned=planned, terminal=terminal)
    value = {
        "schema_version": "full-pipeline-production-hardening-progress.v1",
        **scope_fields(),
        "prompt_index": 7,
        "status": current["status"],
        "overall_percentage": round(percentage, 2),
        "eta_seconds": eta,
        "nominal_planning_target_seconds": 12 * 3600,
        "elapsed_time_kill_switch_enabled": False,
        "phase": phase,
        "detail": (
            f"{terminal}/{planned} hardening tasks terminal"
            if planned
            else "waiting for immutable acceptance plan"
        ),
        "planned_task_count": planned,
        "terminal_task_count": terminal,
        "passed_task_count": current["passed_task_count"],
        "failed_task_count": current["failed_task_count"],
        "updated_at_utc": _utc(),
    }
    write_json_atomic(paths.progress, value)
    return value


def log_event(root: Path | str, *, event: str, detail: object = None) -> None:
    paths = layout(root)
    paths.root.mkdir(parents=True, exist_ok=True)
    row = {
        "timestamp_utc": _utc(),
        "event": event,
        "detail": detail,
    }
    with paths.controller_log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")


class ProgressBridge:
    def __init__(self, root: Path | str, *, interval_sec: float = 10.0) -> None:
        self.root = Path(root)
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        publish_progress(self.root)
        self._thread = threading.Thread(
            target=self._run,
            name="prompt7-progress",
            daemon=True,
        )
        self._thread.start()

    def stop(self, *, phase_hint: str) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(2.0, self.interval_sec + 1.0))
        publish_progress(self.root)
        log_event(self.root, event="progress_bridge_stopped", detail=phase_hint)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_sec):
            publish_progress(self.root)


def _percentage(paths: Layout, *, planned: int, terminal: int) -> tuple[float, str]:
    if paths.completion.is_file():
        return 100.0, "complete"
    if paths.packaging.is_file():
        return 97.0, "finalizing"
    if paths.evidence_index.is_file():
        return 92.0, "packaging"
    if planned:
        return 10.0 + 80.0 * min(1.0, terminal / planned), "hardening"
    if paths.selection.is_file():
        return 7.0, "preparing_hardening"
    if paths.authorization.is_file():
        return 3.0, "selecting"
    return 0.0, "prerequisite_validation"


def _eta(paths: Layout, *, planned: int, terminal: int) -> int | None:
    if paths.completion.is_file():
        return 0
    if not paths.plan.is_file() or planned <= 0:
        return 12 * 3600
    plan = read_json(paths.plan)
    raw_tasks = plan.get("tasks") if isinstance(plan, Mapping) else None
    if not isinstance(raw_tasks, list):
        return None
    remaining = raw_tasks[terminal:]
    seconds = 0.0
    for raw in remaining:
        if not isinstance(raw, Mapping):
            continue
        duration = float(raw.get("duration_sec") or 60.0)
        pace = float(raw.get("pace") or 0.0)
        seconds += duration if pace > 0 else min(duration, 300.0)
        seconds += 120.0
    return int(max(0.0, seconds + 900.0))


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


__all__ = ["ProgressBridge", "log_event", "publish_progress"]
