"""Speaker embedding interfaces and deterministic adapters."""

from __future__ import annotations

import hashlib
import math
import platform
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, fields, is_dataclass
from pathlib import Path
from typing import Mapping, Sequence

import torch

try:
    import resource
except ImportError:  # pragma: no cover - resource is unavailable on Windows
    resource = None  # type: ignore[assignment]

from app.inference_pipeline.contracts import AudioSegment, EvaluationRecord
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject, JsonValue


EMBEDDING_STATUS_OK = "ok"
EMBEDDING_STATUS_TOO_SHORT = "too_short"
EMBEDDING_STATUS_DISABLED = "disabled"
EMBEDDING_STATUS_FAILED = "failed"
EMBEDDING_STATUSES = {
    EMBEDDING_STATUS_OK,
    EMBEDDING_STATUS_TOO_SHORT,
    EMBEDDING_STATUS_DISABLED,
    EMBEDDING_STATUS_FAILED,
}
DEFAULT_MIN_DURATION_SEC = 0.75


@dataclass(frozen=True)
class SpeakerEmbeddingContext:
    """Context needed to embed one segment without changing runner contracts."""

    recording_id: str
    utt_id: str
    source_audio_path: Path
    segment_index: int = 0
    segment_start_sec: float | None = None
    segment_end_sec: float | None = None
    device: str = "cpu"
    dtype: str = "float32"
    run_config: JsonObject | None = None

    @classmethod
    def from_record_segment(
        cls,
        record: EvaluationRecord | Mapping[str, object] | object,
        segment: AudioSegment,
        *,
        segment_index: int = 0,
        run_config: Mapping[str, object] | None = None,
        device: str = "cpu",
        dtype: str = "float32",
    ) -> "SpeakerEmbeddingContext":
        """Build context from a selected metadata record and model-ready segment."""

        return cls(
            recording_id=str(_record_value(record, "recording_id")),
            utt_id=str(_record_value(record, "utt_id")),
            source_audio_path=segment.audio_path,
            segment_index=segment_index,
            segment_start_sec=segment.start_sec,
            segment_end_sec=segment.end_sec,
            device=device,
            dtype=dtype,
            run_config=dict(run_config or {}),
        )

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class SpeakerEmbeddingRuntimeStats:
    """Runtime and resource stats for one speaker embedding call."""

    model_name: str
    load_sec: float | None = None
    inference_sec: float | None = None
    audio_duration_sec: float | None = None
    realtime_factor: float | None = None
    device: str = "cpu"
    dtype: str = "float32"
    peak_gpu_memory_mb: float | None = None
    cpu_memory_mb: float | None = None

    @classmethod
    def from_timings(
        cls,
        *,
        model_name: str,
        load_sec: float | None,
        inference_sec: float | None,
        audio_duration_sec: float | None,
        device: str,
        dtype: str,
        peak_gpu_memory_mb: float | None = None,
        cpu_memory_mb: float | None = None,
    ) -> "SpeakerEmbeddingRuntimeStats":
        duration = audio_duration_sec if audio_duration_sec and audio_duration_sec > 0 else None
        realtime_factor = inference_sec / duration if inference_sec is not None and duration else None
        return cls(
            model_name=model_name,
            load_sec=load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio_duration_sec,
            realtime_factor=realtime_factor,
            device=device,
            dtype=dtype,
            peak_gpu_memory_mb=peak_gpu_memory_mb,
            cpu_memory_mb=cpu_memory_mb,
        )

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, object]) -> "SpeakerEmbeddingRuntimeStats":
        return cls(
            model_name=str(mapping.get("model_name") or ""),
            load_sec=_optional_float(mapping.get("load_sec")),
            inference_sec=_optional_float(mapping.get("inference_sec")),
            audio_duration_sec=_optional_float(mapping.get("audio_duration_sec")),
            realtime_factor=_optional_float(mapping.get("realtime_factor")),
            device=str(mapping.get("device") or "cpu"),
            dtype=str(mapping.get("dtype") or "float32"),
            peak_gpu_memory_mb=_optional_float(mapping.get("peak_gpu_memory_mb")),
            cpu_memory_mb=_optional_float(mapping.get("cpu_memory_mb")),
        )

    def to_jsonable(self) -> JsonObject:
        return _dataclass_jsonable(self)


@dataclass(frozen=True)
class SpeakerEmbedding:
    """Serializable speaker embedding result with validation metadata."""

    embedding_id: str
    vector: tuple[float, ...] = ()
    model_name: str = "unknown"
    dimension: int | None = None
    segment_duration_sec: float | None = None
    device: str = "cpu"
    runtime: SpeakerEmbeddingRuntimeStats | None = None
    status: str = EMBEDDING_STATUS_OK
    reliable: bool = True
    recording_id: str | None = None
    utt_id: str | None = None
    start_sec: float | None = None
    end_sec: float | None = None
    sample_rate_hz: int | None = None
    metadata: JsonObject | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.embedding_id, str) or not self.embedding_id.strip():
            raise ContractValidationError("embedding_id must be a non-empty string")
        vector = tuple(float(value) for value in self.vector)
        object.__setattr__(self, "vector", vector)
        if self.dimension is None:
            object.__setattr__(self, "dimension", len(vector))
        elif self.dimension != len(vector):
            raise ContractValidationError(
                f"dimension {self.dimension} does not match vector length {len(vector)}"
            )
        if self.status not in EMBEDDING_STATUSES:
            raise ContractValidationError(f"unknown speaker embedding status {self.status!r}")
        if self.status == EMBEDDING_STATUS_OK:
            if not vector:
                raise ContractValidationError("successful speaker embeddings must have a vector")
            if not is_l2_normalized(vector):
                raise ContractValidationError("successful speaker embeddings must be L2-normalized")
        else:
            object.__setattr__(self, "reliable", False)
        if self.start_sec is not None and self.end_sec is not None and self.end_sec < self.start_sec:
            raise ContractValidationError("SpeakerEmbedding end_sec must be >= start_sec")
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @classmethod
    def from_jsonable(cls, mapping: Mapping[str, object]) -> "SpeakerEmbedding":
        """Load an embedding result from a JSON-safe mapping."""

        runtime_value = mapping.get("runtime")
        runtime = (
            SpeakerEmbeddingRuntimeStats.from_mapping(runtime_value)
            if isinstance(runtime_value, Mapping)
            else None
        )
        vector_value = mapping.get("vector") or ()
        if not isinstance(vector_value, Sequence) or isinstance(vector_value, str | bytes | bytearray):
            raise ContractValidationError("speaker embedding vector must be a sequence")
        metadata = mapping.get("metadata")
        return cls(
            embedding_id=str(mapping.get("embedding_id") or ""),
            vector=tuple(float(value) for value in vector_value),
            model_name=str(mapping.get("model_name") or "unknown"),
            dimension=_optional_int(mapping.get("dimension")),
            segment_duration_sec=_optional_float(mapping.get("segment_duration_sec")),
            device=str(mapping.get("device") or "cpu"),
            runtime=runtime,
            status=str(mapping.get("status") or EMBEDDING_STATUS_OK),
            reliable=bool(mapping.get("reliable", True)),
            recording_id=_optional_string(mapping.get("recording_id")),
            utt_id=_optional_string(mapping.get("utt_id")),
            start_sec=_optional_float(mapping.get("start_sec")),
            end_sec=_optional_float(mapping.get("end_sec")),
            sample_rate_hz=_optional_int(mapping.get("sample_rate_hz")),
            metadata=dict(metadata) if isinstance(metadata, Mapping) else {},
        )

    def to_jsonable(self) -> JsonObject:
        """Return a JSON-safe representation for JSONL or parquet storage."""

        return _dataclass_jsonable(self)


class SpeakerEmbeddingBase(ABC):
    """Backend-swappable speaker embedding interface."""

    name = "speaker_embedding_base"

    def __init__(
        self,
        *,
        model_name: str | None = None,
        min_duration_sec: float = DEFAULT_MIN_DURATION_SEC,
        device: str = "cpu",
        dtype: str = "float32",
    ) -> None:
        if min_duration_sec < 0:
            raise ContractValidationError("min_duration_sec must be >= 0")
        self.model_name = model_name or self.name
        self.min_duration_sec = float(min_duration_sec)
        self.device = device
        self.dtype = dtype
        self.last_embedding: SpeakerEmbedding | None = None
        self.last_runtime_stats: SpeakerEmbeddingRuntimeStats | None = None

    @abstractmethod
    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        """Convert one speech segment into a speaker embedding."""

    def _segment_duration(self, audio_segment: AudioSegment) -> float | None:
        if audio_segment.duration_sec is not None:
            return float(audio_segment.duration_sec)
        if audio_segment.start_sec is not None and audio_segment.end_sec is not None:
            return max(0.0, float(audio_segment.end_sec) - float(audio_segment.start_sec))
        return None

    def _is_too_short(self, duration_sec: float | None) -> bool:
        return duration_sec is not None and duration_sec < self.min_duration_sec

    def _short_embedding(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
        *,
        started_at: float,
        duration_sec: float | None,
        reason: str | None = None,
    ) -> SpeakerEmbedding:
        runtime = self._runtime_stats(started_at, duration_sec, context.device)
        embedding = SpeakerEmbedding(
            embedding_id=embedding_id(context),
            vector=(),
            model_name=self.model_name,
            segment_duration_sec=duration_sec,
            device=context.device,
            runtime=runtime,
            status=EMBEDDING_STATUS_TOO_SHORT,
            reliable=False,
            recording_id=context.recording_id,
            utt_id=context.utt_id,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            sample_rate_hz=audio_segment.sample_rate_hz,
            metadata={
                "min_duration_sec": self.min_duration_sec,
                "reason": reason or "segment shorter than min_duration_sec",
            },
        )
        self.last_embedding = embedding
        self.last_runtime_stats = runtime
        return embedding

    def _runtime_stats(
        self,
        started_at: float,
        duration_sec: float | None,
        device: str,
        *,
        load_sec: float | None = 0.0,
    ) -> SpeakerEmbeddingRuntimeStats:
        inference_sec = time.perf_counter() - started_at
        return SpeakerEmbeddingRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=duration_sec,
            device=device,
            dtype=self.dtype,
            peak_gpu_memory_mb=peak_gpu_memory_mb(device),
            cpu_memory_mb=process_memory_mb(),
        )


class NoOpSpeakerEmbedding(SpeakerEmbeddingBase):
    """Disabled speaker embedding adapter."""

    name = "no_op_speaker_embedding"

    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        started_at = time.perf_counter()
        duration = self._segment_duration(audio_segment)
        runtime = self._runtime_stats(started_at, duration, context.device)
        embedding = SpeakerEmbedding(
            embedding_id=embedding_id(context),
            vector=(),
            model_name=self.model_name,
            segment_duration_sec=duration,
            device=context.device,
            runtime=runtime,
            status=EMBEDDING_STATUS_DISABLED,
            reliable=False,
            recording_id=context.recording_id,
            utt_id=context.utt_id,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            sample_rate_hz=audio_segment.sample_rate_hz,
            metadata={"reason": "speaker embedding component disabled"},
        )
        self.last_embedding = embedding
        self.last_runtime_stats = runtime
        return embedding


class DeterministicFakeSpeakerEmbedding(SpeakerEmbeddingBase):
    """Deterministic adapter for tests and local script smoke checks."""

    name = "fake_speaker_embedding"

    def __init__(
        self,
        dimension: int = 16,
        *,
        seed: str = "m9_speaker_embedding",
        min_duration_sec: float = DEFAULT_MIN_DURATION_SEC,
        model_name: str | None = None,
        device: str = "cpu",
        dtype: str = "float32",
    ) -> None:
        if int(dimension) < 1:
            raise ContractValidationError("dimension must be >= 1")
        super().__init__(
            model_name=model_name or self.name,
            min_duration_sec=min_duration_sec,
            device=device,
            dtype=dtype,
        )
        self.dimension = int(dimension)
        self.seed = seed

    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        started_at = time.perf_counter()
        duration = self._segment_duration(audio_segment)
        if self._is_too_short(duration):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=duration,
            )

        vector = normalize_vector(self._deterministic_values(self._payload(audio_segment, context)))
        runtime = self._runtime_stats(started_at, duration, context.device)
        embedding = SpeakerEmbedding(
            embedding_id=embedding_id(context),
            vector=vector,
            model_name=self.model_name,
            segment_duration_sec=duration,
            device=context.device,
            runtime=runtime,
            status=EMBEDDING_STATUS_OK,
            reliable=True,
            recording_id=context.recording_id,
            utt_id=context.utt_id,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            sample_rate_hz=audio_segment.sample_rate_hz,
            metadata={
                "adapter": self.name,
                "seed": self.seed,
                "min_duration_sec": self.min_duration_sec,
            },
        )
        self.last_embedding = embedding
        self.last_runtime_stats = runtime
        return embedding

    def _payload(self, audio_segment: AudioSegment, context: SpeakerEmbeddingContext) -> bytes:
        text = "|".join(
            [
                self.seed,
                self.model_name,
                str(self.dimension),
                context.recording_id,
                context.utt_id,
                str(context.segment_index),
                str(audio_segment.audio_path),
                str(audio_segment.start_sec),
                str(audio_segment.end_sec),
                str(audio_segment.duration_sec),
            ]
        )
        return text.encode("utf-8")

    def _deterministic_values(self, payload: bytes) -> tuple[float, ...]:
        return _deterministic_values(payload, self.dimension)


def build_speaker_embedding_from_config(config: object) -> SpeakerEmbeddingBase | None:
    """Instantiate configured speaker embedding without changing runner contracts."""

    component = _speaker_embedding_component(config)
    if component is None or not _component_enabled(component):
        return None

    name = _component_name(component)
    params = _component_params(component)
    if name == "no_op_speaker_embedding":
        return NoOpSpeakerEmbedding()
    if name == "fake_speaker_embedding":
        return DeterministicFakeSpeakerEmbedding(
            dimension=_int_value(params.get("dimension", 16), "dimension"),
            seed=str(params.get("seed") or "m9_speaker_embedding"),
            min_duration_sec=_float_value(
                params.get("min_duration_sec", DEFAULT_MIN_DURATION_SEC),
                "min_duration_sec",
            ),
            model_name=_optional_string(params.get("model_name")),
            device=str(params.get("device") or "cpu"),
            dtype=str(params.get("dtype") or "float32"),
        )
    if name == "speechbrain_ecapa":
        from app.inference_pipeline.speaker_embedding.speechbrain_adapter import (
            SpeechBrainECAPAAdapter,
        )

        return SpeechBrainECAPAAdapter(params)
    raise ContractValidationError(f"unknown speaker embedding component {name!r}")


def embedding_id(context: SpeakerEmbeddingContext) -> str:
    """Build a stable per-segment embedding id while preserving source identity."""

    return (
        f"{context.recording_id}:{context.utt_id}:"
        f"{context.segment_index}:{context.segment_start_sec}:{context.segment_end_sec}"
    )


def normalize_vector(values: Sequence[float] | torch.Tensor) -> tuple[float, ...]:
    """Return a L2-normalized vector as JSON-friendly floats."""

    tensor = torch.as_tensor(values, dtype=torch.float32).flatten()
    if tensor.numel() == 0:
        raise ContractValidationError("cannot normalize an empty embedding vector")
    norm = torch.linalg.vector_norm(tensor)
    if not torch.isfinite(norm) or float(norm.item()) <= 0.0:
        raise ContractValidationError("cannot normalize a zero or non-finite embedding vector")
    return tuple(float(value) for value in (tensor / norm).tolist())


def vector_l2_norm(values: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in values))


def is_l2_normalized(values: Sequence[float], *, tolerance: float = 1e-4) -> bool:
    return abs(vector_l2_norm(values) - 1.0) <= tolerance


def peak_gpu_memory_mb(device: str) -> float | None:
    if device == "cuda" and torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    return None


def process_memory_mb() -> float | None:
    """Return current process max RSS in MB where the platform exposes it."""

    if resource is None:
        return None
    try:
        value = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:
        return None
    if value <= 0:
        return None
    if platform.system() == "Darwin":
        return value / (1024 * 1024)
    return value / 1024


def component_report_path(reports_root: Path, run_id: str) -> Path:
    """Return the required speaker embedding component report path for a run id."""

    return (
        reports_root
        / "component_reports"
        / "speaker_embedding"
        / f"embedding_quality_{run_id}.md"
    )


def _deterministic_values(payload: bytes, dimension: int = 16) -> tuple[float, ...]:
    values: list[float] = []
    counter = 0
    while len(values) < dimension:
        digest = hashlib.sha256(payload + counter.to_bytes(4, "big")).digest()
        for index in range(0, len(digest), 4):
            integer = int.from_bytes(digest[index : index + 4], "big", signed=False)
            values.append((integer / 2**32) * 2.0 - 1.0)
            if len(values) == dimension:
                break
        counter += 1
    return tuple(values)


def _speaker_embedding_component(config: object) -> object | None:
    components = getattr(config, "components", None)
    if isinstance(components, Mapping):
        return components.get("speaker_embedding")
    if isinstance(config, Mapping):
        raw_components = config.get("components")
        if isinstance(raw_components, Mapping):
            return raw_components.get("speaker_embedding")
        return config.get("speaker_embedding")
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
        raise ContractValidationError("speaker embedding params must be a mapping")
    return value


def _record_value(record: EvaluationRecord | Mapping[str, object] | object, key: str) -> object:
    if isinstance(record, Mapping):
        return record[key]
    return getattr(record, key)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("value must be numeric when present") from exc


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("value must be an integer when present") from exc


def _float_value(value: object, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc


def _int_value(value: object, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc


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
