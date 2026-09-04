from __future__ import annotations

import json
from pathlib import Path

from app.h2_portability import controller_adapter as adapter
from app.h2_product_program.contracts import H2Job, ProgramPaths


def _job(kind: str = "onnx_export") -> H2Job:
    return H2Job(
        job_id=f"job_{kind}",
        phase_index=6,
        phase_name="PORTABILITY_RESOURCE",
        job_kind=kind,
        split="none",
        pipeline_id="NOT_APPLICABLE",
        configuration_id=f"TEST_{kind.upper()}",
        mode="NOT_APPLICABLE",
        case_ids=(),
        audio_duration_sec=0.0,
        runtime_tuning={},
        serial=True,
    )


def _paths(tmp_path: Path) -> ProgramPaths:
    evaluation = tmp_path / "tool"
    evaluation.mkdir()
    return ProgramPaths(
        evaluation_root=evaluation,
        workspace=tmp_path / "workspace",
        results_root=tmp_path / "results",
        summary_root=tmp_path / "summary",
        config_path=tmp_path / "config.yaml",
    )


def _snapshot() -> dict[str, object]:
    return {
        "pipeline_id": "fullpipe_v1_ag_dr_ir",
        "runtime_tuning": {"product_mode": "H2_SESSION_MEMORY_ENHANCED"},
        "runtime_tuning_identity_sha256": "a" * 64,
    }


def test_adapter_fails_closed_without_selected_runtime(tmp_path: Path) -> None:
    job = _job()
    result = adapter.execute_portability_job(
        _paths(tmp_path), job, {"jobs": {}}, (job,)
    )
    assert result["state"] == "failed"
    receipt = json.loads(Path(str(result["result_path"])).read_text(encoding="utf-8"))
    assert receipt["status"] == "FAILED"
    assert receipt["marked_complete"] is False
    assert receipt["linux_arm64_ready_claimed"] is False


def test_adapter_success_is_snapshot_and_checksum_bound(
    tmp_path: Path, monkeypatch
) -> None:
    job = _job()
    paths = _paths(tmp_path)
    state = {
        "selected_runtime_snapshot": _snapshot(),
        "jobs": {job.job_id: {"state": "RUNNING"}},
    }

    def fake_handle(paths_arg, job_arg, snapshot, snapshot_sha256):
        assert paths_arg == paths
        assert job_arg == job
        assert snapshot == _snapshot()
        evidence = paths_arg.results_root / "bounded-evidence.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('{"status":"PASS"}\n', encoding="utf-8")
        return {
            "schema_version": adapter.PORTABILITY_JOB_RESULT_SCHEMA,
            "status": "COMPLETE",
            "job_id": job.job_id,
            "selected_runtime_snapshot_sha256": snapshot_sha256,
            "graphs_outside_compact_zip": True,
            "bounded_evidence_path": str(evidence),
        }

    monkeypatch.setattr(adapter, "_handle_export", fake_handle)
    result = adapter.execute_portability_job(paths, job, state, (job,))
    assert result["state"] == "complete"
    assert result["error"] is None
    receipt_path = Path(str(result["result_path"]))
    assert adapter.sha256_file(receipt_path) == result["result_sha256"]
    assert receipt_path.is_relative_to(paths.results_root)
    assert not receipt_path.is_relative_to(paths.summary_root)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["selected_runtime_snapshot_sha256"] == adapter.canonical_sha256(
        _snapshot()
    )
    assert adapter.validate_portability_result_artifacts(receipt)["status"] == "VALID"
    Path(str(receipt["bounded_evidence_path"])).unlink()
    try:
        adapter.validate_portability_result_artifacts(receipt)
    except adapter.PortabilityJobError as exc:
        assert "missing or changed" in str(exc)
    else:  # pragma: no cover - assertion guard.
        raise AssertionError("deleted evidence was accepted")


def test_artifact_root_is_excluded_from_compact_summary(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    root = adapter._artifact_root(paths)
    assert root.is_relative_to(paths.results_root)
    assert not root.is_relative_to(paths.summary_root)
    assert not root.is_relative_to(paths.workspace)


def test_linux_result_contract_never_claims_arm64_ready(
    tmp_path: Path, monkeypatch
) -> None:
    job = _job("linux_portability")
    paths = _paths(tmp_path)
    state = {
        "selected_runtime_snapshot": _snapshot(),
        "jobs": {job.job_id: {"state": "RUNNING"}},
    }

    def fake_handle(*args, **kwargs):
        paths_arg = args[0]
        snapshot_sha256 = args[-1]
        evidence = paths_arg.results_root / "linux-preparation.json"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text('{"status":"PASS"}\n', encoding="utf-8")
        return {
            "schema_version": adapter.PORTABILITY_JOB_RESULT_SCHEMA,
            "status": "COMPLETE",
            "completion_scope": "LINUX_ARM64_PACKAGE_PREPARATION_ONLY",
            "selected_runtime_snapshot_sha256": snapshot_sha256,
            "candidate_classification": "PORT_REQUIRES_WORK",
            "linux_arm64_ready_claimed": False,
            "raspberry_pi_hardware_validated": False,
            "preparation_evidence_path": str(evidence),
        }

    monkeypatch.setattr(adapter, "_handle_linux_portability", fake_handle)
    result = adapter.execute_portability_job(paths, job, state, (job,))
    receipt = json.loads(Path(str(result["result_path"])).read_text(encoding="utf-8"))
    assert result["state"] == "complete"
    assert receipt["candidate_classification"] == "PORT_REQUIRES_WORK"
    assert receipt["linux_arm64_ready_claimed"] is False
    assert receipt["raspberry_pi_hardware_validated"] is False


def test_invalid_e2e_report_is_preserved_and_fresh_attempt_is_used(
    tmp_path: Path, monkeypatch
) -> None:
    paths = _paths(tmp_path)
    case_root = paths.results_root / "case"
    old_report = case_root / "e2e_parity_report.json"
    old_report.parent.mkdir(parents=True)
    old_report.write_text('{"status":"INVALID"}\n', encoding="utf-8")

    def fake_validate(path, **kwargs):
        if Path(path) == old_report:
            raise adapter.PortabilityJobError("full-pipeline E2E parity is invalid")
        return {
            "report_path": str(path),
            "report_sha256": adapter.sha256_file(Path(path)),
        }

    def fake_run(**kwargs):
        report = Path(kwargs["output_root"]) / "e2e_parity_report.json"
        report.parent.mkdir(parents=True)
        report.write_text('{"status":"E2E_PARITY_PASS"}\n', encoding="utf-8")
        return {"status": "E2E_PARITY_PASS"}

    monkeypatch.setattr(adapter, "_validate_e2e_report", fake_validate)
    monkeypatch.setattr(adapter, "run_fresh_factory_pair", fake_run)
    value = adapter._run_or_reuse_e2e_case(
        paths=paths,
        case_root=case_root,
        freeze_path=tmp_path / "freeze.json",
        input_path=tmp_path / "input.wav",
        enrollment_root=tmp_path / "enrollment",
        graph_paths={},
        graph_sha256={},
        snapshot={
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "runtime_tuning": {"product_mode": "H2_SESSION_MEMORY_ENHANCED"},
        },
        snapshot_sha256="a" * 64,
        require_identity=True,
    )
    assert value["superseded_invalid_report"]["preserved"] is True
    assert "attempt_002" in value["report_path"]
    assert old_report.is_file()
