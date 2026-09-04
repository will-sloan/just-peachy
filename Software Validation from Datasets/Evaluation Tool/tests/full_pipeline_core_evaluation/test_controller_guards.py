from __future__ import annotations

from pathlib import Path

import pytest

from app.full_pipeline_core_evaluation import controller


def test_accuracy_rejects_more_than_two_jobs_before_opening_workspace(
    tmp_path: Path,
) -> None:
    with pytest.raises(Exception, match="parallel_jobs"):
        controller.run_accuracy(
            workspace_root=tmp_path,
            prompt4_marker=tmp_path / "not-opened.json",
            parallel_jobs=3,
        )


def test_status_is_inert_for_unprepared_workspace(tmp_path: Path) -> None:
    value = controller.status(workspace_root=tmp_path)

    assert value["stages"]["accuracy"]["status"] == "NOT_PREPARED"
    assert value["stages"]["resources"]["status"] == "NOT_PREPARED"
