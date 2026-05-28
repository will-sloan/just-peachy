"""Speaker matching interfaces, matchers, and calibration helpers."""

from app.inference_pipeline.speaker_matching.base import (
    DECISION_ACCEPTED,
    DECISION_AMBIGUOUS,
    DECISION_BELOW_THRESHOLD,
    DECISION_DIMENSION_MISMATCH,
    DECISION_DISABLED,
    DECISION_INVALID_EMBEDDING,
    DECISION_MODEL_MISMATCH,
    DECISION_NO_ENROLLED_SPEAKERS,
    SCORING_MODE_CENTROID,
    SCORING_MODE_EXEMPLAR,
    UNKNOWN_LABEL,
    NoOpSpeakerMatcher,
    SpeakerDecision,
    SpeakerMatcherBase,
    SpeakerScore,
    build_speaker_matcher_from_config,
)
from app.inference_pipeline.speaker_matching.cosine_matcher import (
    CosineThresholdSpeakerMatcher,
)

_THRESHOLD_EXPORTS = {
    "CalibrationSample",
    "ThresholdCalibrationResult",
    "ThresholdMetrics",
    "VerificationMetrics",
    "calibrate_thresholds",
    "default_threshold_grid",
    "load_calibration_samples",
    "threshold_calibration_report_path",
    "write_threshold_calibration_report",
}

__all__ = [
    "DECISION_ACCEPTED",
    "DECISION_AMBIGUOUS",
    "DECISION_BELOW_THRESHOLD",
    "DECISION_DIMENSION_MISMATCH",
    "DECISION_DISABLED",
    "DECISION_INVALID_EMBEDDING",
    "DECISION_MODEL_MISMATCH",
    "DECISION_NO_ENROLLED_SPEAKERS",
    "SCORING_MODE_CENTROID",
    "SCORING_MODE_EXEMPLAR",
    "UNKNOWN_LABEL",
    "CalibrationSample",
    "CosineThresholdSpeakerMatcher",
    "NoOpSpeakerMatcher",
    "SpeakerDecision",
    "SpeakerMatcherBase",
    "SpeakerScore",
    "ThresholdCalibrationResult",
    "ThresholdMetrics",
    "VerificationMetrics",
    "build_speaker_matcher_from_config",
    "calibrate_thresholds",
    "default_threshold_grid",
    "load_calibration_samples",
    "threshold_calibration_report_path",
    "write_threshold_calibration_report",
]


def __getattr__(name: str) -> object:
    if name in _THRESHOLD_EXPORTS:
        from app.inference_pipeline.speaker_matching import thresholds

        return getattr(thresholds, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
