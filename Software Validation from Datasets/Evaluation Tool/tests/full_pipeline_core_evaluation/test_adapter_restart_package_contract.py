from __future__ import annotations

import json
from pathlib import Path
import zipfile

from app.full_pipeline_core_evaluation import controller, reporting
from app.full_pipeline_evaluation.io import sha256_file


TOOL_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, payload: str = "synthetic\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def test_adapter_binds_exact_active_prompt4_predecessor_and_restart_policy() -> None:
    value = json.loads(
        (TOOL_ROOT / "runs/full_pipeline_program/EIGHT_DAY_ADAPTERS.json").read_text(
            encoding="utf-8"
        )
    )
    prompt4 = value["stages"]["4"]
    prompt5 = value["stages"]["5"]
    expected = prompt4["stage_workspace"] + "\\completion_marker.json"

    assert expected in prompt5["material_paths"]["inputs"]
    assert prompt5["completion_record"] == "${STAGE_WORKSPACE}\\completion_marker.json"
    assert prompt5["restart_policy"] == "RERUN_IDEMPOTENT"
    assert "RunAll" in prompt5["start_command"]
    assert "Stop" in prompt5["stop_command"]
    assert "ValidateCompletion" in prompt5["validate_command"]
    assert reporting.GATE_RECORDS_DIRECTORY == "gate_records"


def test_stop_delegates_to_both_restartable_campaigns(
    tmp_path: Path, monkeypatch
) -> None:
    paths = controller.layout(tmp_path / "workspace")
    _write(paths.accuracy / "campaign_manifest.json", "{}\n")
    _write(paths.resources / "campaign_manifest.json", "{}\n")
    calls: list[Path] = []

    def fake_stop(*, workspace_root: Path) -> dict[str, object]:
        calls.append(Path(workspace_root))
        return {"status": "STOP_REQUESTED"}

    monkeypatch.setattr(controller.evaluation_controller, "stop", fake_stop)
    result = controller.stop(workspace_root=paths.root)

    assert result["status"] == "STOP_REQUESTED"
    assert calls == [paths.accuracy, paths.resources]


def test_resource_execution_boundary_is_always_serial(
    tmp_path: Path, monkeypatch
) -> None:
    paths = controller.layout(tmp_path / "workspace")
    _write(paths.root / "resource_preparation.json", "{}\n")
    selected = [{"protocol_case_id": "synthetic_resource_case"}]
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        controller,
        "_require_prepared",
        lambda *args, **kwargs: (paths, selected, tmp_path / "registry.json"),
    )
    monkeypatch.setattr(controller, "storage_preflight", lambda *args, **kwargs: {})
    monkeypatch.setattr(controller, "_resource_case", lambda rows: dict(rows[0]))
    monkeypatch.setattr(
        controller, "_validate_stage_manifest", lambda *args, **kwargs: {}
    )

    def fake_run(**kwargs) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "COMPLETE"}

    monkeypatch.setattr(controller.evaluation_controller, "_run", fake_run)
    result = controller.run_resources(
        workspace_root=paths.root,
        prompt4_marker=tmp_path / "prompt4.json",
    )

    assert captured["parallel_jobs"] == 1
    assert captured["measurement_mode"] == "resources"
    assert result["parallel_jobs"] == 1
    assert result["serial_resource_comparison"] is True


def test_compact_collection_is_deterministic_and_excludes_raw_trees(
    tmp_path: Path, monkeypatch
) -> None:
    paths = controller.layout(tmp_path / "workspace")
    for name in reporting.REQUIRED_REPORT_FILES:
        _write(paths.report / name)
    protocol_inputs = (
        paths.authorization,
        paths.root / "selection/selection_manifest.json",
        paths.selected_cases,
        paths.excluded_cases,
        paths.accuracy / "campaign_manifest.json",
        paths.accuracy / "campaign_progress.json",
        paths.resources / "campaign_manifest.json",
        paths.resources / "campaign_progress.json",
    )
    for source in protocol_inputs:
        _write(source, "{}\n")
    amendment = tmp_path / "eight_day_scope_amendment.json"
    _write(amendment, "{}\n")
    steering = tmp_path / "raspberry_pi_deployment_steering.json"
    _write(steering, "{}\n")
    _write(paths.report / "raw_audio.wav", "not audio")
    _write(paths.report / "model_weights.pt", "not weights")
    _write(paths.report / "predictions/raw_event_tree.jsonl", "{}\n")
    destination = tmp_path / "canonical" / "full_speech_pipeline_v1_reduced_8day_v1"

    monkeypatch.setattr(reporting, "CANONICAL_REPORT_ROOT", destination)
    monkeypatch.setattr(reporting, "DEFAULT_AMENDMENT", amendment)
    monkeypatch.setattr(
        reporting,
        "_validated_deployment_steering",
        lambda authorization: ({}, steering.resolve()),
    )
    monkeypatch.setattr(
        reporting,
        "_validate_deployment_artifact",
        lambda *args, **kwargs: {"pipeline_count": 18},
    )
    monkeypatch.setattr(reporting, "storage_preflight", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        reporting, "_validate_terminal_jobs", lambda *args, **kwargs: {}
    )

    first = reporting.collect(workspace_root=paths.root)
    first_sha = str(first["zip_sha256"])
    second = reporting.collect(workspace_root=paths.root)

    assert second["zip_sha256"] == first_sha
    assert sha256_file(Path(str(second["zip_path"]))) == first_sha
    assert not (destination / "raw_audio.wav").exists()
    assert not (destination / "model_weights.pt").exists()
    assert not (destination / "predictions").exists()
    with zipfile.ZipFile(Path(str(second["zip_path"]))) as archive:
        names = set(archive.namelist())
    assert "raw_audio.wav" not in names
    assert "model_weights.pt" not in names
    assert not any(name.startswith("predictions/") for name in names)
    assert "all18_deployment_evidence.json" in names
    assert "protocol/raspberry_pi_deployment_steering.json" in names
