from __future__ import annotations

from pathlib import Path

import pytest

from app.full_pipeline_development import orchestration


def test_plan_locks_exact_development_scopes(tmp_path: Path) -> None:
    value = orchestration.plan(workspace_root=tmp_path)

    assert value["status"] == "PASS"
    assert value["development_only"] is True
    assert value["held_out_evaluation_allowed"] is False
    stages = value["stages"]
    assert stages["calibration"]["case_count"] == 56
    assert stages["calibration"]["pipeline_count"] == 12
    assert stages["calibration"]["parallel_jobs"] == 2
    assert stages["qualification"]["case_count"] == 1
    assert stages["qualification"]["pipeline_count"] == 18
    assert stages["qualification"]["cold_parallel_jobs"] == 1
    assert stages["development"]["case_count"] == 807
    assert stages["development"]["pipeline_count"] == 18
    assert stages["resources"]["case_count"] == 2
    assert stages["resources"]["source_keys"] == [
        "controlled_v1",
        "product_v2",
    ]
    assert stages["resources"]["parallel_jobs"] == 1
    assert (tmp_path / "orchestration_plan.json").is_file()


def test_development_guard_rejects_held_out_case() -> None:
    with pytest.raises(RuntimeError, match="held-out/evaluation"):
        orchestration._assert_development_only(  # noqa: SLF001
            ({"protocol_case_id": "heldout", "partition": "evaluation"},)
        )


def test_prepare_calibration_delegates_exact_scope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []

    def fake_prepare(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "PASS", "campaign_id": "calibration"}

    monkeypatch.setattr(orchestration.evaluation_controller, "prepare", fake_prepare)
    monkeypatch.setattr(
        orchestration,
        "_require_stage_manifest",
        lambda *args, **kwargs: {"campaign_id": "calibration"},
    )

    value = orchestration.prepare_calibration(workspace_root=tmp_path)

    assert value["status"] == "PASS"
    assert len(calls) == 1
    call = calls[0]
    assert call["campaign_stage"] == orchestration.CALIBRATION_STAGE
    assert call["measurement_modes"] == ("accuracy",)
    assert len(call["case_ids"]) == 56
    assert len(call["pipeline_ids"]) == 12
    assert "decision_policy_registry_path" not in call


def test_resource_run_is_serial_and_uses_isolated_executor(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []
    registry = tmp_path / "resource_spots" / "decision_policy_registry.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        orchestration, "_require_policy_registry", lambda path: Path(path)
    )
    monkeypatch.setattr(
        orchestration,
        "_require_stage_manifest",
        lambda *args, **kwargs: {"campaign_id": "resources"},
    )
    monkeypatch.setattr(
        orchestration,
        "_isolated_job_executor",
        lambda path, measurement_mode: "isolated-resource-executor",
    )

    def fake_run(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "COMPLETE"}

    monkeypatch.setattr(
        orchestration.evaluation_controller, "run_development", fake_run
    )

    value = orchestration.run_resources(workspace_root=tmp_path)

    assert value["status"] == "COMPLETE"
    assert len(calls) == 1
    assert calls[0]["measurement_mode"] == "resources"
    assert calls[0]["parallel_jobs"] == 1
    assert calls[0]["job_executor"] == "isolated-resource-executor"
    assert len(calls[0]["pipeline_ids"]) == 18


def test_qualification_selection_is_one_short_actual_mixed_case() -> None:
    rows = orchestration._qualification_cases(  # noqa: SLF001
        orchestration._development_cases()  # noqa: SLF001
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["partition"] == "development"
    assert row["overlay_id"] == "MIXED_KNOWN_UNKNOWN"
    assert int(row["known_speaker_count"]) > 0
    assert int(row["unknown_speaker_count"]) > 0
    assert str(row["gallery_requested_size"]) == "10"

