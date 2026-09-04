"""Compact, periodically refreshed Prompt-6 progress bridge."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.full_pipeline_evaluation.store import EvaluationStateStore

from . import scope_fields
from .io import read_json, write_json_atomic


def publish_program_progress(paths: object) -> dict[str, object]:
    root = Path(getattr(paths, "root"))
    database = Path(getattr(paths, "database"))
    output = Path(getattr(paths, "program_progress"))
    if not database.is_file():
        value = {
            "schema_version": "full-pipeline-eight-day-program-progress.v1",
            **scope_fields(),
            "overall_percentage": 0.0,
            "eta_seconds": None,
            "phase": "not_prepared",
            "detail": "Run Prepare to freeze the bounded Prompt-6 panel.",
            "total_jobs": 0,
            "terminal_jobs": 0,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(output, value)
        return value
    store = EvaluationStateStore(database)
    jobs = store.list_jobs()
    counts: dict[str, int] = {}
    for row in jobs:
        counts[row.state] = counts.get(row.state, 0) + 1
    terminal = counts.get("complete", 0) + counts.get("failed", 0)
    total = len(jobs)
    percentage = 100.0 * terminal / total if total else 0.0
    eta: float | None = None
    state_path = root / "controller_state.json"
    if state_path.is_file() and terminal and terminal < total:
        state = read_json(state_path)
        started = _timestamp(state.get("stage_started_at_utc"))
        if started is not None:
            elapsed = max(0.0, (datetime.now(timezone.utc) - started).total_seconds())
            eta = elapsed / terminal * (total - terminal)
    completion = Path(getattr(paths, "completion"))
    running = counts.get("running", 0)
    if completion.is_file():
        phase = "complete"
        detail = "Bounded Prompt 6 completed and its universal envelope is available."
        percentage = 100.0
        eta = 0.0
    elif running:
        phase = "running"
        detail = f"{running} job(s) running; {terminal}/{total} terminal."
    elif counts.get("stopped", 0):
        phase = "stopped"
        detail = "A restart-safe stop is active; RunAll resumes retained work."
    elif terminal == total and total:
        phase = "analysis_pending"
        detail = "All jobs are terminal; analysis/finalization remains."
    else:
        phase = "prepared"
        detail = f"{terminal}/{total} jobs terminal."
    value = {
        "schema_version": "full-pipeline-eight-day-program-progress.v1",
        **scope_fields(),
        "overall_percentage": round(percentage, 3),
        "eta_seconds": round(eta, 1) if eta is not None else None,
        "phase": phase,
        "detail": detail,
        "total_jobs": total,
        "terminal_jobs": terminal,
        "state_counts": counts,
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output, value)
    return value


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


__all__ = ["publish_program_progress"]
