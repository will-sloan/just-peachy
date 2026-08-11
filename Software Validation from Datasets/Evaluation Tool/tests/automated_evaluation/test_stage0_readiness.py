from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.registry import REGISTERED_COMPONENTS
from scripts.qualify_speech_components import _reference_asr_fragment


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
CONFIG_ROOT = TOOL_ROOT / "configs" / "automated_evaluation"
DOC_ROOT = TOOL_ROOT / "docs" / "automated_evaluation"


def _yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _component_registry() -> dict[str, object]:
    return _yaml(CONFIG_ROOT / "component_registry.v1.yaml")


def test_registry_schema_is_complete_and_uses_declared_vocabularies() -> None:
    registry = _component_registry()
    assert registry["schema_version"] == "component-registry.v1"
    components = registry["components"]
    assert isinstance(components, list) and components

    required = {
        "id",
        "family",
        "name",
        "implementation_class",
        "implementation_path",
        "registry_adapter_class",
        "config_path",
        "config_sha256",
        "higher_level_config_references",
        "packages",
        "model_assets",
        "credential_requirements",
        "model_terms",
        "supported_os",
        "hardware_support",
        "device_dtype_support",
        "input_contract",
        "output_contract",
        "compatibility_constraints",
        "readiness",
        "intended_final_use_category",
    }
    readiness_vocabulary = set(registry["readiness_status_vocabulary"])
    category_vocabulary = set(registry["final_use_categories"])
    ids: set[str] = set()
    for component in components:
        assert isinstance(component, dict)
        assert required <= component.keys()
        assert component["id"] not in ids
        ids.add(component["id"])
        assert component["readiness"]["status"] in readiness_vocabulary
        assert component["intended_final_use_category"] in category_vocabulary
        assert component["input_contract"] in registry["contracts"]
        assert component["output_contract"] in registry["contracts"]


def test_every_runtime_registered_component_has_a_disposition() -> None:
    components = _component_registry()["components"]
    inventoried = {(item["family"], item["name"]) for item in components}
    registered = {
        (slot, name)
        for slot, by_name in REGISTERED_COMPONENTS.items()
        for name in by_name
    }
    assert registered <= inventoried


def test_every_component_fragment_is_inventoried_with_exact_hash() -> None:
    components = _component_registry()["components"]
    by_slot_name = {
        (item["family"], item["name"]): item
        for item in components
        if item["family"] in REGISTERED_COMPONENTS
    }
    fragment_root = TOOL_ROOT / "configs" / "inference" / "components"
    discovered: set[tuple[str, str]] = set()
    for path in fragment_root.rglob("*.yaml"):
        fragment = _yaml(path)["component"]
        key = (fragment["slot"], fragment["name"])
        discovered.add(key)
        item = by_slot_name[key]
        assert TOOL_ROOT / item["config_path"] == path
        assert item["config_sha256"] == _sha256(path)
    assert discovered <= by_slot_name.keys()


def test_registry_file_references_exist() -> None:
    for item in _component_registry()["components"]:
        assert (TOOL_ROOT / item["implementation_path"]).is_file()
        if item["config_path"] is not None:
            assert (TOOL_ROOT / item["config_path"]).is_file()
        for reference in item["higher_level_config_references"]:
            assert (TOOL_ROOT / reference).is_file(), reference


def test_higher_level_config_references_are_complete() -> None:
    components = _component_registry()["components"]
    by_slot_name = {
        (item["family"], item["name"]): item
        for item in components
        if item["family"] in REGISTERED_COMPONENTS
    }
    expected = {key: set() for key in by_slot_name}
    inference_root = TOOL_ROOT / "configs" / "inference"
    for path in inference_root.glob("*.yaml"):
        config = PipelineConfig.from_yaml_path(path)
        relative = path.relative_to(TOOL_ROOT).as_posix()
        for slot, component in config.components.items():
            expected[(slot, component.name)].add(relative)

    for key, references in expected.items():
        assert set(by_slot_name[key]["higher_level_config_references"]) == references


def test_decision_freeze_is_machine_readable_and_consistent() -> None:
    registry = _component_registry()
    profiles = _yaml(CONFIG_ROOT / "environment_profiles.v1.yaml")
    assert registry["default_seed"] == 3800
    assert registry["reference_asr"] == "whisper_base"
    assert registry["smoke_asr"] == "whisper_tiny"
    assert registry["required_candidate_asr"] == ["whisper_small"]
    assert set(registry["excluded_asr_markers"]) == {"medium", "large", "turbo"}
    assert _reference_asr_fragment()["name"] == "whisper_base"

    rir = profiles["rir_identity_freeze"]
    assert rir["selected_scope"] == ["dining_room", "bedroom", "restaurant"]
    assert rir["bedroom"]["status"] == "pending_decision"
    assert rir["parking_lot"]["file"] == "h044_ParkingLot_4txts.wav"
    assert rir["parking_lot"]["status"] == "excluded"
    assert rir["acoustic_characterization_required"] is False


def test_all_required_environment_profiles_are_defined() -> None:
    profiles = _yaml(CONFIG_ROOT / "environment_profiles.v1.yaml")["profiles"]
    assert set(profiles) == {
        "core_cpu_development",
        "core_cuda",
        "extended_local_backends",
        "onnx_backends",
        "credential_gated_diarization",
        "linux_cuda_nemo",
        "test_only_contract",
    }
    assert profiles["core_cpu_development"]["device"] == "cpu"
    assert profiles["core_cuda"]["status"] == "qualified"
    assert profiles["core_cuda"]["device"] == "cuda:0"
    assert profiles["core_cuda"]["dtype"] == "float32"
    assert profiles["credential_gated_diarization"][
        "credential_environment_variables"
    ] == ["PYANNOTE_AUTH_TOKEN", "PICOVOICE_ACCESS_KEY"]
    assert profiles["linux_cuda_nemo"]["supported_os"] == ["linux"]


def test_core_model_assets_match_frozen_sizes_and_hashes() -> None:
    assets = _yaml(CONFIG_ROOT / "environment_profiles.v1.yaml")[
        "model_asset_inventory"
    ]
    for name in ("whisper_tiny", "whisper_base", "whisper_small"):
        item = assets[name]
        path = REPOSITORY_ROOT / item["path"]
        assert path.stat().st_size == item["bytes"]
        assert _sha256(path) == item["sha256"]

    speechbrain = assets["speechbrain_ecapa"]
    directory = REPOSITORY_ROOT / speechbrain["path"]
    for filename, expected in speechbrain["files"].items():
        path = directory / filename
        assert path.stat().st_size == expected["bytes"]
        assert _sha256(path) == expected["sha256"]


def test_readiness_documents_include_required_safety_and_run_guidance() -> None:
    readme = (DOC_ROOT / "README.md").read_text(encoding="utf-8")
    freeze = (DOC_ROOT / "stage_0_readiness_freeze.md").read_text(encoding="utf-8")
    protected = (DOC_ROOT / "protected_interfaces.md").read_text(encoding="utf-8")
    assert "Anaconda Prompt" in readme
    assert "Inputs and outputs" in readme
    assert "No secrets" in readme
    assert "Whisper Base" in freeze
    assert "h044_ParkingLot_4txts.wav" in freeze
    assert "Unknown" in protected and "preserved and scored" in protected
    assert 'record["inference_audio_path"]' in protected
    assert "predictions/utterances.jsonl" in protected
    assert "benchmark-manifest.v1" in protected
