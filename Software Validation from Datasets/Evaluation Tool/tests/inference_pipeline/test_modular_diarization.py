from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.diarization import (
    ModularClusteringDiarizer,
    build_diarizer_from_config,
)
from app.inference_pipeline.diarization.modular_adapter import (
    _speech_overlap_channels,
)
from app.inference_pipeline.diarization.clustering import (
    agglomerative_cosine_labels,
)
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.registry import resolve_components


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"


def test_cosine_clustering_is_deterministic_and_anonymous_label_ready() -> None:
    embeddings = [
        [1.0, 0.0],
        [0.99, 0.01],
        [0.0, 1.0],
        [0.01, 0.99],
    ]

    first = agglomerative_cosine_labels(embeddings, threshold=0.9)
    second = agglomerative_cosine_labels(embeddings, threshold=0.9)

    assert first == second == [0, 0, 1, 1]
    assert [f"speaker_{label:02d}" for label in first] == [
        "speaker_00",
        "speaker_00",
        "speaker_01",
        "speaker_01",
    ]


def test_clustering_rejects_nonfinite_input() -> None:
    with pytest.raises(ContractValidationError, match="finite"):
        agglomerative_cosine_labels([[1.0, 0.0], [float("nan"), 1.0]], threshold=0.5)


def test_clustering_accepts_maximum_above_available_windows() -> None:
    assert agglomerative_cosine_labels(
        [[1.0, 0.0], [0.99, 0.01]],
        threshold=0.9,
        max_clusters=8,
    ) == [0, 0]


def test_pyannote_reduction_preserves_speech_and_second_speaker_overlap() -> None:
    scores = np.asarray(
        [[[0.9, 0.2, 0.1], [0.8, 0.7, 0.1], [0.4, 0.3, 0.2]]],
        dtype=np.float32,
    )
    reduced = _speech_overlap_channels(scores)
    assert reduced.shape == (1, 3, 2)
    np.testing.assert_allclose(reduced[..., 0], [[0.9, 0.8, 0.4]])
    np.testing.assert_allclose(reduced[..., 1], [[0.2, 0.7, 0.3]])


@pytest.mark.parametrize(
    "fragment",
    [
        "components/diarization/modular_energy_campplus.yaml",
        "components/diarization/modular_pyannote_campplus.yaml",
        "components/diarization/modular_pyannote_eres2net.yaml",
        "components/diarization/modular_energy_wespeaker.yaml",
    ],
)
def test_modular_diarization_fragments_resolve_without_loading_models(
    fragment: str,
) -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["diarization"] = fragment
    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )

    resolved = resolve_components(config)["diarization"]
    built = build_diarizer_from_config(config)

    assert resolved.name.startswith("modular_")
    assert isinstance(built, ModularClusteringDiarizer)
    assert built.clustering_policy_id.startswith("diarization_")


def test_future_pyannote_redimnet_composition_requires_configuration_only() -> None:
    config = PipelineConfig.from_yaml_path(
        CONFIG_ROOT / "cpu_smoke.yaml"
    ).to_jsonable()
    config["components"]["diarization"] = {
        "name": "modular_pyannote_redimnet2_b2",
        "adapter": "ModularClusteringDiarizer",
        "params": {
            "model_source": "modular/future-test",
            "segmentation_source": "pyannote_segmentation_3_0",
            "segmentation_model_path": "models/cache/pyannote/segmentation-3.0",
            "embedding_component_config": "configs/inference/components/speaker_embedding/redimnet2_b2.yaml",
            "clustering_policy_id": "future_test_only",
            "clustering_threshold": 0.5,
        },
    }

    pipeline = PipelineConfig.from_mapping(config, tool_root=TOOL_ROOT)
    resolved = resolve_components(pipeline)["diarization"]
    built = build_diarizer_from_config(pipeline)

    assert isinstance(built, ModularClusteringDiarizer)
    assert built.embedding_component_config.endswith("redimnet2_b2.yaml")
    assert resolved.name == "modular_pyannote_redimnet2_b2"
    assert resolved.adapter_class.__name__ == "ModularDiarizationConfigAdapter"
