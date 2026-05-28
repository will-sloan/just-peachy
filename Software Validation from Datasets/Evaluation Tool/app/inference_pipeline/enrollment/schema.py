"""Serializable enrollment database schema for speaker exemplars."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject, JsonValue


ENROLLMENT_SCHEMA_VERSION = "m10.enrollment_db.v1"


@dataclass(frozen=True)
class EnrollmentExemplar:
    """One enrolled audio sample and its embedding metadata."""

    speaker_id: str
    display_name: str
    prompt_id: str
    audio_path: str
    embedding: tuple[float, ...]
    model_id: str
    created_at: str
    notes: str | None = None
    duration_sec: float | None = None
    embedding_id: str | None = None
    metadata: JsonObject | None = None

    def __post_init__(self) -> None:
        _validate_required_string("speaker_id", self.speaker_id)
        _validate_required_string("display_name", self.display_name)
        _validate_required_string("prompt_id", self.prompt_id)
        _validate_required_string("audio_path", self.audio_path)
        _validate_required_string("model_id", self.model_id)
        _validate_required_string("created_at", self.created_at)
        embedding = _embedding_vector(self.embedding)
        if not embedding:
            raise ContractValidationError("enrollment exemplar embedding must be non-empty")
        object.__setattr__(self, "embedding", embedding)
        if self.duration_sec is not None and self.duration_sec < 0:
            raise ContractValidationError("duration_sec must be >= 0 when present")
        object.__setattr__(self, "notes", _optional_string(self.notes))
        object.__setattr__(self, "embedding_id", _optional_string(self.embedding_id))
        object.__setattr__(self, "metadata", _json_object(self.metadata or {}, "metadata"))

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "EnrollmentExemplar":
        """Load an exemplar from a JSON-safe mapping."""

        return cls(
            speaker_id=_required_string(mapping, "speaker_id"),
            display_name=_required_string(mapping, "display_name"),
            prompt_id=_required_string(mapping, "prompt_id"),
            audio_path=_required_string(mapping, "audio_path"),
            embedding=_sequence_float_tuple(mapping.get("embedding"), "embedding"),
            model_id=_required_string(mapping, "model_id"),
            created_at=_required_string(mapping, "created_at"),
            notes=_optional_string(mapping.get("notes")),
            duration_sec=_optional_float(mapping.get("duration_sec"), "duration_sec"),
            embedding_id=_optional_string(mapping.get("embedding_id")),
            metadata=_optional_json_object(mapping.get("metadata"), "metadata"),
        )

    @property
    def dimension(self) -> int:
        return len(self.embedding)

    def to_jsonable(self) -> JsonObject:
        return {
            "speaker_id": self.speaker_id,
            "display_name": self.display_name,
            "prompt_id": self.prompt_id,
            "audio_path": self.audio_path,
            "embedding": list(self.embedding),
            "model_id": self.model_id,
            "created_at": self.created_at,
            "notes": self.notes,
            "duration_sec": self.duration_sec,
            "embedding_id": self.embedding_id,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class EnrollmentSpeaker:
    """One enrolled speaker with one or more exemplar embeddings."""

    speaker_id: str
    display_name: str
    exemplars: tuple[EnrollmentExemplar, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        _validate_required_string("speaker_id", self.speaker_id)
        _validate_required_string("display_name", self.display_name)
        object.__setattr__(self, "notes", _optional_string(self.notes))
        exemplars = tuple(self.exemplars)
        dimensions = set()
        for exemplar in exemplars:
            if exemplar.speaker_id != self.speaker_id:
                raise ContractValidationError("exemplar speaker_id does not match speaker")
            if _name_key(exemplar.display_name) != _name_key(self.display_name):
                raise ContractValidationError("exemplar display_name does not match speaker")
            dimensions.add(exemplar.dimension)
        if len(dimensions) > 1:
            raise ContractValidationError("speaker exemplars must have one embedding dimension")
        object.__setattr__(self, "exemplars", exemplars)

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "EnrollmentSpeaker":
        """Load a speaker from a JSON-safe mapping."""

        raw_exemplars = mapping.get("exemplars") or ()
        if not isinstance(raw_exemplars, Sequence) or isinstance(
            raw_exemplars,
            str | bytes | bytearray,
        ):
            raise ContractValidationError("speaker exemplars must be a list")
        exemplars = tuple(
            EnrollmentExemplar.from_mapping(_mapping_value(value, "exemplar"))
            for value in raw_exemplars
        )
        return cls(
            speaker_id=_required_string(mapping, "speaker_id"),
            display_name=_required_string(mapping, "display_name"),
            exemplars=exemplars,
            notes=_optional_string(mapping.get("notes")),
        )

    @property
    def centroid_embedding(self) -> tuple[float, ...]:
        """Return a normalized average embedding for centroid matching."""

        if not self.exemplars:
            return ()
        dimension = self.exemplars[0].dimension
        totals = [0.0] * dimension
        for exemplar in self.exemplars:
            for index, value in enumerate(exemplar.embedding):
                totals[index] += value
        mean = tuple(value / len(self.exemplars) for value in totals)
        return _normalize(mean)

    @property
    def duration_sec(self) -> float:
        return sum(
            float(exemplar.duration_sec)
            for exemplar in self.exemplars
            if exemplar.duration_sec is not None
        )

    @property
    def model_ids(self) -> tuple[str, ...]:
        return tuple(sorted({exemplar.model_id for exemplar in self.exemplars}))

    def to_jsonable(self) -> JsonObject:
        return {
            "speaker_id": self.speaker_id,
            "display_name": self.display_name,
            "notes": self.notes,
            "exemplars": [exemplar.to_jsonable() for exemplar in self.exemplars],
            "centroid_embedding": list(self.centroid_embedding),
            "duration_sec": self.duration_sec,
            "model_ids": list(self.model_ids),
        }


@dataclass(frozen=True)
class EnrollmentDatabase:
    """Versioned enrollment database independent of UI or run folders."""

    schema_version: str = ENROLLMENT_SCHEMA_VERSION
    speakers: tuple[EnrollmentSpeaker, ...] = ()
    created_at: str | None = None
    updated_at: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != ENROLLMENT_SCHEMA_VERSION:
            raise ContractValidationError(
                f"unsupported enrollment schema version {self.schema_version!r}"
            )
        speakers = tuple(self.speakers)
        speaker_ids: set[str] = set()
        speaker_names: set[str] = set()
        for speaker in speakers:
            if speaker.speaker_id in speaker_ids:
                raise ContractValidationError(f"duplicate speaker_id {speaker.speaker_id!r}")
            name_key = _name_key(speaker.display_name)
            if name_key in speaker_names:
                raise ContractValidationError(
                    f"duplicate display_name {speaker.display_name!r}"
                )
            speaker_ids.add(speaker.speaker_id)
            speaker_names.add(name_key)
        object.__setattr__(self, "speakers", speakers)
        object.__setattr__(self, "created_at", _optional_string(self.created_at))
        object.__setattr__(self, "updated_at", _optional_string(self.updated_at))
        object.__setattr__(self, "notes", _optional_string(self.notes))

    @classmethod
    def empty(
        cls,
        *,
        created_at: str | None = None,
        notes: str | None = None,
    ) -> "EnrollmentDatabase":
        return cls(
            schema_version=ENROLLMENT_SCHEMA_VERSION,
            speakers=(),
            created_at=created_at,
            updated_at=created_at,
            notes=notes,
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "EnrollmentDatabase":
        """Load an enrollment database from a JSON-safe mapping."""

        raw_speakers = mapping.get("speakers") or ()
        if not isinstance(raw_speakers, Sequence) or isinstance(
            raw_speakers,
            str | bytes | bytearray,
        ):
            raise ContractValidationError("enrollment speakers must be a list")
        return cls(
            schema_version=str(mapping.get("schema_version") or ""),
            speakers=tuple(
                EnrollmentSpeaker.from_mapping(_mapping_value(value, "speaker"))
                for value in raw_speakers
            ),
            created_at=_optional_string(mapping.get("created_at")),
            updated_at=_optional_string(mapping.get("updated_at")),
            notes=_optional_string(mapping.get("notes")),
        )

    @property
    def embedding_model_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    exemplar.model_id
                    for speaker in self.speakers
                    for exemplar in speaker.exemplars
                }
            )
        )

    @property
    def exemplar_count(self) -> int:
        return sum(len(speaker.exemplars) for speaker in self.speakers)

    def to_jsonable(self) -> JsonObject:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
            "embedding_model_ids": list(self.embedding_model_ids),
            "speakers": [speaker.to_jsonable() for speaker in self.speakers],
        }


def _name_key(display_name: str) -> str:
    return " ".join(display_name.casefold().split())


def _normalize(values: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(float(value) * float(value) for value in values))
    if norm <= 0 or not math.isfinite(norm):
        raise ContractValidationError("cannot normalize an empty or non-finite centroid")
    return tuple(float(value) / norm for value in values)


def _embedding_vector(values: Sequence[float]) -> tuple[float, ...]:
    vector = _sequence_float_tuple(values, "embedding")
    for value in vector:
        if not math.isfinite(value):
            raise ContractValidationError("embedding values must be finite")
    return vector


def _sequence_float_tuple(value: object, field_name: str) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        raise ContractValidationError(f"{field_name} must be a sequence")
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must contain only numbers") from exc


def _mapping_value(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field_name} must be a mapping")
    return value


def _required_string(mapping: Mapping[str, object], field_name: str) -> str:
    value = mapping.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")
    return value


def _validate_required_string(field_name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: object, field_name: str) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric when present") from exc


def _optional_json_object(value: object, field_name: str) -> JsonObject | None:
    if value is None:
        return None
    return _json_object(value, field_name)


def _json_object(value: object, field_name: str) -> JsonObject:
    if not isinstance(value, Mapping):
        raise ContractValidationError(f"{field_name} must be a mapping")
    return {str(key): _jsonable(item) for key, item in value.items()}


def _jsonable(value: object) -> JsonValue:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_jsonable(item) for item in value]
    return str(value)
