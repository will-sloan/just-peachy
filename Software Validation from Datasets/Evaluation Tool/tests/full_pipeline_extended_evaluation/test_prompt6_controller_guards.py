from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from app.full_pipeline_extended_evaluation import controller


def test_accuracy_rejects_more_than_two_jobs_before_opening_inputs(
    tmp_path: Path,
) -> None:
    with pytest.raises(Exception, match="parallelism"):
        controller.run_accuracy(
            workspace_root=tmp_path,
            predecessor_path=tmp_path / "not-opened.json",
            parallel_jobs=3,
        )


def test_unprepared_status_has_required_progress_fields(tmp_path: Path) -> None:
    value = controller.status(workspace_root=tmp_path)
    progress = value["progress"]

    assert value["status"] == "PASS"
    assert progress["phase"] == "not_prepared"
    assert progress["overall_percentage"] == 0.0
    assert "eta_seconds" in progress
    assert "detail" in progress


def test_nominal_30_hour_target_is_not_an_elapsed_time_kill_switch() -> None:
    source = inspect.getsource(controller._monitor_run)
    assert "BLOCKED_PROMPT6_30_HOUR_STAGE_CAP" not in source
    assert "deadline" not in source.casefold()
    assert "BLOCKED_C_DRIVE_RESERVE_35_GIB" in source
