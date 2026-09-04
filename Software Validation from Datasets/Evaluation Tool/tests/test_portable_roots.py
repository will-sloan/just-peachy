"""Small, non-inference checks for the Evaluation Tool portability contract."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.benchmark_contracts.scenario import scenario_identity
from app.extended_backends.registry import load_environment_profiles
from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.utils.paths import (
    RootResolutionError,
    data_root,
    evaluation_output_root,
    find_project_root,
    find_repository_root,
    model_root,
    repository_root,
    resolve_data_path_from_logical,
    resolve_metadata_path,
    resolve_model_path_from_logical,
    root_diagnostic,
    run_root,
)


TOOL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]


def _portable_data_root(root: Path) -> Path:
    data = root / "Speech Data With Spaces"
    (data / "Normalized Metadata").mkdir(parents=True)
    (data / "Raw Datasets (Not formatted)").mkdir()
    return data


def test_defaults_preserve_the_existing_layout_and_ignore_cwd(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for variable in ("JP_REPO_ROOT", "JP_DATA_ROOT", "JP_MODEL_ROOT", "JP_RUN_ROOT"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.chdir(tmp_path)

    assert find_repository_root() == REPOSITORY_ROOT
    assert repository_root().path == REPOSITORY_ROOT
    assert data_root().path == REPOSITORY_ROOT / "Software Validation from Datasets"
    assert model_root().path == REPOSITORY_ROOT / "models"
    assert run_root().path == TOOL_ROOT / "runs"
    assert evaluation_output_root("generated_data") == TOOL_ROOT / "JustPeachyGeneratedData"
    assert evaluation_output_root("logs") == TOOL_ROOT / "JustPeachyLogs"
    assert evaluation_output_root("research_summaries") == TOOL_ROOT / "JustPeachyResearchSummaries"
    assert evaluation_output_root("results") == TOOL_ROOT / "JustPeachyResults"
    assert evaluation_output_root("transfers") == TOOL_ROOT / "JustPeachyTransfers"


def test_unknown_evaluation_output_category_fails_clearly() -> None:
    with pytest.raises(ValueError, match="Unknown Evaluation Tool output category"):
        evaluation_output_root("unknown")


def test_data_override_changes_only_physical_resolution_and_supports_spaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    data = _portable_data_root(tmp_path)
    audio = data / "Raw Datasets (Not formatted)" / "fixture audio.wav"
    audio.write_bytes(b"fixture")
    monkeypatch.setenv("JP_DATA_ROOT", str(data))

    logical = "RawDatasets/fixture audio.wav"
    assert find_project_root() == data
    assert resolve_data_path_from_logical("Raw Datasets (Not formatted)/fixture audio.wav") == audio
    assert resolve_metadata_path(logical, find_project_root()) == audio
    assert logical == "RawDatasets/fixture audio.wav"


def test_model_override_changes_only_physical_resolution_and_disables_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    models = tmp_path / "Model Cache With Spaces"
    asset = models / "cache" / "fixture" / "model.bin"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"model")
    monkeypatch.setenv("JP_MODEL_ROOT", str(models))

    logical = "models/cache/fixture/model.bin"
    assert resolve_model_path_from_logical(logical) == asset
    assert resolve_model_path(logical) == asset.resolve()
    assert logical == "models/cache/fixture/model.bin"


def test_invalid_explicit_root_fails_without_silent_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    missing = tmp_path / "not-present"
    monkeypatch.setenv("JP_MODEL_ROOT", str(missing))

    with pytest.raises(RootResolutionError, match="JP_MODEL_ROOT.*does not exist"):
        model_root()

    monkeypatch.delenv("JP_MODEL_ROOT")
    monkeypatch.setenv("JP_DATA_ROOT", str(missing))
    with pytest.raises(RootResolutionError, match="JP_DATA_ROOT.*does not exist"):
        data_root()

    wrong_data = tmp_path / "existing-but-wrong"
    wrong_data.mkdir()
    monkeypatch.setenv("JP_DATA_ROOT", str(wrong_data))
    with pytest.raises(RootResolutionError, match="JP_DATA_ROOT.*data root"):
        data_root()


def test_logical_scenario_identity_is_independent_of_physical_root_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    catalog = (
        TOOL_ROOT
        / "benchmarks"
        / "edge_research"
        / "scenarios_edge_screen_edge_cpu.jsonl"
    )
    scenario = json.loads(catalog.read_text(encoding="utf-8").splitlines()[0])
    before = scenario_identity(scenario)
    models = tmp_path / "separate models"
    models.mkdir()
    monkeypatch.setenv("JP_MODEL_ROOT", str(models))

    assert scenario_identity(scenario) == before
    assert scenario["scenario_id"] == before[1]


def test_diagnostic_reports_all_roots_without_starting_work() -> None:
    locations = {item.name: item for item in root_diagnostic()}

    assert set(locations) == {"repository", "data", "model", "run", "training"}
    assert locations["repository"].environment_variable == "JP_REPO_ROOT"
    assert locations["repository"].source in {"default", "environment override"}


def test_run_root_override_is_reported_without_affecting_logical_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runs = tmp_path / "runs with spaces"
    runs.mkdir()
    monkeypatch.setenv("JP_RUN_ROOT", str(runs))

    assert run_root().path == runs


def test_environment_profile_identity_does_not_include_physical_model_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    before = load_environment_profiles()
    models = tmp_path / "relocated model cache"
    models.mkdir()
    monkeypatch.setenv("JP_MODEL_ROOT", str(models))

    assert load_environment_profiles() == before
    assert set(before["profiles"]) >= {"core-cpu", "edge-cpu", "moonshine-edge", "onnx"}
