"""Standardized prediction schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class UtterancePrediction:
    """Minimum utterance-level prediction contract."""

    recording_id: str
    utt_id: str
    start_sec: float | None
    end_sec: float | None
    speaker_label: str | None
    text: str

    def to_jsonable(self) -> dict[str, object]:
        """Convert to a JSONL row."""

        return asdict(self)


@dataclass(frozen=True)
class WordPrediction:
    """Optional word-level prediction contract."""

    recording_id: str
    utt_id: str
    start_sec: float | None
    end_sec: float | None
    word: str
    speaker_label: str | None
    confidence: float | None = None

    def to_jsonable(self) -> dict[str, object]:
        """Convert to a JSONL row."""

        return asdict(self)


UTTERANCE_REQUIRED_FIELDS = (
    "recording_id",
    "utt_id",
    "start_sec",
    "end_sec",
    "speaker_label",
    "text",
)

WORD_REQUIRED_FIELDS = (
    "recording_id",
    "utt_id",
    "start_sec",
    "end_sec",
    "word",
    "speaker_label",
    "confidence",
)
