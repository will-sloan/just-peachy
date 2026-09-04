from __future__ import annotations

from pathlib import Path

import pytest

from app.full_pipeline_bounded_development import orchestration
from app.full_pipeline_bounded_development.selection import COMPLETION_MARKER
from app.full_pipeline_evaluation.io import write_json_atomic
from app.full_pipeline_evaluation.planning import matrix


def _cases(count: int = 180) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "protocol_case_id": f"case_{index:03d}",
            "partition": "development",
            "source_key": "controlled_v1",
            "duration_sec": 1.0,
        }
        for index in range(count)
    )


def test_prepare_delegates_exact_all18_bounded_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    cases = _cases()
    monkeypatch.setattr(
        orchestration,
        "plan",
        lambda **_: {"status": "PASS", "selected_case_count": 180},
    )
    monkeypatch.setattr(orchestration, "_storage_preflight", lambda *_, **__: {"status": "PASS"})
    monkeypatch.setattr(orchestration, "_material_paths", lambda *args: tuple(Path(v) for v in args))
    monkeypatch.setattr(orchestration, "_selected_cases", lambda *_: cases)
    monkeypatch.setattr(orchestration, "_require_campaign", lambda *args: {})

    def fake_prepare(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {"status": "PASS", "campaign_id": "bounded"}

    monkeypatch.setattr(orchestration.evaluation_controller, "prepare", fake_prepare)
    value = orchestration.prepare(
        workspace_root=tmp_path / "workspace",
        source_evidence_root=tmp_path / "source",
        output_root=tmp_path / "output",
    )

    assert value["status"] == "PASS"
    assert len(calls) == 1
    call = calls[0]
    assert call["campaign_stage"] == orchestration.ACCURACY_STAGE
    assert call["measurement_modes"] == ("accuracy",)
    assert len(call["case_ids"]) == 180
    assert tuple(call["pipeline_ids"]) == matrix().pipeline_ids


def test_accuracy_run_is_limited_to_two_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(orchestration, "_validate_existing_bindings", lambda *_: None)
    monkeypatch.setattr(orchestration, "_storage_preflight", lambda *_, **__: {"status": "PASS"})
    monkeypatch.setattr(orchestration, "_material_paths_from_plan", lambda *_: ())
    monkeypatch.setattr(orchestration, "_selected_cases", lambda *_: _cases())
    monkeypatch.setattr(orchestration, "_require_campaign", lambda *args: {})
    monkeypatch.setattr(
        orchestration.evaluation_controller,
        "run_development",
        lambda **kwargs: calls.append(dict(kwargs)) or {"status": "COMPLETE"},
    )

    value = orchestration.run(workspace_root=tmp_path)

    assert value["status"] == "COMPLETE"
    assert calls[0]["parallel_jobs"] == 2
    assert calls[0]["measurement_mode"] == "accuracy"


def test_resource_run_is_serial_and_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []
    sample = (
        {
            "protocol_case_id": "controlled",
            "partition": "development",
            "source_key": "controlled_v1",
            "overlay_id": "MIXED_KNOWN_UNKNOWN",
            "known_speaker_count": 1,
            "unknown_speaker_count": 1,
            "duration_sec": 2.0,
        },
        {
            "protocol_case_id": "product",
            "partition": "development",
            "source_key": "product_v2",
            "overlay_id": "MIXED_KNOWN_UNKNOWN",
            "known_speaker_count": 1,
            "unknown_speaker_count": 1,
            "duration_sec": 2.0,
        },
    )
    monkeypatch.setattr(orchestration, "_validate_existing_bindings", lambda *_: None)
    monkeypatch.setattr(orchestration, "_storage_preflight", lambda *_, **__: {"status": "PASS"})
    monkeypatch.setattr(orchestration, "_material_paths_from_plan", lambda *_: ())
    monkeypatch.setattr(orchestration, "_selected_cases", lambda *_: sample)
    monkeypatch.setattr(orchestration, "_require_campaign", lambda *args: {})
    monkeypatch.setattr(
        orchestration.legacy_orchestration,
        "_isolated_job_executor",
        lambda *args, **kwargs: "isolated",
    )
    monkeypatch.setattr(
        orchestration.evaluation_controller,
        "run_development",
        lambda **kwargs: calls.append(dict(kwargs)) or {"status": "COMPLETE"},
    )

    orchestration.run_resources(workspace_root=tmp_path)

    assert calls[0]["parallel_jobs"] == 1
    assert calls[0]["measurement_mode"] == "resources"
    assert calls[0]["job_executor"] == "isolated"


def test_universal_completion_envelope_and_prompt5_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = orchestration.layout(tmp_path / "workspace")
    output = tmp_path / "output"
    paths["frozen_configs"].mkdir(parents=True)
    output.mkdir(parents=True)
    write_json_atomic(paths["selection"], {"selection_identity_sha256": "a" * 64})
    write_json_atomic(paths["input_binding"], {"binding": "fixture"})
    write_json_atomic(paths["frozen_configs"] / "checksums.json", {"entries": {}})
    paths["registry"].write_text("{}\n", encoding="utf-8")
    (output / "extended_set.yaml").write_text("pipelines: []\n", encoding="utf-8")
    (output / "development_summary.csv").write_text("pipeline_id\n", encoding="utf-8")
    zip_path = output / "report.zip"
    zip_path.write_bytes(b"zip")
    gates: dict[str, dict[str, object]] = {}
    for key in ("hash_validation", "firewall_validation", "prerequisite_validation"):
        path = paths["root"] / f"{key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
        gates[key] = {"path": str(path.resolve()), "sha256": orchestration.sha256_file(path)}
    manifest = paths["root"] / "artifact_manifest.json"
    manifest.write_text("{}\n", encoding="utf-8")
    artifact_manifest = {
        "path": str(manifest.resolve()),
        "sha256": orchestration.sha256_file(manifest),
    }
    monkeypatch.setenv("JP8_ADAPTER_ID", "fixture-adapter")
    monkeypatch.setenv("JP8_ADAPTER_CONTRACT_SHA256", "b" * 64)

    value = orchestration._completion_document(  # noqa: SLF001
        paths, output, zip_path, gates, artifact_manifest
    )

    assert value["schema_version"] == "full-pipeline-eight-day-stage-completion.v1"
    assert value["status"] == "COMPLETE"
    assert value["completion_marker"] == COMPLETION_MARKER
    assert value["prompt_index"] == 4
    assert value["scope_class"] == "BOUNDED_REDUCED"
    assert value["original_full_scope_complete"] is False
    assert value["adapter_id"] == "fixture-adapter"
    assert value["adapter_contract_sha256"] == "b" * 64
    assert value["predecessor"] is None
    assert set(value["gate_records"]) == {
        "hash_validation",
        "firewall_validation",
        "prerequisite_validation",
    }
    assert set(value["artifacts"]) == {
        "frozen_pipeline_configs",
        "decision_policy_registry",
        "extended_set",
        "development_summary",
    }
    assert value["artifacts"]["frozen_pipeline_configs"]["pipeline_count"] == 18


def test_c_only_guard_rejects_other_drive() -> None:
    with pytest.raises(orchestration.BoundedOrchestrationError, match="must resolve on C"):
        orchestration._require_c_path(Path("D:/not-allowed"), "fixture")  # noqa: SLF001


def test_prompt4_completion_atomically_advances_program_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    completion = tmp_path / "completion_marker.json"
    state = tmp_path / "PROGRAM_STATE.json"
    write_json_atomic(completion, {"completion_marker": COMPLETION_MARKER})
    write_json_atomic(
        state,
        {
            "status": "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE",
            "current_prompt_index": 3,
            "remaining_prompt_indices": [4, 5, 6, 7, 8],
            "completion_state": {
                "prompt_3": "COMPLETE_FULL_PIPELINE_EVALUATION_INFRASTRUCTURE"
            },
        },
    )
    monkeypatch.setattr(orchestration, "PROGRAM_STATE_PATH", state)
    monkeypatch.setattr(
        orchestration, "_validate_completion_envelope", lambda _value: None
    )

    first = orchestration._advance_program_state(completion)  # noqa: SLF001
    second = orchestration._advance_program_state(completion)  # noqa: SLF001

    assert first == second
    assert first["status"] == COMPLETION_MARKER
    assert first["current_prompt_index"] == 4
    assert first["remaining_prompt_indices"] == [5, 6, 7, 8]
    assert first["completion_state"]["prompt_4"] == COMPLETION_MARKER
    assert first["prompt_4_completion_record"] == str(completion.resolve())
    assert len(first["prompt_4_completion_record_sha256"]) == 64


def test_wrapper_exposes_every_restart_safe_action() -> None:
    wrapper = (
        Path(__file__).resolve().parents[2]
        / "scripts/run_full_pipeline_bounded_development.ps1"
    ).read_text(encoding="utf-8")
    for action in (
        "Plan",
        "Prepare",
        "Run",
        "PrepareResources",
        "RunResources",
        "Analyze",
        "Freeze",
        "Collect",
        "Execute",
        "Validate",
        "Status",
        "Stop",
    ):
        assert action in wrapper
