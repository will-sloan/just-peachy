from __future__ import annotations

from pathlib import Path

from app.full_pipeline_eight_day_program.cli import main
from app.full_pipeline_eight_day_program.monitor import duration, progress_bar, render_status
from tests.full_pipeline_eight_day_program.test_contracts import build_config


def test_progress_rendering_is_bounded() -> None:
    assert progress_bar(-2).endswith("0.00%")
    assert progress_bar(120).endswith("100.00%")
    assert duration(90061) == "1d 01:01:01"


def test_render_contains_program_and_stage_progress() -> None:
    rendered = render_status(
        {
            "overall_percentage": 20,
            "status": "RUNNING",
            "current_prompt_index": 5,
            "elapsed_seconds": 12,
            "eta_seconds": 30,
            "remaining_envelope_seconds": 40,
            "c_drive_free_gib": 100,
            "minimum_free_space_reserve_gib": 35,
            "storage_status": "PASS",
            "program_state": "C:\\state.json",
            "milestone_notifications": "C:\\milestones.jsonl",
            "stages": [
                {
                    "prompt_index": 5,
                    "percentage": 50,
                    "status": "RUNNING",
                    "readiness": "READY",
                    "eta_seconds": 30,
                    "adapter_id": "test",
                    "detail": "working",
                }
            ],
        }
    )
    assert "OVERALL" in rendered
    assert "PROMPT 5" in rendered
    assert "C: 100.0 GiB" in rendered


def test_cli_validate_config_is_model_free(
    canonical_program_tmp_path: Path, capsys
) -> None:
    tmp_path = canonical_program_tmp_path
    config = build_config(tmp_path, ready_prompts=())
    assert main(["validate-config", "--adapter-config", str(config), "--json"]) == 0
    assert '"status": "PASS"' in capsys.readouterr().out
    assert not (tmp_path / "program/program_state.json").exists()
