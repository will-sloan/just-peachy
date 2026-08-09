"""Stage 10 speaker enrollment, calibration, and evaluation framework."""

from app.speaker_protocol.contracts import (
    BackendIdentity,
    EmbeddingObservation,
    SpeakerProtocolError,
    UNKNOWN_LABEL,
    backend_identity,
    eligible_embedding_backends,
    load_policy,
    validate_enrollment_compatibility,
)

__all__ = [
    "BackendIdentity",
    "EmbeddingObservation",
    "SpeakerProtocolError",
    "UNKNOWN_LABEL",
    "backend_identity",
    "eligible_embedding_backends",
    "load_policy",
    "validate_enrollment_compatibility",
]
