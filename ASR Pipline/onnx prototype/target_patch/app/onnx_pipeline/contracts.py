from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class InferenceRecord:
    """Normalized input to the ONNX pipeline.

    This object is intentionally independent from the Evaluation Tool record dict.
    """

    recording_id: str
    utt_id: str
    inference_audio_path: Path
    start_sec: float | None = None
    end_sec: float | None = None
    source_recording_id: str | None = None
    reference_text: str | None = None
    reference_speaker_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SpeechSegment:
    """Time span in seconds relative to the provided audio input."""

    start_sec: float
    end_sec: float


@dataclass(slots=True)
class SpeakerMatch:
    """Outcome of speaker matching against the enrollment gallery."""

    label: str | None
    best_score: float | None
    second_best_score: float | None
    accepted: bool
    reason: str


@dataclass(slots=True)
class UtterancePredictionData:
    """Prediction payload that can be converted to the Evaluation Tool contract."""

    recording_id: str
    utt_id: str
    text: str
    start_sec: float | None = None
    end_sec: float | None = None
    speaker_label: str | None = None
    debug: dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "recording_id": self.recording_id,
            "utt_id": self.utt_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "speaker_label": self.speaker_label,
            "text": self.text,
        }
