from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.full_pipeline_evaluation import controller
from app.full_pipeline_evaluation.host_lock import HostRunLock, HostRunLockError


def test_host_lock_excludes_a_second_process(tmp_path: Path) -> None:
    lock_path = tmp_path / "controller.lock"
    script = (
        "from pathlib import Path; "
        "from app.full_pipeline_evaluation.host_lock import HostRunLock; "
        f"lock=HostRunLock(Path({str(lock_path)!r}), measurement_mode='resources'); "
        "lock.__enter__()"
    )
    with HostRunLock(lock_path, measurement_mode="accuracy"):
        completed = subprocess.run(
            [sys.executable, "-c", script],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode != 0
        assert "another full-pipeline evaluation controller is active" in completed.stderr

    with HostRunLock(lock_path, measurement_mode="resources"):
        pass


def test_same_process_second_handle_is_rejected(tmp_path: Path) -> None:
    lock_path = tmp_path / "controller.lock"
    with HostRunLock(lock_path, measurement_mode="accuracy"):
        with pytest.raises(HostRunLockError):
            with HostRunLock(lock_path, measurement_mode="resources"):
                pass


def test_controller_run_is_host_exclusive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    default_workspace = tmp_path / "automated_runs" / "default"
    monkeypatch.setattr(controller, "DEFAULT_WORKSPACE_ROOT", default_workspace)
    monkeypatch.setattr(
        controller,
        "_run_locked",
        lambda **_kwargs: {"status": "COMPLETE", "host_lock_exercised": True},
    )
    kwargs = {
        "workspace_root": tmp_path / "selected",
        "split": "development",
        "measurement_mode": "accuracy",
        "pipeline_ids": (),
        "protocol_ids": (),
        "parallel_jobs": 2,
        "job_executor": None,
    }
    lock_path = default_workspace.parent / ".full_pipeline_evaluation.host.lock"
    with HostRunLock(lock_path, measurement_mode="resources"):
        with pytest.raises(HostRunLockError):
            controller._run(**kwargs)

    assert controller._run(**kwargs)["host_lock_exercised"] is True
