"""Speaker embedding interfaces and adapters."""

from app.inference_pipeline.speaker_embedding.base import (
    DEFAULT_MIN_DURATION_SEC,
    DeterministicFakeSpeakerEmbedding,
    NoOpSpeakerEmbedding,
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
    SpeakerEmbeddingRuntimeStats,
    build_speaker_embedding_from_config,
    component_report_path,
    embedding_id,
    is_l2_normalized,
    normalize_vector,
    vector_l2_norm,
)
from app.inference_pipeline.speaker_embedding.report import (
    SimilarityDistribution,
    cosine_similarity,
    summarize_similarity_distribution,
    write_speaker_embedding_report,
)
from app.inference_pipeline.speaker_embedding.resemblyzer_adapter import (
    ResemblyzerSpeakerEmbeddingAdapter,
    ResemblyzerUnavailableError,
)
from app.inference_pipeline.speaker_embedding.redimnet2_adapter import (
    ReDimNet2B2SpeakerEmbeddingAdapter,
    ReDimNet2UnavailableError,
)
from app.inference_pipeline.speaker_embedding.sherpa_onnx_adapter import (
    CAMPlusSpeakerEmbeddingAdapter,
    ERes2NetBaseSpeakerEmbeddingAdapter,
    SherpaOnnxSpeakerEmbeddingAdapter,
    SherpaOnnxSpeakerEmbeddingUnavailableError,
)
from app.inference_pipeline.speaker_embedding.wespeaker_adapter import (
    WeSpeakerEmbeddingAdapter,
    WeSpeakerUnavailableError,
)

__all__ = [
    "CAMPlusSpeakerEmbeddingAdapter",
    "DEFAULT_MIN_DURATION_SEC",
    "DeterministicFakeSpeakerEmbedding",
    "ERes2NetBaseSpeakerEmbeddingAdapter",
    "NoOpSpeakerEmbedding",
    "ResemblyzerSpeakerEmbeddingAdapter",
    "ResemblyzerUnavailableError",
    "ReDimNet2B2SpeakerEmbeddingAdapter",
    "ReDimNet2UnavailableError",
    "SimilarityDistribution",
    "SpeakerEmbedding",
    "SpeakerEmbeddingBase",
    "SpeakerEmbeddingContext",
    "SpeakerEmbeddingRuntimeStats",
    "SherpaOnnxSpeakerEmbeddingAdapter",
    "SherpaOnnxSpeakerEmbeddingUnavailableError",
    "WeSpeakerEmbeddingAdapter",
    "WeSpeakerUnavailableError",
    "build_speaker_embedding_from_config",
    "component_report_path",
    "cosine_similarity",
    "embedding_id",
    "is_l2_normalized",
    "normalize_vector",
    "summarize_similarity_distribution",
    "vector_l2_norm",
    "write_speaker_embedding_report",
]
