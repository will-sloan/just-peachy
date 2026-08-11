from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.artifact_contracts.layout import validate_campaign_id
from app.artifact_contracts.registry import scenario_type_from_resolved
from scripts import production_release


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]


def test_production_scope_is_credential_free_and_has_only_core_components() -> None:
    contract = production_release.load_contract()
    scope = contract["production_scope"]
    active_text = str(scope["active_components"]).lower()

    assert scope["credentials_required"] == []
    assert set(scope["active_components"]["asr"]) == {
        "whisper_tiny",
        "whisper_base",
        "whisper_small",
    }
    assert set(scope["active_components"]["diarization"]) == {
        "no_op_diarization"
    }
    assert all(
        str(backend).lower() not in active_text
        for backend in scope["excluded_optional_backends"]
    )
    assert scope["rir_policy"] == {
        "approved": ["dining_room_h025", "restaurant_h093"],
        "unresolved_excluded": ["bedroom"],
        "forbidden_substitutions": [
            "parking_lot_for_bedroom",
            "kitchen_for_bedroom",
        ],
    }


def test_every_declared_production_campaign_id_is_valid() -> None:
    campaigns = production_release.load_contract()["campaigns"]
    ids = []
    for name in ("canary", "small", "standard", "massive", "rehearsal"):
        ids.extend(campaigns[name]["ids"].values())
    for campaign_id in ids:
        validate_campaign_id(str(campaign_id))


def test_canary_uses_only_executor_supported_scenarios() -> None:
    contract = production_release.load_contract()
    rows = production_release._gate_rows(contract, "canary", "cuda")

    assert len(rows) == 7
    assert all(scenario_type_from_resolved(row) == "asr" for row in rows)
    components = [production_release._enabled_components(row) for row in rows]
    assert {row["asr"] for row in components} == {
        "whisper_tiny",
        "whisper_base",
        "whisper_small",
    }
    assert {row.get("vad") for row in components} >= {
        None,
        "energy_vad",
        "silero_vad",
    }
    assert any(row.get("segmentation") == "vad_chunks" for row in components)
    assert all("speaker_embedding" not in row for row in components)


def test_small_and_standard_cuda_scenarios_are_explicit_float32_gpu() -> None:
    contract = production_release.load_contract()
    for gate, expected in (("small", 26), ("standard", 41)):
        cuda_rows = production_release._gate_rows(contract, gate, "cuda")
        cpu_rows = production_release._gate_rows(contract, gate, "cpu")
        assert len(cuda_rows) == len(cpu_rows) == expected
        assert {row["scenario_id"] for row in cuda_rows}.isdisjoint(
            {row["scenario_id"] for row in cpu_rows}
        )
        assert {row["runtime"]["device"] for row in cuda_rows} == {"cuda:0"}
        assert {row["runtime"]["dtype"] for row in cuda_rows} == {"float32"}
        assert {row["runtime"]["device"] for row in cpu_rows} == {"cpu"}
        assert {row["runtime"]["dtype"] for row in cpu_rows} == {"float32"}


def test_rehearsal_has_one_case_for_every_declared_operational_condition() -> None:
    contract = production_release.load_contract()
    rows = production_release._rehearsal_rows(contract, "cuda")
    signatures = {
        (
            row["panel"],
            row["tier"],
            row["dataset_slice"]["dataset"],
            row["condition"]["id"],
            row["dataset_slice"]["filters"].get("role"),
        )
        for row in rows
    }

    assert len(rows) == 6
    assert signatures == {
        ("controlled_clean", "small", "cmu_arctic", "clean", None),
        ("controlled_clean", "small", "cmu_arctic", "white_10db", None),
        (
            "controlled_clean",
            "small",
            "cmu_arctic",
            "dining_room_h025",
            None,
        ),
        ("native_robustness", "small", "ami", "native", None),
        ("speaker_protocol", "small", "cmu_arctic", "clean", "known_probe"),
        (
            "controlled_clean",
            "standard",
            "cmu_arctic",
            "restaurant_h093_pink_10db",
            None,
        ),
    }


def test_high_level_scripts_select_profiles_without_manual_paths() -> None:
    common = (REPOSITORY_ROOT / "scripts" / "worker_common.ps1").read_text(
        encoding="utf-8-sig"
    )
    setup = (REPOSITORY_ROOT / "scripts" / "setup_worker.ps1").read_text(
        encoding="utf-8-sig"
    )
    rehearsal = (
        REPOSITORY_ROOT / "scripts" / "run_massive_rehearsal.ps1"
    ).read_text(encoding="utf-8-sig")

    assert ".venv\\Scripts\\python.exe" in common
    assert ".stage8-envs\\core-cuda\\Scripts\\python.exe" in common
    assert "Initialize-ProductionProcessPath" in common
    assert "Microsoft\\WinGet\\Packages" in common
    assert "campaign_05_massive_release" in common
    assert "campaign_06_massive_release_cuda" in common
    assert '[string]$DatasetRoot = ""' in setup
    assert 'ValidateSet("materialize", "run", "status", "stop", "resume", "finalize")' in rehearsal


def test_worker_setup_automates_assets_data_ffmpeg_and_ignored_evidence() -> None:
    setup = (REPOSITORY_ROOT / "scripts" / "setup_worker.ps1").read_text(
        encoding="utf-8-sig"
    )
    prepare = (
        REPOSITORY_ROOT / "scripts" / "prepare_execution_mode.ps1"
    ).read_text(encoding="utf-8-sig")
    gitignore = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert '"-InstallFFmpeg", "-DownloadModels"' in setup
    assert "status --porcelain --untracked-files=all" in setup
    assert "Production setup requires a clean checkout" in setup
    assert "Resolve-DatasetCandidate" in setup
    assert "New-Item -ItemType Junction" in setup
    assert "whisper_tiny" in setup
    assert "whisper_base" in setup
    assert "whisper_small" in setup
    assert "speechbrain_ecapa" in setup
    assert "Remove-InvalidProductionModelCache" in setup
    assert "Get-FileHash -Algorithm SHA256" in setup
    assert "940D761A280DCD8FAAB077074E02BADE649E64E47461D80A4F927A01ABBEF5E2" in setup
    assert "C2CA8A07002943409D31A2C6D6D07BA826AA428FE6EF6CECF2C4FF33D7D4A8A8" in setup
    assert "SHA-256 mismatch; no substitution allowed" in setup
    for asset in production_release.load_contract()["production_scope"][
        "required_models"
    ]:
        assert str(asset["path"]).replace("/", "\\") in setup
        assert str(asset["sha256"]) in setup
    # Definition plus explicit CPU and CUDA calls. This prevents a WinGet
    # install from requiring the operator to reopen PowerShell.
    assert prepare.count("Ensure-FFmpeg") >= 3
    assert (
        "Software Validation from Datasets/Evaluation Tool/artifacts/"
        "production_verification/"
    ) in gitignore


def test_cuda_release_chain_delegates_canary_to_cpu_reference(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repository = tmp_path / "repository"
    tool = tmp_path / "evaluation"
    cpu_python = repository / ".venv" / "Scripts" / "python.exe"
    cpu_python.parent.mkdir(parents=True)
    cpu_python.write_bytes(b"fixture")
    report_path = (
        tool
        / "artifacts"
        / "production_release"
        / "cpu"
        / "canary_gate_result.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        '{"gate":"canary","device_mode":"cpu","passed":true}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(production_release, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(production_release, "TOOL_ROOT", tool)
    monkeypatch.setattr(
        production_release.subprocess,
        "run",
        lambda command, **_kwargs: (
            SimpleNamespace(returncode=0)
            if Path(command[0]) == cpu_python
            else SimpleNamespace(returncode=1)
        ),
    )
    report = production_release._run_reference_cpu_canary_for_cuda_release()

    assert report["device_mode"] == "cpu"
    assert report["requested_release_device"] == "cuda"
    assert "canonical CPU scenarios" in report["execution_note"]


def test_release_result_prerequisite_rejects_missing_or_failed_canary(
    tmp_path: Path,
) -> None:
    result = tmp_path / "canary_gate_result.json"
    with pytest.raises(production_release.ProductionReleaseError, match="missing"):
        production_release._require_passed_result(result, "component canary")

    result.write_text('{"passed": false}\n', encoding="utf-8")
    with pytest.raises(production_release.ProductionReleaseError, match="did not pass"):
        production_release._require_passed_result(result, "component canary")

    result.write_text('{"passed": true}\n', encoding="utf-8")
    production_release._require_passed_result(result, "component canary")
