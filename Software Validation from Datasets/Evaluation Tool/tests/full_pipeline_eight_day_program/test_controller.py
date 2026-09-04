from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

import pytest

from app.full_pipeline_eight_day_program.controller import GIB, ProgramController
from app.full_pipeline_eight_day_program.storage import (
    ControllerLock,
    ProgramContractError,
    atomic_write_json,
)
from app.full_pipeline_eight_day_program import storage
from tests.full_pipeline_eight_day_program.test_contracts import build_config


def test_automatic_transition_validates_prompt4_and_prompt5_then_stops_not_ready(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path)
    controller = ProgramController(config, free_bytes_provider=lambda _: 100 * GIB)
    assert controller.run() == "NOT_READY"
    state = json.loads((tmp_path / "program/program_state.json").read_text())
    assert state["stages"]["4"]["status"] == "COMPLETE"
    assert state["stages"]["5"]["status"] == "COMPLETE"
    assert state["stages"]["4"]["elapsed_seconds"] is not None
    assert state["stages"]["4"]["contingency_consumed_seconds"] == 0
    assert state["stages"]["6"]["status"] == "NOT_READY"
    assert not (tmp_path / "program/prompt_6/completion.json").exists()
    events = [
        json.loads(line)
        for line in (tmp_path / "program/milestones.jsonl").read_text().splitlines()
    ]
    types = [row["event_type"] for row in events]
    assert types.index("STAGE_COMPLETED_AND_VALIDATED") < types.index(
        "AUTOMATIC_TRANSITION_ADMITTED"
    )
    assert types[-1] == "STAGE_NOT_READY"
    prompt5_preflight = json.loads(
        Path(state["stages"]["5"]["latest_preflight"]).read_text()
    )
    predecessor_rows = [
        row
        for row in prompt5_preflight["material_paths"]
        if row["class"] == "predecessor_completion_input"
    ]
    assert len(predecessor_rows) == 1
    assert predecessor_rows[0]["sha256"] == state["stages"]["4"][
        "completion_record_sha256"
    ]


def test_completed_artifact_tampering_prevents_revalidation(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    controller = ProgramController(config, free_bytes_provider=lambda _: 100 * GIB)
    assert controller.run() == "NOT_READY"
    gate = tmp_path / "program/prompt_4/hash_validation.json"
    gate.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ProgramContractError, match="completion validation failed"):
        ProgramController(
            config, free_bytes_provider=lambda _: 100 * GIB
        ).validate_completed_prefix()


def test_not_yet_admitted_adapter_can_be_installed_and_resumed(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    assert (
        ProgramController(config, free_bytes_provider=lambda _: 100 * GIB).run()
        == "NOT_READY"
    )
    first_state = json.loads((tmp_path / "program/program_state.json").read_text())
    assert first_state["stages"]["4"]["status"] == "COMPLETE"
    assert first_state["stages"]["5"]["status"] == "NOT_READY"

    build_config(tmp_path, ready_prompts=(4, 5))
    assert (
        ProgramController(config, free_bytes_provider=lambda _: 100 * GIB).run()
        == "NOT_READY"
    )
    resumed = json.loads((tmp_path / "program/program_state.json").read_text())
    assert resumed["stages"]["4"]["status"] == "COMPLETE"
    assert resumed["stages"]["5"]["status"] == "COMPLETE"
    assert resumed["stages"]["6"]["status"] == "NOT_READY"


def test_low_c_drive_space_blocks_before_adapter_start(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    controller = ProgramController(config, free_bytes_provider=lambda _: 34 * GIB)
    with pytest.raises(ProgramContractError, match="RESERVE_35_GIB"):
        controller.run()
    assert not (tmp_path / "program/prompt_4/native_stage_evidence.txt").exists()
    state = json.loads((tmp_path / "program/program_state.json").read_text())
    assert state["status"] == "BLOCKED_C_DRIVE_RESERVE_35_GIB"


def test_stop_request_is_durable_and_idempotent_until_processed(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    controller = ProgramController(config, free_bytes_provider=lambda _: 100 * GIB)
    first = controller.request_stop(reason="test stop")
    second = controller.request_stop(reason="different text")
    assert second == first
    on_disk = json.loads((tmp_path / "program/stop_request.json").read_text())
    assert on_disk["reason"] == "test stop"


def test_preexisting_stop_request_is_honored_before_start(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    controller = ProgramController(config, free_bytes_provider=lambda _: 100 * GIB)
    controller.request_stop(reason="do not start")
    assert controller.run() == "STOPPED"
    assert not (tmp_path / "program/prompt_4/native_stage_evidence.txt").exists()
    state = json.loads((tmp_path / "program/program_state.json").read_text())
    assert state["status"] == "STOPPED"


def test_controller_lock_rejects_a_second_live_controller(tmp_path: Path) -> None:
    lock_path = tmp_path / "controller.lock"
    state_path = tmp_path / "state.json"
    first = ControllerLock(lock_path, state_path=state_path)
    first.acquire()
    try:
        second = ControllerLock(lock_path, state_path=state_path)
        with pytest.raises(ProgramContractError, match="active"):
            second.acquire()
    finally:
        first.release()


def test_stale_controller_lock_is_archived_before_recovery(tmp_path: Path) -> None:
    lock_path = tmp_path / "controller.lock"
    state_path = tmp_path / "state.json"
    atomic_write_json(
        lock_path,
        {"pid": 99999999, "token": "dead", "schema_version": "test"},
    )
    recovered = ControllerLock(
        lock_path, state_path=state_path, pid_alive=lambda _: False
    )
    stale = recovered.acquire()
    try:
        assert stale is not None
        assert Path(stale["path"]).exists()
    finally:
        recovered.release()


def test_status_reports_percentage_eta_and_storage_without_starting(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    status = ProgramController(
        config, free_bytes_provider=lambda _: 100 * GIB
    ).status()
    assert status["persisted"] is False
    assert status["overall_percentage"] == 0
    assert status["storage_status"] == "PASS"
    assert status["c_drive_free_gib"] == 100


def test_192_hour_target_does_not_block_admission_or_execution(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=(4,))
    controller = ProgramController(config, free_bytes_provider=lambda _: 100 * GIB)
    state = controller._new_state()
    state["program_started_at_utc"] = (
        datetime.now(timezone.utc) - timedelta(hours=193)
    ).isoformat().replace("+00:00", "Z")
    atomic_write_json(controller.state_path, state)
    assert controller.run() == "NOT_READY"
    assert (tmp_path / "program/prompt_4/native_stage_evidence.txt").is_file()
    state = json.loads(controller.state_path.read_text())
    assert state["stages"]["4"]["status"] == "COMPLETE"
    assert state["time_target_policy"] == "ADVISORY_ONLY_NO_AUTOMATIC_STOP"
    status = controller.status()
    assert status["target_remaining_seconds"] == 0
    assert status["target_overrun_seconds"] > 0


def test_atomic_json_replace_retries_transient_windows_sharing_error(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "state.json"
    real_replace = storage.os.replace
    calls = 0

    def flaky_replace(source: object, target: object) -> None:
        nonlocal calls
        calls += 1
        if calls < 3:
            error = PermissionError("synthetic Windows sharing violation")
            error.winerror = 5  # type: ignore[attr-defined]
            raise error
        real_replace(source, target)

    with (
        patch.object(storage.os, "name", "nt"),
        patch.object(storage.os, "replace", side_effect=flaky_replace),
        patch.object(storage.time, "sleep", return_value=None),
    ):
        atomic_write_json(destination, {"status": "PASS"})
    assert calls == 3
    assert json.loads(destination.read_text()) == {"status": "PASS"}
