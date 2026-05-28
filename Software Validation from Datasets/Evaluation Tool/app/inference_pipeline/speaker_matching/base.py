"""Speaker matching interfaces and conservative decision contracts."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.enrollment.schema import EnrollmentDatabase
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject, JsonValue


UNKNOWN_LABEL = "Unknown"
DECISION_ACCEPTED = "accepted"
DECISION_DISABLED = "disabled"
DECISION_NO_ENROLLED_SPEAKERS = "no_enrolled_speakers"
DECISION_INVALID_EMBEDDING = "invalid_embedding"
DECISION_DIMENSION_MISMATCH = "dimension_mismatch"
DECISION_MODEL_MISMATCH = "model_mismatch"
DECISION_BELOW_THRESHOLD = "below_threshold"
DECISION_AMBIGUOUS = "ambiguous"

SCORING_MODE_CENTROID = "centroid"
SCORING_MODE_EXEMPLAR = "exemplar"
SCORING_MODES = {SCORING_MODE_CENTROID, SCORING_MODE_EXEMPLAR}


@dataclass(frozen=True)
class SpeakerScore:
    """One speaker-level similarity score produced by a matcher."""

    speaker_label: str
    score: float
    speaker_id: str | None = None
    reference_id: str | None = None
    model_id: str | None = None
    scoring_mode: str = SCORING_MODE_CENTROID

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class SpeakerDecision:
    """Final speaker assignment decision for one segment embedding."""

    speaker_label: str = UNKNOWN_LABEL
    best_label: str | None = None
    confidence: float | None = None
    margin: float | None = None
    threshold: float | None = None
    min_margin: float | None = None
    threshold_decision: str = DECISION_BELOW_THRESHOLD
    accepted: bool = False
    second_best_label: str | None = None
    second_best_score: float | None = None
    matched_reference_id: str | None = None
    method: str = "speaker_matching"
    embedding_id: str | None = None
    model_id: str | None = None
    scores: tuple[SpeakerScore, ...] = ()
    notes: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "speaker_label", self.speaker_label or UNKNOWN_LABEL)
        object.__setattr__(self, "scores", tuple(self.scores))

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


class SpeakerMatcherBase(ABC):
    """Backend-swappable interface for assigning enrolled speaker names."""

    name = "speaker_matcher_base"

    def __init__(
        self,
        *,
        threshold: float = 0.82,
        min_margin: float = 0.05,
        unknown_label: str = UNKNOWN_LABEL,
        scoring_mode: str = SCORING_MODE_CENTROID,
        runtime_model_id: str | None = None,
        enforce_model_id: bool = True,
    ) -> None:
        if not -1.0 <= float(threshold) <= 1.0:
            raise ContractValidationError("speaker matching threshold must be in [-1.0, 1.0]")
        if float(min_margin) < 0.0:
            raise ContractValidationError("speaker matching min_margin must be >= 0")
        if scoring_mode not in SCORING_MODES:
            known = ", ".join(sorted(SCORING_MODES))
            raise ContractValidationError(f"unknown speaker matching scoring_mode {scoring_mode!r}; known: {known}")
        if not unknown_label.strip():
            raise ContractValidationError("unknown_label must be non-empty")
        self.threshold = float(threshold)
        self.min_margin = float(min_margin)
        self.unknown_label = unknown_label
        self.scoring_mode = scoring_mode
        self.runtime_model_id = runtime_model_id
        self.enforce_model_id = bool(enforce_model_id)

    @abstractmethod
    def match(
        self,
        embedding: object,
        enrollment_db: EnrollmentDatabase | Mapping[str, object],
    ) -> SpeakerDecision:
        """Return a known speaker name or Unknown for one segment embedding."""

    def unknown_decision(
        self,
        reason: str,
        *,
        embedding: object | None = None,
        best_score: SpeakerScore | None = None,
        second_best_score: SpeakerScore | None = None,
        scores: Sequence[SpeakerScore] = (),
        notes: str | None = None,
    ) -> SpeakerDecision:
        margin = _score_margin(best_score, second_best_score)
        return SpeakerDecision(
            speaker_label=self.unknown_label,
            best_label=best_score.speaker_label if best_score is not None else None,
            confidence=best_score.score if best_score is not None else None,
            margin=margin,
            threshold=self.threshold,
            min_margin=self.min_margin,
            threshold_decision=reason,
            accepted=False,
            second_best_label=(
                second_best_score.speaker_label
                if second_best_score is not None
                else None
            ),
            second_best_score=(
                second_best_score.score
                if second_best_score is not None
                else None
            ),
            matched_reference_id=(
                best_score.reference_id
                if best_score is not None
                else None
            ),
            method=self.name,
            embedding_id=embedding_id_from_embedding(embedding),
            model_id=model_id_from_embedding(embedding) or self.runtime_model_id,
            scores=tuple(scores),
            notes=notes,
        )


class NoOpSpeakerMatcher(SpeakerMatcherBase):
    """Disabled matcher that always chooses Unknown."""

    name = "no_op_speaker_matching"

    def match(
        self,
        embedding: object,
        enrollment_db: EnrollmentDatabase | Mapping[str, object],
    ) -> SpeakerDecision:
        _ = enrollment_db
        return self.unknown_decision(
            DECISION_DISABLED,
            embedding=embedding,
            notes="speaker matching component disabled",
        )


def build_speaker_matcher_from_config(config: object) -> SpeakerMatcherBase | None:
    """Instantiate the configured speaker matcher without changing runner contracts."""

    component = _speaker_matching_component(config)
    if component is None or not _component_enabled(component):
        return None

    name = _component_name(component)
    params = _component_params(component)
    if name == "no_op_speaker_matching":
        return NoOpSpeakerMatcher()
    if name == "cosine_threshold":
        from app.inference_pipeline.speaker_matching.cosine_matcher import (
            CosineThresholdSpeakerMatcher,
        )

        return CosineThresholdSpeakerMatcher(
            threshold=_float_value(params.get("threshold", 0.82), "threshold"),
            min_margin=_float_value(params.get("min_margin", 0.05), "min_margin"),
            unknown_label=str(params.get("unknown_label") or UNKNOWN_LABEL),
            scoring_mode=str(params.get("scoring_mode") or SCORING_MODE_CENTROID),
            runtime_model_id=_optional_string(params.get("runtime_model_id")),
            enforce_model_id=_optional_bool(params.get("enforce_model_id"), default=True),
        )
    raise ContractValidationError(f"unknown speaker matching component {name!r}")


def ensure_enrollment_database(
    enrollment_db: EnrollmentDatabase | Mapping[str, object],
) -> EnrollmentDatabase:
    if isinstance(enrollment_db, EnrollmentDatabase):
        return enrollment_db
    if isinstance(enrollment_db, Mapping):
        return EnrollmentDatabase.from_mapping(enrollment_db)
    raise ContractValidationError("enrollment_db must be an EnrollmentDatabase or mapping")


def vector_from_embedding(embedding: object) -> tuple[float, ...]:
    raw_vector: object
    if isinstance(embedding, Mapping):
        raw_vector = embedding.get("vector") or embedding.get("embedding") or ()
    elif hasattr(embedding, "detach") and hasattr(embedding, "cpu"):
        raw_vector = embedding.detach().cpu().flatten().tolist()
    elif isinstance(embedding, Sequence) and not isinstance(embedding, str | bytes | bytearray):
        raw_vector = embedding
    else:
        raw_vector = getattr(embedding, "vector", None)
        if raw_vector is None:
            raw_vector = getattr(embedding, "embedding", None)
    if hasattr(raw_vector, "detach") and hasattr(raw_vector, "cpu"):
        raw_vector = raw_vector.detach().cpu().flatten().tolist()
    elif hasattr(raw_vector, "tolist") and not isinstance(raw_vector, list | tuple):
        raw_vector = raw_vector.tolist()
    if not isinstance(raw_vector, Sequence) or isinstance(
        raw_vector,
        str | bytes | bytearray,
    ):
        raise ContractValidationError("speaker match embedding vector must be a sequence")
    try:
        vector = tuple(float(value) for value in raw_vector)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("speaker match embedding vector must contain numbers") from exc
    if not vector:
        raise ContractValidationError("speaker match embedding vector must be non-empty")
    return vector


def embedding_id_from_embedding(embedding: object | None) -> str | None:
    if embedding is None:
        return None
    if isinstance(embedding, Mapping):
        value = embedding.get("embedding_id")
    else:
        value = getattr(embedding, "embedding_id", None)
    return str(value) if value is not None else None


def model_id_from_embedding(embedding: object | None) -> str | None:
    if embedding is None:
        return None
    if isinstance(embedding, Mapping):
        value = embedding.get("model_id") or embedding.get("model_name")
    else:
        value = getattr(embedding, "model_id", None) or getattr(embedding, "model_name", None)
    if value is None:
        return None
    text = str(value)
    return text if text and text != "unknown" else None


def _score_margin(
    best_score: SpeakerScore | None,
    second_best_score: SpeakerScore | None,
) -> float | None:
    if best_score is None:
        return None
    if second_best_score is None:
        return None
    return best_score.score - second_best_score.score


def _speaker_matching_component(config: object) -> object | None:
    components = getattr(config, "components", None)
    if isinstance(components, Mapping):
        return components.get("speaker_matching")
    if isinstance(config, Mapping):
        raw_components = config.get("components")
        if isinstance(raw_components, Mapping):
            return raw_components.get("speaker_matching")
        return config.get("speaker_matching")
    return None


def _component_name(component: object) -> str:
    if isinstance(component, Mapping):
        return str(component.get("name") or "")
    return str(getattr(component, "name", ""))


def _component_enabled(component: object) -> bool:
    if isinstance(component, Mapping):
        return bool(component.get("enabled", True))
    return bool(getattr(component, "enabled", True))


def _component_params(component: object) -> Mapping[str, object]:
    if isinstance(component, Mapping):
        value = component.get("params") or {}
    else:
        value = getattr(component, "params", {}) or {}
    if not isinstance(value, Mapping):
        raise ContractValidationError("speaker matching params must be a mapping")
    return value


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def _float_value(value: object, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc


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
