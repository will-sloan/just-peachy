from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf
import yaml

from app.artifact_contracts.atomic import file_sha256
from app.benchmark_contracts.scenario import finalize_scenario
from app.campaign_exchange import create_worker_assignment
from app.campaign_executor.planner import plan_campaign
from app.inference_pipeline.catalog import ComponentCatalogEntry
from app.launch_readiness import credential_readiness, preflight_worker_assignment
from app.launch_readiness.preflight import (
    LAUNCH_PREFLIGHT_SCHEMA_VERSION,
    _execution_runtime_checks,
    _inspect_audio,
    _model_asset_checks,
)
from scripts.launch_readiness_probe import build_parser
from scripts import materialize_launch_campaign as materializer


TOOL_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage2"
COMMIT = "a" * 40
CREATED = datetime(2032, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, dict[str, object]]:
    repository_root = tmp_path / "repository"
    project_root = repository_root / "Software Validation from Datasets"
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir(parents=True)
    repository_root.mkdir(parents=True)
    shutil.copy2(
        FIXTURES / "golden_manifest.parquet",
        catalog_root / "golden_manifest.parquet",
    )
    identity = json.loads(
        (FIXTURES / "golden_manifest_identity.json").read_text(encoding="utf-8")
    )
    scenario = json.loads(
        (FIXTURES / "golden_scenario_source.json").read_text(encoding="utf-8")
    )
    scenario["benchmark_manifest"] = {**identity, "path": "golden_manifest.parquet"}
    scenario["dataset_slice"]["row_count"] = 1
    scenario["condition"] = {
        "id": "clean",
        "augmentation": "none",
        "noise_type": None,
        "snr_db": None,
        "rir": None,
    }
    model_path = repository_root / "models" / "cache" / "fixture" / "model.bin"
    model_path.parent.mkdir(parents=True)
    model_path.write_bytes(b"fixture-model-bytes")
    model_hash = file_sha256(model_path)
    scenario["pipeline"]["models"]["asr"]["assets"] = [
        {
            "configured_identity": (
                f"models/cache/fixture/model.bin|{model_path.stat().st_size}|"
                f"sha256:{model_hash}"
            ),
            "path": "models/cache/fixture/model.bin",
            "expected_bytes": model_path.stat().st_size,
            "expected_sha256": model_hash,
        }
    ]
    scenario = finalize_scenario(scenario)
    catalog = catalog_root / "resolved_scenarios.jsonl"
    catalog.write_text(json.dumps(scenario, sort_keys=True) + "\n", encoding="utf-8")
    campaign_root = plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=tmp_path / "automated_runs",
        campaign_id="campaign_launchtest",
        created_at=CREATED,
    ).campaign_root
    assignment = create_worker_assignment(
        campaign_root,
        worker_id="machine_a",
        expected_git_commit=COMMIT,
        expected_environment_profile="core-cpu",
        created_at=CREATED,
    )
    assignment_path = campaign_root / "worker_assignments" / "worker_machine_a.yaml"
    audio_path = (
        project_root / "Raw Datasets (Not formatted)" / "CMU Arctic" / "fixture-a.wav"
    )
    audio_path.parent.mkdir(parents=True)
    sf.write(audio_path, np.zeros(4 * 16000, dtype=np.float32), 16000)
    profile = {
        "schema_version": "launch-machine-profile.v1",
        "machine_id": "machine_a",
        "profile_sha256": "B" * 64,
        "repository": {"commit": COMMIT, "dirty": False, "changed_path_count": 0},
        "operating_system": {"system": "Windows"},
        "hardware": {
            "ram_total_bytes": 16 * 1024**3,
            "disk_free_bytes": 20 * 1024**3,
        },
    }
    assert assignment["scenario_ids"] == [scenario["scenario_id"]]
    return campaign_root, assignment_path, repository_root, project_root, profile


def _catalog_entry() -> ComponentCatalogEntry:
    return ComponentCatalogEntry(
        family="asr",
        name="fixture_asr",
        implementation_class="FixtureASR",
        implementation_path="fixture.py",
        registry_adapter_class="FixtureASRAdapter",
        source_config_path=None,
        source_config_sha256=None,
        required_packages=(),
        required_assets=(),
        credential_requirements=(),
        environment_profiles=("core-cpu",),
        supported_operating_systems=("Windows", "Linux"),
        hardware_requirements={"cpu": True},
        device_dtype_settings=("cpu/float32",),
        input_contract="audio_segments.v1",
        output_contract="asr_transcript.v1",
        compatibility_rules=(),
        supported_parameters=(),
        qualification_status="qualified",
        qualification_evidence="fixture",
        qualification_backend_id=None,
        final_use_category="test",
        model_identity={"model_name": "fixture"},
        model_asset_identity=(),
        configured_component=None,
    )


def _run_preflight(
    tmp_path: Path, monkeypatch
) -> tuple[dict[str, object], tuple[Path, ...]]:
    campaign, assignment, repository, project, profile = _fixture(tmp_path)
    monkeypatch.setattr(
        "app.launch_readiness.preflight.ComponentCatalog.load",
        lambda: SimpleNamespace(entries=(_catalog_entry(),)),
    )
    monkeypatch.setattr(
        "app.launch_readiness.preflight._resolve_and_verify_pipeline",
        lambda *_args, **_kwargs: object(),
    )
    report = preflight_worker_assignment(
        campaign_root=campaign,
        assignment_path=assignment,
        repository_root=repository,
        project_root=project,
        machine_profile=profile,
        expected_environment_profile="core-cpu",
        minimum_free_disk_reserve_bytes=1024,
    )
    return report, (campaign, assignment, repository, project)


def test_complete_assignment_preflight_requires_every_scenario(
    tmp_path: Path, monkeypatch
) -> None:
    report, _ = _run_preflight(tmp_path, monkeypatch)

    assert report["schema_version"] == LAUNCH_PREFLIGHT_SCHEMA_VERSION
    assert report["verdict"] == "READY_TO_LAUNCH"
    assert report["coverage"]["assigned_scenario_count"] == 1
    assert report["coverage"]["preflighted_scenario_count"] == 1
    assert report["coverage"]["complete_assignment_preflight"] is True
    assert report["coverage"]["ready_scenario_count"] == 1
    assert report["coverage"]["item_execution_count"] == 1


def test_missing_audio_and_dirty_worktree_block_launch(
    tmp_path: Path, monkeypatch
) -> None:
    campaign, assignment, repository, project, profile = _fixture(tmp_path)
    audio = project / "Raw Datasets (Not formatted)" / "CMU Arctic" / "fixture-a.wav"
    audio.unlink()
    profile["repository"]["dirty"] = True
    monkeypatch.setattr(
        "app.launch_readiness.preflight.ComponentCatalog.load",
        lambda: SimpleNamespace(entries=(_catalog_entry(),)),
    )
    monkeypatch.setattr(
        "app.launch_readiness.preflight._resolve_and_verify_pipeline",
        lambda *_args, **_kwargs: object(),
    )

    report = preflight_worker_assignment(
        campaign_root=campaign,
        assignment_path=assignment,
        repository_root=repository,
        project_root=project,
        machine_profile=profile,
        expected_environment_profile="core-cpu",
        minimum_free_disk_reserve_bytes=1024,
    )

    assert report["verdict"] == "NOT_READY_TO_LAUNCH"
    assert report["coverage"]["blocked_scenario_count"] == 1
    blocker_ids = {item["id"] for item in report["blockers"]}
    assert "repository_clean" in blocker_ids
    assert "missing_audio:1" in blocker_ids


def test_unsupported_executor_scenario_type_blocks_launch(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.launch_readiness.preflight.scenario_type_from_resolved",
        lambda _scenario: "embedding_extraction",
    )
    report, _ = _run_preflight(tmp_path, monkeypatch)

    assert report["verdict"] == "NOT_READY_TO_LAUNCH"
    assert report["coverage"]["scenario_specific_ready_count"] == 0
    assert report["scenarios"][0]["scenario_type"] == "embedding_extraction"
    assert (
        "executor_support:embedding_extraction"
        in report["scenarios"][0]["local_blockers"]
    )


def test_audio_header_probe_and_model_hash_are_real(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    sf.write(audio_path, np.zeros(16000, dtype=np.float32), 16000)
    audio = _inspect_audio(audio_path, inspect_header=True)
    assert audio["readable"] is True
    assert audio["sample_rate_hz"] == 16000
    assert audio["channels"] == 1

    model_path = tmp_path / "models" / "model.bin"
    model_path.parent.mkdir()
    model_path.write_bytes(b"model")
    expected_hash = hashlib.sha256(b"model").hexdigest().upper()
    scenario = {
        "pipeline": {
            "models": {
                "asr": {
                    "assets": [
                        {
                            "path": "models/model.bin",
                            "configured_identity": "models/model.bin",
                            "expected_bytes": 5,
                            "expected_sha256": expected_hash,
                        }
                    ]
                }
            }
        }
    }
    checks = _model_asset_checks([scenario], tmp_path)
    assert checks[0]["ready"] is True
    model_path.write_bytes(b"tampered")
    assert _model_asset_checks([scenario], tmp_path)[0]["ready"] is False


def test_launch_probe_cli_exposes_machine_and_assignment_commands() -> None:
    parser = build_parser()
    common = [
        "--machine-id",
        "machine_a",
        "--repository-root",
        ".",
        "--project-root",
        "project",
        "--environment-profile",
        "core-cpu",
        "--output-root",
        "runs",
    ]
    assert (
        parser.parse_args(["machine", *common, "--output", "profile.json"]).action
        == "machine"
    )
    assert parser.parse_args(["credentials"]).action == "credentials"
    assert (
        parser.parse_args(
            [
                "assignment",
                *common,
                "--campaign-root",
                "runs/campaign",
                "--assignment",
                "assignment.yaml",
                "--output",
                "preflight.json",
            ]
        ).action
        == "assignment"
    )
    assert materializer.build_parser().parse_args([]).bind_current_commit is False
    assert (
        materializer.build_parser()
        .parse_args(["--bind-current-commit"])
        .bind_current_commit
        is True
    )
    parsed = parser.parse_args(
        [
            "machine",
            *common,
            "--device",
            "cuda:0",
            "--dtype",
            "float32",
            "--output",
            "profile.json",
        ]
    )
    assert parsed.device == "cuda:0"
    assert parsed.dtype == "float32"


def test_cuda_preflight_rejects_cpu_torch_and_accepts_explicit_cuda_runtime() -> None:
    scenario = {"runtime": {"device": "cuda:0", "dtype": "float32"}}
    cpu_profile = {
        "runtime": {
            "torch": {
                "available": True,
                "version": "2.11.0+cpu",
                "cuda_available": False,
                "cuda_runtime": None,
                "device_count": 0,
                "allocation_probe_succeeded": False,
                "allocation_probe_reason": "CUDA unavailable",
            }
        },
        "execution_policy": {"selected_device": "cuda:0", "execution_dtype": "float32"},
    }
    failed = _execution_runtime_checks(
        [scenario],
        expected_environment_profile="core-cuda",
        machine_profile=cpu_profile,
    )
    assert {row["id"] for row in failed if not row["ready"]} >= {
        "cuda_torch_build",
        "cuda_runtime_available",
        "cuda_device_open",
        "cuda_device_index",
    }

    cuda_profile = deepcopy(cpu_profile)
    cuda_profile["runtime"]["torch"].update(
        {
            "version": "2.11.0+cu128",
            "cuda_available": True,
            "cuda_runtime": "12.8",
            "device_count": 1,
            "allocation_probe_succeeded": True,
            "allocation_probe_reason": None,
        }
    )
    passed = _execution_runtime_checks(
        [scenario],
        expected_environment_profile="core-cuda",
        machine_profile=cuda_profile,
    )
    assert all(row["ready"] for row in passed)


def test_credential_readiness_reports_presence_only(monkeypatch) -> None:
    for name in (
        "PYANNOTE_LICENSE_ACCEPTED",
        "PYANNOTE_AUTH_TOKEN",
        "PICOVOICE_LICENSE_ACCEPTED",
        "PICOVOICE_ACCESS_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PYANNOTE_LICENSE_ACCEPTED", "accepted")
    monkeypatch.setenv("PYANNOTE_AUTH_TOKEN", "secret-not-returned")

    assert credential_readiness() == {"pyannote": "READY", "falcon": "MISSING"}


def test_frozen_launch_package_has_complete_non_overlapping_worker_coverage() -> None:
    package = yaml.safe_load(
        (
            TOOL_ROOT / "configs" / "automated_evaluation" / "launch_package.v1.yaml"
        ).read_text(encoding="utf-8")
    )
    massive = package["massive_campaign"]
    global_ids = set(massive["scenario_ids"])
    machine_a_ids = set(massive["workers"]["machine_a"]["scenario_ids"])
    machine_b_ids = set(massive["workers"]["machine_b"]["scenario_ids"])

    assert package["readiness_state"] == "NOT_READY_TO_LAUNCH"
    assert massive["campaign_id"] == "campaign_05_massive_release"
    assert massive["scenario_count"] == len(global_ids) == 41
    assert massive["item_execution_count"] == 25_798
    assert massive["workers"]["machine_a"]["scenario_count"] == len(machine_a_ids) == 20
    assert massive["workers"]["machine_b"]["scenario_count"] == len(machine_b_ids) == 21
    assert machine_a_ids.isdisjoint(machine_b_ids)
    assert machine_a_ids | machine_b_ids == global_ids
    assert massive["required_credentials"] == []
    assert {item["id"] for item in massive["required_rirs"]} == {
        "dining_room_h025",
        "restaurant_h093",
    }


def test_gpu_launch_package_preserves_cpu_coverage_with_new_identities() -> None:
    cpu_package_path = (
        TOOL_ROOT / "configs" / "automated_evaluation" / "launch_package.v1.yaml"
    )
    gpu_package_path = (
        TOOL_ROOT
        / "configs"
        / "automated_evaluation"
        / "launch_package.gpu.v1.yaml"
    )
    cpu = yaml.safe_load(cpu_package_path.read_text(encoding="utf-8"))
    gpu = yaml.safe_load(gpu_package_path.read_text(encoding="utf-8"))
    cpu_massive = cpu["massive_campaign"]
    massive = gpu["massive_campaign"]

    assert gpu["reference_cpu_campaign"]["campaign_manifest_sha256"] == (
        cpu_massive["campaign_manifest_sha256"]
    )
    assert gpu["reference_cpu_campaign"]["preserved"] is True
    assert massive["campaign_id"] == "campaign_06_massive_release_cuda"
    assert massive["environment_profile"] == "core-cuda"
    assert massive["device"] == "cuda:0"
    assert massive["dtype"] == "float32"
    assert massive["scenario_count"] == cpu_massive["scenario_count"] == 41
    assert massive["item_execution_count"] == cpu_massive["item_execution_count"]
    assert set(massive["scenario_ids"]).isdisjoint(cpu_massive["scenario_ids"])
    machine_a = set(massive["workers"]["machine_a"]["scenario_ids"])
    machine_b = set(massive["workers"]["machine_b"]["scenario_ids"])
    assert machine_a.isdisjoint(machine_b)
    assert machine_a | machine_b == set(massive["scenario_ids"])


def test_cpu_and_cuda_launch_wrappers_support_preflight_only() -> None:
    wrapper_names = (
        "launch_campaign_machine_a.ps1",
        "launch_campaign_machine_b.ps1",
        "launch_campaign_machine_a_gpu.ps1",
        "launch_campaign_machine_b_gpu.ps1",
    )
    for name in wrapper_names:
        text = (TOOL_ROOT / "scripts" / name).read_text(encoding="utf-8-sig")
        assert "[switch]$PreflightOnly" in text
        assert "if ($PreflightOnly)" in text
        assert "inference was not started" in text


def test_first_class_setup_script_keeps_cpu_and_cuda_isolated() -> None:
    text = (
        TOOL_ROOT.parents[1] / "scripts" / "prepare_execution_mode.ps1"
    ).read_text(encoding="utf-8-sig")
    assert '[ValidateSet("cpu", "cuda")]' in text
    assert '.venv\\Scripts\\python.exe' in text
    assert '.stage8-envs\\core-cuda\\Scripts\\python.exe' in text
    assert '"--device", "cpu"' in text
    assert '"--device", "cuda"' in text
    stage8 = (TOOL_ROOT.parents[1] / "scripts" / "install_stage8_profile.ps1").read_text(
        encoding="utf-8-sig"
    )
    assert '"--speechbrain-ecapa"' in stage8
    assert '"--silero"' in stage8


def test_post_commit_materialization_binds_assignments_without_source_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bound_commit = "b" * 40
    monkeypatch.setattr(
        materializer,
        "current_git_commit",
        lambda _root: bound_commit,
    )
    package_path = (
        TOOL_ROOT / "configs" / "automated_evaluation" / "launch_package.v1.yaml"
    )

    report = materializer.materialize(
        package_path,
        tmp_path / "runs",
        bind_current_commit=True,
    )

    campaign_root = Path(str(report["campaign_root"]))
    binding = json.loads(
        (campaign_root / "worker_assignments" / "release_binding.json").read_text(
            encoding="utf-8"
        )
    )
    assignment_a = yaml.safe_load(
        (campaign_root / "worker_assignments" / "machine_a.yaml").read_text(
            encoding="utf-8"
        )
    )
    assignment_b = yaml.safe_load(
        (campaign_root / "worker_assignments" / "machine_b.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert binding["bound_git_commit"] == bound_commit
    assert binding["binding_mode"] == "current_head"
    assert assignment_a["expected_git_commit"] == bound_commit
    assert assignment_b["expected_git_commit"] == bound_commit
    assert report["assignment_validation"]["assigned_scenario_count"] == 41
    assert report["assignment_validation"]["overlaps"] == []
