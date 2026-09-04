"""Overall Prompt-5 progress bridge for the eight-day controller."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import threading
from typing import Mapping

from app.full_pipeline_evaluation.io import read_json, write_json_atomic

from .controller import Layout, layout
from .io import ensure_c_drive, scope_fields


def progress_path(paths: Layout) -> Path:
    raw = os.environ.get("JP8_PROGRESS_RECORD")
    return (
        ensure_c_drive(raw, label="Prompt-5 progress record")
        if raw
        else paths.root / "program_progress.json"
    )


def publish_program_progress(
    paths: Layout,
    *,
    phase_hint: str | None = None,
) -> dict[str, object]:
    accuracy = _optional_json(paths.accuracy / "campaign_progress.json")
    resources = _optional_json(paths.resources / "campaign_progress.json")
    accuracy_percent = float(accuracy.get("overall_percentage") or 0.0)
    resource_percent = float(resources.get("overall_percentage") or 0.0)
    prepared = (paths.root / "preparation.json").is_file()
    analyzed = (paths.report / "analysis.json").is_file()
    collected = (paths.root / "collection.json").is_file()
    completed = paths.completion_marker.is_file() or bool(
        os.environ.get("JP8_COMPLETION_RECORD")
        and Path(os.environ["JP8_COMPLETION_RECORD"]).is_file()
    )
    percentage = (
        2.0 * int(prepared)
        + 82.0 * accuracy_percent / 100.0
        + 9.0 * resource_percent / 100.0
        + 4.0 * int(analyzed)
        + 2.0 * int(collected)
        + 1.0 * int(completed)
    )
    eta = _eta(accuracy, resources, accuracy_percent, resource_percent)
    phase = phase_hint or _phase(
        completed=completed,
        collected=collected,
        analyzed=analyzed,
        resources=resources,
        accuracy=accuracy,
        prepared=prepared,
    )
    detail = (
        resources.get("latest_activity")
        if resources and resource_percent < 100
        else accuracy.get("latest_activity")
        if accuracy and accuracy_percent < 100
        else phase
    )
    value = {
        "schema_version": "full-pipeline-core-progress.v1",
        **scope_fields(),
        "prompt_index": 5,
        "status": "COMPLETE"
        if completed
        else "RUNNING"
        if prepared
        else "NOT_PREPARED",
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": phase,
        "overall_percentage": max(0.0, min(100.0, percentage)),
        "eta_seconds": eta,
        "detail": str(detail or phase),
        "stages": {
            "preparation": {"weight_percent": 2.0, "complete": prepared},
            "accuracy": {
                "weight_percent": 82.0,
                "percentage": accuracy_percent,
                "progress": accuracy,
            },
            "serial_resources": {
                "weight_percent": 9.0,
                "percentage": resource_percent,
                "progress": resources,
            },
            "analysis": {"weight_percent": 4.0, "complete": analyzed},
            "collection": {"weight_percent": 2.0, "complete": collected},
            "completion": {"weight_percent": 1.0, "complete": completed},
        },
    }
    target = progress_path(paths)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(target, value)
    return value


class ProgressBridge:
    """Poll campaign snapshots while the blocking stage adapter runs."""

    def __init__(self, workspace_root: Path, *, interval_sec: float = 5.0) -> None:
        self.paths = layout(workspace_root)
        self.interval_sec = interval_sec
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="prompt5-progress-bridge", daemon=True
        )

    def start(self) -> None:
        publish_program_progress(self.paths, phase_hint="admission_and_preparation")
        self._thread.start()

    def stop(self, *, phase_hint: str | None = None) -> None:
        self._stop.set()
        self._thread.join(timeout=max(2.0, self.interval_sec * 2))
        publish_program_progress(self.paths, phase_hint=phase_hint)

    def _run(self) -> None:
        while not self._stop.wait(self.interval_sec):
            try:
                publish_program_progress(self.paths)
            except Exception:
                # Progress telemetry cannot mutate or cancel scientific work. The
                # final validator still requires all scientific artifacts.
                continue


def _optional_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def _eta(
    accuracy: Mapping[str, object],
    resources: Mapping[str, object],
    accuracy_percent: float,
    resource_percent: float,
) -> float | None:
    if accuracy_percent < 100:
        value = accuracy.get("eta_sec")
        return float(value) if isinstance(value, (int, float)) else None
    if resource_percent < 100:
        value = resources.get("eta_sec")
        return float(value) if isinstance(value, (int, float)) else None
    return 0.0 if accuracy_percent >= 100 and resource_percent >= 100 else None


def _phase(
    *,
    completed: bool,
    collected: bool,
    analyzed: bool,
    resources: Mapping[str, object],
    accuracy: Mapping[str, object],
    prepared: bool,
) -> str:
    if completed:
        return "complete"
    if collected:
        return "final_validation"
    if analyzed:
        return "collection"
    if resources:
        return "serial_resources"
    if accuracy:
        return "accuracy"
    return "prepared" if prepared else "admission"
