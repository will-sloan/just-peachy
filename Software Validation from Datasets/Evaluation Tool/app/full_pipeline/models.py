"""Small backend-neutral value objects used by the streaming runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

import numpy as np


CONTRACT_SCHEMA_VERSION = "full-pipeline-contracts.v1"
RUNTIME_SCHEMA_VERSION = "full-pipeline-runtime.v1"


def utc_now_text() -> str:
    """Return a contract-compatible UTC timestamp."""

    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


class IdentityState(str, Enum):
    """Internal product states; public events map these to contract states."""

    GENERIC = "GENERIC"
    TENTATIVE_KNOWN = "TENTATIVE_KNOWN"
    CONFIRMED_KNOWN = "CONFIRMED_KNOWN"
    UNKNOWN_INSTANCE = "UNKNOWN_INSTANCE"
    RELEASED = "RELEASED"


@dataclass(frozen=True)
class RawAudioFrame:
    """One source-native audio frame before downmixing or resampling."""

    frame_id: str
    sequence: int
    samples: np.ndarray
    sample_rate_hz: int
    channel_count: int
    source_sample_start: int
    source_sample_end: int
    audio_start_sec: float
    audio_end_sec: float
    capture_start_monotonic_ns: int | None
    capture_end_monotonic_ns: int | None
    capture_start_utc: str | None
    capture_end_utc: str | None
    source_clock_id: str
    source_clock_type: str
    discontinuity_before: bool = False
    dropped_source_samples_before: int = 0

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples[:, None]
        if samples.ndim != 2:
            raise ValueError("raw audio samples must have shape (samples, channels)")
        if samples.shape[1] != self.channel_count:
            raise ValueError("raw audio channel_count does not match samples")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be positive")
        if self.source_sample_end < self.source_sample_start:
            raise ValueError("source sample indices are reversed")
        object.__setattr__(self, "samples", np.ascontiguousarray(samples))


@dataclass(frozen=True)
class NormalizedAudioFrame:
    """Mono 16 kHz frame plus source and normalization provenance."""

    frame_id: str
    sequence: int
    samples: np.ndarray
    sample_rate_hz: int
    sample_start: int
    sample_end: int
    audio_start_sec: float
    audio_end_sec: float
    source_sample_rate_hz: int
    source_channel_count: int
    source_sample_start: int
    source_sample_end: int
    source_audio_start_sec: float
    source_audio_end_sec: float
    capture_start_monotonic_ns: int | None
    capture_end_monotonic_ns: int | None
    capture_start_utc: str | None
    capture_end_utc: str | None
    source_clock_id: str
    source_clock_type: str
    discontinuity_before: bool = False
    dropped_source_samples_before: int = 0
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        samples = np.asarray(self.samples, dtype=np.float32).reshape(-1)
        if self.sample_rate_hz != 16000:
            raise ValueError("normalized audio must be 16 kHz")
        if self.sample_end - self.sample_start != samples.size:
            raise ValueError("normalized sample interval does not match samples")
        object.__setattr__(self, "samples", np.ascontiguousarray(samples))

    @property
    def duration_sec(self) -> float:
        return self.samples.size / self.sample_rate_hz

    def capture_contract(self) -> dict[str, object]:
        return {
            "sample_start_index": self.sample_start,
            "sample_end_index": self.sample_end,
            "audio_start_sec": self.audio_start_sec,
            "audio_end_sec": self.audio_end_sec,
            "capture_start_monotonic_ns": self.capture_start_monotonic_ns,
            "capture_end_monotonic_ns": self.capture_end_monotonic_ns,
            "capture_start_utc": self.capture_start_utc,
            "capture_end_utc": self.capture_end_utc,
            "discontinuity_before": self.discontinuity_before,
            "dropped_sample_count_before": self.dropped_source_samples_before,
        }


@dataclass(frozen=True)
class SpeechRegionUpdate:
    region_id: str
    state: str
    start_sec: float
    end_sec: float
    committed_through_sec: float
    algorithmic_lookahead_sec: float
    compute_latency_ms: float
    raw_score: float | None = None
    score_type: str | None = None
    overlap: bool = False
    reason: str = "causal_segmentation_update"


@dataclass(frozen=True)
class EmbeddingWindow:
    window_id: str
    start_sec: float
    end_sec: float
    assignment_start_sec: float
    assignment_end_sec: float
    samples: np.ndarray
    role: str
    predicted_overlap: bool = False


@dataclass(frozen=True)
class EmbeddingResult:
    window_id: str
    backend_id: str
    model_id: str
    model_sha256: str | None
    vector: np.ndarray
    duration_sec: float
    role: str
    quality: Mapping[str, float | bool | str | None] = field(default_factory=dict)
    cache_key: str | None = None
    compute_latency_ms: float | None = None

    def __post_init__(self) -> None:
        vector = np.asarray(self.vector, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if vector.size == 0 or not np.isfinite(norm) or norm <= 0:
            raise ValueError("embedding vector must be finite and non-zero")
        object.__setattr__(self, "vector", np.ascontiguousarray(vector / norm))


@dataclass(frozen=True)
class AnonymousClusterUpdate:
    anonymous_speaker_id: str
    cluster_revision: int
    start_sec: float
    end_sec: float
    state: str
    similarity: float | None
    created: bool
    reentry: bool
    boundary: bool
    evidence_duration_sec: float
    evidence_window_count: int
    source_window_ids: tuple[str, ...]


@dataclass(frozen=True)
class TranscriptSpan:
    span_id: str
    start_sec: float | None
    end_sec: float | None
    text: str
    state: str
    anonymous_speaker_id: str | None = None
    speaker_label: str | None = None
    source_event_ids: tuple[str, ...] = ()
    timestamp_provenance: str = "backend"


@dataclass(frozen=True)
class ComponentRuntimeIdentity:
    component_family: str
    backend_id: str
    backend_config_id: str
    backend_config_sha256: str
    pipeline_config_sha256: str
    model_id: str | None
    model_asset_sha256s: tuple[str, ...]
    environment_profile_id: str | None = None
    environment_fingerprint_sha256: str | None = None
    implementation_id: str | None = None
    implementation_sha256: str | None = None

    def to_contract(self) -> dict[str, object]:
        return {
            "component_family": self.component_family,
            "backend_id": self.backend_id,
            "backend_config_id": self.backend_config_id,
            "backend_config_sha256": self.backend_config_sha256,
            "pipeline_config_sha256": self.pipeline_config_sha256,
            "model_id": self.model_id,
            "model_asset_sha256s": list(self.model_asset_sha256s),
            "environment_profile_id": self.environment_profile_id,
            "environment_fingerprint_sha256": self.environment_fingerprint_sha256,
            "implementation_id": self.implementation_id,
            "implementation_sha256": self.implementation_sha256,
        }


@dataclass(frozen=True)
class WorkerStatus:
    worker_id: str
    role: str
    backend_id: str
    environment_profile: str
    state: str
    pid: int | None
    restart_count: int
    warm: bool
    model_identity: Mapping[str, object]
    detail: str | None = None
