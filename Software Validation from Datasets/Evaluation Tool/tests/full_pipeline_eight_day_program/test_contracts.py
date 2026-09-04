from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

from app.full_pipeline_eight_day_program import COMPLETION_MARKERS, PROMPTS
from app.full_pipeline_eight_day_program.contracts import (
    load_adapter_configuration,
    template_configuration,
    validate_amendment,
)
from app.full_pipeline_eight_day_program.storage import ProgramContractError


TOOL_ROOT = Path(__file__).resolve().parents[2]
AMENDMENT = TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json"
FAKE = Path(__file__).with_name("fake_adapter.py").resolve()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def test_authoritative_amendment_matches_compiled_contract() -> None:
    result = validate_amendment(AMENDMENT)
    assert result["scope"]["total_wall_target_hours"] == 192
    assert result["storage_policy"]["minimum_free_space_reserve_gib"] == 35
    assert result["completion_markers"]["prompt_8"] == COMPLETION_MARKERS[8]


def test_template_is_safe_and_all_adapters_are_not_ready(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    raw = template_configuration(evaluation_tool_root=TOOL_ROOT)
    raw["program_workspace"] = str(tmp_path / "program")
    path = tmp_path / "adapters.json"
    _write(path, raw)
    loaded = load_adapter_configuration(path)
    assert set(loaded.stages) == set(PROMPTS)
    assert all(stage.readiness == "NOT_READY" for stage in loaded.stages.values())


def test_other_drive_path_is_rejected(tmp_path: Path) -> None:
    raw = template_configuration(evaluation_tool_root=TOOL_ROOT)
    raw["program_workspace"] = "D:\\eight_day_program"
    path = tmp_path / "adapters.json"
    _write(path, raw)
    with pytest.raises(ProgramContractError, match="C:-only"):
        load_adapter_configuration(path)


def test_ready_adapter_requires_restart_stop_validation_and_path_inventory(
    canonical_program_tmp_path: Path,
) -> None:
    tmp_path = canonical_program_tmp_path
    raw = template_configuration(evaluation_tool_root=TOOL_ROOT)
    raw["program_workspace"] = str(tmp_path / "program")
    raw["stages"]["4"] = {
        "adapter_id": "incomplete",
        "readiness": "READY",
        "expected_duration_hours": 1,
    }
    path = tmp_path / "adapters.json"
    _write(path, raw)
    with pytest.raises(ProgramContractError, match="stage_workspace"):
        load_adapter_configuration(path)


def build_config(tmp_path: Path, *, ready_prompts: tuple[int, ...] = (4, 5)) -> Path:
    program = tmp_path / "program"
    raw = template_configuration(evaluation_tool_root=TOOL_ROOT)
    raw["program_workspace"] = str(program)
    raw["poll_interval_seconds"] = 1
    for prompt in ready_prompts:
        stage = program / f"prompt_{prompt}"
        completion = stage / "completion.json"
        progress = stage / "progress.json"
        log = stage / "controller.log"
        start_command = [sys.executable, str(FAKE), "start"]
        if prompt > 4:
            start_command.append("${PREDECESSOR_COMPLETION_PATH}")
        raw["stages"][str(prompt)] = {
            "adapter_id": f"synthetic_prompt_{prompt}",
            "readiness": "READY",
            "expected_duration_hours": 0.01,
            "stage_workspace": str(stage),
            "cwd": str(stage),
            "completion_record": str(completion),
            "progress_record": str(progress),
            "controller_log": str(log),
            "start_command": start_command,
            "resume_command": [],
            "stop_command": [sys.executable, str(FAKE), "stop"],
            "validate_command": [sys.executable, str(FAKE), "validate"],
            "restart_policy": "RERUN_IDEMPOTENT",
            "stop_grace_seconds": 5,
            "environment": {},
            "material_paths": {
                "inputs": [str(FAKE)],
                "workspaces": [str(stage), str(completion), str(progress)],
                "caches": [str(stage / "cache")],
                "temporary": [str(stage / "temp")],
                "logs": [str(log)],
                "results": [str(completion), str(progress)],
                "reports": [str(stage / "reports")],
                "packages": [str(stage / "packages")],
                "checkpoints": [],
            },
        }
    path = tmp_path / "adapters.json"
    _write(path, raw)
    return path


def test_embedded_off_drive_environment_path_is_rejected(
    canonical_program_tmp_path: Path,
) -> None:
    path = build_config(canonical_program_tmp_path, ready_prompts=(4,))
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["stages"]["4"]["environment"] = {"MODEL_CACHE": "D:\\forbidden"}
    _write(path, raw)
    with pytest.raises(ProgramContractError, match="off-C"):
        load_adapter_configuration(path)


def test_embedded_off_drive_command_argument_is_rejected(
    canonical_program_tmp_path: Path,
) -> None:
    path = build_config(canonical_program_tmp_path, ready_prompts=(4,))
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["stages"]["4"]["start_command"].append("--output=D:\\forbidden")
    _write(path, raw)
    with pytest.raises(ProgramContractError, match="off-C"):
        load_adapter_configuration(path)
