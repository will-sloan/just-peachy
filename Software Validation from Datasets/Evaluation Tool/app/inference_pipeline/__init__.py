"""Model-free contracts for future inference pipeline milestones."""

from app.inference_pipeline.contracts import (
    ASRTranscript,
    AudioSegment,
    EvaluationRecord,
    PipelineOutput,
    RuntimeStats,
    SpeakerDecision,
    SpeakerEmbedding,
    SpeechRegion,
    TranscriptItem,
    WordTiming,
)
from app.inference_pipeline.config import (
    ComponentConfig,
    ConfigValidationError,
    PipelineConfig,
    RuntimeOptions,
)
from app.inference_pipeline.errors import (
    ContractValidationError,
    IdentityMismatchError,
    InferencePipelineError,
    MissingRequiredFieldError,
)
from app.inference_pipeline.registry import (
    UnknownComponentError,
    dry_run_config,
    resolve_component,
    resolve_components,
)

__all__ = [
    "ASRTranscript",
    "AudioSegment",
    "ComponentConfig",
    "ConfigValidationError",
    "ContractValidationError",
    "EvaluationRecord",
    "IdentityMismatchError",
    "InferencePipelineError",
    "MissingRequiredFieldError",
    "PipelineOutput",
    "PipelineConfig",
    "RuntimeStats",
    "RuntimeOptions",
    "SpeakerDecision",
    "SpeakerEmbedding",
    "SpeechRegion",
    "TranscriptItem",
    "UnknownComponentError",
    "WordTiming",
    "dry_run_config",
    "resolve_component",
    "resolve_components",
]

