"""Checksum-strict ReDim embedding reuse for the H2 product runtime.

The diarization and identity APIs remain role separated.  This module only
allows a previously computed diarization vector to satisfy an identity request
when a role-independent scientific-equivalence fingerprint proves that the
model input is identical.  Public diagnostics contain hashes and scalar
comparisons only; embedding vectors never leave the in-process router.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import asdict, dataclass
import hashlib
import json
import time
from typing import Any, Mapping

import numpy as np

from .models import EmbeddingResult, EmbeddingWindow


R1_TWO_INDEPENDENT_MODELS = "R1_TWO_INDEPENDENT_MODELS"
R2_ONE_SHARED_MODEL = "R2_ONE_SHARED_MODEL"
R3_EXACT_WINDOW_EMBEDDING_REUSE = "R3_EXACT_WINDOW_EMBEDDING_REUSE"
R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION = (
    "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION"
)
REDIM_EXECUTION_STRATEGIES = frozenset(
    {
        R1_TWO_INDEPENDENT_MODELS,
        R2_ONE_SHARED_MODEL,
        R3_EXACT_WINDOW_EMBEDDING_REUSE,
        R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
    }
)

FINGERPRINT_SCHEMA_VERSION = "h2-embedding-request-fingerprint.v1"
OBSERVATION_SCHEMA_VERSION = "h2-embedding-reuse-observation.v1"
TELEMETRY_SCHEMA_VERSION = "h2-embedding-reuse-telemetry.v1"
REUSE_IMPLEMENTATION_VERSION = "h2-redim-reuse-router.v1"

R4_QUALITY_POLICY: Mapping[str, object] = {
    "policy_id": "h2-r4-identity-reuse-quality.v1",
    "minimum_rms": 1.0e-5,
    "minimum_voiced_proportion": 0.05,
    "voiced_absolute_amplitude": 1.0e-4,
    "maximum_clipping_proportion": 0.02,
    "clipping_absolute_amplitude": 0.999,
    "nonfinite_allowed": False,
    "fallback": "fresh_identity_embedding",
}


def _canonical_sha256(value: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


R4_QUALITY_POLICY_SHA256 = _canonical_sha256(dict(R4_QUALITY_POLICY))


def _float32_bytes(value: np.ndarray) -> bytes:
    return np.ascontiguousarray(np.asarray(value, dtype="<f4")).tobytes()


def vector_sha256(value: np.ndarray) -> str:
    """Hash the exact normalized FP32 vector representation."""

    return hashlib.sha256(_float32_bytes(value)).hexdigest()


def _adapter_identity(adapter: Any) -> dict[str, object]:
    if hasattr(adapter, "reuse_identity_contract"):
        raw = adapter.reuse_identity_contract()
        if not isinstance(raw, Mapping):
            raise TypeError("embedding adapter reuse identity must be a mapping")
        value = dict(raw)
    else:
        value = {
            "backend_id": getattr(adapter, "backend_id", None),
            "model_id": getattr(adapter, "model_id", None),
            "model_sha256": getattr(adapter, "model_sha256", None),
            "backend_config_sha256": getattr(
                adapter, "backend_config_sha256", None
            ),
            "preprocessing": {
                "sample_rate_hz": 16000,
                "channel_policy": "mono",
                "sample_dtype": "float32",
                "normalization": "backend_l2",
            },
        }
    required = (
        "backend_id",
        "model_id",
        "model_sha256",
        "backend_config_sha256",
        "preprocessing",
    )
    missing = [name for name in required if not value.get(name)]
    value["complete"] = not missing
    value["missing_fields"] = missing
    return value


@dataclass(frozen=True)
class EmbeddingRequestFingerprint:
    """Strict request identity plus role-independent equivalence identity."""

    window_id: str
    role: str
    source_start_sample: int
    source_end_sample: int
    assignment_start_sample: int
    assignment_end_sample: int
    duration_samples: int
    normalized_pcm_sha256: str
    backend_id: str | None
    model_id: str | None
    model_sha256: str | None
    backend_config_sha256: str | None
    preprocessing_identity_sha256: str
    normalization: str | None
    identity_complete: bool
    missing_identity_fields: tuple[str, ...]

    @property
    def equivalence_payload(self) -> dict[str, object]:
        return {
            "schema_version": FINGERPRINT_SCHEMA_VERSION,
            "source_start_sample": self.source_start_sample,
            "source_end_sample": self.source_end_sample,
            "assignment_start_sample": self.assignment_start_sample,
            "assignment_end_sample": self.assignment_end_sample,
            "duration_samples": self.duration_samples,
            "sample_rate_hz": 16000,
            "normalized_pcm_sha256": self.normalized_pcm_sha256,
            "backend_id": self.backend_id,
            "model_id": self.model_id,
            "model_sha256": self.model_sha256,
            "backend_config_sha256": self.backend_config_sha256,
            "preprocessing_identity_sha256": self.preprocessing_identity_sha256,
            "normalization": self.normalization,
        }

    @property
    def equivalence_sha256(self) -> str:
        return _canonical_sha256(self.equivalence_payload)

    @property
    def request_sha256(self) -> str:
        return _canonical_sha256(
            {
                **self.equivalence_payload,
                "window_id": self.window_id,
                "role": self.role,
            }
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": FINGERPRINT_SCHEMA_VERSION,
            **asdict(self),
            "request_sha256": self.request_sha256,
            "scientific_equivalence_sha256": self.equivalence_sha256,
        }

    def equivalent_to(self, other: "EmbeddingRequestFingerprint") -> bool:
        return (
            self.identity_complete
            and other.identity_complete
            and self.equivalence_sha256 == other.equivalence_sha256
        )


def request_fingerprint(
    window: EmbeddingWindow, adapter: Any
) -> EmbeddingRequestFingerprint:
    samples = np.asarray(window.samples, dtype=np.float32).reshape(-1)
    identity = _adapter_identity(adapter)
    preprocessing = identity.get("preprocessing")
    if not isinstance(preprocessing, Mapping):
        preprocessing = {"invalid": True}
    normalization = preprocessing.get("normalization")
    source_start_sample = round(float(window.start_sec) * 16000)
    source_end_sample = source_start_sample + int(samples.size)
    return EmbeddingRequestFingerprint(
        window_id=str(window.window_id),
        role=str(window.role),
        source_start_sample=source_start_sample,
        source_end_sample=source_end_sample,
        assignment_start_sample=round(
            float(window.assignment_start_sec) * 16000
        ),
        assignment_end_sample=round(float(window.assignment_end_sec) * 16000),
        duration_samples=int(samples.size),
        normalized_pcm_sha256=hashlib.sha256(_float32_bytes(samples)).hexdigest(),
        backend_id=(
            str(identity["backend_id"])
            if identity.get("backend_id") is not None
            else None
        ),
        model_id=(
            str(identity["model_id"])
            if identity.get("model_id") is not None
            else None
        ),
        model_sha256=(
            str(identity["model_sha256"])
            if identity.get("model_sha256") is not None
            else None
        ),
        backend_config_sha256=(
            str(identity["backend_config_sha256"])
            if identity.get("backend_config_sha256") is not None
            else None
        ),
        preprocessing_identity_sha256=_canonical_sha256(dict(preprocessing)),
        normalization=(str(normalization) if normalization is not None else None),
        identity_complete=bool(identity["complete"]),
        missing_identity_fields=tuple(
            str(value) for value in identity["missing_fields"]
        ),
    )


@dataclass(frozen=True)
class _DiarizationCandidate:
    fingerprint: EmbeddingRequestFingerprint
    result: EmbeddingResult


@dataclass(frozen=True)
class EmbeddingReuseObservation:
    strategy: str
    window_id: str
    diarization_request_sha256: str
    identity_request_sha256: str
    diarization_equivalence_sha256: str
    identity_equivalence_sha256: str
    diarization_normalized_pcm_sha256: str
    identity_normalized_pcm_sha256: str
    source_start_sample: int
    source_end_sample: int
    assignment_start_sample: int
    assignment_end_sample: int
    duration_samples: int
    diarization_preprocessing_identity_sha256: str
    identity_preprocessing_identity_sha256: str
    normalization: str | None
    diarization_vector_sha256: str
    identity_vector_sha256: str
    embedding_cosine_agreement: float | None
    maximum_absolute_error: float | None
    backend_id: str | None
    model_id: str | None
    model_sha256: str | None
    backend_config_sha256: str | None
    reused: bool
    reuse_reason: str
    fresh_fallback: bool
    fallback_reason: str | None
    identity_quality_status: str
    identity_quality_policy_sha256: str | None
    duration_sec: float
    identity_accumulation: str
    duration_weighting: bool
    recent_vs_accumulated: str
    quality_metrics: Mapping[str, float | bool]
    diarization_model_calls_after: int
    identity_model_calls_after: int
    reuse_hits_after: int

    def to_jsonable(self) -> dict[str, object]:
        return {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            **asdict(self),
            "raw_embedding_vectors_present": False,
        }


class H2EmbeddingReuseRouter:
    """Route role-specific requests and retain bounded private diagnostics."""

    def __init__(
        self,
        *,
        strategy: str,
        diarization_embedder: Any,
        identity_embedder: Any,
        minimum_identity_duration_sec: float,
        identity_accumulation: str,
        maximum_candidates: int = 512,
        maximum_observations: int = 4096,
    ) -> None:
        if strategy not in REDIM_EXECUTION_STRATEGIES:
            raise ValueError(f"unsupported ReDim execution strategy: {strategy}")
        if minimum_identity_duration_sec <= 0:
            raise ValueError("minimum identity duration must be positive")
        if identity_accumulation not in {"recent_window", "accumulated_window"}:
            raise ValueError("unsupported identity accumulation")
        self.strategy = strategy
        self.diarization_embedder = diarization_embedder
        self.identity_embedder = identity_embedder
        self.minimum_identity_duration_sec = float(
            minimum_identity_duration_sec
        )
        self.identity_accumulation = identity_accumulation
        self.maximum_candidates = int(maximum_candidates)
        self.maximum_observations = int(maximum_observations)
        self._candidates: OrderedDict[str, _DiarizationCandidate] = OrderedDict()
        self._observations: list[EmbeddingReuseObservation] = []
        self._counts = {
            "diarization_requests": 0,
            "identity_requests": 0,
            "diarization_model_calls": 0,
            "identity_model_calls": 0,
            "reuse_hits": 0,
            "fresh_fallbacks": 0,
            "fingerprint_mismatches": 0,
            "quality_fallbacks": 0,
        }
        self._audio_seconds_embedded = 0.0
        self._audio_seconds_reused = 0.0
        self._routing_wall_sec = 0.0

    def embed_diarization(self, window: EmbeddingWindow) -> EmbeddingResult:
        if window.role != "anonymous_diarization":
            raise ValueError("diarization route requires anonymous_diarization role")
        started = time.perf_counter()
        fingerprint = request_fingerprint(window, self.diarization_embedder)
        self._counts["diarization_requests"] += 1
        result = self.diarization_embedder.embed(window)
        self._counts["diarization_model_calls"] += 1
        self._audio_seconds_embedded += float(result.duration_sec)
        self._candidates[window.window_id] = _DiarizationCandidate(
            fingerprint=fingerprint,
            result=result,
        )
        self._candidates.move_to_end(window.window_id)
        while len(self._candidates) > self.maximum_candidates:
            self._candidates.popitem(last=False)
        self._routing_wall_sec += time.perf_counter() - started
        return result

    def embed_identity(self, window: EmbeddingWindow) -> EmbeddingResult:
        if window.role != "identity_matching":
            raise ValueError("identity route requires identity_matching role")
        started = time.perf_counter()
        self._counts["identity_requests"] += 1
        identity_fingerprint = request_fingerprint(window, self.identity_embedder)
        candidate = self._candidates.get(window.window_id)
        reused = False
        fresh_fallback = False
        fallback_reason: str | None = None
        reuse_reason = "strategy_requires_fresh_identity_embedding"
        quality_status = "not_applicable"
        quality_metrics: dict[str, float | bool] = {}
        quality_policy_sha: str | None = None

        reuse_strategy = self.strategy in {
            R3_EXACT_WINDOW_EMBEDDING_REUSE,
            R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION,
        }
        if reuse_strategy:
            if candidate is None:
                fresh_fallback = True
                fallback_reason = "diarization_candidate_missing"
            elif not candidate.fingerprint.equivalent_to(identity_fingerprint):
                fresh_fallback = True
                fallback_reason = "scientific_equivalence_fingerprint_mismatch"
                self._counts["fingerprint_mismatches"] += 1
            elif self.strategy == R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION:
                quality_policy_sha = R4_QUALITY_POLICY_SHA256
                quality_status, quality_metrics, quality_reason = self._r4_quality(
                    window
                )
                if quality_status != "accepted":
                    fresh_fallback = True
                    fallback_reason = quality_reason
                    self._counts["quality_fallbacks"] += 1

        if reuse_strategy and not fresh_fallback and candidate is not None:
            reused = True
            reuse_reason = (
                "exact_equivalent_diarization_window"
                if self.strategy == R3_EXACT_WINDOW_EMBEDDING_REUSE
                else "quality_accepted_segment_with_identity_aggregation"
            )
            self._counts["reuse_hits"] += 1
            self._audio_seconds_reused += float(window.end_sec - window.start_sec)
            result = EmbeddingResult(
                window_id=window.window_id,
                backend_id=candidate.result.backend_id,
                model_id=candidate.result.model_id,
                model_sha256=candidate.result.model_sha256,
                vector=candidate.result.vector,
                duration_sec=float(window.end_sec - window.start_sec),
                role=window.role,
                quality={
                    **dict(candidate.result.quality),
                    "status": "accepted",
                    "embedding_reused": True,
                    "reuse_strategy": self.strategy,
                    "reuse_contract_version": REUSE_IMPLEMENTATION_VERSION,
                    "identity_quality_status": quality_status,
                    "identity_quality_policy_sha256": quality_policy_sha,
                },
                # A diarization cache key is not falsely relabelled as an
                # identity-embedding dependency.
                cache_key=None,
                compute_latency_ms=(time.perf_counter() - started) * 1000.0,
            )
        else:
            if reuse_strategy:
                self._counts["fresh_fallbacks"] += 1
                reuse_reason = "fresh_identity_fallback"
            result = self.identity_embedder.embed(window)
            self._counts["identity_model_calls"] += 1
            self._audio_seconds_embedded += float(result.duration_sec)
            if reuse_strategy:
                result = EmbeddingResult(
                    window_id=result.window_id,
                    backend_id=result.backend_id,
                    model_id=result.model_id,
                    model_sha256=result.model_sha256,
                    vector=result.vector,
                    duration_sec=result.duration_sec,
                    role=result.role,
                    quality={
                        **dict(result.quality),
                        "embedding_reused": False,
                        "reuse_strategy": self.strategy,
                        "fresh_fallback": True,
                        "fallback_reason": fallback_reason,
                        "identity_quality_status": quality_status,
                        "identity_quality_policy_sha256": quality_policy_sha,
                    },
                    cache_key=result.cache_key,
                    compute_latency_ms=result.compute_latency_ms,
                )

        if candidate is not None:
            left = np.asarray(candidate.result.vector, dtype=np.float32)
            right = np.asarray(result.vector, dtype=np.float32)
            if left.shape == right.shape:
                denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
                cosine = (
                    float(np.dot(left, right) / denominator)
                    if denominator > 0.0
                    else None
                )
                max_abs = float(np.max(np.abs(left - right)))
            else:
                cosine = None
                max_abs = None
        else:
            cosine = None
            max_abs = None
        self._append_observation(
            candidate=candidate,
            identity_fingerprint=identity_fingerprint,
            result=result,
            reused=reused,
            reuse_reason=reuse_reason,
            fresh_fallback=fresh_fallback,
            fallback_reason=fallback_reason,
            quality_status=quality_status,
            quality_policy_sha=quality_policy_sha,
            quality_metrics=quality_metrics,
            cosine=cosine,
            max_abs=max_abs,
        )
        self._routing_wall_sec += time.perf_counter() - started
        return result

    def _r4_quality(
        self, window: EmbeddingWindow
    ) -> tuple[str, dict[str, float | bool], str | None]:
        samples = np.asarray(window.samples, dtype=np.float32).reshape(-1)
        finite = bool(samples.size and np.all(np.isfinite(samples)))
        duration = float(samples.size / 16000.0)
        rms = (
            float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
            if finite
            else 0.0
        )
        voiced = (
            float(
                np.mean(
                    np.abs(samples)
                    >= float(R4_QUALITY_POLICY["voiced_absolute_amplitude"])
                )
            )
            if finite
            else 0.0
        )
        clipped = (
            float(
                np.mean(
                    np.abs(samples)
                    >= float(R4_QUALITY_POLICY["clipping_absolute_amplitude"])
                )
            )
            if finite
            else 1.0
        )
        metrics: dict[str, float | bool] = {
            "finite": finite,
            "duration_sec": duration,
            "rms": rms,
            "voiced_proportion": voiced,
            "clipping_proportion": clipped,
        }
        if not finite:
            return "rejected", metrics, "identity_quality_nonfinite_pcm"
        if duration + 1e-12 < self.minimum_identity_duration_sec:
            return "rejected", metrics, "identity_quality_duration_below_minimum"
        if rms < float(R4_QUALITY_POLICY["minimum_rms"]):
            return "rejected", metrics, "identity_quality_level_below_minimum"
        if voiced < float(R4_QUALITY_POLICY["minimum_voiced_proportion"]):
            return "rejected", metrics, "identity_quality_voicing_below_minimum"
        if clipped > float(R4_QUALITY_POLICY["maximum_clipping_proportion"]):
            return "rejected", metrics, "identity_quality_clipping_above_maximum"
        return "accepted", metrics, None

    def _append_observation(
        self,
        *,
        candidate: _DiarizationCandidate | None,
        identity_fingerprint: EmbeddingRequestFingerprint,
        result: EmbeddingResult,
        reused: bool,
        reuse_reason: str,
        fresh_fallback: bool,
        fallback_reason: str | None,
        quality_status: str,
        quality_policy_sha: str | None,
        quality_metrics: Mapping[str, float | bool],
        cosine: float | None,
        max_abs: float | None,
    ) -> None:
        if candidate is None:
            diar_request_sha = "UNAVAILABLE"
            diar_equivalence_sha = "UNAVAILABLE"
            diar_pcm_sha = "UNAVAILABLE"
            diar_preprocessing_sha = "UNAVAILABLE"
            diar_vector_sha = "UNAVAILABLE"
        else:
            diar_request_sha = candidate.fingerprint.request_sha256
            diar_equivalence_sha = candidate.fingerprint.equivalence_sha256
            diar_pcm_sha = candidate.fingerprint.normalized_pcm_sha256
            diar_preprocessing_sha = (
                candidate.fingerprint.preprocessing_identity_sha256
            )
            diar_vector_sha = vector_sha256(candidate.result.vector)
        observation = EmbeddingReuseObservation(
            strategy=self.strategy,
            window_id=identity_fingerprint.window_id,
            diarization_request_sha256=diar_request_sha,
            identity_request_sha256=identity_fingerprint.request_sha256,
            diarization_equivalence_sha256=diar_equivalence_sha,
            identity_equivalence_sha256=identity_fingerprint.equivalence_sha256,
            diarization_normalized_pcm_sha256=diar_pcm_sha,
            identity_normalized_pcm_sha256=(
                identity_fingerprint.normalized_pcm_sha256
            ),
            source_start_sample=identity_fingerprint.source_start_sample,
            source_end_sample=identity_fingerprint.source_end_sample,
            assignment_start_sample=(
                identity_fingerprint.assignment_start_sample
            ),
            assignment_end_sample=identity_fingerprint.assignment_end_sample,
            duration_samples=identity_fingerprint.duration_samples,
            diarization_preprocessing_identity_sha256=diar_preprocessing_sha,
            identity_preprocessing_identity_sha256=(
                identity_fingerprint.preprocessing_identity_sha256
            ),
            normalization=identity_fingerprint.normalization,
            diarization_vector_sha256=diar_vector_sha,
            identity_vector_sha256=vector_sha256(result.vector),
            embedding_cosine_agreement=cosine,
            maximum_absolute_error=max_abs,
            backend_id=identity_fingerprint.backend_id,
            model_id=identity_fingerprint.model_id,
            model_sha256=identity_fingerprint.model_sha256,
            backend_config_sha256=identity_fingerprint.backend_config_sha256,
            reused=reused,
            reuse_reason=reuse_reason,
            fresh_fallback=fresh_fallback,
            fallback_reason=fallback_reason,
            identity_quality_status=quality_status,
            identity_quality_policy_sha256=quality_policy_sha,
            duration_sec=float(result.duration_sec),
            identity_accumulation=self.identity_accumulation,
            duration_weighting=True,
            recent_vs_accumulated=self.identity_accumulation,
            quality_metrics=dict(quality_metrics),
            diarization_model_calls_after=self._counts[
                "diarization_model_calls"
            ],
            identity_model_calls_after=self._counts["identity_model_calls"],
            reuse_hits_after=self._counts["reuse_hits"],
        )
        self._observations.append(observation)
        overflow = len(self._observations) - self.maximum_observations
        if overflow > 0:
            del self._observations[:overflow]

    def observations(self) -> tuple[dict[str, object], ...]:
        return tuple(row.to_jsonable() for row in self._observations)

    def telemetry(self) -> dict[str, object]:
        adapters = (self.diarization_embedder, self.identity_embedder)
        worker_ids = {
            id(worker)
            for adapter in adapters
            if (worker := getattr(adapter, "worker", None)) is not None
        }
        started_workers = {
            id(worker)
            for adapter in adapters
            if getattr(adapter, "_worker_started", False)
            and (worker := getattr(adapter, "worker", None)) is not None
        }
        adapter_statuses = []
        unique_adapters = {id(adapter): adapter for adapter in adapters}
        for adapter in unique_adapters.values():
            if not hasattr(adapter, "status"):
                continue
            try:
                adapter_statuses.append(dict(adapter.status()))
            except Exception as exc:  # diagnostic only; do not mask inference.
                adapter_statuses.append(
                    {"status": "UNAVAILABLE", "error": type(exc).__name__}
                )
        initialization = 0.0
        model_bytes: set[int] = set()
        for status in adapter_statuses:
            telemetry = status.get("embedding_telemetry")
            if not isinstance(telemetry, Mapping):
                continue
            initialization += float(telemetry.get("initialization_sec") or 0.0)
            value = telemetry.get("model_bytes")
            if isinstance(value, (int, float)) and value >= 0:
                model_bytes.add(int(value))
        model_bytes_value = sum(model_bytes) if model_bytes else None
        calls = (
            self._counts["diarization_model_calls"]
            + self._counts["identity_model_calls"]
        )
        return {
            "schema_version": TELEMETRY_SCHEMA_VERSION,
            "strategy": self.strategy,
            "reuse_implementation_version": REUSE_IMPLEMENTATION_VERSION,
            **dict(self._counts),
            "total_embedding_model_calls": calls,
            "audio_seconds_embedded": self._audio_seconds_embedded,
            "audio_seconds_reused": self._audio_seconds_reused,
            "routing_wall_sec": self._routing_wall_sec,
            "embedding_rtf": (
                self._routing_wall_sec / self._audio_seconds_embedded
                if self._audio_seconds_embedded > 0
                else None
            ),
            "model_instance_handles": len(worker_ids),
            "model_instances_loaded": len(started_workers),
            "initialization_sec": initialization,
            "startup_sec": initialization,
            "model_bytes": model_bytes_value,
            "model_bytes_status": (
                "MEASURED_FROM_VERIFIED_BACKEND_ASSET_INVENTORY"
                if model_bytes_value is not None
                else "UNSUPPORTED_NOT_REPORTED_BY_ADAPTER"
            ),
            "queue_delay_ms": 0.0,
            "queue_delay_status": "SYNCHRONOUS_INLINE_REQUEST_CHANNEL_NO_QUEUE",
            "adapter_statuses": adapter_statuses,
            "raw_embedding_vectors_present": False,
        }

    def clear(self) -> None:
        self._candidates.clear()
        self._observations.clear()

    def clear_candidates(self) -> None:
        """Drop volatile reuse state without erasing append-only diagnostics."""

        self._candidates.clear()


__all__ = [
    "EmbeddingRequestFingerprint",
    "EmbeddingReuseObservation",
    "H2EmbeddingReuseRouter",
    "R1_TWO_INDEPENDENT_MODELS",
    "R2_ONE_SHARED_MODEL",
    "R3_EXACT_WINDOW_EMBEDDING_REUSE",
    "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
    "R4_QUALITY_POLICY_SHA256",
    "REDIM_EXECUTION_STRATEGIES",
    "request_fingerprint",
    "vector_sha256",
]
