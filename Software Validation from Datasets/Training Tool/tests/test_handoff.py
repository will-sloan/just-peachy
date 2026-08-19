"""Targeted tests for the portable successor and RTX 3090 handoff."""

from __future__ import annotations

import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = TOOL_ROOT.parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from training_data.handoff import (  # noqa: E402
    EXPERIMENTS,
    PARENT_PHASE4_ID,
    PARENT_PHASE4_SHA256,
    verify_successor,
)
from training_data import asset_layout  # noqa: E402
from training_data.parallel_adapter import run_jobs, status_root  # noqa: E402
from training_data.phase4 import dataset_weights  # noqa: E402
from training_data.portability import (  # noqa: E402
    portable_roots,
    resolve_logical_path,
)


def test_all_five_roots_resolve_under_alternate_windows_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    values = {
        "JP_REPO_ROOT": tmp_path / "Checkout With Spaces",
        "JP_DATA_ROOT": tmp_path / "Shared Data",
        "JP_TRAINING_ROOT": tmp_path / "Training State",
        "JP_MODEL_ROOT": tmp_path / "Model Assets",
        "JP_RUN_ROOT": tmp_path / "Run Outputs",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, str(value))
    roots = portable_roots(Path("C:/unused"))
    assert roots.as_mapping() == {key: value.resolve() for key, value in values.items()}
    assert resolve_logical_path("JP_RUN_ROOT:adapters/O AGE/result.json", roots) == (
        values["JP_RUN_ROOT"] / "adapters/O AGE/result.json"
    ).resolve()


def test_common_voice_legacy_logical_path_uses_shared_external_alias(
    tmp_path: Path,
) -> None:
    roots = portable_roots(REPOSITORY)
    roots = type(roots)(
        tmp_path / "repo",
        tmp_path / "data with spaces",
        tmp_path / "training",
        tmp_path / "models",
        tmp_path / "runs",
    )
    relative = "clips/fixture.mp3"
    preferred = (
        roots.data
        / "Raw Datasets (Not formatted)"
        / "Common Voice"
        / "cv-corpus-26.0-2026-06-12"
        / "prepared"
        / "en"
        / relative
    )
    preferred.parent.mkdir(parents=True)
    preferred.write_bytes(b"fixture")
    logical = (
        "JP_TRAINING_ROOT:datasets/common_voice/english/"
        "cv-corpus-26.0-2026-06-12/prepared/en/"
        + relative
    )
    assert resolve_logical_path(logical, roots) == preferred


def test_common_voice_reconcile_is_noop_when_legacy_alias_is_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    shared = tmp_path / "shared prepared tree"
    clip = shared / "clips" / "fixture.mp3"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"fixture audio")
    digest = hashlib.sha256(clip.read_bytes()).hexdigest().upper()
    registry = tmp_path / "registry.parquet"
    pd.DataFrame(
        [{"prepared_audio_relative_path": "clips/fixture.mp3", "audio_sha256": digest}]
    ).to_parquet(registry, index=False)
    sample = hashlib.sha256(
        f"clips/fixture.mp3\0{digest}\n".encode()
    ).hexdigest().upper()
    monkeypatch.setattr(asset_layout, "paths", lambda: (shared, shared, registry))
    monkeypatch.setattr(asset_layout, "EXPECTED_FILES", 1)
    monkeypatch.setattr(asset_layout, "EXPECTED_BYTES", clip.stat().st_size)
    monkeypatch.setattr(asset_layout, "EXPECTED_SAMPLE_SHA256", sample)
    result = asset_layout.reconcile()
    assert result["ready"] and result["fully_consolidated"]
    assert clip.read_bytes() == b"fixture audio"


def test_successor_manifest_arithmetic_and_exclusions_when_materialized() -> None:
    roots = portable_roots(REPOSITORY)
    result = verify_successor(roots)
    if not result["valid"]:
        pytest.skip("machine-local successor is absent")
    freeze_path = Path(result["path"])
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    assert freeze["parent_phase4"] == {
        "id": PARENT_PHASE4_ID,
        "sha256": PARENT_PHASE4_SHA256,
        "logical_path": "JP_TRAINING_ROOT:successors/phase4_training_manifests_v1/registries/training_manifest_freeze_phase4.json",
    }
    age = freeze["source_manifests"]["AGE_TRAIN"]
    dev = freeze["source_manifests"]["AGE_DEV"]
    assert (age["record_count"], age["speaker_count"]) == (91_123, 1_217)
    assert age["effective_unique_source_hours"] == pytest.approx(139.79333974338232)
    assert (dev["record_count"], dev["speaker_count"]) == (10_288, 35)
    assert dev["effective_unique_source_hours"] == pytest.approx(18.055174539930555)
    declarations = freeze["declarations"]
    assert declarations["former_common_voice_heldout_reclassified_to_train"]
    assert not declarations["common_voice_final_heldout_required"]
    assert not declarations["age_dev_used_for_gradients"]
    assert declarations["large_benchmark_is_independent_post_training_benchmark"]
    age_frame = pd.read_parquet(resolve_logical_path(age["logical_path"], roots))
    assert set(age_frame["training_role"].astype(str)) == {"train"}
    assert bool(age_frame["training_eligible_for_experiment"].all())
    phase3 = pd.read_parquet(
        roots.training
        / "successors/common_voice_26_english_phase3/registries/common_voice_older_registry.parquet",
        columns=["source_item_id", "training_role"],
    )
    dev_ids = set(
        phase3.loc[
            phase3["training_role"].astype(str) == "dev", "source_item_id"
        ].astype(str)
    )
    assert dev_ids.isdisjoint(set(age_frame["source_registry_row_id"].astype(str)))


def test_successor_bundle_weights_are_canonical_and_robust_is_unchanged() -> None:
    roots = portable_roots(REPOSITORY)
    result = verify_successor(roots)
    if not result["valid"]:
        pytest.skip("machine-local successor is absent")
    freeze = json.loads(Path(result["path"]).read_text(encoding="utf-8"))
    robust = freeze["bundles"]["ROBUST"]
    assert robust["id"] == "robust_bundle_204aa1c051dd"
    assert robust["sha256"] == (
        "204AA1C051DD159AABB6B870000F2B48A4A0DDC2273B192A4CDE48FD524FB239"
    )
    age = freeze["source_manifests"]["AGE_TRAIN"]["effective_unique_source_hours"]
    source = freeze["source_manifests"]
    hours = {
        "common_voice": age,
        "ami": source["AMI_TRAIN"]["effective_unique_source_hours"],
        "chime6": source["CHIME_TRAIN"]["effective_unique_source_hours"],
        "voices": source["VOICES_TRAIN"]["effective_unique_source_hours"],
    }
    expected = dataset_weights(hours)
    bundle = json.loads(
        resolve_logical_path(
            freeze["bundles"]["AGE_ROBUST"]["logical_path"], roots
        ).read_text(encoding="utf-8")
    )
    actual = {item["dataset_id"]: item["probability"] for item in bundle["train_sources"]}
    assert actual == {key: value["final_probability"] for key, value in expected.items()}
    assert sum(Decimal(value) for value in actual.values()) == Decimal(1)


def test_successor_plan_is_eight_original_jobs_without_giga() -> None:
    assert [item[0] for item in EXPERIMENTS] == [
        "O-AGE",
        "O-AMI",
        "O-CHIME",
        "O-VOICES",
        "O-ROBUST",
        "O-AGE-ROBUST",
        "O-CMU",
        "O-AGE-ROBUST-CMU",
    ]
    assert all(item[0].startswith("O-") for item in EXPERIMENTS)


def test_data_inventory_has_required_schema_and_no_git_audio() -> None:
    path = TOOL_ROOT / "handoff" / "training_handoff_data_inventory.json"
    inventory = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "DATASET_NAME",
        "DATASET_VERSION",
        "ROLE",
        "LICENSE",
        "REHOST_ALLOWED_OR_NOT",
        "COMMERCIAL_REVIEW_FLAG",
        "CANONICAL_LOGICAL_ROOT",
        "EXPECTED_SUBPATH",
        "CURRENT_LOCAL_RESOLVED_PATH",
        "SOURCE_ARCHIVE_OR_DIRECTORY",
        "EXPECTED_SIZE",
        "EXPECTED_SHA256",
        "NUMBER_OF_REQUIRED_FILES",
        "NUMBER_OF_REQUIRED_RECORDS",
        "ACQUISITION_METHOD",
        "OFFICIAL_SOURCE_REFERENCE",
        "GIT_TRACKED",
        "REQUIRED_ON_RECEIVER",
        "VERIFICATION_COMMAND",
    }
    assert {item["DATASET_NAME"] for item in inventory["SOURCES"]} >= {
        "Common Voice English older speakers",
        "AMI Meeting Corpus",
        "CHiME-6",
        "CMU Arctic",
        "VOiCES",
        "LibriSpeech",
        "Hi-Fi Multi-Speaker English TTS (HiFiTTS)",
    }
    assert all(required <= set(item) for item in inventory["SOURCES"])
    assert all(item["GIT_TRACKED"] == "NO" for item in inventory["SOURCES"])


def test_bootstrap_has_bounded_actions_and_is_dry_by_default() -> None:
    script = (TOOL_ROOT / "scripts" / "bootstrap_training_machine.ps1").read_text(
        encoding="utf-8"
    )
    for action in (
        "Diagnose",
        "Configure",
        "MaterializeData",
        "VerifyData",
        "BootstrapEnvironment",
        "VerifyModels",
        "Qualify",
        "Summary",
    ):
        assert f"'{action}'" in script
    assert "[switch]$Apply" in script
    assert "JP_WSL_DISTRO" in script


def test_parallel_dry_run_uses_isolated_status_and_defaults_to_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JP_RUN_ROOT", str(tmp_path / "runs with spaces"))
    plan = run_jobs(["O-AMI", "O-VOICES"], maximum=1, dry_run=True)
    assert plan["max_parallel_adapter_jobs"] == 1
    assert plan["independent_processes"]
    assert not plan["gpu_large_evaluation_concurrent"]
    roots = [Path(item["status_root"]) for item in plan["commands"]]
    assert roots[0] != roots[1]
    assert roots == [status_root("O-AMI"), status_root("O-VOICES")]


def test_parallel_two_is_blocked_without_measured_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("JP_RUN_ROOT", str(tmp_path))
    with pytest.raises(Exception, match="benchmark gate"):
        run_jobs(["O-AMI", "O-VOICES"], maximum=2, dry_run=True)
