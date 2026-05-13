import importlib
import json
import sys
from pathlib import Path

import pytest

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.registry import (
    UnknownComponentError,
    dry_run_config,
    resolve_components,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
FORBIDDEN_MODEL_MODULES = {
    "torch",
    "numpy",
    "transformers",
    "speechbrain",
    "whisper",
    "silero",
}


def load_config(name: str) -> PipelineConfig:
    return PipelineConfig.from_yaml_path(CONFIG_ROOT / name)


def test_cpu_smoke_config_loads_successfully() -> None:
    config = load_config("cpu_smoke.yaml")
    dry_run = dry_run_config(config)

    assert config.config_name == "cpu_smoke"
    assert config.runtime.device == "cpu"
    assert config.runtime.dry_run is True
    assert config.runtime.allow_model_downloads is False
    assert dry_run["components"]["asr"]["adapter_class"] == "NoOpASRAdapter"


def test_base_config_loads_successfully() -> None:
    config = load_config("base.yaml")

    assert config.config_name == "base"
    assert set(config.components) == {
        "vad",
        "segmentation",
        "asr",
        "speaker_embedding",
        "speaker_matching",
    }


def test_desktop_gpu_config_resolves_without_model_imports() -> None:
    before_modules = set(sys.modules)
    config = load_config("desktop_gpu.yaml")
    dry_run = dry_run_config(config)
    after_modules = set(sys.modules)

    assert dry_run["runtime"]["device"] == "cuda"
    assert dry_run["components"]["vad"]["adapter_class"] == "SileroVADAdapter"
    assert dry_run["components"]["asr"]["adapter_class"] == "WhisperTinyASRAdapter"
    assert (
        dry_run["components"]["speaker_embedding"]["adapter_class"]
        == "SpeechBrainECAPAAdapter"
    )
    assert FORBIDDEN_MODEL_MODULES.isdisjoint(after_modules - before_modules)


def test_raspberry_pi_future_config_loads_as_future_profile() -> None:
    config = load_config("raspberry_pi_future.yaml")

    assert config.future is True
    assert config.runtime.device == "cpu"
    assert config.runtime.precision == "int8"


def test_changing_asr_or_vad_names_changes_resolved_components() -> None:
    mapping = load_config("cpu_smoke.yaml").to_jsonable()
    original = PipelineConfig.from_mapping(mapping)
    swapped_mapping = json.loads(json.dumps(mapping))
    swapped_mapping["components"]["asr"]["name"] = "whisper_tiny"
    swapped_mapping["components"]["asr"]["adapter"] = "WhisperTinyASRAdapter"
    swapped_mapping["components"]["vad"]["name"] = "silero_vad"
    swapped_mapping["components"]["vad"]["adapter"] = "SileroVADAdapter"
    swapped = PipelineConfig.from_mapping(swapped_mapping)

    original_resolved = resolve_components(original)
    swapped_resolved = resolve_components(swapped)

    assert original_resolved["asr"].adapter_class.__name__ == "NoOpASRAdapter"
    assert swapped_resolved["asr"].adapter_class.__name__ == "WhisperTinyASRAdapter"
    assert original_resolved["vad"].adapter_class.__name__ == "NoOpVADAdapter"
    assert swapped_resolved["vad"].adapter_class.__name__ == "SileroVADAdapter"


def test_unknown_component_name_fails_cleanly() -> None:
    mapping = load_config("cpu_smoke.yaml").to_jsonable()
    mapping["components"]["asr"]["name"] = "definitely_not_registered"
    config = PipelineConfig.from_mapping(mapping)

    with pytest.raises(UnknownComponentError, match="unknown component"):
        resolve_components(config)


def test_disabled_components_are_represented_in_dry_run_output() -> None:
    mapping = load_config("cpu_smoke.yaml").to_jsonable()
    mapping["components"]["vad"]["name"] = "disabled_custom_vad"
    mapping["components"]["vad"]["enabled"] = False
    config = PipelineConfig.from_mapping(mapping)
    dry_run = dry_run_config(config)

    vad = dry_run["components"]["vad"]
    assert vad["enabled"] is False
    assert vad["name"] == "disabled_custom_vad"
    assert vad["adapter_class"] == "DisabledComponentAdapter"


def test_pipeline_config_to_jsonable_is_json_serializable() -> None:
    config = load_config("cpu_smoke.yaml")

    json.dumps(config.to_jsonable())


def test_dry_run_output_is_json_serializable() -> None:
    config = load_config("desktop_gpu.yaml")

    json.dumps(dry_run_config(config))


def test_config_modules_import_without_ml_frameworks() -> None:
    before_modules = set(sys.modules)
    importlib.import_module("app.inference_pipeline.config")
    importlib.import_module("app.inference_pipeline.registry")
    after_modules = set(sys.modules)

    assert FORBIDDEN_MODEL_MODULES.isdisjoint(after_modules - before_modules)

