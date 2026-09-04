"""Explicit assets and scheduling policy for the clean edge pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
EVALUATION_ROOT = Path(__file__).resolve().parents[2]


def default_data_root() -> Path:
    value = os.environ.get("EDGE_SPEECH_DATA_ROOT")
    return Path(value).expanduser().resolve() if value else EVALUATION_ROOT


@dataclass(frozen=True)
class AssetSpec:
    component_id: str
    path: Path
    sha256: str
    deployment_relative_path: str


def default_assets() -> tuple[AssetSpec, ...]:
    bundle_root_value = os.environ.get("EDGE_SPEECH_ASSET_ROOT")
    if bundle_root_value:
        bundle = Path(bundle_root_value).expanduser().resolve()
        asr = bundle / "models" / "sherpa_giga"
        portable = bundle / "models" / "h2"
    else:
        asr = REPOSITORY_ROOT / "models" / "cache" / "sherpa_onnx" / "asr" / (
            "sherpa-onnx-streaming-zipformer-en-2023-06-21"
        )
        punctuation = REPOSITORY_ROOT / "models" / "cache" / "sherpa_onnx" / (
            "punctuation/sherpa-onnx-online-punct-en-2024-08-06"
        )
        portable = EVALUATION_ROOT / "JustPeachyResults" / "h2_product_program" / (
            "portability_bounded_20260824"
        )
    if bundle_root_value:
        punctuation = bundle / "models" / "punctuation"
    return (
        AssetSpec("sherpa_giga_encoder_int8", asr / "encoder-epoch-99-avg-1.int8.onnx", "32c98281c7bd8b63e3e142d007251b37f120572e8fdea9a4f5a79ce22b10ec4f", "models/sherpa_giga/encoder-epoch-99-avg-1.int8.onnx"),
        AssetSpec("sherpa_giga_decoder_fp32", asr / "decoder-epoch-99-avg-1.onnx", "9da02b77cb08826756ec6a88635f35a40374e4164e7c6359121a9145958a6ceb", "models/sherpa_giga/decoder-epoch-99-avg-1.onnx"),
        AssetSpec("sherpa_giga_joiner_int8", asr / "joiner-epoch-99-avg-1.int8.onnx", "831477d390e59a61f1b6a6f763b9903e6c6366ff6034f1ddba613be82637122f", "models/sherpa_giga/joiner-epoch-99-avg-1.int8.onnx"),
        AssetSpec("sherpa_giga_tokens", asr / "tokens.txt", "49e3c2646595fd907228b3c6787069658f67b17377c60aeb8619c4551b2316fb", "models/sherpa_giga/tokens.txt"),
        AssetSpec("sherpa_online_punctuation_int8", punctuation / "model.int8.onnx", "9d611f445fe4a46186080fe161be6059d87d72eb88d3a8cb00c1a06e83a6067e", "models/punctuation/model.int8.onnx"),
        AssetSpec("sherpa_online_punctuation_bpe", punctuation / "bpe.vocab", "e118b7ad88c54db562517df49e1cffd4836d166c34fb190fd311d7f34eb238f5", "models/punctuation/bpe.vocab"),
        AssetSpec("redimnet2_b2_fp32", portable / "redimnet2_b2_fp32.onnx", "5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609", "models/h2/redimnet2_b2_fp32.onnx"),
        AssetSpec("pyannote_segmentation_3_0_fp32", portable / "pyannote_segmentation_3_0_fp32.onnx", "b4b65085bbf2cc455565696604c87fedade1359aa6ddfac5d726d69124d5069a", "models/h2/pyannote_segmentation_3_0_fp32.onnx"),
    )


@dataclass(frozen=True)
class PipelineConfig:
    sample_rate: int = 16_000
    capture_block_ms: int = 20
    journal_read_ms: int = 100
    raw_capture_reserve_sec: int = 120
    asr_threads: int = 2
    punctuation_threads: int = 1
    speaker_threads: int = 2
    endpoint_rule1_silence_sec: float = 2.4
    endpoint_rule2_silence_sec: float = 1.2
    endpoint_rule3_utterance_sec: float = 20.0
    segmentation_window_sec: float = 10.0
    segmentation_hop_sec: float = 0.75
    segmentation_onset: float = 0.46
    segmentation_offset: float = 0.45
    embedding_window_sec: float = 0.5
    embedding_hop_sec: float = 0.25
    clustering_threshold: float = 0.35
    identity_score_threshold: float = 0.5128856897354127
    identity_margin_threshold: float = 0.03
    identity_minimum_evidence_sec: float = 2.0
    minimum_rms: float = 0.002
    session_root: Path = field(default_factory=lambda: default_data_root() / "edge_speech_sessions")
    profile_root: Path = field(default_factory=lambda: default_data_root() / "edge_speech_profiles")
    assets: tuple[AssetSpec, ...] = field(default_factory=default_assets)

    def asset(self, component_id: str) -> AssetSpec:
        for item in self.assets:
            if item.component_id == component_id:
                return item
        raise KeyError(component_id)
