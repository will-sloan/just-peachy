"""Model-free contracts for the future inference pipeline."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .errors import (
    ContractValidationError,
    IdentityMismatchError,
    MissingRequiredFieldError,
)
from .typing import JsonObject, JsonValue


UTTERANCE_PREDICTION_FIELDS = (
    "recording_id",
    "utt_id",
    "start_sec",
    "end_sec",
    "speaker_label",
    "text",
)


@dataclass(frozen=True)
class EvaluationRecord:
    """One selected Evaluation Tool metadata row prepared for inference."""

    recording_id: str
    utt_id: str
    inference_audio_path: Path
    start_sec: float | None = None
    end_sec: float | None = None
    speaker_label: str | None = None
    source_recording_id: str | None = None
    augmentation_condition_id: str | None = None
    augmentation_mode: str | None = None
    channel_index: int | None = None
    channel_count: int | None = None
    sample_rate_hz: int | None = None
    duration_sec: float | None = None
    extras: JsonObject | None = None

    def __post_init__(self) -> None:
        _validate_required_identity("recording_id", self.recording_id)
        _validate_required_identity("utt_id", self.utt_id)
        _validate_path(self.inference_audio_path, "inference_audio_path")
        _validate_time_range(self.start_sec, self.end_sec, "EvaluationRecord")
        _validate_channel(self.channel_index, self.channel_count)

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> "EvaluationRecord":
        """Build a contract object from one selected metadata row."""

        known_fields = {
            "recording_id",
            "utt_id",
            "inference_audio_path",
            "start_sec",
            "end_sec",
            "speaker_label",
            "source_recording_id",
            "augmentation_condition_id",
            "augmentation_mode",
            "channel_index",
            "channel_count",
            "sample_rate_hz",
            "duration_sec",
        }
        inference_audio_path = _required_path(record, "inference_audio_path")
        extras = {
            str(key): _jsonable(value)
            for key, value in record.items()
            if key not in known_fields
        }

        return cls(
            recording_id=_required_string(record, "recording_id"),
            utt_id=_required_string(record, "utt_id"),
            inference_audio_path=inference_audio_path,
            start_sec=_optional_float(record.get("start_sec"), "start_sec"),
            end_sec=_optional_float(record.get("end_sec"), "end_sec"),
            speaker_label=_optional_string(record.get("speaker_label")),
            source_recording_id=_optional_string(record.get("source_recording_id")),
            augmentation_condition_id=_optional_string(record.get("augmentation_condition_id")),
            augmentation_mode=_optional_string(record.get("augmentation_mode")),
            channel_index=_optional_int(record.get("channel_index"), "channel_index"),
            channel_count=_optional_int(record.get("channel_count"), "channel_count"),
            sample_rate_hz=_optional_int(record.get("sample_rate_hz"), "sample_rate_hz"),
            duration_sec=_optional_float(record.get("duration_sec"), "duration_sec"),
            extras=extras,
        )

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class AudioSegment:
    """Model-ready audio metadata for a full file or selected interval."""

    audio_path: Path
    start_sec: float | None = None
    end_sec: float | None = None
    sample_rate_hz: int | None = None
    channel_index: int | None = None
    channel_count: int = 1
    is_mono: bool | None = None
    duration_sec: float | None = None

    def __post_init__(self) -> None:
        _validate_path(self.audio_path, "audio_path")
        _validate_time_range(self.start_sec, self.end_sec, "AudioSegment")
        _validate_channel(self.channel_index, self.channel_count)
        if self.is_mono is None:
            object.__setattr__(self, "is_mono", self.channel_count == 1)

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class SpeechRegion:
    """Voice activity detection output for one speech-like region."""

    start_sec: float
    end_sec: float
    confidence: float | None = None
    channel_index: int | None = None
    label: str | None = None

    def __post_init__(self) -> None:
        _validate_time_range(self.start_sec, self.end_sec, "SpeechRegion")

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class WordTiming:
    """Optional ASR word with timing and confidence."""

    word: str
    start_sec: float | None = None
    end_sec: float | None = None
    confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.word.strip():
            raise ContractValidationError("word must be non-empty")
        _validate_time_range(self.start_sec, self.end_sec, "WordTiming")

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class ASRTranscript:
    """ASR output for an audio segment or speech region."""

    text: str
    words: tuple[WordTiming, ...] = ()
    language: str | None = None
    confidence: float | None = None
    start_sec: float | None = None
    end_sec: float | None = None

    def __post_init__(self) -> None:
        _validate_time_range(self.start_sec, self.end_sec, "ASRTranscript")
        object.__setattr__(self, "words", tuple(self.words))

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class SpeakerEmbedding:
    """Speaker embedding metadata without a tensor dependency."""

    embedding_id: str
    vector: tuple[float, ...]
    dim: int | None = None
    model_name: str | None = None
    channel_index: int | None = None
    source_region: SpeechRegion | None = None

    def __post_init__(self) -> None:
        _validate_required_identity("embedding_id", self.embedding_id)
        vector = tuple(float(value) for value in self.vector)
        object.__setattr__(self, "vector", vector)
        if self.dim is None:
            object.__setattr__(self, "dim", len(vector))
        elif self.dim != len(vector):
            raise ContractValidationError(
                f"dim {self.dim} does not match vector length {len(vector)}"
            )

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class SpeakerDecision:
    """Speaker matching or labeling output."""

    speaker_label: str | None = None
    confidence: float | None = None
    method: str | None = None
    embedding_id: str | None = None
    matched_reference_id: str | None = None
    notes: str | None = None

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class TranscriptItem:
    """A transcript span after optional VAD, ASR, and speaker processing."""

    text: str
    start_sec: float | None = None
    end_sec: float | None = None
    speaker_label: str | None = None
    confidence: float | None = None
    words: tuple[WordTiming, ...] = ()

    def __post_init__(self) -> None:
        _validate_time_range(self.start_sec, self.end_sec, "TranscriptItem")
        object.__setattr__(self, "words", tuple(self.words))

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class RuntimeStats:
    """Runtime timings, counters, and model version metadata."""

    total_sec: float | None = None
    audio_load_sec: float | None = None
    vad_sec: float | None = None
    asr_sec: float | None = None
    speaker_sec: float | None = None
    postprocess_sec: float | None = None
    device: str = "cpu"
    model_versions: JsonObject | None = None
    counters: JsonObject | None = None

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class PipelineOutput:
    """Final model-free output for one Evaluation Tool record."""

    recording_id: str
    utt_id: str
    start_sec: float | None
    end_sec: float | None
    speaker_label: str | None
    text: str
    transcript: ASRTranscript | None = None
    transcript_items: tuple[TranscriptItem, ...] = ()
    runtime_stats: RuntimeStats | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _validate_required_identity("recording_id", self.recording_id)
        _validate_required_identity("utt_id", self.utt_id)
        _validate_time_range(self.start_sec, self.end_sec, "PipelineOutput")
        object.__setattr__(self, "transcript_items", tuple(self.transcript_items))
        object.__setattr__(self, "warnings", tuple(str(value) for value in self.warnings))
        object.__setattr__(self, "errors", tuple(str(value) for value in self.errors))

    @classmethod
    def from_record_and_transcript(
        cls,
        record: EvaluationRecord,
        transcript: ASRTranscript,
        speaker_decision: SpeakerDecision | None = None,
        runtime_stats: RuntimeStats | None = None,
        transcript_items: Sequence[TranscriptItem] = (),
        warnings: Sequence[str] = (),
        errors: Sequence[str] = (),
    ) -> "PipelineOutput":
        """Build output from a source EvaluationRecord and ASR transcript."""

        speaker_label = (
            speaker_decision.speaker_label
            if speaker_decision is not None
            else record.speaker_label
        )
        return cls(
            recording_id=record.recording_id,
            utt_id=record.utt_id,
            start_sec=record.start_sec,
            end_sec=record.end_sec,
            speaker_label=speaker_label,
            text=transcript.text,
            transcript=transcript,
            transcript_items=tuple(transcript_items),
            runtime_stats=runtime_stats,
            warnings=tuple(warnings),
            errors=tuple(errors),
        ).validate_identity(record)

    def validate_identity(self, record: EvaluationRecord) -> "PipelineOutput":
        """Ensure this output still matches the source EvaluationRecord."""

        if self.recording_id != record.recording_id:
            raise IdentityMismatchError(
                f"recording_id changed from {record.recording_id!r} to {self.recording_id!r}"
            )
        if self.utt_id != record.utt_id:
            raise IdentityMismatchError(
                f"utt_id changed from {record.utt_id!r} to {self.utt_id!r}"
            )
        return self

    def to_utterance_prediction_row(self) -> JsonObject:
        """Return exactly the fields required by predictions/utterances.jsonl."""

        return {
            "recording_id": self.recording_id,
            "utt_id": self.utt_id,
            "start_sec": self.start_sec,
            "end_sec": self.end_sec,
            "speaker_label": self.speaker_label,
            "text": self.text,
        }

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for logs and reports."""

        return _dataclass_jsonable(self)


def _required_string(record: Mapping[str, object], field_name: str) -> str:
    if field_name not in record:
        raise MissingRequiredFieldError(f"missing required field {field_name!r}")
    value = record[field_name]
    if value is None:
        raise MissingRequiredFieldError(f"missing required field {field_name!r}")
    text = value if isinstance(value, str) else str(value)
    _validate_required_identity(field_name, text)
    return text


def _required_path(record: Mapping[str, object], field_name: str) -> Path:
    if field_name not in record or record[field_name] is None:
        raise MissingRequiredFieldError(f"missing required field {field_name!r}")
    path = Path(str(record[field_name]))
    _validate_path(path, field_name)
    return path


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value)


def _optional_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be a number or None") from exc


def _optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer or None") from exc


def _validate_required_identity(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise MissingRequiredFieldError(f"{field_name} must be a non-empty string")


def _validate_path(path: Path, field_name: str) -> None:
    if not str(path).strip():
        raise MissingRequiredFieldError(f"{field_name} must be a non-empty path")


def _validate_time_range(
    start_sec: float | None,
    end_sec: float | None,
    label: str,
) -> None:
    if start_sec is not None and end_sec is not None and end_sec < start_sec:
        raise ContractValidationError(f"{label} end_sec must be >= start_sec")


def _validate_channel(channel_index: int | None, channel_count: int | None) -> None:
    if channel_count is not None and channel_count < 1:
        raise ContractValidationError("channel_count must be at least 1")
    if channel_index is not None and channel_index < 0:
        raise ContractValidationError("channel_index must be >= 0")
    if (
        channel_index is not None
        and channel_count is not None
        and channel_index >= channel_count
    ):
        raise ContractValidationError("channel_index must be less than channel_count")


def _dataclass_jsonable(value: object) -> JsonObject:
    return {
        field.name: _jsonable(getattr(value, field.name))
        for field in fields(value)
    }


def _jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _dataclass_jsonable(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return str(value)

