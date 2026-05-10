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
from app.inference_pipeline.errors import (
    ContractValidationError,
    IdentityMismatchError,
    InferencePipelineError,
    MissingRequiredFieldError,
)

__all__ = [
    "ASRTranscript",
    "AudioSegment",
    "ContractValidationError",
    "EvaluationRecord",
    "IdentityMismatchError",
    "InferencePipelineError",
    "MissingRequiredFieldError",
    "PipelineOutput",
    "RuntimeStats",
    "SpeakerDecision",
    "SpeakerEmbedding",
    "SpeechRegion",
    "TranscriptItem",
    "WordTiming",
]

