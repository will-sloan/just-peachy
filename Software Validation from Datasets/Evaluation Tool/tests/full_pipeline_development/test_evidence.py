from __future__ import annotations

import copy
from pathlib import Path

import pytest

from app.full_pipeline_development.evidence import (
    DevelopmentEvidenceError,
    combine_development_evidence,
    freeze_development_outputs,
)
from app.full_pipeline_evaluation.io import read_json, write_json_atomic
from app.full_pipeline_evaluation.planning import matrix


SHA = "a" * 64


def _campaign(root: Path, mode: str) -> tuple[dict[str, object], dict[str, object]]:
    case_id = f"{mode}_case"
    jobs: list[dict[str, object]] = []
    rows: list[dict[str, object]] = []
    for index, pipeline_id in enumerate(matrix().pipeline_ids):
        job_id = f"job_{mode}_{index:02d}"
        job = {
            "job_id": job_id,
            "pipeline_id": pipeline_id,
            "protocol_id": "source_protocol.v1",
            "split": "development",
            "source_key": "product_v2",
            "measurement_mode": mode,
            "seed": 5107,
            "case_count": 1,
            "audio_duration_sec": 1.0,
            "protocol_identity": "b" * 64,
            "pipeline_identity": "c" * 64,
            "reuse_identity": {"identity_sha256": "d" * 64},
            "case_ids": [case_id],
            "result_relative_path": f"development/{mode}/{pipeline_id}/{job_id}",
        }
        jobs.append(job)
        rows.append(
            {
                "job_id": job_id,
                "pipeline_id": pipeline_id,
                "protocol_id": "source_protocol.v1",
                "source_key": "product_v2",
                "split": "development",
                "measurement_mode": mode,
                "reuse_identity": {"identity_sha256": "d" * 64},
                "result_root": f"X:/{mode}/{job_id}",
                "result_checksums_sha256": f"{index + 1:064x}",
                "summary": {"mode": mode, "pipeline_id": pipeline_id},
            }
        )
    manifest: dict[str, object] = {
        "schema_version": "full-pipeline-evaluation-campaign.v1",
        "campaign_id": f"campaign_{mode}",
        "campaign_identity_sha256": ("e" if mode == "accuracy" else "f") * 64,
        "full_protocol_id": "full_speech_pipeline_v1_fixture",
        "development_identity": "b" * 64,
        "evaluation_identity": "1" * 64,
        "matrix_sha256": "2" * 64,
        "runtime_config_sha256": "3" * 64,
        "scorer_version": "scorer.v1",
        "result_contract_version": "result.v1",
        "implementation_identity": {"source_tree_sha256": "4" * 64},
        "seed": 5107,
        "campaign_stage": f"prompt4_{mode}",
        "selected_pipeline_ids": list(matrix().pipeline_ids),
        "measurement_modes": [mode],
        "decision_policy_registry_sha256": SHA,
        "pipeline_count": 18,
        "job_count": 18,
        "case_count": 1,
        "case_index": {
            case_id: {
                "case_id": case_id,
                "split": "development",
                "source_key": "product_v2",
            }
        },
        "parallelism_policy": {
            "accuracy_maximum_jobs": 2,
            "resource_measurement_jobs": 1,
            "resource_results_comparable_only_with_serial_resource_results": True,
        },
        "jobs": jobs,
    }
    analysis: dict[str, object] = {
        "schema_version": "full-pipeline-evaluation-analysis.v1",
        "campaign_id": manifest["campaign_id"],
        "created_at_utc": "2026-08-23T00:00:00Z",
        "complete_result_count": 18,
        "pipeline_ids": list(matrix().pipeline_ids),
        "protocol_ids": ["source_protocol.v1"],
        "weighted_composite_score_created": False,
        "rows": rows,
    }
    write_json_atomic(root / "campaign_manifest.json", manifest)
    write_json_atomic(root / "analysis/analysis.json", analysis)
    return manifest, analysis


def test_combines_checksum_validated_all18_accuracy_and_serial_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, accuracy = _campaign(tmp_path / "accuracy", "accuracy")
    _, resources = _campaign(tmp_path / "resources", "resources")
    validated: list[Path] = []

    def fake_validate(*, workspace_root: Path, verify_audio: bool) -> dict[str, object]:
        assert verify_audio is False
        validated.append(Path(workspace_root))
        return {"valid": True, "status": "PASS", "errors": []}

    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.validate", fake_validate
    )
    first = combine_development_evidence(
        output_workspace_root=tmp_path / "combined",
        accuracy_workspace_root=tmp_path / "accuracy",
        resource_workspace_root=tmp_path / "resources",
        accuracy_analysis=accuracy,
        resource_analysis=resources,
    )
    second = combine_development_evidence(
        output_workspace_root=tmp_path / "combined",
        accuracy_workspace_root=tmp_path / "accuracy",
        resource_workspace_root=tmp_path / "resources",
        accuracy_analysis=accuracy,
        resource_analysis=resources,
    )

    assert first["status"] == "PASS"
    assert first["pipeline_count"] == 18
    assert first["job_count"] == 36
    assert first["accuracy_job_count"] == 18
    assert first["resource_job_count"] == 18
    assert first["campaign_identity_sha256"] == second["campaign_identity_sha256"]
    assert len(validated) == 4
    manifest = read_json(tmp_path / "combined/campaign_manifest.json")
    combined_analysis = read_json(tmp_path / "combined/analysis/analysis.json")
    assert manifest["schema_version"] == (
        "full-pipeline-development-combined-campaign.v1"
    )
    assert manifest["development_only"] is True
    assert manifest["evaluation_material_inspected"] is False
    assert manifest["measurement_modes"] == ["accuracy", "resources"]
    assert manifest["parallelism_policy"]["resource_measurement_jobs"] == 1
    assert len({row["job_id"] for row in manifest["jobs"]}) == 36
    assert combined_analysis["development_result_set_sha256"] == manifest[
        "development_result_set_sha256"
    ]
    assert all(row["split"] == "development" for row in combined_analysis["rows"])


def test_calls_controller_analyze_when_outputs_are_not_supplied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, accuracy = _campaign(tmp_path / "accuracy", "accuracy")
    _, resources = _campaign(tmp_path / "resources", "resources")
    called: list[str] = []

    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.validate",
        lambda **_: {"valid": True, "status": "PASS", "errors": []},
    )

    def fake_analyze(*, workspace_root: Path) -> dict[str, object]:
        called.append(Path(workspace_root).name)
        return accuracy if Path(workspace_root).name == "accuracy" else resources

    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.analyze", fake_analyze
    )
    combine_development_evidence(
        output_workspace_root=tmp_path / "combined",
        accuracy_workspace_root=tmp_path / "accuracy",
        resource_workspace_root=tmp_path / "resources",
    )
    assert called == ["accuracy", "resources"]


def test_combined_identity_ignores_analysis_time_and_physical_result_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, accuracy = _campaign(tmp_path / "accuracy", "accuracy")
    _, resources = _campaign(tmp_path / "resources", "resources")
    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.validate",
        lambda **_: {"valid": True, "status": "PASS", "errors": []},
    )
    first = combine_development_evidence(
        output_workspace_root=tmp_path / "combined1",
        accuracy_workspace_root=tmp_path / "accuracy",
        resource_workspace_root=tmp_path / "resources",
        accuracy_analysis=accuracy,
        resource_analysis=resources,
    )
    accuracy["created_at_utc"] = "2026-08-24T12:34:56Z"
    resources["created_at_utc"] = "2026-08-25T12:34:56Z"
    for row in accuracy["rows"]:
        row["result_root"] = "Y:/relocated/accuracy"
    for row in resources["rows"]:
        row["result_root"] = "Y:/relocated/resources"
    write_json_atomic(tmp_path / "accuracy/analysis/analysis.json", accuracy)
    write_json_atomic(tmp_path / "resources/analysis/analysis.json", resources)
    second = combine_development_evidence(
        output_workspace_root=tmp_path / "combined2",
        accuracy_workspace_root=tmp_path / "accuracy",
        resource_workspace_root=tmp_path / "resources",
        accuracy_analysis=accuracy,
        resource_analysis=resources,
    )
    assert first["campaign_identity_sha256"] == second[
        "campaign_identity_sha256"
    ]


def test_rejects_nonserial_resource_or_mismatched_scientific_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, accuracy = _campaign(tmp_path / "accuracy", "accuracy")
    resource_manifest, resources = _campaign(tmp_path / "resources", "resources")
    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.validate",
        lambda **_: {"valid": True, "status": "PASS", "errors": []},
    )
    resource_manifest["parallelism_policy"]["resource_measurement_jobs"] = 2
    write_json_atomic(
        tmp_path / "resources/campaign_manifest.json", resource_manifest
    )
    with pytest.raises(DevelopmentEvidenceError, match="not attested as serial"):
        combine_development_evidence(
            output_workspace_root=tmp_path / "combined",
            accuracy_workspace_root=tmp_path / "accuracy",
            resource_workspace_root=tmp_path / "resources",
            accuracy_analysis=accuracy,
            resource_analysis=resources,
        )

    resource_manifest["parallelism_policy"]["resource_measurement_jobs"] = 1
    resource_manifest["runtime_config_sha256"] = "9" * 64
    write_json_atomic(
        tmp_path / "resources/campaign_manifest.json", resource_manifest
    )
    with pytest.raises(DevelopmentEvidenceError, match="runtime_config_sha256"):
        combine_development_evidence(
            output_workspace_root=tmp_path / "combined",
            accuracy_workspace_root=tmp_path / "accuracy",
            resource_workspace_root=tmp_path / "resources",
            accuracy_analysis=accuracy,
            resource_analysis=resources,
        )


def test_rejects_heldout_or_incomplete_analysis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, accuracy = _campaign(tmp_path / "accuracy", "accuracy")
    _, resources = _campaign(tmp_path / "resources", "resources")
    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.validate",
        lambda **_: {"valid": True, "status": "PASS", "errors": []},
    )
    heldout = copy.deepcopy(resources)
    heldout["rows"][0]["split"] = "evaluation"
    write_json_atomic(tmp_path / "resources/analysis/analysis.json", heldout)
    with pytest.raises(DevelopmentEvidenceError, match="split differs"):
        combine_development_evidence(
            output_workspace_root=tmp_path / "combined",
            accuracy_workspace_root=tmp_path / "accuracy",
            resource_workspace_root=tmp_path / "resources",
            accuracy_analysis=accuracy,
            resource_analysis=heldout,
        )

    incomplete = copy.deepcopy(resources)
    incomplete["rows"].pop()
    incomplete["complete_result_count"] = 17
    write_json_atomic(tmp_path / "resources/analysis/analysis.json", incomplete)
    with pytest.raises(DevelopmentEvidenceError, match="does not cover every"):
        combine_development_evidence(
            output_workspace_root=tmp_path / "combined2",
            accuracy_workspace_root=tmp_path / "accuracy",
            resource_workspace_root=tmp_path / "resources",
            accuracy_analysis=accuracy,
            resource_analysis=incomplete,
        )


def test_freeze_wrapper_passes_combined_result_identity_and_attestation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, accuracy = _campaign(tmp_path / "accuracy", "accuracy")
    _, resources = _campaign(tmp_path / "resources", "resources")
    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.controller.validate",
        lambda **_: {"valid": True, "status": "PASS", "errors": []},
    )
    combined = combine_development_evidence(
        output_workspace_root=tmp_path / "combined",
        accuracy_workspace_root=tmp_path / "accuracy",
        resource_workspace_root=tmp_path / "resources",
        accuracy_analysis=accuracy,
        resource_analysis=resources,
    )
    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.validate_development_policy_registry",
        lambda registry: None,
    )
    captured: dict[str, object] = {}

    def fake_freeze(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"schema_version": "fixture", "status": "PASS", "pipeline_count": 18}

    monkeypatch.setattr(
        "app.full_pipeline_development.evidence.freeze_all_pipeline_configs",
        fake_freeze,
    )
    attestation = {
        "schema_version": "full-pipeline-anchor-runtime-qualification.v1",
        "status": "PASS",
        "qualification_result_sha256": "8" * 64,
        "evaluation_material_inspected": False,
    }
    result = freeze_development_outputs(
        combined_workspace_root=tmp_path / "combined",
        policy_registry={
            "protocol_id": "full_speech_pipeline_v1_fixture",
            "development_identity_sha256": "b" * 64,
        },
        runtime_anchor_qualification=attestation,
        frozen_config_root=tmp_path / "frozen-configs",
    )
    assert captured["development_result_set_sha256"] == combined[
        "development_result_set_sha256"
    ]
    assert captured["runtime_anchor_qualification"] == attestation
    assert result["production_winner_selected"] is False
