"""Event-driven coordinator for one selected full-pipeline runtime session."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import threading
import time
from typing import Any, Mapping, Sequence
import uuid

import numpy as np

from .alignment import (
    SpeakerRegion,
    TranscriptSpeakerAligner,
    TranscriptSpan,
    stable_span_id,
)
from .artifacts import RuntimeArtifactWriter
from .asr import ACCEPTED_AUDIO_INTERVAL_PROVENANCE
from .audio import AudioReadTimeout, BoundedFrameQueue, DropPolicy
from .cache import (
    CacheDependency,
    ContentAddressedCache,
    make_runtime_cache_key,
    result_affecting_identity,
    score_matrix_source_identity,
    canonical_sha256,
    make_cache_key,
)
from .enrollment import (
    ProtectedEnrollmentStore,
    RuntimeEnrollmentProfile,
    score_profile,
)
from .embedding_reuse import H2EmbeddingReuseRouter
from .events import EventFactory, OrderedJsonlEventSink
from .identity import (
    ClusterCreation,
    IdentityEvidence,
    IdentityState,
    IdentityTransition,
    SessionIdentityManager,
)
from .matrix import PipelineSelection
from .models import (
    ComponentRuntimeIdentity,
    EmbeddingResult,
    EmbeddingWindow,
    NormalizedAudioFrame,
    SpeechRegionUpdate,
    utc_now_text,
)
from .paragraphs import build_paragraphs
from .product_modes import BoundedSessionMemory, H2RuntimeTuning
from .segmentation import CausalDiarizationWindowPlanner


CALIBRATION_RESULT_SHA256 = (
    "2e93bab8d820160fb33c002670670687634968800840dfe190d13792fa7a886a"
)
CALIBRATION_PROTOCOL_ID = "hybrid_speaker_attribution_product_v2_a68cc1ac26aa"
QUALITY_POLICY_ID = "full_pipeline_identity_embedding_quality.v1"


@dataclass(frozen=True)
class CoordinatorConfig:
    session_id: str
    recording_id: str
    output_root: Path
    maximum_queue_frames: int = 16
    queue_policy: DropPolicy = "block"
    telemetry_enabled: bool = True
    maximum_audio_history_sec: float = 30.0


class _AudioHistory:
    def __init__(
        self, *, sample_rate_hz: int = 16000, maximum_sec: float = 30.0
    ) -> None:
        self.sample_rate_hz = sample_rate_hz
        self.maximum_samples = round(maximum_sec * sample_rate_hz)
        self._frames: list[NormalizedAudioFrame] = []

    def add(self, frame: NormalizedAudioFrame) -> None:
        self._frames.append(frame)
        floor = frame.sample_end - self.maximum_samples
        self._frames = [row for row in self._frames if row.sample_end > floor]

    def slice(self, start_sec: float, end_sec: float) -> np.ndarray | None:
        start = round(start_sec * self.sample_rate_hz)
        # Quantize the requested duration once and anchor it at the quantized
        # start.  Independently rounding two floating-point endpoints can make
        # an exact 0.50 s request one sample short (7,999 rather than 8,000).
        # This preserves the requested audio duration without padding or
        # relaxing any backend minimum-duration rule.
        duration_samples = round((end_sec - start_sec) * self.sample_rate_hz)
        end = start + duration_samples
        if end <= start:
            return None
        result = np.zeros(end - start, dtype=np.float32)
        covered = np.zeros(end - start, dtype=bool)
        for frame in self._frames:
            left = max(start, frame.sample_start)
            right = min(end, frame.sample_end)
            if right <= left:
                continue
            result[left - start : right - start] = frame.samples[
                left - frame.sample_start : right - frame.sample_start
            ]
            covered[left - start : right - start] = True
        if not bool(np.all(covered)):
            return None
        return result


class StreamingPipelineCoordinator:
    """Run capture, native ASR, causal diarization, identity, and alignment.

    Component implementations are injected so the coordinator itself never
    imports incompatible model stacks.  Production construction uses isolated
    worker adapters; tests use deterministic in-process fakes implementing the
    same interfaces.
    """

    def __init__(
        self,
        *,
        config: CoordinatorConfig,
        selection: PipelineSelection,
        source: Any,
        normalizer: Any,
        asr: Any,
        segmenter: Any,
        diarization_embedder: Any,
        cluster_manager: Any,
        identity_embedder: Any,
        enrollment_store: ProtectedEnrollmentStore,
        identity_manager: SessionIdentityManager,
        transcript_aligner: TranscriptSpeakerAligner,
        identities: Mapping[str, ComponentRuntimeIdentity],
        decision_policy_contract: Mapping[str, object] | None = None,
        resource_monitor: Any | None = None,
        cache: ContentAddressedCache | None = None,
        runtime_tuning: H2RuntimeTuning | None = None,
        emit_identity_score_diagnostics: bool = False,
    ) -> None:
        self.config = config
        self.selection = selection
        self.source = source
        self.normalizer = normalizer
        self.asr = asr
        self.segmenter = segmenter
        self.diarization_embedder = diarization_embedder
        self.cluster_manager = cluster_manager
        self.identity_embedder = identity_embedder
        self.enrollment_store = enrollment_store
        self.identity_manager = identity_manager
        self.transcript_aligner = transcript_aligner
        self.identities = dict(identities)
        self.decision_policy_contract = (
            dict(decision_policy_contract) if decision_policy_contract is not None else None
        )
        self.resource_monitor = resource_monitor
        self.cache = cache
        self.runtime_tuning = runtime_tuning
        self.emit_identity_score_diagnostics = bool(
            emit_identity_score_diagnostics
        )
        self.mode_behavior = runtime_tuning.behavior if runtime_tuning is not None else None
        self.session_memory = (
            BoundedSessionMemory(runtime_tuning)
            if runtime_tuning is not None
            else None
        )
        self.embedding_reuse_router = (
            H2EmbeddingReuseRouter(
                strategy=runtime_tuning.redim_execution_strategy,
                diarization_embedder=diarization_embedder,
                identity_embedder=identity_embedder,
                minimum_identity_duration_sec=runtime_tuning.minimum_embedding_sec,
                identity_accumulation=runtime_tuning.identity_accumulation,
                maximum_candidates=max(
                    32,
                    runtime_tuning.maximum_identity_observations_per_cluster
                    * runtime_tuning.maximum_session_speakers,
                ),
                maximum_observations=max(
                    512,
                    runtime_tuning.maximum_session_event_history * 8,
                ),
            )
            if runtime_tuning is not None
            else None
        )
        self.output_root = Path(config.output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.artifacts = RuntimeArtifactWriter(self.output_root)
        self.sink = OrderedJsonlEventSink(self.output_root / "events/events.jsonl")
        self.factory = EventFactory(
            session_id=config.session_id,
            pipeline_id=selection.pipeline_id,
            protocol_version=selection.protocol_version,
            stream_id=f"stream:{config.session_id}",
            recording_id=config.recording_id,
            source_clock={
                "clock_id": f"normalized_audio:{config.session_id}",
                "clock_type": "audio_sample",
                "sample_rate_hz": 16000,
                "utc_epoch": utc_now_text(),
                "monotonic_epoch_ns": time.perf_counter_ns(),
                "external_timebase": "source_media_time",
                "drift_parts_per_million": None,
            },
        )
        self.queue = BoundedFrameQueue(
            config.maximum_queue_frames, drop_policy=config.queue_policy
        )
        self.history = _AudioHistory(maximum_sec=config.maximum_audio_history_sec)
        self.window_planner = CausalDiarizationWindowPlanner(
            duration_sec=(
                runtime_tuning.embedding_window_sec
                if runtime_tuning is not None
                else 1.5
            ),
            step_sec=(
                runtime_tuning.embedding_hop_sec
                if runtime_tuning is not None
                else 0.75
            ),
            minimum_sec=(
                runtime_tuning.minimum_embedding_sec
                if runtime_tuning is not None
                else 0.75
            ),
        )
        self._stop = threading.Event()
        self._control = threading.Condition(threading.RLock())
        # UI session controls run on another thread. This makes a pause/reset
        # wait for the current frame instead of racing partially updated state.
        self._processing_lock = threading.RLock()
        self._pause_requested = False
        self._user_stop_requested = False
        self._producer_error: BaseException | None = None
        self._producer: threading.Thread | None = None
        self._started_utc: str | None = None
        self._ended_utc: str | None = None
        self._state = "created"
        self._recoverable = True
        self._warnings: list[str] = []
        self._errors: list[str] = []
        self._counts: dict[str, int] = {
            "audio_frames": 0,
            "events": 0,
            "transcript_revisions": 0,
            "anonymous_speakers": 0,
            "identity_evidence_events": 0,
            "identity_label_events": 0,
            "warnings": 0,
            "errors": 0,
        }
        self._event_groups: dict[str, list[Mapping[str, object]]] = {
            "asr": [],
            "transcript": [],
            "anonymous": [],
            "identity_evidence": [],
            "identity_label": [],
            "telemetry": [],
        }
        self._asr_diagnostics: list[Mapping[str, object]] = []
        self._identity_diagnostics: list[Mapping[str, object]] = []
        self._calibrated_identity_score_diagnostics: list[
            Mapping[str, object]
        ] = []
        self._overlap_identity_diagnostics: list[Mapping[str, object]] = []
        self._boundary_corrections: list[Mapping[str, object]] = []
        self._cluster_reconciliations: list[Mapping[str, object]] = []
        self._last_asr_event_by_line: dict[str, str] = {}
        self._hypothesis_spans: dict[str, tuple[str, ...]] = {}
        self._speaker_regions: list[SpeakerRegion] = []
        self._speaker_regions_by_window: dict[str, SpeakerRegion] = {}
        self._window_cluster_intervals: dict[str, tuple[str, float, float]] = {}
        self._anonymous_event_by_window: dict[str, Mapping[str, object]] = {}
        self._cluster_intervals: dict[str, list[tuple[float, float]]] = {}
        self._identity_vectors: dict[str, dict[str, tuple[np.ndarray, float]]] = {}
        self._identity_observation_times: dict[str, dict[str, float]] = {}
        self._profiles: tuple[RuntimeEnrollmentProfile, ...] = ()
        self._created_clusters: set[str] = set()
        self._last_cluster_id: str | None = None
        self._sample_sequence = 0
        self._source_horizon_sec = 0.0
        self._queue_blocked_total_sec = 0.0
        self._queue_blocked_max_sec = 0.0
        self._status_lock = threading.Lock()
        self._last_status_write_monotonic = 0.0
        self._asr_utterance_digest = hashlib.sha256()
        self._asr_utterance_start_sample = 0
        self._asr_utterance_end_sample = 0
        self._last_processed_frame: NormalizedAudioFrame | None = None
        self._anonymous_epoch = 0

    def run(self) -> Mapping[str, object]:
        self._started_utc = utc_now_text()
        self._set_state("starting")
        try:
            self._start_components()
            self._set_state("running")
            self._emit_status("running", "runtime_started")
            self._start_producer()
            while True:
                if not self._wait_until_runtime_resumed():
                    break
                frame = self.queue.get(timeout_sec=0.25)
                if frame is None:
                    if self.queue.closed:
                        break
                    if self._stop.is_set():
                        break
                    continue
                if not self._wait_until_runtime_resumed():
                    break
                with self._processing_lock:
                    self._process_raw_frame(frame)
            if self._producer is not None:
                self._producer.join(timeout=5.0)
                if self._producer.is_alive():
                    raise RuntimeError("audio producer did not stop cleanly")
            if self._producer_error is not None and not self._is_user_stop_requested():
                raise RuntimeError("audio source failed") from self._producer_error
            self._finalize_components()
            if self._is_user_stop_requested():
                self._emit_status("stopping", "user_stop_completed")
                self._set_state("stopped")
            else:
                self._set_state("completed" if not self._errors else "degraded")
                self._emit_status(self._state, "end_of_input")
        except BaseException as exc:
            self._set_state("failed")
            self._recoverable = True
            self._errors.append(f"{type(exc).__name__}: {exc}")
            self._counts["errors"] = len(self._errors)
            try:
                self._emit_status("failed", "runtime_exception")
            except Exception:
                pass
        finally:
            self._stop.set()
            with self._control:
                self._pause_requested = False
                self._control.notify_all()
            self.queue.close()
            try:
                self.source.stop()
            except Exception as exc:
                self._warnings.append(
                    f"source shutdown warning: {type(exc).__name__}: {exc}"
                )
            if self._producer is not None and self._producer.is_alive():
                self._producer.join(timeout=5.0)
                if self._producer.is_alive():
                    self._warnings.append(
                        "audio producer remained alive after bounded shutdown"
                    )
            self._stop_components()
            self._ended_utc = utc_now_text()
            self.sink.close()
        try:
            return self._write_result()
        finally:
            if self.mode_behavior is not None and (
                self.mode_behavior.delete_anonymous_state_on_end
            ):
                with self._processing_lock:
                    self._clear_volatile_session_state(
                        preserve_transcript=True,
                        increment_epoch=False,
                    )

    def request_stop(self) -> None:
        with self._control:
            if self._state not in {"completed", "degraded", "failed", "stopped"}:
                self._state = "stopping"
            self._user_stop_requested = True
            self._pause_requested = False
            self._control.notify_all()
        self._stop.set()
        self.queue.close()
        try:
            self.source.stop()
        except Exception as exc:
            self._warnings.append(f"source stop warning: {type(exc).__name__}")

    def request_pause(self) -> None:
        """Pause processing and capture at the next source-frame boundary."""

        with self._control:
            if self._state not in {"running", "paused"} or self._stop.is_set():
                return
            if self._pause_requested:
                return
            self._pause_requested = True
            self._state = "paused"
        try:
            if hasattr(self.source, "pause"):
                self.source.pause()
        except BaseException:
            with self._control:
                self._pause_requested = False
                self._state = "running"
                self._control.notify_all()
            raise

    def request_resume(self) -> None:
        """Resume a paused runtime without changing its scientific identity."""

        with self._control:
            if not self._pause_requested or self._stop.is_set():
                return
        if hasattr(self.source, "resume"):
            self.source.resume()
        with self._control:
            self._pause_requested = False
            self._state = "running"
            self._control.notify_all()

    def clear_anonymous_memory(
        self, *, preserve_transcript: bool = True
    ) -> Mapping[str, object]:
        """Delete volatile clusters/mappings while preserving enrollment.

        The operation is accepted before execution or while paused.  Requiring
        a frame boundary prevents a UI thread from racing model output.  Event
        logs remain append-only audit evidence; they are not active voice
        profiles and are never reused for a decision.
        """

        with self._control:
            state = self._state
            if state == "running" and not self._pause_requested:
                raise RuntimeError("pause the runtime before clearing anonymous memory")
            if state in {"completed", "degraded", "failed", "stopped"}:
                raise RuntimeError("completed runtime memory is already disposed")
        profile_ids = tuple(row.profile_id for row in self._profiles)
        with self._processing_lock:
            cleared = self._clear_volatile_session_state(
                preserve_transcript=preserve_transcript,
                increment_epoch=True,
            )
        if tuple(row.profile_id for row in self._profiles) != profile_ids:
            raise RuntimeError("permanent enrollment changed during anonymous reset")
        self._emit_status(
            "running" if state in {"running", "paused"} else "ready",
            "anonymous_memory_cleared",
            self._last_processed_frame,
        )
        return {
            "schema_version": "h2-session-reset-result.v1",
            "action": "clear_anonymous_memory",
            "product_mode": (
                self.runtime_tuning.product_mode.value
                if self.runtime_tuning is not None
                else None
            ),
            "transcript_preserved": bool(preserve_transcript),
            "permanent_enrollment_preserved": True,
            "enrollment_profile_ids": list(profile_ids),
            **cleared,
        }

    def reset_session(
        self, *, preserve_transcript: bool = True
    ) -> Mapping[str, object]:
        """Reset decoder plus volatile speaker state without unloading models."""

        with self._control:
            state = self._state
            if state == "running" and not self._pause_requested:
                raise RuntimeError("pause the runtime before resetting the session")
            if state in {"completed", "degraded", "failed", "stopped"}:
                raise RuntimeError("cannot reset a completed runtime")
        with self._processing_lock:
            if state in {"running", "paused"}:
                for row in self.asr.reset("user_session_reset"):
                    self._handle_asr(row, self._last_processed_frame)
                origin_sample = (
                    self._last_processed_frame.sample_end
                    if self._last_processed_frame is not None
                    else 0
                )
                if hasattr(self.segmenter, "reset"):
                    try:
                        self.segmenter.reset(origin_sample=origin_sample)
                    except TypeError:
                        self.segmenter.reset()
            result = dict(
                self.clear_anonymous_memory(
                    preserve_transcript=preserve_transcript
                )
            )
        result["action"] = "reset_session"
        return result

    def status(self) -> Mapping[str, object]:
        with self._control:
            state = self._state
            paused = self._pause_requested
            stop_requested = self._user_stop_requested
        with self._processing_lock:
            identity_state = self.identity_manager.session_state()
            session_memory = (
                self.session_memory.snapshot()
                if self.session_memory is not None
                and self.mode_behavior is not None
                and self.mode_behavior.active_roster
                else None
            )
            bounded_state = {
                "identity_observation_count": sum(
                    len(value) for value in self._identity_vectors.values()
                ),
                "active_region_count": len(self._speaker_regions_by_window),
                "identity_cluster_count": identity_state["cluster_count"],
                "identity_history_count": sum(
                    len(row["evidence_history"])
                    for row in identity_state["clusters"]
                ),
                "identity_history_maximum_per_cluster": identity_state[
                    "maximum_evidence_history_per_cluster"
                ],
                "identity_cluster_bound": identity_state["maximum_clusters"],
                "session_memory_roster_count": (
                    len(session_memory["roster"])
                    if session_memory is not None
                    else 0
                ),
                "session_memory_history_count": (
                    len(session_memory["history"])
                    if session_memory is not None
                    else 0
                ),
            }
        return {
            "schema_version": "full-pipeline-runtime-status.v1",
            "session_id": self.config.session_id,
            "pipeline_id": self.selection.pipeline_id,
            "state": state,
            "paused": paused,
            "stop_requested": stop_requested,
            "recoverable": self._recoverable,
            "source_time_sec": self._source_horizon_sec,
            "queue_depth": self.queue.depth,
            "dropped_frame_count": self.queue.dropped_count,
            "queue_backpressure": {
                "policy": self.config.queue_policy,
                "current_depth": self.queue.depth,
                "maximum_depth": self.queue.max_depth,
                "blocked_total_sec": self._queue_blocked_total_sec,
                "blocked_max_sec": self._queue_blocked_max_sec,
            },
            "counts": dict(self._counts),
            "warnings": list(self._warnings),
            "errors": list(self._errors),
            "components": self._component_statuses(),
            "h2_product_mode": (
                self.runtime_tuning.product_mode.value
                if self.runtime_tuning is not None
                else None
            ),
            "runtime_tuning_sha256": (
                self.runtime_tuning.identity_sha256
                if self.runtime_tuning is not None
                else None
            ),
            "bounded_session_state": bounded_state,
            "session_memory": session_memory,
        }

    def _set_state(self, state: str) -> None:
        with self._control:
            self._state = state
            self._control.notify_all()

    def _is_user_stop_requested(self) -> bool:
        with self._control:
            return self._user_stop_requested

    def _wait_until_runtime_resumed(self) -> bool:
        with self._control:
            while self._pause_requested and not self._stop.is_set():
                self._control.wait(timeout=0.25)
            return not self._stop.is_set()

    def _clear_volatile_session_state(
        self,
        *,
        preserve_transcript: bool,
        increment_epoch: bool,
    ) -> dict[str, object]:
        allocation_count = len(self.identity_manager.allocator.snapshot())
        vector_count = sum(len(value) for value in self._identity_vectors.values())
        region_count = len(self._speaker_regions_by_window)
        if preserve_transcript:
            sealed = self.transcript_aligner.seal_existing_spans()
        else:
            sealed = ()
            self.transcript_aligner.reset()
            self._hypothesis_spans.clear()
            self._last_asr_event_by_line.clear()
        self.identity_manager.clear_anonymous_memory()
        self.cluster_manager.reset()
        self._identity_vectors.clear()
        self._identity_observation_times.clear()
        self._created_clusters.clear()
        self._last_cluster_id = None
        self._speaker_regions.clear()
        self._speaker_regions_by_window.clear()
        self._window_cluster_intervals.clear()
        self._anonymous_event_by_window.clear()
        self._cluster_intervals.clear()
        if self.embedding_reuse_router is not None:
            self.embedding_reuse_router.clear_candidates()
        if self.session_memory is not None:
            self.session_memory.clear()
        self.window_planner = CausalDiarizationWindowPlanner(
            duration_sec=(
                self.runtime_tuning.embedding_window_sec
                if self.runtime_tuning is not None
                else 1.5
            ),
            step_sec=(
                self.runtime_tuning.embedding_hop_sec
                if self.runtime_tuning is not None
                else 0.75
            ),
            minimum_sec=(
                self.runtime_tuning.minimum_embedding_sec
                if self.runtime_tuning is not None
                else 0.75
            ),
        )
        if increment_epoch:
            self._anonymous_epoch += 1
        return {
            "anonymous_allocations_deleted": allocation_count,
            "embedding_observations_deleted": vector_count,
            "active_regions_deleted": region_count,
            "sealed_transcript_span_count": len(sealed),
            "anonymous_epoch": self._anonymous_epoch,
        }

    def _start_components(self) -> None:
        self.asr.start(self.config.session_id)
        if hasattr(self.segmenter, "start"):
            self.segmenter.start(self.config.session_id)
        for component in (self.diarization_embedder, self.identity_embedder):
            if hasattr(component, "start"):
                component.start(self.config.session_id)
        self._profiles = tuple(
            self.enrollment_store.load_profiles(
                str(self.selection.identity["backend_id"])
            )
        )
        self._validate_profiles()
        if self.resource_monitor is not None and self.config.telemetry_enabled:
            self.resource_monitor.on_sample = self._on_telemetry
            self.resource_monitor.start()

    def _start_producer(self) -> None:
        def produce() -> None:
            try:
                self.source.start()
                while not self._stop.is_set():
                    try:
                        frame = self.source.read(timeout_sec=0.5)
                    except AudioReadTimeout:
                        continue
                    if frame is None:
                        break
                    outcome = self.queue.put(frame)
                    self._queue_blocked_total_sec += outcome.blocked_sec
                    self._queue_blocked_max_sec = max(
                        self._queue_blocked_max_sec, outcome.blocked_sec
                    )
                    if outcome.closed:
                        break
                    if outcome.dropped is not None:
                        self._warnings.append(
                            f"audio queue {outcome.reason}: frame {outcome.dropped.frame_id}"
                        )
            except BaseException as exc:
                self._producer_error = exc
            finally:
                try:
                    self.source.stop()
                finally:
                    self.queue.close()

        self._producer = threading.Thread(
            target=produce, name="full-pipeline-audio-source", daemon=True
        )
        self._producer.start()

    def _process_raw_frame(self, raw: Any) -> None:
        frame: NormalizedAudioFrame = self.normalizer.normalize(raw)
        self._source_horizon_sec = max(
            self._source_horizon_sec, float(frame.audio_end_sec)
        )
        if frame.discontinuity_before:
            self._warnings.append(
                f"audio discontinuity before {frame.frame_id}: {frame.dropped_source_samples_before} internal samples"
            )
            for row in self.asr.finalize("audio_discontinuity"):
                self._handle_asr(row, self._last_processed_frame)
            self.asr.reset("audio_discontinuity")
            self._asr_utterance_digest = hashlib.sha256()
            self._asr_utterance_start_sample = frame.sample_start
            self._asr_utterance_end_sample = frame.sample_start
            if hasattr(self.segmenter, "reset"):
                for region in self.segmenter.finalize():
                    self._handle_speech_region(region, self._last_processed_frame)
                self.segmenter.reset(origin_sample=frame.sample_start)
        self._asr_utterance_digest.update(
            f"{frame.sample_start}:{frame.sample_end}:".encode("ascii")
        )
        self._asr_utterance_digest.update(
            np.ascontiguousarray(frame.samples, dtype=np.float32).tobytes()
        )
        self._asr_utterance_end_sample = frame.sample_end
        self.history.add(frame)
        self._emit_audio_frame(frame)
        for row in self.asr.accept_audio(frame):
            self._handle_asr(row, frame)
        for region in self.segmenter.accept_audio(frame):
            self._handle_speech_region(region, frame)
        if self.session_memory is not None:
            self.session_memory.advance_time(frame.audio_end_sec)
        decay_half_life = (
            self.runtime_tuning.confidence_decay_half_life_sec
            if self.runtime_tuning is not None
            and self.runtime_tuning.memory_level
            in {"M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"}
            else None
        )
        for transition in self.identity_manager.advance_time(
            frame.audio_end_sec,
            confidence_decay_half_life_sec=decay_half_life,
            confidence_decay_release_floor=(
                self.runtime_tuning.confidence_decay_release_floor
                if self.runtime_tuning is not None
                else 0.25
            ),
        ):
            self._emit_expiry_transition(transition, frame)
        self._prune_bounded_runtime_state(frame.audio_end_sec)
        self._last_processed_frame = frame

    def _finalize_components(self) -> None:
        for row in self.asr.finalize("input_finished"):
            self._handle_asr(row, None)
        for region in self.segmenter.finalize():
            self._handle_speech_region(region, None)

    def _stop_components(self) -> None:
        if self.resource_monitor is not None and self.config.telemetry_enabled:
            try:
                self.resource_monitor.stop()
            except Exception as exc:
                self._warnings.append(
                    f"telemetry shutdown warning: {type(exc).__name__}"
                )
        for component in (
            self.asr,
            self.segmenter,
            self.diarization_embedder,
            self.identity_embedder,
        ):
            try:
                component.close()
            except Exception as exc:
                self._warnings.append(
                    f"component shutdown warning: {type(exc).__name__}"
                )

    def _emit_audio_frame(self, frame: NormalizedAudioFrame) -> None:
        event = self.factory.create(
            contract_type="AudioFrame",
            event_type="audio_frame",
            component_identity=self.identities["capture"],
            capture_timestamps=frame.capture_contract(),
            event_reason="normalized_audio_frame",
            detail=json.dumps(dict(frame.provenance), sort_keys=True),
            payload={
                "frame_id": frame.frame_id,
                "frame_sequence": frame.sequence,
                "sample_rate_hz": frame.sample_rate_hz,
                "channel_count": 1,
                "sample_count_per_channel": int(frame.samples.size),
                "sample_format": "float32",
                "pcm_encoding": "normalized_float",
                "payload": {
                    "representation": "in_memory_handle",
                    "inline_base64": None,
                    "artifact": None,
                    "in_memory_handle_id": frame.frame_id,
                },
                "disposition": "discontinuous"
                if frame.discontinuity_before
                else "replayed",
            },
        )
        self._publish(event)
        self._counts["audio_frames"] += 1

    def _handle_asr(
        self, row: Mapping[str, object], frame: NormalizedAudioFrame | None
    ) -> None:
        adapter_type = str(row.get("adapter_event_type"))
        if adapter_type == "asr_reset":
            self._asr_diagnostics.append(dict(row))
            return
        is_final = adapter_type == "asr_final" or bool(row.get("is_final"))
        contract_type = "AsrFinalEvent" if is_final else "AsrPartialEvent"
        event_type = "asr_final" if is_final else "asr_partial"
        line_number = int(row.get("utterance_index", 1))
        line_id = f"line_{line_number:06d}"
        prior_event = self._last_asr_event_by_line.get(line_id)
        revision_number = int(row.get("revision_number", 0))
        words = self._asr_word_contracts(row, line_id)
        accepted_interval = self._asr_accepted_audio_interval(row)
        payload: dict[str, object] = {
            "hypothesis_id": str(
                row.get("hypothesis_id") or f"{self.config.session_id}:{line_id}"
            ),
            "hypothesis_state": "final" if is_final else "partial",
            "text": str(row.get("normalized_text") or row.get("text") or ""),
            "language": "en",
            "words": words,
            "audio_consumed_through_sec": float(
                row.get("audio_consumed_through_sec") or 0.0
            ),
            "line_id": line_number,
            "revision": {
                "revision_id": f"{line_id}:revision:{revision_number}",
                "revision_number": revision_number,
                "supersedes_revision_id": (
                    f"{line_id}:revision:{max(0, revision_number - 1)}"
                    if revision_number
                    else None
                ),
                "corrected_event_ids": [prior_event] if prior_event else [],
                "reason": {
                    "code": "native_sherpa_hypothesis_update",
                    "detail": str(row.get("stable_prefix_method") or ""),
                    "causal_event_ids": [prior_event] if prior_event else [],
                },
            },
        }
        if is_final:
            payload.update(
                {
                    "finalization_reason": str(
                        row.get("finalization_reason") or "input_finished"
                    ),
                    "endpoint_policy_id": str(
                        row.get("endpoint_policy_id") or "sherpa_backend_default"
                    ),
                }
            )
        if accepted_interval is not None:
            capture = {
                "sample_start_index": accepted_interval["sample_start_index"],
                "sample_end_index": accepted_interval["sample_end_index"],
                "audio_start_sec": accepted_interval["audio_start_sec"],
                "audio_end_sec": accepted_interval["audio_end_sec"],
            }
        elif frame is not None:
            capture = frame.capture_contract()
        else:
            capture = {
                "sample_start_index": None,
                "sample_end_index": None,
                "audio_start_sec": None,
                "audio_end_sec": float(row.get("audio_consumed_through_sec") or 0.0),
            }
        event = self.factory.create(
            contract_type=contract_type,
            event_type=event_type,
            component_identity=self.identities["asr"],
            capture_timestamps=capture,
            event_reason="native_stateful_stream_update",
            detail=(
                f"timing_provenance={ACCEPTED_AUDIO_INTERVAL_PROVENANCE};"
                "word_timestamps_inferred=false"
                if accepted_interval is not None
                else None
            ),
            causation_event_id=(
                self._event_groups["asr"][-1]["event_id"]
                if self._event_groups["asr"]
                else None
            ),
            causal_event_ids=[prior_event] if prior_event else [],
            backend_latency_ms=float(row.get("decode_latency_ms") or 0.0),
            payload=payload,
        )
        self._publish(event, "asr")
        if is_final:
            self._cache_asr_final(row)
        self._last_asr_event_by_line[line_id] = str(event["event_id"])
        self._asr_diagnostics.append(
            {**dict(row), "public_event_id": event["event_id"]}
        )
        self._update_transcript(event, row, words)

    def _cache_asr_final(self, row: Mapping[str, object]) -> None:
        if self._asr_utterance_end_sample <= self._asr_utterance_start_sample:
            return
        final_digest = self._asr_utterance_digest.hexdigest()
        start_sample = self._asr_utterance_start_sample
        end_sample = self._asr_utterance_end_sample
        self._asr_utterance_digest = hashlib.sha256()
        self._asr_utterance_start_sample = end_sample
        if self.cache is None:
            return
        key = make_cache_key(
            artifact_kind="asr_finalized_results",
            role="asr_finalized_result",
            source_audio_sha256=final_digest,
            source_start_sample=start_sample,
            source_end_sample=end_sample,
            sample_rate_hz=16000,
            window_identity={
                "finalization_reason": row.get("finalization_reason"),
                "audio_consumed_through_sec": row.get("audio_consumed_through_sec"),
            },
            preprocessing_identity={
                "normalization_policy_id": "full_pipeline_audio_normalization.v1",
                "partial_event_timing_replayed": False,
            },
            model_identity={
                "component_id": self.selection.asr["component_id"],
                "config_sha256": self.selection.asr["config_sha256"],
                "model_id": self.selection.asr["model_asset"]["asset_id"],
                "model_asset_sha256": self.selection.asr["model_asset"][
                    "installed_tree_sha256"
                ],
            },
            configuration_identity={
                "runtime_config_sha256": self.selection.runtime_config_sha256,
                "adapter_policy_id": "full_pipeline_native_sherpa_session.v1",
                "endpoint_policy_id": row.get("endpoint_policy_id"),
            },
        )
        if self.cache.load(key) is None:
            self.cache.publish(
                key,
                {
                    "finalized_adapter_result": dict(row),
                    "replays_partial_event_timing": False,
                },
            )

    def _asr_word_contracts(
        self, row: Mapping[str, object], line_id: str
    ) -> list[dict[str, object]]:
        raw_words = [str(value) for value in row.get("words", []) if str(value).strip()]
        timestamps = [float(value) for value in row.get("token_timestamps_sec", [])]
        consumed = float(row.get("audio_consumed_through_sec") or 0.0)
        result = []
        timestamp_compatible = len(raw_words) == len(timestamps) and bool(raw_words)
        for index, word in enumerate(raw_words):
            start = timestamps[index] if timestamp_compatible else None
            end = (
                timestamps[index + 1]
                if timestamp_compatible and index + 1 < len(timestamps)
                else (consumed if timestamp_compatible else None)
            )
            result.append(
                {
                    "word_id": f"{line_id}:word:{index:06d}",
                    "word": word,
                    "start_sec": start,
                    "end_sec": end,
                    "raw_score": None,
                    "score_type": None,
                }
            )
        return result

    @staticmethod
    def _asr_accepted_audio_interval(
        row: Mapping[str, object],
    ) -> dict[str, object] | None:
        raw = row.get("accepted_audio_interval")
        if not isinstance(raw, Mapping):
            return None
        if raw.get("timing_provenance") != ACCEPTED_AUDIO_INTERVAL_PROVENANCE:
            raise ValueError("ASR accepted-audio interval provenance is unsupported")
        if raw.get("word_timestamps_inferred") is not False:
            raise ValueError("ASR accepted-audio interval must not imply word timing")
        start_sec = float(raw["audio_start_sec"])
        end_sec = float(raw["audio_end_sec"])
        sample_start = int(raw["sample_start_index"])
        sample_end = int(raw["sample_end_index"])
        if (
            not np.isfinite(start_sec)
            or not np.isfinite(end_sec)
            or start_sec < 0
            or end_sec <= start_sec
            or sample_start < 0
            or sample_end <= sample_start
        ):
            raise ValueError("ASR accepted-audio interval is invalid")
        return {
            "sample_start_index": sample_start,
            "sample_end_index": sample_end,
            "audio_start_sec": start_sec,
            "audio_end_sec": end_sec,
            "timing_provenance": ACCEPTED_AUDIO_INTERVAL_PROVENANCE,
        }

    def _update_transcript(
        self,
        event: Mapping[str, object],
        adapter_row: Mapping[str, object],
        words: Sequence[Mapping[str, object]],
    ) -> None:
        line_id = str(event["line_id"])
        state = "final" if event["contract_type"] == "AsrFinalEvent" else "provisional"
        spans: list[TranscriptSpan] = []
        if words and all(
            row["start_sec"] is not None and row["end_sec"] is not None for row in words
        ):
            for index, word in enumerate(words):
                spans.append(
                    TranscriptSpan(
                        span_id=stable_span_id(
                            transcript_id=self.transcript_aligner.transcript_id,
                            source_event_ids=[str(event["event_id"]), line_id],
                            start_sec=float(word["start_sec"]),
                            end_sec=float(word["end_sec"]),
                            source_ordinal=index,
                        ),
                        text=str(word["word"]),
                        start_sec=float(word["start_sec"]),
                        end_sec=float(word["end_sec"]),
                        state=state,
                        timing_provenance="word",
                        source_event_ids=(str(event["event_id"]),),
                    )
                )
        elif str(event.get("text") or "").strip():
            accepted_interval = self._asr_accepted_audio_interval(adapter_row)
            start_sec = (
                float(accepted_interval["audio_start_sec"])
                if accepted_interval is not None
                else None
            )
            end_sec = (
                float(accepted_interval["audio_end_sec"])
                if accepted_interval is not None
                else None
            )
            spans.append(
                TranscriptSpan(
                    span_id=stable_span_id(
                        transcript_id=self.transcript_aligner.transcript_id,
                        source_event_ids=[str(event["event_id"]), line_id],
                        start_sec=start_sec,
                        end_sec=end_sec,
                        source_ordinal=0,
                    ),
                    text=str(event["text"]),
                    start_sec=start_sec,
                    end_sec=end_sec,
                    state=state,
                    timing_provenance=(
                        "accepted_audio_interval"
                        if accepted_interval is not None
                        else "missing"
                    ),
                    source_event_ids=(str(event["event_id"]),),
                )
            )
        previous = self._hypothesis_spans.get(line_id, ())
        source_time = max(
            self._source_horizon_sec,
            float(adapter_row.get("audio_consumed_through_sec") or 0.0),
        )
        if previous:
            revision = self.transcript_aligner.replace_spans(
                spans,
                replaced_span_ids=previous,
                caused_by_event_ids=[str(event["event_id"])],
                source_time_sec=source_time,
            )
        else:
            revision = (
                self.transcript_aligner.append_spans(
                    spans,
                    caused_by_event_ids=[str(event["event_id"])],
                    source_time_sec=source_time,
                )
                if spans
                else None
            )
        self._hypothesis_spans[line_id] = tuple(value.span_id for value in spans)
        if revision is not None:
            self._emit_transcript_revision(
                revision, event_reason="asr_hypothesis_revision"
            )
        if spans and self._speaker_regions:
            alignment = self.transcript_aligner.align_regions(
                self._speaker_regions,
                caused_by_event_ids=[str(event["event_id"])],
                source_time_sec=source_time,
            )
            if alignment is not None:
                self._emit_transcript_revision(
                    alignment, event_reason="anonymous_speaker_alignment"
                )

    def _handle_speech_region(
        self,
        region: SpeechRegionUpdate | Mapping[str, object],
        frame: NormalizedAudioFrame | None,
    ) -> None:
        value = (
            asdict(region) if isinstance(region, SpeechRegionUpdate) else dict(region)
        )
        internal_state = str(
            value.get("state") or value.get("activity_state") or "speech_update"
        )
        public_state = {
            "speech_start": "speech_started",
            "speech_update": "speech_active",
            "speech_end": "speech_ended",
        }.get(internal_state, internal_state)
        event = self.factory.create(
            contract_type="SpeechActivityEvent",
            event_type="speech_activity",
            component_identity=self.identities["segmentation"],
            capture_timestamps=(
                frame.capture_contract()
                if frame is not None
                else {
                    "audio_start_sec": value.get("start_sec"),
                    "audio_end_sec": value.get("end_sec"),
                }
            ),
            event_reason=str(value.get("reason") or "causal_segmentation_commit"),
            detail=(
                f"algorithmic_lookahead_sec={value.get('algorithmic_lookahead_sec')};"
                f"compute_latency_ms={value.get('compute_latency_ms')}"
            ),
            backend_latency_ms=float(value.get("compute_latency_ms") or 0.0),
            payload={
                "speech_region_id": str(value["region_id"]),
                "activity_state": public_state,
                "start_sec": float(value["start_sec"]),
                "end_sec": float(value["end_sec"]),
                "channel_index": 0,
                "raw_score": value.get("raw_score"),
                "score_type": value.get("score_type"),
            },
        )
        self._publish(event)
        region_id = str(value["region_id"])
        start_sec = float(value["start_sec"])
        end_sec = float(value["end_sec"])
        final = internal_state == "speech_end"
        previous_state = self.window_planner.cache_state(region_id)
        window_key = make_cache_key(
            artifact_kind="diarization_windows",
            role="anonymous_diarization_windows",
            source_audio_sha256=canonical_sha256(
                {
                    "region_id": region_id,
                    "start_sec": start_sec,
                    "end_sec": end_sec,
                    "final": final,
                }
            ),
            source_start_sample=round(start_sec * 16000),
            source_end_sample=max(round(start_sec * 16000) + 1, round(end_sec * 16000)),
            sample_rate_hz=16000,
            window_identity={
                "duration_sec": self.window_planner.duration_sec,
                "step_sec": self.window_planner.step_sec,
                "minimum_sec": self.window_planner.minimum_sec,
                "previous_state_sha256": canonical_sha256(previous_state),
            },
            preprocessing_identity={
                "upstream": "causal_speech_region",
                "algorithmic_lookahead_sec": value.get("algorithmic_lookahead_sec"),
            },
            model_identity=self.identities["segmentation"].to_contract(),
            configuration_identity={
                "runtime_config_sha256": self.selection.runtime_config_sha256,
                "policy_id": "diarization_midpoint_windows_1p5s_step_0p75s.v1",
            },
        )
        cached_plan = self.cache.load(window_key) if self.cache is not None else None
        if cached_plan is None:
            plan = self.window_planner.advance(
                region_id=region_id,
                start_sec=start_sec,
                end_sec=end_sec,
                final=final,
            )
            if self.cache is not None:
                self.cache.publish(
                    window_key,
                    {
                        "new_windows": [asdict(row) for row in plan.new_windows],
                        "revised_windows": [
                            asdict(row) for row in plan.revised_windows
                        ],
                        "next_state": self.window_planner.cache_state(region_id),
                    },
                )
        else:
            plan = self.window_planner.restore_cached(region_id, dict(cached_plan))
        for window in (*plan.new_windows, *plan.revised_windows):
            self._process_window(window, str(event["event_id"]))
        if (
            internal_state == "speech_end"
            and float(value["end_sec"]) - float(value["start_sec"])
            < (
                self.runtime_tuning.short_turn_inheritance_max_sec
                if self.runtime_tuning is not None
                else 0.75
            )
        ):
            self._process_short_turn(value, str(event["event_id"]))
        if (
            internal_state == "speech_end"
            and self.mode_behavior is not None
            and not self.mode_behavior.anonymous_profiles_across_turns
        ):
            self._clear_volatile_session_state(
                preserve_transcript=True,
                increment_epoch=True,
            )

    def _process_window(self, window: Any, speech_event_id: str) -> None:
        window_id = str(window.window_id)
        samples = self.history.slice(float(window.start_sec), float(window.end_sec))
        if samples is None:
            self._warnings.append(f"audio history unavailable for {window_id}")
            return
        predicted_overlap = bool(
            hasattr(self.segmenter, "predicted_overlap")
            and self.segmenter.predicted_overlap(
                float(window.start_sec), float(window.end_sec)
            )
        )
        diar_window = EmbeddingWindow(
            window_id=window_id,
            start_sec=float(window.start_sec),
            end_sec=float(window.end_sec),
            assignment_start_sec=float(window.assignment_start_sec),
            assignment_end_sec=float(window.assignment_end_sec),
            samples=samples,
            role="anonymous_diarization",
            predicted_overlap=predicted_overlap,
        )
        diar_embedding: EmbeddingResult = (
            self.embedding_reuse_router.embed_diarization(diar_window)
            if self.embedding_reuse_router is not None
            else self.diarization_embedder.embed(diar_window)
        )
        cluster_update = self._cluster_observe(diar_window, diar_embedding)
        assignment = getattr(cluster_update, "assignment", cluster_update)
        cluster_id = self._session_cluster_id(str(getattr(assignment, "cluster_id")))
        start = float(getattr(assignment, "start_sec", window.assignment_start_sec))
        end = float(getattr(assignment, "end_sec", window.assignment_end_sec))
        if (
            self.runtime_tuning is not None
            and self.runtime_tuning.boundary_correction_ms > 0
            and self._last_cluster_id is not None
            and self._last_cluster_id != cluster_id
        ):
            start = self._apply_boundary_correction(
                previous_cluster_id=self._last_cluster_id,
                next_cluster_id=cluster_id,
                original_boundary_sec=start,
                correction_ms=self.runtime_tuning.boundary_correction_ms,
                source_window_id=window_id,
            )
        unknown = self._ensure_cluster(cluster_id, start)
        anonymous_event = self._emit_anonymous(
            cluster_id,
            unknown,
            start,
            end,
            window,
            assignment,
            speech_event_id,
        )
        self._apply_cluster_reconciliation(
            cluster_update,
            current_window_id=window_id,
            causation=anonymous_event,
            source_time_sec=max(self._source_horizon_sec, end),
        )
        identity_snapshot = self.identity_manager.snapshot(cluster_id)
        snapshot_label = identity_snapshot.speaker_label
        snapshot_known_id = identity_snapshot.known_speaker_id
        if (
            self.mode_behavior is not None
            and not self.mode_behavior.confirmed_name_inheritance
        ):
            snapshot_label = identity_snapshot.unknown_label
            snapshot_known_id = None
        public_snapshot_label = self._public_speaker_label(
            snapshot_label,
            snapshot_known_id,
        )
        if (
            self.session_memory is not None
            and self.mode_behavior is not None
            and self.mode_behavior.active_roster
        ):
            self.session_memory.observe_cluster(
                anonymous_speaker_id=cluster_id,
                public_label=public_snapshot_label,
                source_time_sec=end,
            )
        speaker_region = SpeakerRegion(
            start_sec=start,
            end_sec=end,
            anonymous_speaker_id=cluster_id,
            speaker_label=public_snapshot_label,
            source_event_id=str(anonymous_event["event_id"]),
        )
        previous_cluster_id = self._replace_window_region(
            window_id, cluster_id, speaker_region
        )
        if previous_cluster_id is not None and previous_cluster_id != cluster_id:
            prior_vectors = self._identity_vectors.get(previous_cluster_id)
            if prior_vectors is not None:
                prior_vectors.pop(window_id, None)
                if not prior_vectors:
                    self._identity_vectors.pop(previous_cluster_id, None)
        alignment = self.transcript_aligner.align_regions(
            self._speaker_regions,
            caused_by_event_ids=[str(anonymous_event["event_id"])],
            source_time_sec=max(self._source_horizon_sec, end),
        )
        if alignment is not None:
            self._emit_transcript_revision(
                alignment, event_reason="anonymous_speaker_alignment"
            )

        identity_window = EmbeddingWindow(
            window_id=window_id,
            start_sec=float(window.start_sec),
            end_sec=float(window.end_sec),
            assignment_start_sec=float(window.assignment_start_sec),
            assignment_end_sec=float(window.assignment_end_sec),
            samples=samples,
            role="identity_matching",
            predicted_overlap=predicted_overlap,
        )
        identity_embedding: EmbeddingResult = (
            self.embedding_reuse_router.embed_identity(identity_window)
            if self.embedding_reuse_router is not None
            else self.identity_embedder.embed(identity_window)
        )
        exclude_overlap = (
            self.runtime_tuning is None
            or self.runtime_tuning.overlap_policy
            == "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY"
        )
        if predicted_overlap and exclude_overlap:
            vectors = self._identity_vectors.get(cluster_id)
            if vectors is not None:
                vectors.pop(window_id, None)
                if not vectors:
                    self._identity_vectors.pop(cluster_id, None)
            self._record_overlap_identity_diagnostic(
                cluster_id=cluster_id,
                embedding=identity_embedding,
                source_time_sec=max(self._source_horizon_sec, end),
                window_id=window_id,
            )
            return
        self._process_identity(
            cluster_id,
            identity_embedding,
            max(self._source_horizon_sec, end),
            anonymous_event,
            window_id,
            predicted_overlap=predicted_overlap,
        )

    def _replace_window_region(
        self,
        window_id: str,
        cluster_id: str,
        region: SpeakerRegion,
    ) -> str | None:
        """Replace one revised window instead of double-counting its old interval."""

        previous = self._window_cluster_intervals.get(window_id)
        previous_cluster_id = previous[0] if previous is not None else None
        if previous is not None:
            old_cluster_id, old_start, old_end = previous
            old_intervals = self._cluster_intervals.get(old_cluster_id, [])
            try:
                old_intervals.remove((old_start, old_end))
            except ValueError:
                pass
            if not old_intervals:
                self._cluster_intervals.pop(old_cluster_id, None)
        self._speaker_regions_by_window[window_id] = region
        self._speaker_regions = sorted(
            self._speaker_regions_by_window.values(),
            key=lambda row: (
                row.start_sec,
                row.end_sec,
                row.anonymous_speaker_id,
                row.source_event_id,
            ),
        )
        self._window_cluster_intervals[window_id] = (
            cluster_id,
            region.start_sec,
            region.end_sec,
        )
        self._cluster_intervals.setdefault(cluster_id, []).append(
            (region.start_sec, region.end_sec)
        )
        return previous_cluster_id

    def _apply_boundary_correction(
        self,
        *,
        previous_cluster_id: str,
        next_cluster_id: str,
        original_boundary_sec: float,
        correction_ms: int,
        source_window_id: str,
    ) -> float:
        """Move a stabilized boundary backward inside the bounded correction buffer."""

        corrected = max(0.0, original_boundary_sec - correction_ms / 1000.0)
        changed: list[dict[str, object]] = []
        for window_id, region in tuple(self._speaker_regions_by_window.items()):
            if region.anonymous_speaker_id != previous_cluster_id:
                continue
            if region.end_sec <= corrected or region.start_sec >= original_boundary_sec:
                continue
            before = {
                "window_id": window_id,
                "start_sec": region.start_sec,
                "end_sec": region.end_sec,
                "anonymous_speaker_id": region.anonymous_speaker_id,
                "speaker_label": region.speaker_label,
            }
            if region.start_sec >= corrected - 1e-9:
                self._speaker_regions_by_window.pop(window_id, None)
                self._window_cluster_intervals.pop(window_id, None)
                after = None
            else:
                updated = replace(region, end_sec=corrected)
                self._speaker_regions_by_window[window_id] = updated
                self._window_cluster_intervals[window_id] = (
                    previous_cluster_id,
                    updated.start_sec,
                    updated.end_sec,
                )
                after = {
                    "window_id": window_id,
                    "start_sec": updated.start_sec,
                    "end_sec": updated.end_sec,
                    "anonymous_speaker_id": updated.anonymous_speaker_id,
                    "speaker_label": updated.speaker_label,
                }
            changed.append({"original_assignment": before, "corrected_assignment": after})
        self._speaker_regions = sorted(
            self._speaker_regions_by_window.values(),
            key=lambda row: (
                row.start_sec,
                row.end_sec,
                row.anonymous_speaker_id,
                row.source_event_id,
            ),
        )
        self._cluster_intervals = {}
        for region in self._speaker_regions:
            self._cluster_intervals.setdefault(region.anonymous_speaker_id, []).append(
                (region.start_sec, region.end_sec)
            )
        self._boundary_corrections.append(
            {
                "schema_version": "h2-boundary-correction.v1",
                "source_window_id": source_window_id,
                "previous_anonymous_speaker_id": previous_cluster_id,
                "next_anonymous_speaker_id": next_cluster_id,
                "original_boundary_sec": original_boundary_sec,
                "corrected_boundary_sec": corrected,
                "correction_ms": correction_ms,
                "changed_assignments": changed,
                "bounded_by_runtime_policy": True,
            }
        )
        return corrected

    def _process_short_turn(
        self, value: Mapping[str, object], speech_event_id: str
    ) -> None:
        cluster_update = self.cluster_manager.observe(
            window_id=f"{value['region_id']}_short",
            start_sec=float(value["start_sec"]),
            end_sec=float(value["end_sec"]),
            embedding=None,
        )
        assignment = cluster_update.assignment
        cluster_id = self._session_cluster_id(str(assignment.cluster_id))
        unknown = self._ensure_cluster(cluster_id, float(assignment.start_sec))
        anonymous_event = self._emit_anonymous(
            cluster_id,
            unknown,
            float(assignment.start_sec),
            float(assignment.end_sec),
            None,
            assignment,
            speech_event_id,
        )
        snapshot = self.identity_manager.snapshot(cluster_id)
        transition = None
        decision_time = max(self._source_horizon_sec, float(assignment.end_sec))
        if (
            self.mode_behavior is not None
            and self.mode_behavior.short_turn_inheritance
        ):
            transition = self.identity_manager.inherit_confirmed_short_turn(
                cluster_id,
                source_time_sec=decision_time,
                maximum_gap_sec=(
                    self.runtime_tuning.short_turn_inheritance_max_sec
                    if self.runtime_tuning is not None
                    else 0.75
                ),
            )
        if transition is not None:
            label = transition.speaker_label
            known_id = transition.known_speaker_id
        else:
            label = snapshot.unknown_label
            known_id = None
        public_label = self._public_speaker_label(label, known_id)
        short_window_id = str(assignment.window_id)
        region = SpeakerRegion(
            start_sec=float(assignment.start_sec),
            end_sec=float(assignment.end_sec),
            anonymous_speaker_id=cluster_id,
            speaker_label=public_label,
            source_event_id=str(anonymous_event["event_id"]),
        )
        self._replace_window_region(short_window_id, cluster_id, region)
        alignment = self.transcript_aligner.align_regions(
            self._speaker_regions,
            caused_by_event_ids=[str(anonymous_event["event_id"])],
            source_time_sec=decision_time,
        )
        if alignment is not None:
            self._emit_transcript_revision(
                alignment, event_reason="short_turn_speaker_alignment"
            )
        if (
            self.session_memory is not None
            and self.mode_behavior is not None
            and self.mode_behavior.active_roster
        ):
            self.session_memory.observe_cluster(
                anonymous_speaker_id=cluster_id,
                public_label=public_label,
                source_time_sec=decision_time,
            )
        if transition is not None:
            evidence_event = self._identity_evidence_event_for_transition(transition)
            if evidence_event is not None:
                label_event = self._emit_identity_label(
                    transition,
                    evidence_event,
                    self._threshold_contract(max(1, len(self._profiles))),
                )
                self._relabel_transcript(
                    cluster_id,
                    transition.speaker_label,
                    label_event,
                    decision_time,
                    known_speaker_id=transition.known_speaker_id,
                )
                if self.session_memory is not None:
                    self.session_memory.observe_identity(transition)

    def _cluster_observe(
        self, window: EmbeddingWindow, embedding: EmbeddingResult
    ) -> Any:
        if hasattr(self.cluster_manager, "observe"):
            return self.cluster_manager.observe(
                window_id=window.window_id,
                start_sec=window.assignment_start_sec,
                end_sec=window.assignment_end_sec,
                embedding=embedding.vector,
                evidence_duration_sec=window.end_sec - window.start_sec,
            )
        return self.cluster_manager.update(embedding, window)

    def _apply_cluster_reconciliation(
        self,
        cluster_update: Any,
        *,
        current_window_id: str,
        causation: Mapping[str, object],
        source_time_sec: float,
    ) -> None:
        """Apply an M5 whole-cluster merge to identity and transcript state."""

        reconciliation = getattr(cluster_update, "reconciliation", None)
        if reconciliation is None:
            return
        source_cluster_id = self._session_cluster_id(
            str(reconciliation.source_cluster_id)
        )
        survivor_cluster_id = self._session_cluster_id(
            str(reconciliation.survivor_cluster_id)
        )
        if source_cluster_id == survivor_cluster_id:
            raise RuntimeError("cluster reconciliation source equals survivor")
        if not self.identity_manager.allocator.contains(survivor_cluster_id):
            raise RuntimeError("reconciliation survivor lacks causal identity state")
        if self.identity_manager.allocator.contains(source_cluster_id):
            merged = self.identity_manager.merge_clusters(
                [survivor_cluster_id, source_cluster_id]
            )
            if merged.anonymous_speaker_id != survivor_cluster_id:
                raise RuntimeError(
                    "identity allocator selected a different reconciliation survivor"
                )
        else:
            merged = self.identity_manager.snapshot(survivor_cluster_id)

        source_vectors = self._identity_vectors.pop(source_cluster_id, {})
        survivor_vectors = self._identity_vectors.setdefault(
            survivor_cluster_id, {}
        )
        survivor_vectors.update(source_vectors)
        source_times = self._identity_observation_times.pop(source_cluster_id, {})
        survivor_times = self._identity_observation_times.setdefault(
            survivor_cluster_id, {}
        )
        survivor_times.update(source_times)
        if self.session_memory is not None:
            self.session_memory.merge_clusters(
                survivor_cluster_id=survivor_cluster_id,
                source_cluster_id=source_cluster_id,
                source_time_sec=source_time_sec,
            )

        public_label = self._public_speaker_label(
            merged.speaker_label, merged.known_speaker_id
        )
        revised_window_ids: list[str] = []
        for revision in reconciliation.revisions:
            window_id = str(revision.window_id)
            if window_id == current_window_id:
                continue
            region = self._speaker_regions_by_window.get(window_id)
            if region is None:
                continue
            updated = replace(
                region,
                anonymous_speaker_id=survivor_cluster_id,
                speaker_label=public_label,
            )
            self._replace_window_region(window_id, survivor_cluster_id, updated)
            self._emit_reconciliation_anonymous_revision(
                window_id=window_id,
                region=updated,
                unknown_label=merged.unknown_label,
                causation=causation,
                source_cluster_id=source_cluster_id,
                survivor_cluster_id=survivor_cluster_id,
            )
            revised_window_ids.append(window_id)
        if self._last_cluster_id == source_cluster_id:
            self._last_cluster_id = survivor_cluster_id
        diagnostic = {
            "schema_version": "h2-cluster-reconciliation-runtime.v1",
            **reconciliation.to_jsonable(),
            "source_cluster_id": source_cluster_id,
            "survivor_cluster_id": survivor_cluster_id,
            "source_time_sec": source_time_sec,
            "revised_window_ids": revised_window_ids,
            "identity_conflict_safe_reset": merged.known_speaker_id is None,
            "open_set_threshold_bypassed": False,
            "active_roster_narrowed_gallery": False,
            "causation_event_id": str(causation["event_id"]),
        }
        self._cluster_reconciliations.append(diagnostic)

    def _emit_reconciliation_anonymous_revision(
        self,
        *,
        window_id: str,
        region: SpeakerRegion,
        unknown_label: str,
        causation: Mapping[str, object],
        source_cluster_id: str,
        survivor_cluster_id: str,
    ) -> None:
        prior_event = self._anonymous_event_by_window.get(window_id)
        if prior_event is None:
            return
        prior_revision = prior_event.get("revision")
        prior_number = (
            int(prior_revision.get("revision_number") or 0)
            if isinstance(prior_revision, Mapping)
            else 0
        )
        prior_revision_id = (
            str(prior_revision.get("revision_id"))
            if isinstance(prior_revision, Mapping)
            and prior_revision.get("revision_id") is not None
            else None
        )
        try:
            ordinal = int(unknown_label.rsplit("_", 1)[-1])
        except ValueError:
            ordinal = 1
        event = self.factory.create(
            contract_type="AnonymousSpeakerEvent",
            event_type="anonymous_speaker",
            component_identity=self.identities["clustering"],
            capture_timestamps={
                "audio_start_sec": region.start_sec,
                "audio_end_sec": region.end_sec,
            },
            event_reason="causal_fragment_reconciliation_voice_timing",
            causation_event_id=str(causation["event_id"]),
            causal_event_ids=[
                str(causation["event_id"]),
                str(prior_event["event_id"]),
            ],
            detail=f"{source_cluster_id}->{survivor_cluster_id}",
            payload={
                "anonymous_speaker_id": survivor_cluster_id,
                "unknown_label": unknown_label,
                "unknown_ordinal": ordinal,
                "cluster_state": "confirmed",
                "start_sec": region.start_sec,
                "end_sec": region.end_sec,
                "overlap": False,
                "source_turn_ids": [window_id],
                "revision": {
                    "revision_id": f"{window_id}:reconciliation:{prior_number + 1}",
                    "revision_number": prior_number + 1,
                    "supersedes_revision_id": prior_revision_id,
                    "corrected_event_ids": [str(prior_event["event_id"])],
                    "reason": {
                        "code": "causal_fragment_reconciliation_voice_timing",
                        "detail": f"{source_cluster_id}->{survivor_cluster_id}",
                        "causal_event_ids": [
                            str(causation["event_id"]),
                            str(prior_event["event_id"]),
                        ],
                    },
                },
            },
        )
        self._publish(event, "anonymous")
        self._anonymous_event_by_window[window_id] = event

    def _ensure_cluster(self, cluster_id: str, start_sec: float) -> str:
        snapshot = self.identity_manager.ensure_cluster(
            ClusterCreation(
                start_sample_index=round(start_sec * 16000),
                creation_event_sequence=self.factory.next_sequence,
                anonymous_speaker_id=cluster_id,
            )
        )
        if cluster_id not in self._created_clusters:
            self._created_clusters.add(cluster_id)
            self._counts["anonymous_speakers"] = len(self._created_clusters)
        return snapshot.unknown_label

    def _emit_anonymous(
        self,
        cluster_id: str,
        unknown_label: str,
        start: float,
        end: float,
        window: Any | None,
        assignment: Any,
        speech_event_id: str,
    ) -> Mapping[str, object]:
        ordinal = int(unknown_label.split("_")[-1])
        window_id = str(getattr(window, "window_id", f"short:{speech_event_id}"))
        revision_number = int(getattr(window, "revision", 0))
        prior_event = self._anonymous_event_by_window.get(window_id)
        prior_revision = (
            prior_event.get("revision") if prior_event is not None else None
        )
        prior_revision_id = (
            str(prior_revision.get("revision_id"))
            if isinstance(prior_revision, Mapping)
            and prior_revision.get("revision_id") is not None
            else None
        )
        causal_event_ids = [speech_event_id]
        if prior_event is not None:
            causal_event_ids.append(str(prior_event["event_id"]))
        event = self.factory.create(
            contract_type="AnonymousSpeakerEvent",
            event_type="anonymous_speaker",
            component_identity=self.identities["clustering"],
            capture_timestamps={"audio_start_sec": start, "audio_end_sec": end},
            event_reason=(
                "online_causal_cluster_revision"
                if prior_event is not None
                else "online_causal_cluster_assignment"
            ),
            causation_event_id=speech_event_id,
            causal_event_ids=causal_event_ids,
            payload={
                "anonymous_speaker_id": cluster_id,
                "unknown_label": unknown_label,
                "unknown_ordinal": ordinal,
                "cluster_state": "tentative"
                if bool(getattr(assignment, "provisional", False))
                else "confirmed",
                "start_sec": start,
                "end_sec": end,
                "overlap": bool(getattr(window, "predicted_overlap", False)),
                "source_turn_ids": [window_id],
                "revision": {
                    "revision_id": f"{window_id}:revision:{revision_number}",
                    "revision_number": revision_number,
                    "supersedes_revision_id": prior_revision_id,
                    "corrected_event_ids": (
                        [str(prior_event["event_id"])]
                        if prior_event is not None
                        else []
                    ),
                    "reason": {
                        "code": "online_cluster_update",
                        "detail": "reentry"
                        if bool(getattr(assignment, "reentry", False))
                        else None,
                        "causal_event_ids": causal_event_ids,
                    },
                },
            },
        )
        self._publish(event, "anonymous")
        self._anonymous_event_by_window[window_id] = event
        if self._last_cluster_id is not None and self._last_cluster_id != cluster_id:
            self._emit_boundary(
                self._last_cluster_id,
                cluster_id,
                start,
                event,
                overlap_active=bool(getattr(window, "predicted_overlap", False)),
            )
        self._last_cluster_id = cluster_id
        return event

    def _emit_boundary(
        self,
        previous: str,
        next_cluster: str,
        at_sec: float,
        causation: Mapping[str, object],
        *,
        overlap_active: bool = False,
    ) -> None:
        event = self.factory.create(
            contract_type="SpeakerBoundaryEvent",
            event_type="speaker_boundary",
            component_identity=self.identities["clustering"],
            capture_timestamps={"audio_start_sec": at_sec, "audio_end_sec": at_sec},
            event_reason="online_cluster_change",
            causation_event_id=str(causation["event_id"]),
            causal_event_ids=[str(causation["event_id"])],
            payload={
                "boundary_id": f"boundary_{self.factory.next_sequence:09d}",
                "boundary_type": "speaker_change",
                "boundary_sec": at_sec,
                "previous_anonymous_speaker_id": previous,
                "next_anonymous_speaker_id": next_cluster,
                "overlap_active": overlap_active,
                "raw_score": None,
                "score_type": None,
            },
        )
        self._publish(event)

    def _process_identity(
        self,
        cluster_id: str,
        embedding: EmbeddingResult,
        source_time_sec: float,
        anonymous_event: Mapping[str, object],
        window_id: str,
        *,
        predicted_overlap: bool,
    ) -> None:
        if not self._profiles:
            return
        changed, observation_rows = self._upsert_identity_observation(
            cluster_id,
            window_id,
            embedding.vector,
            embedding.duration_sec,
            source_time_sec=source_time_sec,
        )
        if not changed:
            return
        weights = np.asarray([duration for _, duration in observation_rows])
        query = np.average(
            np.stack([vector for vector, _ in observation_rows]),
            axis=0,
            weights=weights,
        )
        query = query / np.linalg.norm(query)
        duration = float(np.sum(weights))
        consistency = self._embedding_consistency(observation_rows, aggregate=query)
        profiles_by_speaker = {row.speaker_id: row for row in self._profiles}
        if len(profiles_by_speaker) != len(self._profiles):
            raise ValueError("enrollment gallery contains duplicate speaker IDs")
        full_gallery_ids = tuple(sorted(profiles_by_speaker))
        active_roster_ids: tuple[str, ...] = ()
        search_order_ids = full_gallery_ids
        if (
            self.session_memory is not None
            and self.runtime_tuning is not None
            and self.runtime_tuning.memory_level
            in {"M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"}
        ):
            active_roster_ids = self.session_memory.active_known_speaker_ids(
                list(full_gallery_ids), source_time_sec=source_time_sec
            )
            search_order_ids = self.session_memory.full_gallery_search_order(
                list(full_gallery_ids), source_time_sec=source_time_sec
            )
        if set(search_order_ids) != set(full_gallery_ids) or len(
            search_order_ids
        ) != len(full_gallery_ids):
            raise RuntimeError("identity search schedule did not retain the full gallery")
        scoring_profiles = tuple(
            profiles_by_speaker[speaker_id] for speaker_id in search_order_ids
        )
        gallery_execution = {
            "policy_id": "h2_active_roster_full_gallery_search_order.v1",
            "active_roster_prior_applied": bool(active_roster_ids),
            "active_roster_speaker_ids": list(active_roster_ids),
            "search_order_speaker_ids": list(search_order_ids),
            "full_gallery_speaker_ids": list(full_gallery_ids),
            "full_gallery_completed_before_decision": True,
            "active_roster_narrowed_gallery": False,
            "score_or_threshold_boost_applied": False,
        }
        profile_hash = hashlib.sha256(
            "".join(sorted(row.profile_sha256 for row in self._profiles)).encode(
                "ascii"
            )
        ).hexdigest()
        score_key = None
        cached_scores = None
        if self.cache is not None and embedding.cache_key is not None:
            score_key = make_runtime_cache_key(
                cache_kind="score_matrices",
                source_mode="aggregate",
                source_identity=score_matrix_source_identity(
                    probe_set_sha256=hashlib.sha256(
                        np.ascontiguousarray(query).tobytes()
                    ).hexdigest(),
                    reference_set_sha256=profile_hash,
                ),
                window_identity=result_affecting_identity(
                    "full_pipeline_identity_evidence_windows.v1",
                    {
                        "window_ids": sorted(
                            self._identity_vectors.get(cluster_id, {})
                        ),
                        "evidence_duration_sec": duration,
                    },
                ),
                preprocessing_identity=result_affecting_identity(
                    "full_pipeline_l2_query.v1",
                    {"query_normalization": "l2", "score_type": "cosine_similarity"},
                ),
                producer_identity=result_affecting_identity(
                    "full_pipeline_score_profile.v1",
                    {
                        "backend_id": embedding.backend_id,
                        "model_id": embedding.model_id,
                        "model_sha256": embedding.model_sha256,
                    },
                ),
                configuration_identity=result_affecting_identity(
                    "full_pipeline_gallery_score_config.v1",
                    {
                        "policy_id": self.identity_manager.policy.policy_id,
                        "profiles": [
                            {
                                "profile_id": profile.profile_id,
                                "profile_sha256": profile.profile_sha256,
                                "aggregation_method": profile.aggregation_method,
                                "aggregation_top_k": profile.aggregation_top_k,
                            }
                            for profile in sorted(
                                self._profiles, key=lambda value: value.profile_id
                            )
                        ],
                    },
                ),
                upstream_dependencies=(
                    CacheDependency("identity_embeddings", embedding.cache_key),
                ),
            )
            cached_scores = self.cache.load(score_key)
        if cached_scores is None:
            scores = {
                profile.speaker_id: score_profile(query, profile)
                for profile in scoring_profiles
            }
            if self.cache is not None and score_key is not None:
                self.cache.publish(
                    score_key,
                    {
                        "score_type": "cosine_similarity",
                        "scores": dict(sorted(scores.items())),
                    },
                )
        else:
            cached_score_payload = dict(cached_scores)
            if cached_score_payload.get("score_type") != "cosine_similarity":
                raise ValueError("score-matrix cache has an incompatible score type")
            scores = {
                str(name): float(value)
                for name, value in dict(cached_score_payload["scores"]).items()
            }
        if set(scores) != set(full_gallery_ids) or len(scores) != len(
            full_gallery_ids
        ):
            raise ValueError("identity score matrix did not cover the full gallery")
        if self.emit_identity_score_diagnostics:
            self._calibrated_identity_score_diagnostics.append(
                {
                    "schema_version": (
                        "full-pipeline-development-identity-score-diagnostic.v1"
                    ),
                    "anonymous_speaker_id": cluster_id,
                    "source_time_sec": source_time_sec,
                    "evidence_duration_sec": duration,
                    "embedding_consistency": consistency,
                    "candidate_raw_cosine_scores": dict(sorted(scores.items())),
                    "gallery_execution": gallery_execution,
                    "predicted_overlap": bool(predicted_overlap),
                    "decision_policy_calibrated": bool(
                        self.identity_manager.policy.calibrated
                    ),
                    "diagnostic_only": True,
                    "raw_embedding_vectors_present": False,
                }
            )
        if not self.identity_manager.policy.calibrated:
            self._identity_diagnostics.append(
                {
                    "schema_version": "full-pipeline-unresolved-identity-score.v1",
                    "anonymous_speaker_id": cluster_id,
                    "source_time_sec": source_time_sec,
                    "evidence_duration_sec": duration,
                    "embedding_consistency": consistency,
                    "candidate_raw_cosine_scores": dict(sorted(scores.items())),
                    "gallery_execution": gallery_execution,
                    "decision": "UNKNOWN_ONLY",
                    "reason": "challenger_calibration_unresolved",
                    "threshold": None,
                    "margin_threshold": None,
                }
            )
            return
        evidence = IdentityEvidence(
            anonymous_speaker_id=cluster_id,
            source_time_sec=source_time_sec,
            evidence_duration_sec=duration,
            candidate_scores=scores,
            embedding_consistency=consistency,
            evidence_event_id=f"pending:{self.factory.next_sequence}",
            usable=not bool(embedding.quality.get("rejected", False)),
        )
        transition = self.identity_manager.observe(evidence)
        threshold = self._threshold_contract_for_transition(
            len(self._profiles), transition
        )
        ranked_profiles = sorted(self._profiles, key=lambda row: row.speaker_id)
        profile_by_id = {row.speaker_id: row for row in ranked_profiles}
        candidates = [
            {
                "candidate_speaker_id": speaker_id,
                "candidate_display_label": profile_by_id[speaker_id].display_label,
                "reference_id": profile_by_id[speaker_id].profile_id,
                "raw_score": score,
                "score_type": "cosine_similarity",
            }
            for speaker_id, score in sorted(
                scores.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        evidence_event = self.factory.create(
            contract_type="IdentityEvidenceEvent",
            event_type="identity_evidence",
            component_identity=self.identities["speaker_matching"],
            capture_timestamps={"audio_end_sec": source_time_sec},
            event_reason=transition.decision_reason,
            causation_event_id=str(anonymous_event["event_id"]),
            causal_event_ids=[str(anonymous_event["event_id"])],
            backend_latency_ms=embedding.compute_latency_ms,
            payload={
                "anonymous_speaker_id": cluster_id,
                "enrollment_profile_id": "gallery:"
                + "+".join(sorted(row.profile_id for row in self._profiles)),
                "enrollment_profile_sha256": profile_hash,
                "evidence_duration_sec": duration,
                "evidence_window_count": len(observation_rows),
                "usable_segment_count": len(observation_rows),
                "quality_gate": {
                    "status": "accepted"
                    if evidence.usable
                    and consistency
                    >= self.identity_manager.policy.minimum_embedding_consistency
                    else "rejected",
                    "policy_id": QUALITY_POLICY_ID,
                    "policy_sha256": self.selection.runtime_config_sha256,
                    "metrics": {"embedding_consistency": consistency},
                    "reason_codes": []
                    if evidence.usable
                    and consistency
                    >= self.identity_manager.policy.minimum_embedding_consistency
                    else ["embedding_quality_below_gate"],
                },
                "candidate_scores": candidates,
                "top1_candidate_speaker_id": transition.top1_candidate_id,
                "top1_raw_score": transition.top1_score,
                "top2_candidate_speaker_id": transition.top2_candidate_id,
                "top2_raw_score": transition.top2_score,
                "score_type": "cosine_similarity",
                "top1_top2_margin": transition.margin,
                "threshold_identity": threshold,
                "decision": self._identity_decision_contract(
                    transition, evidence, consistency
                ),
                "decision_reason": {
                    "code": transition.decision_reason,
                    "detail": None,
                    "causal_event_ids": [str(anonymous_event["event_id"])],
                },
            },
        )
        self._publish(evidence_event, "identity_evidence")
        self._counts["identity_evidence_events"] += 1
        self.identity_manager.bind_latest_evidence_event(
            cluster_id, str(evidence_event["event_id"])
        )
        label_event = self._emit_identity_label(transition, evidence_event, threshold)
        if (
            self.session_memory is not None
            and self.mode_behavior is not None
            and self.mode_behavior.active_roster
        ):
            self.session_memory.observe_identity(transition)
        visible_label = self._public_speaker_label(
            transition.speaker_label, transition.known_speaker_id
        )
        requires_visible_relabel = any(
            region.anonymous_speaker_id == cluster_id
            and region.speaker_label != visible_label
            for region in self._speaker_regions_by_window.values()
        )
        if transition.changed or requires_visible_relabel:
            self._relabel_transcript(
                cluster_id,
                transition.speaker_label,
                label_event,
                source_time_sec,
                known_speaker_id=transition.known_speaker_id,
            )

    def _record_overlap_identity_diagnostic(
        self,
        *,
        cluster_id: str,
        embedding: EmbeddingResult,
        source_time_sec: float,
        window_id: str,
    ) -> None:
        """Retain overlap-window scores without using them in primary evidence."""

        vector = np.asarray(embedding.vector, dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        if norm <= 0.0 or not np.isfinite(norm):
            scores: dict[str, float] = {}
            status = "invalid_embedding"
        else:
            query = vector / norm
            scores = {
                profile.speaker_id: score_profile(query, profile)
                for profile in self._profiles
            }
            status = "diagnostic_only"
        self._overlap_identity_diagnostics.append(
            {
                "schema_version": "full-pipeline-overlap-identity-score.v1",
                "pipeline_id": self.selection.pipeline_id,
                "hybrid_label": self.selection.hybrid_label,
                "window_id": window_id,
                "anonymous_speaker_id": cluster_id,
                "source_time_sec": source_time_sec,
                "evidence_duration_sec": embedding.duration_sec,
                "predicted_overlap": True,
                "candidate_raw_cosine_scores": dict(sorted(scores.items())),
                "decision_eligible": False,
                "status": status,
                "reason": "frozen_policy_excludes_predicted_overlap_primary",
            }
        )

    def _upsert_identity_observation(
        self,
        cluster_id: str,
        window_id: str,
        vector: np.ndarray,
        duration_sec: float,
        *,
        source_time_sec: float | None = None,
    ) -> tuple[bool, list[tuple[np.ndarray, float]]]:
        observations = self._identity_vectors.setdefault(cluster_id, {})
        observation_times = getattr(self, "_identity_observation_times", None)
        if observation_times is None:
            observation_times = {}
            self._identity_observation_times = observation_times
        times = observation_times.setdefault(cluster_id, {})
        tuning = getattr(self, "runtime_tuning", None)
        previous = observations.get(window_id)
        keys_before = frozenset(observations)
        observations[window_id] = (vector, duration_sec)
        times[window_id] = (
            float(source_time_sec)
            if source_time_sec is not None
            else max(times.values(), default=0.0)
        )
        if (
            tuning is not None
            and tuning.identity_accumulation == "recent_window"
        ):
            for key in tuple(observations):
                if key != window_id:
                    observations.pop(key, None)
                    times.pop(key, None)
        if tuning is not None:
            floor = times[window_id] - tuning.identity_observation_retention_sec
            for key in tuple(observations):
                if times.get(key, times[window_id]) < floor:
                    observations.pop(key, None)
                    times.pop(key, None)
            overflow = (
                len(observations)
                - tuning.maximum_identity_observations_per_cluster
            )
            if overflow > 0:
                oldest = sorted(
                    observations,
                    key=lambda key: (times.get(key, -1.0), key),
                )[:overflow]
                for key in oldest:
                    observations.pop(key, None)
                    times.pop(key, None)
        changed = keys_before != frozenset(observations) or not (
            previous is not None
            and np.array_equal(previous[0], vector)
            and previous[1] == duration_sec
        )
        return changed, list(observations.values())

    def _emit_identity_label(
        self,
        transition: Any,
        evidence_event: Mapping[str, object],
        threshold: Mapping[str, object],
    ) -> Mapping[str, object]:
        public_state = {
            IdentityState.TENTATIVE_KNOWN: "tentative",
            IdentityState.CONFIRMED_KNOWN: "confirmed",
        }.get(transition.state, "unknown")
        prior_state = {
            IdentityState.TENTATIVE_KNOWN: "tentative",
            IdentityState.CONFIRMED_KNOWN: "confirmed",
        }.get(transition.prior_state, "unknown")
        event = self.factory.create(
            contract_type="IdentityLabelEvent",
            event_type="identity_label",
            component_identity=self.identities["speaker_matching"],
            capture_timestamps={"audio_end_sec": transition.source_time_sec},
            event_reason=transition.decision_reason,
            causation_event_id=str(evidence_event["event_id"]),
            causal_event_ids=[str(evidence_event["event_id"])],
            payload={
                "anonymous_speaker_id": transition.anonymous_speaker_id,
                "identity_state": public_state,
                "speaker_label": self._speaker_label_contract(
                    transition.speaker_label, transition.known_speaker_id
                ),
                "visible_to_user": public_state != "tentative"
                or self.identity_manager.policy.tentative_visible,
                "prior_identity_state": prior_state,
                "prior_speaker_label": self._speaker_label_contract(
                    transition.prior_speaker_label,
                    None,
                ),
                "evidence_event_ids": [str(evidence_event["event_id"])],
                "evidence_duration_sec": float(evidence_event["evidence_duration_sec"]),
                "confirmation_count": transition.confirmation_count,
                "required_confirmation_count": transition.required_confirmation_count,
                "threshold_identity": dict(threshold),
                "expiry_policy_id": (
                    (
                        "source_clock_confidence_decay_"
                        f"{self.runtime_tuning.confidence_decay_half_life_sec:g}s_"
                        f"floor_{self.runtime_tuning.confidence_decay_release_floor:g}.v1"
                    )
                    if transition.decision_reason == "identity_confidence_decayed"
                    and self.runtime_tuning is not None
                    and self.runtime_tuning.confidence_decay_half_life_sec is not None
                    else (
                        "source_clock_identity_expiry_"
                        f"{self.identity_manager.policy.identity_expiry_sec:g}s.v1"
                    )
                ),
                "hysteresis_applied": transition.hysteresis_applied,
                "revision": {
                    "revision_id": f"{transition.anonymous_speaker_id}:identity:{transition.revision_number}",
                    "revision_number": transition.revision_number,
                    "supersedes_revision_id": (
                        f"{transition.anonymous_speaker_id}:identity:{transition.revision_number - 1}"
                        if transition.revision_number > 1
                        else None
                    ),
                    "corrected_event_ids": [],
                    "reason": {
                        "code": transition.decision_reason,
                        "detail": None,
                        "causal_event_ids": [str(evidence_event["event_id"])],
                    },
                },
            },
        )
        self._publish(event, "identity_label")
        self._counts["identity_label_events"] += 1
        return event

    def _emit_expiry_transition(
        self, transition: Any, frame: NormalizedAudioFrame
    ) -> None:
        evidence_event = self._identity_evidence_event_for_transition(transition)
        if evidence_event is None:
            self._warnings.append(
                "identity expiry lacked a retained causal evidence event for "
                + str(transition.anonymous_speaker_id)
            )
            return
        label_event = self._emit_identity_label(
            transition,
            evidence_event,
            self._threshold_contract(max(1, len(self._profiles))),
        )
        if self.session_memory is not None:
            self.session_memory.observe_identity(transition)
        # Expiry is normal source-clock behavior, not a degraded pipeline state.
        # Relabelling is bounded to intervals at/after expiry, so past correctly
        # named transcript is never erased merely because the roster timed out.
        self._relabel_transcript(
            transition.anonymous_speaker_id,
            transition.unknown_label,
            label_event,
            transition.source_time_sec,
            effective_start_sec=transition.source_time_sec,
        )

    def _relabel_transcript(
        self,
        cluster_id: str,
        label: str,
        causation: Mapping[str, object],
        source_time_sec: float,
        *,
        known_speaker_id: str | None = None,
        effective_start_sec: float | None = None,
    ) -> None:
        from .alignment import TimeInterval

        public_label = self._public_speaker_label(label, known_speaker_id)
        intervals = []
        for start, end in self._cluster_intervals.get(cluster_id, []):
            if effective_start_sec is not None:
                start = max(start, effective_start_sec)
            if end > start:
                intervals.append(TimeInterval(start, end))
        if not intervals:
            return
        for window_id, region in tuple(self._speaker_regions_by_window.items()):
            if (
                region.anonymous_speaker_id == cluster_id
                and (
                    effective_start_sec is None
                    or region.end_sec > effective_start_sec
                )
            ):
                self._speaker_regions_by_window[window_id] = replace(
                    region, speaker_label=public_label
                )
        self._speaker_regions = sorted(
            self._speaker_regions_by_window.values(),
            key=lambda row: (
                row.start_sec,
                row.end_sec,
                row.anonymous_speaker_id,
                row.source_event_id,
            ),
        )
        revision = self.transcript_aligner.relabel_identity(
            anonymous_speaker_id=cluster_id,
            speaker_label=public_label,
            effective_intervals=intervals,
            caused_by_event_ids=[str(causation["event_id"])],
            source_time_sec=source_time_sec,
        )
        if revision is not None:
            self._emit_transcript_revision(revision, event_reason="identity_revision")

    def _emit_transcript_revision(self, revision: Any, *, event_reason: str) -> None:
        value = revision.to_jsonable()
        spans = []
        for row in value["spans"]:
            known_speaker_id = self._known_speaker_id_for_label(
                row["speaker_label"], row["anonymous_speaker_id"]
            )
            spans.append(
                {
                    "span_id": row["span_id"],
                    "start_sec": row["start_sec"],
                    "end_sec": row["end_sec"],
                    "text": row["text"],
                    "state": row["state"],
                    "anonymous_speaker_id": row["anonymous_speaker_id"],
                    "speaker_label": (
                        self._speaker_label_contract(
                            row["speaker_label"], known_speaker_id
                        )
                        if row["speaker_label"] is not None
                        else None
                    ),
                    "source_event_ids": row["source_event_ids"],
                }
            )
        committed = " ".join(
            row["text"]
            for row in value["spans"]
            if row["state"] in {"committed", "final"}
        )
        provisional = " ".join(
            row["text"] for row in value["spans"] if row["state"] == "provisional"
        )
        event = self.factory.create(
            contract_type="TranscriptRevisionEvent",
            event_type="transcript_revision",
            component_identity=self.identities["transcript"],
            capture_timestamps={"audio_end_sec": value["source_time_sec"]},
            event_reason=(
                "timestamp_resolution_insufficient"
                if value["uncertain_span_ids"]
                else event_reason
            ),
            causal_event_ids=value["caused_by_event_ids"],
            causation_event_id=value["caused_by_event_ids"][0],
            payload={
                "transcript_id": value["transcript_id"],
                "revision": {
                    **value["revision"],
                    "reason": {
                        "code": value["revision"]["reason"],
                        "detail": (
                            "uncertain_span_ids="
                            + ",".join(value["uncertain_span_ids"])
                            if value["uncertain_span_ids"]
                            else None
                        ),
                        "causal_event_ids": value["caused_by_event_ids"],
                    },
                },
                "transcript_state": (
                    "final"
                    if all(row["state"] == "final" for row in value["spans"])
                    else "provisional"
                ),
                "operation": value["operation"],
                "target_span_ids": value["target_span_ids"],
                "before_snapshot_sha256": value["before_snapshot_sha256"],
                "after_snapshot_sha256": value["after_snapshot_sha256"],
                "committed_text": committed,
                "provisional_text": provisional,
                "spans": spans,
                "caused_by_event_ids": value["caused_by_event_ids"],
            },
        )
        self._publish(event, "transcript")
        self._counts["transcript_revisions"] += 1

    def _on_telemetry(self, row: Mapping[str, object]) -> None:
        self._sample_sequence += 1
        availability = {}
        if self.resource_monitor is not None and hasattr(
            self.resource_monitor, "_sampler"
        ):
            availability = dict(self.resource_monitor._sampler.availability())
        event = self.factory.create(
            contract_type="ResourceTelemetryEvent",
            event_type="resource_telemetry",
            component_identity=self.identities["telemetry"],
            event_reason="periodic_resource_sample",
            payload={
                "sample_sequence": self._sample_sequence,
                "host_id": str(row.get("host") or "unknown_host"),
                "root_pid": int(row.get("root_pid") or 0),
                "process_tree_pids": list(row.get("process_tree_pids") or []),
                "active_component": row.get("active_component"),
                "elapsed_sec": float(row.get("elapsed_sec") or 0.0),
                "process_cpu_percent": row.get("process_cpu_percent"),
                "system_cpu_percent": row.get("system_cpu_percent"),
                "process_rss_bytes": row.get("process_rss_bytes"),
                "process_vms_bytes": row.get("process_vms_bytes"),
                "system_ram_total_bytes": row.get("system_ram_total_bytes"),
                "system_ram_available_bytes": row.get("system_ram_available_bytes"),
                "system_ram_used_bytes": row.get("system_ram_used_bytes"),
                "system_ram_percent": row.get("system_ram_percent"),
                "process_disk_read_bytes": row.get("process_disk_read_bytes"),
                "process_disk_write_bytes": row.get("process_disk_write_bytes"),
                "system_disk_read_bytes": row.get("system_disk_read_bytes"),
                "system_disk_write_bytes": row.get("system_disk_write_bytes"),
                "disk_free_bytes": row.get("disk_free_bytes"),
                "gpu_index": row.get("gpu_index"),
                "gpu_uuid": row.get("gpu_uuid"),
                "gpu_utilization_percent": row.get("gpu_utilization_percent"),
                "gpu_memory_utilization_percent": row.get(
                    "gpu_memory_utilization_percent"
                ),
                "gpu_vram_bytes": row.get("gpu_vram_bytes"),
                "gpu_peak_vram_bytes": row.get("gpu_peak_vram_bytes"),
                "gpu_total_vram_bytes": row.get("gpu_total_vram_bytes"),
                "gpu_temperature_c": row.get("gpu_temperature_c"),
                "gpu_power_w": row.get("gpu_power_w"),
                "sampling_gap": bool(row.get("sampling_gap", False)),
                "availability": availability,
            },
        )
        self._publish(event, "telemetry")
        self._maybe_write_live_status()

    def _emit_status(
        self,
        state: str,
        reason: str,
        frame: NormalizedAudioFrame | None = None,
    ) -> None:
        contract_state = (
            state
            if state
            in {
                "starting",
                "ready",
                "running",
                "degraded",
                "stopping",
                "completed",
                "failed",
            }
            else "degraded"
        )
        event = self.factory.create(
            contract_type="PipelineStatusEvent",
            event_type="pipeline_status",
            component_identity=self.identities["pipeline"],
            capture_timestamps=frame.capture_contract() if frame is not None else None,
            event_reason=reason,
            payload={
                "pipeline_state": contract_state,
                "recoverable": self._recoverable,
                "component_statuses": self._component_statuses(),
                "progress": {
                    "completed_units": self._counts["audio_frames"],
                    "total_units": (
                        self._counts["audio_frames"]
                        if contract_state == "completed"
                        else None
                    ),
                    "percent": 100.0 if contract_state == "completed" else None,
                },
                "queue_depth": self.queue.depth,
                "dropped_frame_count": self.queue.dropped_count,
                "warnings": list(self._warnings),
                "errors": list(self._errors),
            },
        )
        self._publish(event)
        self._maybe_write_live_status(force=True)

    def _component_statuses(self) -> list[dict[str, object]]:
        rows = []
        for identity_name, component in (
            ("asr", self.asr),
            ("segmentation", self.segmenter),
            ("diarization", self.diarization_embedder),
            ("speaker_embedding", self.identity_embedder),
        ):
            errors: list[str] = []
            try:
                status = (
                    dict(component.status())
                    if hasattr(component, "status")
                    else {"state": "ready"}
                )
                internal_state = str(status.get("state") or "ready")
                state = {
                    "created": "pending",
                    "finalized": "completed",
                    "closed": "stopped",
                }.get(internal_state, internal_state)
                if state not in {
                    "pending",
                    "starting",
                    "ready",
                    "running",
                    "degraded",
                    "stopped",
                    "completed",
                    "failed",
                }:
                    state = "degraded"
                detail = json.dumps(status, sort_keys=True, default=str)
            except Exception as exc:
                state, detail = "failed", f"{type(exc).__name__}: {exc}"
                errors.append(detail)
            rows.append(
                {
                    "component_identity": self.identities[identity_name].to_contract(),
                    "state": state,
                    "updated_at_utc": utc_now_text(),
                    "reason": {
                        "code": "component_status_snapshot",
                        "detail": detail,
                        "causal_event_ids": [],
                    },
                    "errors": errors,
                }
            )
        return rows

    def _identity_decision_contract(
        self, transition: Any, evidence: IdentityEvidence, consistency: float
    ) -> str:
        if (
            not evidence.usable
            or consistency
            < self.identity_manager.policy.minimum_embedding_consistency
        ):
            return "quality_rejected"
        if transition.state in {
            IdentityState.TENTATIVE_KNOWN,
            IdentityState.CONFIRMED_KNOWN,
        }:
            return "accepted_known"
        if transition.decision_reason in {
            "insufficient_evidence",
            "minimum_evidence_not_met",
            "confirmation_pending",
            "known_identity_tentative",
            "challenger_confirmation_pending",
            "no_candidate_scores",
            "challenger_calibration_unresolved",
        }:
            return "insufficient_evidence"
        return "rejected_unknown"

    def _publish(self, event: Mapping[str, object], group: str | None = None) -> None:
        self.sink.emit(event)
        self._counts["events"] += 1
        if group is not None:
            self._event_groups[group].append(dict(event))
        self._maybe_write_live_status()

    def _validate_profiles(self) -> None:
        expected_config = str(self.selection.identity["config_sha256"])
        expected_model = str(self.selection.identity["model_identity_sha256"])
        for profile in self._profiles:
            if profile.backend_config_sha256.lower() != expected_config.lower():
                raise ValueError(
                    f"enrollment profile {profile.profile_id} backend config mismatch"
                )
            if profile.model_sha256.lower() != expected_model.lower():
                raise ValueError(
                    f"enrollment profile {profile.profile_id} model identity mismatch"
                )

    def _threshold_contract(self, gallery_size: int) -> dict[str, object]:
        policy = self.identity_manager.policy
        score_threshold = (
            policy.score_threshold if policy.score_threshold is not None else 2.0
        )
        margin_threshold = (
            policy.margin_threshold if policy.margin_threshold is not None else 2.0
        )
        resolved = dict(self.decision_policy_contract or {})
        decision_sha = str(
            resolved.get("decision_policy_sha256")
            or policy.decision_policy_sha256
            or ""
        ).lower()
        if policy.calibrated and len(decision_sha) != 64:
            raise ValueError("calibrated identity policy lacks decision-policy SHA-256")
        calibration_protocol_id = str(
            resolved.get("calibration_protocol_id")
            or policy.calibration_protocol_id
            or CALIBRATION_PROTOCOL_ID
        )
        calibration_result_sha256 = str(
            resolved.get("calibration_result_sha256")
            or policy.calibration_result_sha256
            or decision_sha
        ).lower()
        return {
            "threshold_policy_id": policy.policy_id,
            "threshold_policy_sha256": decision_sha
            if decision_sha
            else CALIBRATION_RESULT_SHA256,
            "calibration_protocol_id": calibration_protocol_id,
            "calibration_result_sha256": calibration_result_sha256
            if calibration_result_sha256
            else CALIBRATION_RESULT_SHA256,
            "operating_mode": str(
                resolved.get("operating_mode")
                or ("BALANCED" if policy.calibrated else "UNRESOLVED_CHALLENGER")
            ),
            "gallery_size": max(1, gallery_size),
            "raw_score_type": "cosine_similarity",
            "score_threshold": score_threshold,
            "margin_threshold": margin_threshold,
            "minimum_evidence_sec": policy.minimum_evidence_sec,
            "target_fpir": resolved.get("target_fpir", policy.target_fpir),
            "selection_tier": "frozen_anchor"
            if policy.frozen_anchor
            else "development_required",
            "threshold_scope": resolved.get(
                "threshold_scope",
                "frozen_product_v2_balanced_gallery10_scalar_reused_for_all_galleries"
                if policy.frozen_anchor
                else "development_calibration_required",
            ),
        }

    def _threshold_contract_for_transition(
        self, gallery_size: int, transition: IdentityTransition
    ) -> dict[str, object]:
        """Return the exact adaptive gates used by one evidence decision.

        Session-level metadata continues to call :meth:`_threshold_contract`
        directly and therefore retains the calibrated base policy.  Only an
        event backed by an actual transition receives its duration-effective
        H2A/H4 score and margin gates.
        """

        threshold = self._threshold_contract(gallery_size)
        if transition.effective_score_threshold is not None:
            threshold["score_threshold"] = float(
                transition.effective_score_threshold
            )
        if transition.effective_margin_threshold is not None:
            threshold["margin_threshold"] = float(
                transition.effective_margin_threshold
            )
        return threshold

    def _profile_for_speaker_id(
        self, speaker_id: str | None
    ) -> RuntimeEnrollmentProfile | None:
        if speaker_id is None:
            return None
        matches = sorted(
            (row for row in self._profiles if row.speaker_id == speaker_id),
            key=lambda row: row.profile_id,
        )
        return matches[0] if matches else None

    def _known_speaker_id_for_label(
        self,
        label: object,
        anonymous_speaker_id: object | None = None,
    ) -> str | None:
        if label is None or self._is_public_unknown_label(str(label)):
            return None
        text = str(label)
        if anonymous_speaker_id is not None:
            try:
                snapshot = self.identity_manager.snapshot(str(anonymous_speaker_id))
            except (KeyError, ValueError):
                snapshot = None
            if snapshot is not None and snapshot.known_speaker_id is not None:
                profile = self._profile_for_speaker_id(snapshot.known_speaker_id)
                if text in {
                    snapshot.speaker_label,
                    profile.display_label if profile is not None else "",
                }:
                    return snapshot.known_speaker_id
        if self._profile_for_speaker_id(text) is not None:
            return text
        matches = {
            row.speaker_id for row in self._profiles if row.display_label == text
        }
        return next(iter(matches)) if len(matches) == 1 else None

    def _public_speaker_label(self, label: str, known_id: str | None) -> str:
        resolved_id = known_id or self._known_speaker_id_for_label(label)
        profile = self._profile_for_speaker_id(resolved_id)
        if profile is not None:
            return profile.display_label
        if self.mode_behavior is not None and self._is_public_unknown_label(label):
            return self.mode_behavior.public_unknown_label(label)
        return label

    @staticmethod
    def _is_public_unknown_label(label: str) -> bool:
        return (
            label == "Unknown"
            or label.startswith("Unknown_")
            or label == "Speaker"
            or label.startswith("Speaker_")
        )

    def _session_cluster_id(self, raw_cluster_id: str) -> str:
        if self._anonymous_epoch == 0:
            return raw_cluster_id
        return f"epoch_{self._anonymous_epoch:04d}:{raw_cluster_id}"

    def _identity_evidence_event_for_transition(
        self, transition: Any
    ) -> Mapping[str, object] | None:
        requested = set(str(value) for value in transition.evidence_event_ids)
        if not requested:
            try:
                last_id = self.identity_manager.last_evidence_event_id(
                    str(transition.anonymous_speaker_id)
                )
            except KeyError:
                last_id = None
            if last_id is not None:
                requested.add(last_id)
        if not requested:
            return None
        return next(
            (
                event
                for event in reversed(self._event_groups["identity_evidence"])
                if str(event.get("event_id")) in requested
            ),
            None,
        )

    def _prune_bounded_runtime_state(self, source_time_sec: float) -> None:
        if self.runtime_tuning is None:
            return
        correction_floor = max(
            0.0, source_time_sec - self.runtime_tuning.retroactive_correction_sec
        )
        self.transcript_aligner.seal_spans_ending_at_or_before(correction_floor)
        for window_id, region in tuple(self._speaker_regions_by_window.items()):
            if region.end_sec >= correction_floor:
                continue
            self._speaker_regions_by_window.pop(window_id, None)
            self._window_cluster_intervals.pop(window_id, None)
            self._anonymous_event_by_window.pop(window_id, None)
        self._speaker_regions = sorted(
            self._speaker_regions_by_window.values(),
            key=lambda row: (
                row.start_sec,
                row.end_sec,
                row.anonymous_speaker_id,
                row.source_event_id,
            ),
        )
        for cluster_id, intervals in tuple(self._cluster_intervals.items()):
            retained = [
                (max(left, correction_floor), right)
                for left, right in intervals
                if right > correction_floor
            ]
            if retained:
                self._cluster_intervals[cluster_id] = retained
            else:
                self._cluster_intervals.pop(cluster_id, None)
        retention = self.runtime_tuning.identity_observation_retention_sec
        if self.runtime_tuning.product_mode.value == "H2_KNOWN_ONLY":
            retention = min(
                retention, self.runtime_tuning.unmatched_embedding_retention_sec
            )
        evidence_floor = source_time_sec - retention
        for cluster_id, times in tuple(self._identity_observation_times.items()):
            observations = self._identity_vectors.get(cluster_id, {})
            for window_id, observed_at in tuple(times.items()):
                if observed_at < evidence_floor:
                    times.pop(window_id, None)
                    observations.pop(window_id, None)
            if not observations:
                self._identity_vectors.pop(cluster_id, None)
                self._identity_observation_times.pop(cluster_id, None)
        overflow = (
            len(self._boundary_corrections)
            - self.runtime_tuning.maximum_session_event_history
        )
        if overflow > 0:
            del self._boundary_corrections[:overflow]
        reconciliation_overflow = (
            len(self._cluster_reconciliations)
            - self.runtime_tuning.maximum_session_event_history
        )
        if reconciliation_overflow > 0:
            del self._cluster_reconciliations[:reconciliation_overflow]

    def _speaker_label_contract(
        self, label: str, known_id: str | None
    ) -> dict[str, object]:
        if self._is_public_unknown_label(label):
            return {
                "label_kind": "unknown",
                "display_label": self._public_speaker_label(label, None),
                "enrolled_speaker_id": None,
            }
        resolved_id = known_id or self._known_speaker_id_for_label(label)
        return {
            "label_kind": "known",
            "display_label": self._public_speaker_label(label, resolved_id),
            "enrolled_speaker_id": resolved_id or label,
        }

    def _embedding_consistency(
        self,
        rows: Sequence[tuple[np.ndarray, float]],
        *,
        aggregate: np.ndarray | None = None,
    ) -> float:
        if len(rows) < 2:
            return 1.0
        if (
            self.identity_manager.policy.consistency_method
            != "frozen_mean_cosine_to_aggregate"
        ):
            raise ValueError("unsupported identity consistency method")
        vectors = np.stack([value for value, _ in rows]).astype(np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if np.any(norms <= 0.0):
            return -1.0
        vectors = vectors / norms
        if aggregate is None:
            weights = np.asarray(
                [duration for _, duration in rows], dtype=np.float64
            )
            aggregate = np.average(vectors, axis=0, weights=weights)
        aggregate = np.asarray(aggregate, dtype=np.float64)
        aggregate_norm = float(np.linalg.norm(aggregate))
        if aggregate_norm <= 0.0:
            return -1.0
        aggregate = aggregate / aggregate_norm
        return float(np.mean(vectors @ aggregate))

    def _maybe_write_live_status(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_status_write_monotonic < 0.5:
            return
        # ``status()`` acquires ``_processing_lock``.  Capture it before taking
        # ``_status_lock`` so the telemetry thread cannot hold the status lock
        # while waiting for processing as the processing thread simultaneously
        # waits to publish a status file (an ABBA deadlock under accelerated
        # file input on Windows and Linux alike).
        snapshot = self.status()
        with self._status_lock:
            now = time.monotonic()
            if not force and now - self._last_status_write_monotonic < 0.5:
                return
            path = self.output_root / "status.json"
            temporary = path.with_name(f".status.{uuid.uuid4().hex}.tmp")
            temporary.write_text(
                json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
            self._last_status_write_monotonic = now

    def _write_live_status(self) -> None:
        self._maybe_write_live_status(force=True)

    def _write_result(self) -> Mapping[str, object]:
        self._counts["warnings"] = len(self._warnings)
        self._counts["errors"] = len(self._errors)
        event_ref = self.artifacts.register_existing(
            "events/events.jsonl",
            schema_version="full-pipeline-contracts.v1",
            media_type="application/x-ndjson",
        )
        transcript_snapshot = {
            "schema_version": "full-pipeline-final-transcript.v1",
            "transcript_id": self.transcript_aligner.transcript_id,
            "spans": [row.to_jsonable() for row in self.transcript_aligner.spans],
        }
        final_transcript = self.artifacts.write_json(
            "transcript/final_transcript.json",
            transcript_snapshot,
            schema_version="full-pipeline-final-transcript.v1",
            privacy="private",
        )
        if self.runtime_tuning is not None:
            paragraphs = build_paragraphs(
                self.transcript_aligner.spans,
                policy=self.runtime_tuning.paragraph_policy,
                pause_sec=self.runtime_tuning.paragraph_pause_sec,
                maximum_words=self.runtime_tuning.paragraph_max_words,
            )
            self.artifacts.write_json(
                "transcript/paragraphs.json",
                {
                    "schema_version": "h2-transcript-paragraphs.v1",
                    "policy": self.runtime_tuning.paragraph_policy,
                    "pause_sec": self.runtime_tuning.paragraph_pause_sec,
                    "maximum_words": self.runtime_tuning.paragraph_max_words,
                    "paragraphs": [row.to_jsonable() for row in paragraphs],
                },
                schema_version="h2-transcript-paragraphs.v1",
                privacy="private",
            )
        revisions = self.artifacts.write_jsonl(
            "transcript/revisions.jsonl",
            self._event_groups["transcript"],
            schema_version="full-pipeline-contracts.v1",
            privacy="private",
        )
        anonymous = self.artifacts.write_jsonl(
            "speakers/anonymous.jsonl",
            self._event_groups["anonymous"],
            schema_version="full-pipeline-contracts.v1",
            privacy="private",
        )
        evidence = self.artifacts.write_jsonl(
            "speakers/identity_evidence.jsonl",
            self._event_groups["identity_evidence"],
            schema_version="full-pipeline-contracts.v1",
            privacy="biometric_sensitive",
        )
        labels = self.artifacts.write_jsonl(
            "speakers/identity_labels.jsonl",
            self._event_groups["identity_label"],
            schema_version="full-pipeline-contracts.v1",
            privacy="private",
        )
        telemetry = self.artifacts.write_jsonl(
            "telemetry/resource_samples.jsonl",
            self._event_groups["telemetry"],
            schema_version="full-pipeline-contracts.v1",
        )
        self.artifacts.write_jsonl(
            "diagnostics/asr_native_events.jsonl",
            self._asr_diagnostics,
            schema_version="full-pipeline-asr-adapter-event.v1",
            privacy="private",
        )
        self.artifacts.write_jsonl(
            "diagnostics/unresolved_identity_scores.jsonl",
            self._identity_diagnostics,
            schema_version="full-pipeline-unresolved-identity-score.v1",
            privacy="biometric_sensitive",
        )
        self.artifacts.write_jsonl(
            "diagnostics/identity_score_diagnostics.jsonl",
            self._calibrated_identity_score_diagnostics,
            schema_version=(
                "full-pipeline-development-identity-score-diagnostic.v1"
            ),
            privacy="biometric_sensitive",
        )
        self.artifacts.write_jsonl(
            "diagnostics/overlap_identity_scores.jsonl",
            self._overlap_identity_diagnostics,
            schema_version="full-pipeline-overlap-identity-score.v1",
            privacy="biometric_sensitive",
        )
        self.artifacts.write_jsonl(
            "diagnostics/boundary_corrections.jsonl",
            self._boundary_corrections,
            schema_version="h2-boundary-correction.v1",
            privacy="private",
        )
        self.artifacts.write_jsonl(
            "diagnostics/cluster_reconciliations.jsonl",
            self._cluster_reconciliations,
            schema_version="h2-cluster-reconciliation-runtime.v1",
            privacy="private",
        )
        reuse_telemetry = (
            self.embedding_reuse_router.telemetry()
            if self.embedding_reuse_router is not None
            else None
        )
        self.artifacts.write_jsonl(
            "diagnostics/embedding_reuse_observations.jsonl",
            (
                self.embedding_reuse_router.observations()
                if self.embedding_reuse_router is not None
                else ()
            ),
            schema_version="h2-embedding-reuse-observation.v1",
            privacy="biometric_sensitive",
        )
        if reuse_telemetry is not None:
            self.artifacts.write_json(
                "diagnostics/embedding_reuse_telemetry.json",
                reuse_telemetry,
                schema_version="h2-embedding-reuse-telemetry.v1",
                privacy="private",
            )
        metrics = self.artifacts.write_json(
            "metrics/runtime_metrics.json",
            {
                "schema_version": "full-pipeline-runtime-metrics.v1",
                "counts": dict(self._counts),
                "queue": {
                    "policy": self.config.queue_policy,
                    "maximum_frames": self.config.maximum_queue_frames,
                    "maximum_observed_depth": self.queue.max_depth,
                    "dropped_frames": self.queue.dropped_count,
                    "blocked_total_sec": self._queue_blocked_total_sec,
                    "blocked_max_sec": self._queue_blocked_max_sec,
                },
                "embedding_execution": reuse_telemetry,
                "asr": {
                    "first_partial_elapsed_sec": next(
                        (
                            row.get("emitted_elapsed_sec")
                            for row in self._asr_diagnostics
                            if row.get("is_first_partial")
                        ),
                        None,
                    ),
                    "partial_revision_count": sum(
                        1
                        for row in self._asr_diagnostics
                        if not row.get("is_final")
                        and row.get("adapter_event_type") != "asr_reset"
                    ),
                    "endpoint_count": sum(
                        1
                        for row in self._asr_diagnostics
                        if row.get("endpoint_detected")
                    ),
                    "finalization_latencies_ms": [
                        row.get("finalization_latency_ms")
                        for row in self._asr_diagnostics
                        if row.get("finalization_latency_ms") is not None
                    ],
                    "stable_prefix_method": "consecutive_hypothesis_token_lcp.v1",
                },
                "segmentation": {
                    "algorithmic_lookahead_sec": getattr(
                        self.segmenter, "algorithmic_lookahead_sec", None
                    ),
                    "compute_latency_reported_separately": True,
                },
                "cluster_reconciliation": {
                    "event_count": len(self._cluster_reconciliations),
                    "future_spatial_hook_available": False,
                    "future_spatial_hook_result_effect": False,
                    "open_set_threshold_bypassed": False,
                },
                "bounded_session_state": {
                    "identity_observation_count": sum(
                        len(value) for value in self._identity_vectors.values()
                    ),
                    "active_region_count": len(self._speaker_regions_by_window),
                    "identity_manager": self.identity_manager.session_state(),
                    "active_roster": (
                        self.session_memory.snapshot()
                        if self.session_memory is not None
                        else None
                    ),
                },
            },
            schema_version="full-pipeline-runtime-metrics.v1",
        )
        provenance = self.artifacts.write_json(
            "manifests/provenance.json",
            {
                "schema_version": "full-pipeline-runtime-provenance.v1",
                "session_id": self.config.session_id,
                "pipeline_id": self.selection.pipeline_id,
                "pipeline_config_sha256": self.selection.pipeline_config_sha256,
                "runtime_config_sha256": self.selection.runtime_config_sha256,
                "component_identities": [
                    value.to_contract() for _, value in sorted(self.identities.items())
                ],
                "worker_reported_identities": self._worker_reported_identities(),
                "profiles": [
                    {"profile_id": row.profile_id, "profile_sha256": row.profile_sha256}
                    for row in self._profiles
                ],
                "identity_decision_policy": self._threshold_contract(
                    max(1, len(self._profiles))
                ),
                "identity_decision_policy_resolution": (
                    dict(self.decision_policy_contract)
                    if self.decision_policy_contract is not None
                    else None
                ),
                "identity_consistency_method": (
                    self.identity_manager.policy.consistency_method
                ),
                "identity_hysteresis_score_mode": (
                    self.identity_manager.policy.hysteresis_score_mode
                ),
                "h2_runtime_tuning": (
                    {
                        **self.runtime_tuning.to_jsonable(),
                        "identity_sha256": self.runtime_tuning.identity_sha256,
                    }
                    if self.runtime_tuning is not None
                    else None
                ),
                "no_implicit_downloads": True,
            },
            schema_version="full-pipeline-runtime-provenance.v1",
        )
        license_manifest = self.artifacts.write_json(
            "manifests/license_reference.json",
            {
                "schema_version": "full-pipeline-license-reference.v1",
                "canonical_logical_path": "docs/full_pipeline/LICENSE_AND_ASSET_MANIFEST.md",
                "technical_ranking_separate_from_deployment_eligibility": True,
            },
            schema_version="full-pipeline-license-reference.v1",
        )
        session_state = self._build_session_state(
            transcript_state_artifact=final_transcript,
            telemetry_artifact=telemetry,
        )
        self.artifacts.write_json(
            "session_state.json",
            session_state,
            schema_version="full-pipeline-contracts.v1",
            privacy="private",
        )
        checksums = self.artifacts.checksum_manifest()
        if self._state == "stopped" and not self._errors:
            completion = "stopped"
        elif self._state in {"completed", "degraded"} and not self._errors:
            completion = "complete"
        else:
            completion = "failed"
        unsigned = {
            "schema_version": "full-pipeline-contracts.v1",
            "contract_type": "PipelineResult",
            "result_id": f"result:{self.config.session_id}",
            "session_id": self.config.session_id,
            "pipeline_id": self.selection.pipeline_id,
            "protocol_version": self.selection.protocol_version,
            "pipeline_config_sha256": self.selection.pipeline_config_sha256,
            "completion_state": completion,
            "started_at_utc": self._started_utc,
            "ended_at_utc": self._ended_utc,
            "source_clock": dict(self.factory.source_clock),
            "component_identities": [
                value.to_contract() for _, value in sorted(self.identities.items())
            ],
            "counts": dict(self._counts),
            "final_transcript_artifact": final_transcript,
            "transcript_revision_artifact": revisions,
            "anonymous_speaker_artifact": anonymous,
            "identity_evidence_artifact": evidence,
            "identity_label_artifact": labels,
            "event_log_artifact": event_ref,
            "resource_telemetry_artifact": telemetry,
            "metrics_artifact": metrics,
            "provenance_manifest_artifact": provenance,
            "license_manifest_artifact": license_manifest,
            "checksum_manifest_artifact": checksums,
            "warnings": list(self._warnings),
            "errors": list(self._errors),
        }
        result = {
            **unsigned,
            "result_sha256": hashlib.sha256(
                json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                )
            ).hexdigest(),
        }
        self.artifacts.write_json(
            "result.json",
            result,
            schema_version="full-pipeline-contracts.v1",
            privacy="private",
        )
        self._write_live_status()
        return result

    def _worker_reported_identities(self) -> list[dict[str, object]]:
        rows: dict[str, dict[str, object]] = {}
        for component in (
            self.asr,
            self.segmenter,
            self.diarization_embedder,
            self.identity_embedder,
        ):
            worker = getattr(component, "worker", None)
            if worker is None or not hasattr(worker, "status"):
                continue
            status = dict(worker.status())
            identity = status.get("identity")
            if isinstance(identity, Mapping):
                rows[str(status.get("worker_id") or id(worker))] = {
                    "worker_id": str(status.get("worker_id") or "unknown_worker"),
                    "environment_profile": status.get("environment_profile"),
                    "restart_count": int(status.get("restart_count") or 0),
                    "identity": dict(identity),
                }
        return [rows[key] for key in sorted(rows)]

    def _build_session_state(
        self,
        *,
        transcript_state_artifact: Mapping[str, object],
        telemetry_artifact: Mapping[str, object],
    ) -> dict[str, object]:
        """Materialize the locked restart/handoff state at session completion."""

        events = self.sink.events()
        last_event = events[-1] if events else None
        latest_cluster_state: dict[str, str] = {}
        for event in self._event_groups["anonymous"]:
            latest_cluster_state[str(event["anonymous_speaker_id"])] = str(
                event["cluster_state"]
            )
        last_evidence_event: dict[str, str] = {}
        for event in self._event_groups["identity_evidence"]:
            last_evidence_event[str(event["anonymous_speaker_id"])] = str(
                event["event_id"]
            )

        anonymous_speakers: list[dict[str, object]] = []
        identity_labels: list[dict[str, object]] = []
        for allocation in self.identity_manager.allocator.snapshot():
            cluster_id = allocation.anonymous_speaker_id
            snapshot = self.identity_manager.snapshot(cluster_id)
            anonymous_speakers.append(
                {
                    "anonymous_speaker_id": cluster_id,
                    "unknown_label": allocation.unknown_label,
                    "unknown_ordinal": allocation.unknown_ordinal,
                    "cluster_state": latest_cluster_state.get(cluster_id, "tentative"),
                }
            )
            public_state = {
                IdentityState.TENTATIVE_KNOWN: "tentative",
                IdentityState.CONFIRMED_KNOWN: "confirmed",
            }.get(snapshot.state, "unknown")
            identity_labels.append(
                {
                    "anonymous_speaker_id": cluster_id,
                    "identity_state": public_state,
                    "speaker_label": self._speaker_label_contract(
                        snapshot.speaker_label, snapshot.known_speaker_id
                    ),
                    "last_evidence_event_id": last_evidence_event.get(cluster_id),
                }
            )

        source_status: Mapping[str, object] = {}
        if hasattr(self.source, "status"):
            try:
                source_status = dict(self.source.status())
            except Exception:
                source_status = {}
        internal_source_mode = str(source_status.get("source_mode") or "")
        source_mode = (
            "live_microphone"
            if internal_source_mode == "microphone"
            else "incremental_audio_file"
            if internal_source_mode.startswith("file_")
            else "synthetic_replay"
        )
        discontinuity_count = sum(
            1
            for event in events
            if event.get("contract_type") == "AudioFrameEvent"
            and bool(
                dict(event.get("capture_timestamps") or {}).get(
                    "discontinuity_before", False
                )
            )
        )
        updated_at = self._ended_utc or utc_now_text()
        return {
            "schema_version": "full-pipeline-contracts.v1",
            "contract_type": "SessionState",
            "session_id": self.config.session_id,
            "state_revision": 1,
            "lifecycle_state": self._state,
            "source_mode": source_mode,
            "source_clock": dict(self.factory.source_clock),
            "started_at_utc": self._started_utc,
            "updated_at_utc": updated_at,
            "ended_at_utc": self._ended_utc,
            "pipeline_id": self.selection.pipeline_id,
            "protocol_version": self.selection.protocol_version,
            "pipeline_config_sha256": self.selection.pipeline_config_sha256,
            "component_identities": [
                value.to_contract() for _, value in sorted(self.identities.items())
            ],
            "next_event_sequence": self.factory.next_sequence,
            "last_event_id": (
                str(last_event["event_id"]) if last_event is not None else None
            ),
            "last_event_sequence": (
                int(last_event["event_sequence"]) if last_event is not None else None
            ),
            "transcript_id": self.transcript_aligner.transcript_id,
            "transcript_revision_id": self.transcript_aligner.last_revision_id,
            "transcript_state_artifact": dict(transcript_state_artifact),
            "anonymous_speakers": anonymous_speakers,
            "identity_labels": identity_labels,
            "enrollment_profiles": [
                {
                    "profile_id": profile.profile_id,
                    "profile_sha256": profile.profile_sha256,
                }
                for profile in self._profiles
            ],
            "queue_depth": self.queue.depth,
            "dropped_frame_count": self.queue.dropped_count,
            "discontinuity_count": discontinuity_count,
            "telemetry_artifact": dict(telemetry_artifact),
            "warnings": list(self._warnings),
            "errors": list(self._errors),
            "resume_checkpoint": None,
        }
