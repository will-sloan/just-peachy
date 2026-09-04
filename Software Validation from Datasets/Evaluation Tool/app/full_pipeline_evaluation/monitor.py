"""Read-only measured progress snapshots for full-pipeline evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Sequence

from .io import write_json_atomic
from .store import EvaluationJobState, EvaluationStateStore, utc_now


def progress_snapshot(
    store: EvaluationStateStore,
    *,
    campaign_id: str,
    selected_job_ids: Sequence[str] = (),
) -> dict[str, object]:
    rows = store.list_jobs()
    if selected_job_ids:
        selected = set(selected_job_ids)
        rows = tuple(row for row in rows if row.spec.job_id in selected)
    total_cases = sum(row.spec.case_count for row in rows)
    completed_cases = sum(
        min(row.completed_cases, row.spec.case_count) for row in rows
    )
    total_audio = sum(row.spec.audio_duration_sec for row in rows)
    completed_audio = sum(
        min(row.completed_audio_sec, row.spec.audio_duration_sec) for row in rows
    )
    percentage = (
        100.0 * completed_audio / total_audio
        if total_audio > 0
        else (100.0 * completed_cases / total_cases if total_cases else 0.0)
    )
    metadata = store.metadata()
    now = datetime.now(timezone.utc)
    baseline_time = _parse_utc(metadata.get("progress_baseline_utc"))
    baseline_audio = float(metadata.get("progress_baseline_audio_sec", 0.0))
    elapsed = (
        max(0.0, (now - baseline_time).total_seconds())
        if baseline_time is not None
        else None
    )
    measured_audio = max(0.0, completed_audio - baseline_audio)
    measured_rate = (
        measured_audio / elapsed
        if elapsed is not None and elapsed > 0 and measured_audio > 0
        else None
    )
    active = [row for row in rows if row.state == "running"]
    remaining_audio = max(0.0, total_audio - completed_audio)
    eta = (
        remaining_audio / measured_rate
        if active
        and measured_rate is not None
        and measured_rate > 0
        and remaining_audio > 0
        else (0.0 if remaining_audio == 0 and rows else None)
    )
    estimated_finish = (
        (now + timedelta(seconds=eta)).isoformat().replace("+00:00", "Z")
        if eta is not None
        else None
    )
    selected_job_id_set = {row.spec.job_id for row in rows}
    attempt_rows = tuple(
        attempt
        for attempt in store.attempt_rows()
        if attempt.get("job_id") in selected_job_id_set
    )
    failed_attempts = sum(attempt.get("state") == "failed" for attempt in attempt_rows)
    retry_attempts = sum(max(0, row.attempt_count - 1) for row in rows)
    current = active[0] if active else _latest(rows)
    states = {row.state for row in rows}
    if active:
        status = "RUNNING"
    elif rows and states == {"complete"}:
        status = "COMPLETE"
    elif "failed" in states:
        status = "FAILED"
    elif store.stop_requested() or "stopped" in states:
        status = "STOPPED"
    elif any(row.state in {"partial", "complete"} for row in rows):
        status = "PARTIAL"
    else:
        status = "PREPARED"
    resource_rows = [
        row for row in active if row.spec.measurement_mode == "resources"
    ]
    snapshot: dict[str, object] = {
        "schema_version": "full-pipeline-evaluation-progress.v1",
        "campaign_id": campaign_id,
        "status": status,
        "updated_at_utc": utc_now(),
        "phase": _phase(current),
        "current_pipeline_id": current.spec.pipeline_id if current else None,
        "current_protocol_id": current.spec.protocol_id if current else None,
        "current_case_id": current.current_case_id if current else None,
        "planned_jobs": len(rows),
        "complete_jobs": sum(row.state == "complete" for row in rows),
        "running_jobs": len(active),
        "failed_jobs": sum(row.state == "failed" for row in rows),
        "partial_jobs": sum(row.state == "partial" for row in rows),
        "planned_cases": total_cases,
        "completed_cases": completed_cases,
        "planned_audio_sec": total_audio,
        "completed_audio_sec": completed_audio,
        "overall_percentage": max(0.0, min(100.0, percentage)),
        "elapsed_sec": elapsed,
        "eta_sec": eta,
        "eta_basis": (
            {
                "kind": "measured_completed_audio_over_wall_time",
                "baseline_at_utc": metadata.get("progress_baseline_utc"),
                "baseline_audio_sec": baseline_audio,
                "measured_audio_sec": measured_audio,
                "measured_wall_sec": elapsed,
                "measured_audio_per_wall_sec": measured_rate,
            }
            if baseline_time is not None
            else None
        ),
        "estimated_finish_utc": estimated_finish,
        "rolling_rtf": current.rolling_rtf if current else None,
        "current_cpu_percent": current.cpu_percent if current else None,
        "current_rss_mb": current.rss_mb if current else None,
        "current_queue_depth": current.queue_depth if current else None,
        "cache_hits": sum(row.cache_hits for row in rows),
        "failures": failed_attempts,
        "retries": retry_attempts,
        "latest_activity": current.latest_activity if current else None,
        "resource_measurement_concurrency": len(resource_rows),
        "resource_measurement_serial": len(resource_rows) <= 1,
        "jobs": [_job_progress(row) for row in rows],
    }
    return snapshot


def publish_progress(
    store: EvaluationStateStore,
    *,
    campaign_id: str,
    output_path: Path,
    selected_job_ids: Sequence[str] = (),
) -> dict[str, object]:
    value = progress_snapshot(
        store, campaign_id=campaign_id, selected_job_ids=selected_job_ids
    )
    write_json_atomic(output_path, value)
    return value


def _job_progress(row: EvaluationJobState) -> dict[str, object]:
    percent = (
        100.0 * row.completed_audio_sec / row.spec.audio_duration_sec
        if row.spec.audio_duration_sec > 0
        else 100.0 * row.completed_cases / row.spec.case_count
    )
    return {
        "job_id": row.spec.job_id,
        "pipeline_id": row.spec.pipeline_id,
        "protocol_id": row.spec.protocol_id,
        "source_key": row.spec.source_key,
        "split": row.spec.split,
        "measurement_mode": row.spec.measurement_mode,
        "state": row.state,
        "completed_cases": row.completed_cases,
        "planned_cases": row.spec.case_count,
        "completed_audio_sec": row.completed_audio_sec,
        "planned_audio_sec": row.spec.audio_duration_sec,
        "percentage": max(0.0, min(100.0, percent)),
        "current_case_id": row.current_case_id,
        "rolling_rtf": row.rolling_rtf,
        "cpu_percent": row.cpu_percent,
        "rss_mb": row.rss_mb,
        "queue_depth": row.queue_depth,
        "cache_hits": row.cache_hits,
        "retry_count": row.retry_count,
        "attempt_count": row.attempt_count,
        "latest_activity": row.latest_activity,
        "last_error": row.last_error,
        "updated_at_utc": row.updated_at_utc,
    }


def _phase(row: EvaluationJobState | None) -> str:
    if row is None:
        return "not_prepared"
    return f"{row.spec.split}:{row.spec.measurement_mode}:{row.state}"


def _latest(rows: Sequence[EvaluationJobState]) -> EvaluationJobState | None:
    return max(rows, key=lambda row: row.updated_at_utc) if rows else None


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc)
