"""Coordinator-facing adapters over the persistent isolated worker protocol."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import time
from typing import Mapping

import numpy as np
import soundfile as sf

from .cache import ContentAddressedCache, make_cache_key
from .models import (
    EmbeddingResult,
    EmbeddingWindow,
    NormalizedAudioFrame,
    SpeechRegionUpdate,
)
from .segmentation import (
    CausalSpeechRegionTracker,
    RollingSegmentationConfig,
    RollingSegmentationPlanner,
)
from .workers import PersistentWorker


def _audio_sha(samples: np.ndarray) -> str:
    value = np.ascontiguousarray(samples, dtype=np.float32)
    return hashlib.sha256(value.tobytes()).hexdigest()


def _atomic_wav(path: Path, samples: np.ndarray, sample_rate_hz: int = 16000) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
    sf.write(temporary, samples, sample_rate_hz, subtype="FLOAT")
    temporary.replace(path)


class NativeASRWorkerAdapter:
    """Persistent remote Sherpa decoder implementing StreamingASRAdapter."""

    def __init__(
        self,
        worker: PersistentWorker,
        work_root: Path,
        *,
        expected_config_sha256: str | None = None,
    ) -> None:
        self.worker = worker
        self.backend_id = worker.spec.component_id
        self.work_root = Path(work_root).resolve()
        self.expected_config_sha256 = expected_config_sha256
        self._state = "created"
        self._session_id: str | None = None

    def start(self, session_id: str) -> None:
        identity = self.worker.start()
        _validate_reported_worker_identity(
            identity,
            component_id=self.backend_id,
            expected_config_sha256=self.expected_config_sha256,
        )
        self.worker.call(
            "start_session", {"session_id": session_id, "source_start_sec": 0.0}
        )
        self._session_id = session_id
        self._state = "running"

    def accept_audio(
        self, frame: NormalizedAudioFrame
    ) -> tuple[Mapping[str, object], ...]:
        path = self.work_root / "asr_frames" / f"{_audio_sha(frame.samples)}.npy"
        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.tmp")
            with temporary.open("wb") as handle:
                np.save(handle, frame.samples, allow_pickle=False)
            temporary.replace(path)
        result = self.worker.call(
            "accept_audio",
            {
                "samples_path": str(path),
                "sample_rate_hz": frame.sample_rate_hz,
                "source_start_sec": frame.audio_start_sec,
                "source_end_sec": frame.audio_end_sec,
                "source_sample_start": frame.sample_start,
                "source_sample_end": frame.sample_end,
                "source_clock_id": frame.source_clock_id,
                "source_clock_type": frame.source_clock_type,
            },
            retry_on_worker_failure=False,
        )
        return tuple(dict(row) for row in result.get("updates", []))

    def finalize(self, reason: str) -> tuple[Mapping[str, object], ...]:
        if self._state != "running":
            return ()
        result = self.worker.call(
            "finalize", {"reason": reason}, retry_on_worker_failure=False
        )
        self._state = "finalized"
        return tuple(dict(row) for row in result.get("updates", []))

    def reset(self, reason: str) -> tuple[Mapping[str, object], ...]:
        if self._state == "running":
            self.worker.call("reset", {"reason": reason}, retry_on_worker_failure=False)
        else:
            self.worker.call(
                "start_session",
                {
                    "session_id": self._session_id or "reset-session",
                    "source_start_sec": 0.0,
                },
            )
            self._state = "running"
        return ()

    def status(self) -> Mapping[str, object]:
        return {"state": self._state, **self.worker.status()}

    def close(self) -> None:
        self.worker.shutdown()
        self._state = "closed"


class WorkerStreamingSegmenter:
    """Rolling 10 s / truthful 5 s lookahead around isolated Pyannote."""

    backend_id = "pyannote_segmentation_3_0"

    def __init__(
        self,
        worker: PersistentWorker,
        work_root: Path,
        *,
        config: RollingSegmentationConfig | None = None,
        cache: ContentAddressedCache | None = None,
        expected_model_asset_files: Mapping[str, str] | None = None,
        lazy_worker_start: bool = False,
    ) -> None:
        self.worker = worker
        self.work_root = Path(work_root).resolve()
        self.config = config or RollingSegmentationConfig()
        self.algorithmic_lookahead_sec = self.config.algorithmic_lookahead_sec
        self.planner = RollingSegmentationPlanner(self.config)
        self.tracker = CausalSpeechRegionTracker()
        self._overlap_tracker = CausalSpeechRegionTracker()
        self._predicted_overlap_intervals: list[tuple[float, float]] = []
        self.cache = cache or ContentAddressedCache(
            self.work_root / "cache/segmentation"
        )
        self.expected_model_asset_files = {
            str(name): str(value).lower()
            for name, value in dict(expected_model_asset_files or {}).items()
        }
        self.lazy_worker_start = bool(lazy_worker_start)
        self._worker_started = False
        self._cache_hits = 0
        self._cache_misses = 0
        self._session_id = "unstarted"
        self._state = "created"
        self._active_region_id: str | None = None
        self._active_region_start: float | None = None
        self._active_region_announced = False
        self._region_counter = 0

    def start(self, session_id: str) -> None:
        self._session_id = session_id
        if not self.lazy_worker_start:
            self._ensure_worker_started()
        self._state = "running"

    def _ensure_worker_started(self) -> None:
        if self._worker_started:
            return
        identity = self.worker.start()
        _validate_reported_worker_identity(
            identity,
            component_id=self.backend_id,
            expected_model_asset_files=self.expected_model_asset_files,
        )
        self._worker_started = True

    def accept_audio(
        self, frame: NormalizedAudioFrame
    ) -> tuple[SpeechRegionUpdate, ...]:
        updates: list[SpeechRegionUpdate] = []
        for chunk in self.planner.add(frame.samples):
            updates.extend(self._process_chunk(chunk))
        return tuple(updates)

    def finalize(self) -> tuple[SpeechRegionUpdate, ...]:
        updates: list[SpeechRegionUpdate] = []
        for chunk in self.planner.flush():
            updates.extend(self._process_chunk(chunk))
        self._state = "finalized"
        return tuple(updates)

    def _process_chunk(self, chunk: object) -> tuple[SpeechRegionUpdate, ...]:
        audio = np.asarray(chunk.audio, dtype=np.float32)
        digest = _audio_sha(audio)
        path = self.work_root / "segmentation_chunks" / f"{digest}.wav"
        key = make_cache_key(
            artifact_kind="pyannote_segmentation",
            role="anonymous_diarization_segmentation",
            source_audio_sha256=digest,
            source_start_sample=int(chunk.input_start_sample),
            source_end_sample=int(chunk.input_end_sample),
            sample_rate_hz=16000,
            window_identity=self.config.to_jsonable(),
            preprocessing_identity={"mono": True, "sample_rate_hz": 16000},
            model_identity={
                "backend_id": self.backend_id,
                "model_id": "pyannote/segmentation-3.0",
                "model_revision": "e66f3d3b9eb0873085418a7b813d3b369bf160bb",
                "model_asset_sha256": "0bd17acc0afbd3ae9b78f0ac2912d660297d59d9c107cf75bb75b39dcb8c7e14",
            },
            configuration_identity={"policy_id": self.config.policy_id},
        )
        cached = self.cache.load(key)
        if cached is None:
            self._cache_misses += 1
            self._ensure_worker_started()
            _atomic_wav(path, audio)
            result = self.worker.call(
                "segment",
                {
                    "audio_path": str(path),
                    "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "recording_id": self._session_id,
                    "chunk_id": f"chunk_{chunk.chunk_index:06d}",
                    "start_sec": 0.0,
                    "end_sec": len(audio) / 16000,
                    "source_timestamp_offset_sec": chunk.input_start_sample / 16000,
                    "algorithmic_lookahead_sec": chunk.algorithmic_lookahead_sec,
                    "segmentation_onset": self.config.onset,
                    "segmentation_offset": self.config.offset,
                    "segmentation_min_duration_on": (
                        self.config.minimum_speech_duration_sec
                    ),
                    "segmentation_min_duration_off": (
                        self.config.minimum_silence_duration_sec
                    ),
                },
            )
            result_identity = result.get("identity")
            if not isinstance(result_identity, Mapping):
                raise RuntimeError(
                    "segmentation worker response omitted model identity"
                )
            _validate_reported_worker_identity(
                result_identity,
                component_id=self.backend_id,
                expected_model_asset_files=self.expected_model_asset_files,
            )
            cached_payload = {
                name: value
                for name, value in result.items()
                if name != "segmentation_compute_sec"
            }
            self.cache.publish(key, cached_payload)
        else:
            self._cache_hits += 1
            result = dict(cached)
        commit = self.tracker.commit(chunk, result.get("speech_regions", []))
        overlap_commit = self._overlap_tracker.commit(
            chunk, result.get("predicted_overlap_regions", [])
        )
        self._predicted_overlap_intervals.extend(overlap_commit.speech_regions)
        latency_ms = (
            float(result.get("segmentation_compute_sec") or 0.0) * 1000
            if cached is None
            else 0.0
        )
        return self._updates_from_commit(
            commit, latency_ms, overlap_commit=overlap_commit
        )

    def _updates_from_commit(
        self,
        commit: object,
        latency_ms: float,
        *,
        overlap_commit: object | None = None,
    ) -> tuple[SpeechRegionUpdate, ...]:
        updates: list[SpeechRegionUpdate] = []
        reason = (
            "end_of_stream_reduced_lookahead"
            if commit.final_tail
            else "rolling_pyannote_causal_commit"
        )

        def begin(timestamp_sec: float) -> None:
            if self._active_region_id is not None:
                return
            self._region_counter += 1
            self._active_region_id = f"speech_{self._region_counter:06d}"
            self._active_region_start = float(timestamp_sec)
            self._active_region_announced = False

        def emit(state: str, end_sec: float) -> None:
            if self._active_region_id is None or self._active_region_start is None:
                return
            if end_sec <= self._active_region_start + 1e-9:
                return
            updates.append(
                SpeechRegionUpdate(
                    region_id=self._active_region_id,
                    state=state,
                    start_sec=float(self._active_region_start),
                    end_sec=float(end_sec),
                    committed_through_sec=float(commit.commit_end_sec),
                    algorithmic_lookahead_sec=float(commit.algorithmic_lookahead_sec),
                    compute_latency_ms=latency_ms,
                    overlap=self.predicted_overlap(
                        float(self._active_region_start), float(end_sec)
                    ),
                    reason=reason,
                )
            )

        def close_region(timestamp_sec: float) -> None:
            emit("speech_end", timestamp_sec)
            self._active_region_id = None
            self._active_region_start = None
            self._active_region_announced = False

        indexed_boundaries = sorted(
            enumerate(commit.boundaries),
            key=lambda item: (float(item[1].timestamp_sec), item[0]),
        )
        boundary_index = 0

        def apply_boundaries(through_sec: float) -> None:
            nonlocal boundary_index
            while boundary_index < len(indexed_boundaries):
                boundary = indexed_boundaries[boundary_index][1]
                if float(boundary.timestamp_sec) > through_sec + 1e-9:
                    break
                boundary_index += 1
                if boundary.event == "speech_end":
                    close_region(float(boundary.timestamp_sec))
                elif boundary.event == "speech_start":
                    begin(float(boundary.timestamp_sec))

        for start, region_end in commit.speech_regions:
            apply_boundaries(float(start))
            begin(float(start))
            region_id = self._active_region_id
            apply_boundaries(float(region_end))
            if self._active_region_id == region_id:
                if commit.final_tail and region_end >= commit.commit_end_sec - 1e-9:
                    close_region(float(region_end))
                else:
                    state = (
                        "speech_update"
                        if self._active_region_announced
                        else "speech_start"
                    )
                    emit(state, float(region_end))
                    self._active_region_announced = True
        apply_boundaries(float(commit.commit_end_sec))
        if commit.final_tail and self._active_region_id is not None:
            close_region(float(commit.commit_end_sec))
        return tuple(updates)

    def reset(self, *, origin_sample: int = 0) -> None:
        self.planner.reset(origin_sample=origin_sample)
        self.tracker.reset(origin_sec=origin_sample / self.config.sample_rate_hz)
        if hasattr(self, "_overlap_tracker"):
            self._overlap_tracker.reset(
                origin_sec=origin_sample / self.config.sample_rate_hz
            )
        self._predicted_overlap_intervals = []
        self._active_region_id = None
        self._active_region_start = None
        self._active_region_announced = False
        if getattr(self, "_worker_started", True):
            self.worker.reset()
        self._state = "running"

    def predicted_overlap(self, start_sec: float, end_sec: float) -> bool:
        """Whether a committed Pyannote overlap region intersects an interval."""

        if end_sec <= start_sec:
            return False
        return any(
            min(float(right), end_sec) - max(float(left), start_sec) > 1e-9
            for left, right in getattr(self, "_predicted_overlap_intervals", ())
        )

    def status(self) -> Mapping[str, object]:
        return {
            "state": self._state,
            "algorithmic_lookahead_sec": self.algorithmic_lookahead_sec,
            "shared_execution": {
                "lazy_worker_start": self.lazy_worker_start,
                "worker_started": self._worker_started,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "execution_origin": (
                    "primary_computed"
                    if self._worker_started
                    else "cache_replayed"
                    if self._cache_hits
                    else "not_used"
                ),
            },
            **self.worker.status(),
        }

    def close(self) -> None:
        self.worker.shutdown()
        self._state = "closed"


@dataclass
class WorkerEmbeddingAdapter:
    """Role-separated cached embeddings from one persistent backend worker."""

    worker: PersistentWorker
    work_root: Path
    backend_config_sha256: str
    model_id: str
    model_sha256: str
    cache: ContentAddressedCache | None = None
    lazy_worker_start: bool = False

    def __post_init__(self) -> None:
        self.work_root = Path(self.work_root).resolve()
        self.backend_id = self.worker.spec.component_id
        self.cache = self.cache or ContentAddressedCache(
            self.work_root / "cache/embeddings"
        )
        self._state = "created"
        self._worker_started = False
        self._cache_hits = 0
        self._cache_misses = 0
        self._embedding_requests = 0
        self._neural_embedding_calls = 0
        self._requested_audio_sec = 0.0
        self._neural_audio_sec = 0.0
        self._embedding_wall_sec = 0.0
        self._initialization_sec = 0.0
        self._model_bytes: int | None = None

    def start(self, _session_id: str) -> None:
        if not self.lazy_worker_start:
            self._ensure_worker_started()
        self._state = "running"

    def _ensure_worker_started(self) -> None:
        if self._worker_started:
            return
        started = time.perf_counter()
        identity = self.worker.start()
        _validate_reported_worker_identity(
            identity,
            component_id=self.backend_id,
            expected_config_sha256=self.backend_config_sha256,
        )
        self._initialization_sec += time.perf_counter() - started
        self._model_bytes = _reported_embedding_model_bytes(identity)
        self._worker_started = True

    def embed(self, window: EmbeddingWindow) -> EmbeddingResult:
        request_started = time.perf_counter()
        duration_sec = float(window.end_sec - window.start_sec)
        self._embedding_requests += 1
        self._requested_audio_sec += duration_sec
        digest = _audio_sha(window.samples)
        source_start_sample = round(window.start_sec * 16000)
        source_end_sample = source_start_sample + int(
            np.asarray(window.samples).size
        )
        key = make_cache_key(
            artifact_kind="speaker_embedding",
            role=window.role,
            source_audio_sha256=digest,
            source_start_sample=source_start_sample,
            source_end_sample=source_end_sample,
            sample_rate_hz=16000,
            window_identity={
                "window_id": window.window_id,
                "start_sec": window.start_sec,
                "end_sec": window.end_sec,
                "assignment_start_sec": window.assignment_start_sec,
                "assignment_end_sec": window.assignment_end_sec,
            },
            preprocessing_identity={
                "mono": True,
                "sample_rate_hz": 16000,
                "normalization": "backend_l2",
            },
            model_identity={
                "backend_id": self.backend_id,
                "model_id": self.model_id,
                "model_sha256": self.model_sha256,
            },
            configuration_identity={
                "backend_config_sha256": self.backend_config_sha256
            },
        )
        cached = self.cache.load(key)
        started = time.perf_counter()
        if cached is None:
            self._cache_misses += 1
            self._ensure_worker_started()
            self._neural_embedding_calls += 1
            self._neural_audio_sec += duration_sec
            path = self.work_root / "embedding_windows" / window.role / f"{digest}.wav"
            _atomic_wav(path, window.samples)
            result = self.worker.call(
                "embed",
                {
                    "audio_path": str(path),
                    "audio_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "recording_id": "full_pipeline_runtime",
                    "window_id": window.window_id,
                    "role": window.role,
                    "start_sec": 0.0,
                    "end_sec": len(window.samples) / 16000,
                    "segment_index": 0,
                    "device": "cpu",
                },
            )
            result_identity = result.get("identity")
            if not isinstance(result_identity, Mapping):
                raise RuntimeError("embedding worker response omitted model identity")
            _validate_reported_worker_identity(
                result_identity,
                component_id=self.backend_id,
                expected_config_sha256=self.backend_config_sha256,
            )
            embedding = dict(result["embedding"])
            payload = {
                "vector": embedding.get("vector"),
                "status": embedding.get("status"),
                "dimension": embedding.get("dimension"),
                "worker_wall_sec": result.get("worker_wall_sec"),
            }
            self.cache.publish(key, payload)
        else:
            self._cache_hits += 1
            payload = dict(cached)
        if payload.get("status") != "ok" or not payload.get("vector"):
            raise RuntimeError(
                f"embedding failed for {self.backend_id}: {payload.get('status')}"
            )
        value = EmbeddingResult(
            window_id=window.window_id,
            backend_id=self.backend_id,
            model_id=self.model_id,
            model_sha256=self.model_sha256,
            vector=np.asarray(payload["vector"], dtype=np.float32),
            duration_sec=window.end_sec - window.start_sec,
            role=window.role,
            quality={"status": "accepted"},
            cache_key=key.digest,
            compute_latency_ms=(time.perf_counter() - started) * 1000,
        )
        self._embedding_wall_sec += time.perf_counter() - request_started
        return value

    def reuse_identity_contract(self) -> Mapping[str, object]:
        """Return the result-affecting identity used by the H2 reuse gate."""

        return {
            "schema_version": "full-pipeline-embedding-reuse-identity.v1",
            "backend_id": self.backend_id,
            "model_id": self.model_id,
            "model_sha256": self.model_sha256,
            "backend_config_sha256": self.backend_config_sha256,
            "preprocessing": {
                "sample_rate_hz": 16000,
                "channel_policy": "mono",
                "sample_dtype": "float32",
                "normalization": "backend_l2",
                "worker_audio_transport": "pcm16_wav",
            },
        }

    def status(self) -> Mapping[str, object]:
        return {
            "state": self._state,
            "embedding_telemetry": {
                "schema_version": "full-pipeline-embedding-adapter-telemetry.v1",
                "embedding_requests": self._embedding_requests,
                "neural_embedding_calls": self._neural_embedding_calls,
                "requested_audio_sec": self._requested_audio_sec,
                "neural_audio_sec": self._neural_audio_sec,
                "embedding_wall_sec": self._embedding_wall_sec,
                "embedding_rtf": (
                    self._embedding_wall_sec / self._neural_audio_sec
                    if self._neural_audio_sec > 0
                    else None
                ),
                "initialization_sec": self._initialization_sec,
                "startup_sec": self._initialization_sec,
                "model_bytes": self._model_bytes,
                "model_bytes_status": (
                    "MEASURED_FROM_VERIFIED_BACKEND_ASSET_INVENTORY"
                    if self._model_bytes is not None
                    else "UNSUPPORTED_NOT_REPORTED_BY_WORKER"
                ),
                "queue_delay_ms": 0.0,
                "queue_delay_status": (
                    "SYNCHRONOUS_INLINE_REQUEST_CHANNEL_NO_QUEUE"
                ),
            },
            "shared_execution": {
                "lazy_worker_start": self.lazy_worker_start,
                "worker_started": self._worker_started,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "execution_origin": (
                    "primary_computed"
                    if self._worker_started
                    else "cache_replayed"
                    if self._cache_hits
                    else "not_used"
                ),
            },
            **self.worker.status(),
        }

    def close(self) -> None:
        self.worker.shutdown()
        self._state = "closed"


def _reported_embedding_model_bytes(identity: Mapping[str, object]) -> int | None:
    """Sum verified backend assets without guessing unreported model memory."""

    declared = identity.get("declared_backend")
    if not isinstance(declared, Mapping):
        return None
    assets = declared.get("model_asset_identity")
    if not isinstance(assets, list):
        return None
    values: list[int] = []
    for raw in assets:
        if not isinstance(raw, Mapping):
            continue
        observed = raw.get("observed_bytes")
        if (
            raw.get("present") is True
            and raw.get("verification_status") == "verified"
            and isinstance(observed, int)
            and observed >= 0
        ):
            values.append(observed)
    return sum(values) if values else None


def _validate_reported_worker_identity(
    identity: Mapping[str, object],
    *,
    component_id: str,
    expected_config_sha256: str | None = None,
    expected_model_asset_files: Mapping[str, str] | None = None,
) -> None:
    """Reject a worker whose self-reported runtime identity is not selected."""

    if str(identity.get("component_id")) != component_id:
        raise RuntimeError(
            f"worker component mismatch: expected {component_id}, "
            f"observed {identity.get('component_id')}"
        )
    if expected_config_sha256 is not None:
        observed_config = identity.get("config_sha256")
        declared_backend = identity.get("declared_backend")
        if observed_config is None and isinstance(declared_backend, Mapping):
            observed_config = declared_backend.get("config_hash")
        if str(observed_config).lower() != expected_config_sha256.lower():
            raise RuntimeError(
                f"worker config mismatch for {component_id}: expected "
                f"{expected_config_sha256}, observed {observed_config}"
            )
    expected_files = {
        str(name): str(value).lower()
        for name, value in dict(expected_model_asset_files or {}).items()
    }
    if expected_files:
        observed_files = identity.get("model_asset_files")
        normalized_observed = (
            {str(name): str(value).lower() for name, value in observed_files.items()}
            if isinstance(observed_files, Mapping)
            else {}
        )
        if normalized_observed != expected_files:
            raise RuntimeError(
                f"worker model assets mismatch for {component_id}: expected "
                f"{expected_files}, observed {normalized_observed}"
            )
