"""Independent-lane runtime: capture, ASR, and speaker work never share a queue."""

from __future__ import annotations

from datetime import datetime, timezone
from collections import deque
from contextlib import nullcontext
import json
import os
from pathlib import Path
import queue
import threading
import time
import uuid

import numpy as np

from .audio import AudioJournal, MicrophoneSource, WavSource
from .config import PipelineConfig
from .contracts import PipelineEvent, SpeakerDecision, SpatialEvidence
from .enrollment import (
    EnrollmentRecorder,
    enroll_wavs,
    enrollment_recording_path,
    record_microphone_wav,
)
from .models import SherpaStream, SpeakerModels
from .speakers import ProfileStore, SpeakerTracker
from .text_format import format_partial_display


class PipelineEngine:
    """One session at a time, backed by persistent model objects."""

    def __init__(self, config: PipelineConfig | None = None, *, research_profile=None, spatial_provider=None, model_bundle=None, research_gallery=None, s6d_settings=None, s7_settings=None) -> None:
        self.config = research_profile.apply(config) if research_profile is not None else config or PipelineConfig()
        self._research_profile = research_profile
        self._research_v3 = getattr(research_profile, "schema_version", None) == "edge-research-profile.v3"
        self._research_v2 = getattr(research_profile, "schema_version", None) in {"edge-research-profile.v2", "edge-research-profile.v3"}
        from .research_s6d import S6DSettings
        self._s6d = s6d_settings or (S6DSettings.load(self.config.s6d_settings_path) if self.config.s6d_settings_path else None)
        if self._s6d is not None:
            self._s6d.validate()
            if not self._research_v3:
                raise ValueError("S6D requires an explicit v3 matched application profile")
        self._s6d_writer = self._s6d_punctuation = self._s6d_presentation = None
        self._s7 = s7_settings.validate() if s7_settings is not None else None
        if self._s7 is not None and (self._s6d is None or not self._research_v3):
            raise ValueError("S7 requires explicit matched v3 profile and S6D delivery")
        self._s7_trace = None
        self._s7_observed_clock = None
        self._s7_presentation_options = None
        if self._s7 is not None and self._s7.availability_clock == "observed" and not self._s6d.text_delivery:
            raise ValueError("Observed availability requires explicit bounded S6D text delivery")
        if self._s7 is not None and self._s7.mode == "M0" and research_gallery is not None:
            raise ValueError("Caption-only M0 must not load an optional identity gallery")
        self._s6d_event_serial = 0
        self._s6d_punctuated = {}
        self._research_gallery = None
        self._identity_journal = None
        self._paired_journal = None
        if research_gallery is not None:
            if not self._research_v3 or research_profile.identity.mode != "post_association":
                raise ValueError("an explicit research gallery requires v3 post-association naming")
            self._research_gallery = self._admit_research_gallery(research_gallery, research_profile.identity.max_gallery_profiles)
        elif self._research_v3 and research_profile.identity.mode != "none":
            raise ValueError("S6C naming cannot run without an explicit admitted research gallery")
        if self._s6d is not None and (self._s6d.transcript_mode != "T0" or self._s6d.direction_mode in {"V2", "V3"}):
            if self._research_gallery is None:
                raise ValueError("selected/enrolled S6D modes require the actual admitted gallery")
            if set(self._s6d.selected_profile_ids)-set(self._research_gallery.ids):
                raise ValueError("preselected profile IDs must belong to the admitted gallery")
        self._model_bundle = model_bundle
        self._bundle_acquired = False
        self._scheduler = None
        self._research_utterance_start_sec = 0.0
        self._research_asr_event_serial = 0
        self._spatial_provider = spatial_provider
        if research_profile is not None and research_profile.xvf.mode != "none" and spatial_provider is None:
            raise ValueError("a cue-enabled profile requires an explicit causal spatial provider")
        self._research_speaker_history = deque(maxlen=4096)
        self._research_segmentation_history = deque(maxlen=4096)
        self._research_asr_available_sec = 0.0
        self.events: queue.SimpleQueue[PipelineEvent] = queue.SimpleQueue()
        self._event_lock = threading.RLock() if self._s6d is not None else threading.Lock()
        self._speaker_lock = threading.Lock()
        self._models_lock = threading.Lock()
        self._speaker_models: SpeakerModels | None = None
        self._enrollment_recorder: EnrollmentRecorder | None = None
        self._enrollment_name: str | None = None
        self._last_enrollment_status: dict[str, object] = {
            "active": False,
            "duration_sec": 0.0,
        }
        self._source: MicrophoneSource | WavSource | None = None
        self._journal: AudioJournal | None = None
        self._event_handle = None
        self._transcript_handle = None
        self._readable_transcript_handle = None
        self._session_dir: Path | None = None
        self._threads: list[threading.Thread] = []
        self._finalization_thread: threading.Thread | None = None
        self._finalization_error: Exception | None = None
        self._stop_event = threading.Event()
        self._current_speaker: SpeakerDecision | None = None
        self._overlap_active = False
        self._state = "IDLE"
        self._started_monotonic = 0.0
        self._telemetry: dict[str, object] = {
            "audio_frames_dropped": 0,
            "portaudio_input_overflows": 0,
            "raw_capture_reserve_failures": 0,
            "asr_cursor_sec": 0.0,
            "speaker_cursor_sec": 0.0,
            "speaker_analyzed_through_sec": 0.0,
            "speaker_unanalyzed_short_tail_sec": 0.0,
            "asr_lag_sec": 0.0,
            "speaker_lag_sec": 0.0,
            "punctuation_utterances": 0,
            "punctuation_total_ms": 0.0,
            "punctuation_max_ms": 0.0,
            "punctuation_fallbacks": 0,
            "punctuation_terminal_fallbacks": 0,
            "punctuation_inference_failures": 0,
        }

    @property
    def state(self) -> str:
        return self._state

    @property
    def session_dir(self) -> Path | None:
        return self._session_dir

    def _ensure_speaker_models(self) -> SpeakerModels:
        with self._models_lock:
            if self._speaker_models is None:
                self._speaker_models = SpeakerModels(self.config)
            return self._speaker_models

    def enroll_files(self, display_name: str, wav_paths: list[Path]) -> dict[str, object]:
        """Backend-owned enrollment entry point used identically by GUI and CLI."""

        return enroll_wavs(
            display_name,
            wav_paths,
            models=self._ensure_speaker_models(),
            config=self.config,
        )

    def enroll_microphone(
        self,
        display_name: str,
        *,
        device: int | None,
        duration_sec: float = 6.0,
    ) -> dict[str, object]:
        output = enrollment_recording_path(self.config.profile_root, display_name)
        recorded = record_microphone_wav(
            output, device=device, duration_sec=duration_sec
        )
        return self.enroll_files(display_name, [recorded])

    def start_enrollment_recording(
        self, display_name: str, *, device: int | None
    ) -> dict[str, object]:
        """Start an unlimited disk-backed enrollment recording."""

        name = display_name.strip()
        if not name:
            raise ValueError("display name is required")
        if self._state not in {"IDLE", "COMPLETED", "FAILED"}:
            raise RuntimeError("stop the transcript session before enrollment")
        if self._enrollment_recorder is not None:
            raise RuntimeError("an enrollment recording is already active")
        recorder = EnrollmentRecorder(
            enrollment_recording_path(self.config.profile_root, name),
            device=device,
            preferred_rate=self.config.sample_rate,
            block_ms=self.config.capture_block_ms,
            reserve_sec=self.config.raw_capture_reserve_sec,
        )
        self._enrollment_recorder = recorder
        self._enrollment_name = name
        try:
            status = recorder.start()
        except Exception:
            self._enrollment_recorder = None
            self._enrollment_name = None
            raise
        self._last_enrollment_status = dict(status)
        return status

    def stop_enrollment_recording(self) -> dict[str, object]:
        """Stop capture, quality-check all audio, and build the local profile."""

        recorder = self._enrollment_recorder
        name = self._enrollment_name
        if recorder is None or name is None:
            raise RuntimeError("no enrollment recording is active")
        try:
            path = recorder.stop()
            self._last_enrollment_status = dict(recorder.status())
        finally:
            self._enrollment_recorder = None
            self._enrollment_name = None
        return self.enroll_files(name, [path])

    def cancel_enrollment_recording(self) -> None:
        recorder = self._enrollment_recorder
        if recorder is not None:
            recorder.cancel()
            self._last_enrollment_status = dict(recorder.status())
        self._enrollment_recorder = None
        self._enrollment_name = None

    def enrollment_recording_status(self) -> dict[str, object]:
        if self._enrollment_recorder is not None:
            self._last_enrollment_status = dict(
                self._enrollment_recorder.status()
            )
        return dict(self._last_enrollment_status)

    def start_live(self, device: int | None = None) -> Path:
        if self._research_v3:
            raise ValueError("S6C v3 currently supports admitted file routes only")
        self._begin_session("microphone")
        assert self._journal is not None
        source = MicrophoneSource(
            self._journal,
            device=device,
            target_rate=self.config.sample_rate,
            block_ms=self.config.capture_block_ms,
            reserve_sec=self.config.raw_capture_reserve_sec,
            status_callback=self._source_status,
        )
        return self._launch(source)

    def start_file(
        self, path: Path, *, realtime: bool = True, accelerated_factor: float = 4.0
    ) -> Path:
        if self._research_v3:
            if self._research_profile.input.asr_tap != self._research_profile.input.identity_tap:
                raise ValueError("split-tap profile requires start_paired_files with both inputs")
            return self.start_paired_files(path, path, realtime=realtime, accelerated_factor=accelerated_factor)
        self._begin_session("wav")
        assert self._journal is not None
        source = WavSource(
            self._journal,
            path,
            target_rate=self.config.sample_rate,
            realtime=realtime,
            accelerated_factor=accelerated_factor,
            status_callback=self._source_status,
        )
        return self._launch(source)

    def start_paired_files(self, asr_path: Path, identity_path: Path, *, realtime: bool = True, accelerated_factor: float = 4.0) -> Path:
        if not self._research_v3:
            raise ValueError("paired input routing requires an explicit S6C v3 profile")
        from .research_audio_v3 import PairedJournal, PairedWavSource
        # Validate before creating a native session; the producer rechecks actual delivered lengths.
        import soundfile as sf
        infos = [sf.info(p) for p in (asr_path, identity_path)]
        if any(i.samplerate != 16000 or i.channels != 1 for i in infos) or infos[0].frames != infos[1].frames:
            raise ValueError("paired inputs must be aligned equal-length mono16kHz files")
        self._begin_session("paired_wav")
        try:
            identity = AudioJournal(self._session_dir / "identity_audio_spool.pcm16", self.config.sample_rate)
            pair = PairedJournal(self._journal, identity, trace=self._s7_trace)
            self._paired_journal = pair
            self._journal, self._identity_journal = pair.view(0), pair.view(1)
            source = PairedWavSource(pair, asr_path, identity_path, realtime=realtime,
                accelerated_factor=accelerated_factor, status_callback=self._source_status,
                source_block_ms=self._research_profile.input.source_block_ms,
                pacing=self._s7.pacing if self._s7 else "relative", trace=self._s7_trace)
            self._emit("research_input_route", 0., {"asr_path": str(Path(asr_path).resolve()),
                "identity_path": str(Path(identity_path).resolve()), "asr_tap": self._research_profile.input.asr_tap,
                "identity_tap": self._research_profile.input.identity_tap, "gain_applied_in_runtime": 1.,
                "already_gained": True, "expected_samples_per_journal": infos[0].frames,
                "common_origin": self._research_profile.input.common_origin, "shared_commit_barrier": True})
            return self._launch(source)
        except Exception as exc:
            self._fail("paired input launch failed: " + str(exc))
            raise

    def _begin_session(self, mode: str) -> None:
        if self._enrollment_recorder is not None:
            raise RuntimeError(
                "stop or cancel enrollment recording before starting transcription"
            )
        if self._state not in {"IDLE", "COMPLETED", "FAILED"}:
            raise RuntimeError(f"a session is already {self._state.lower()}")
        if self._finalization_thread is not None and self._finalization_thread.is_alive():
            raise RuntimeError("the previous session is still finalizing its artifacts")
        if self._s6d is not None and self._session_dir is not None:
            if not self.events.empty():
                raise RuntimeError('Consume the previous S6D session events before starting another session; committed events are preserved')
            if not (self._session_dir/'s6d_consumer_closure.json').exists():
                raise RuntimeError('The actual consumer must record previous S6D session closure before restart')
        self._finalization_thread = None
        self._finalization_error = None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._session_dir = self.config.session_root / f"edge_{mode}_{stamp}_{uuid.uuid4().hex[:8]}"
        self._session_dir.mkdir(parents=True, exist_ok=False)
        if self._s7 is not None:
            from .research_s7 import TraceWriter
            self._s7_trace = TraceWriter(self._session_dir / "s7_clocks.jsonl",
                                        self._session_dir.name, self._s7.trace_capacity)
            if self._s7.availability_clock == "observed":
                from .research_s7_policy import ObservedClock
                self._s7_observed_clock = ObservedClock(self._s7_trace)
            self._s7_presentation_options = (
                {"mode": self._s7.mode, "session_id": self._session_dir.name,
                 "ownership_mode": self._s7.ownership_mode}
                if self._s7.presentation_enabled else None)
        self._journal = self._make_audio_journal(self._session_dir / "audio_spool.pcm16")
        self._event_handle = self._open_journal_text(self._session_dir / "events.jsonl")
        self._transcript_handle = self._open_journal_text(self._session_dir / "labelled_transcript.jsonl")
        self._readable_transcript_handle = self._open_journal_text(self._session_dir / "transcript.md")
        self._readable_transcript_handle.write("# Session transcript\n\n")
        self._stop_event.clear()
        self._current_speaker = None
        self._overlap_active = False
        self._research_speaker_history.clear()
        self._research_segmentation_history.clear()
        self._research_asr_available_sec = 0.0
        self._research_utterance_start_sec = 0.0
        self._research_asr_event_serial = 0
        if self._s6d is not None:
            from .research_s6d import BoundedWorker, EventInbox, PresentationState
            self.events = EventInbox(self._s6d.queue_capacity)
            self._s6d_presentation = PresentationState(self._s6d)
            if self._s7_presentation_options is not None:
                from .research_s6d import build_presentation_state
                self._s6d_presentation = build_presentation_state(self._s6d, s7=self._s7_presentation_options)
            self._s6d_event_serial = 0
            self._s6d_punctuated = {}
            if self._s6d.text_delivery:
                self._s6d_writer = BoundedWorker("edge-s6d-journal", self._s6d_write_event, self._s6d.queue_capacity)
        if self._research_v3:
            if self._s6d is not None:
                from .research_s6d import build_s6d_scheduler
                self._scheduler = build_s6d_scheduler(self._research_profile, self._research_gallery,
                    self._spatial_provider, self._scheduled_event, self._s6d,
                    observed_clock=self._s7_observed_clock)
            else:
                from .research_scheduler_v3 import build_s6c_policy
                self._scheduler = build_s6c_policy(self._research_profile, self._research_gallery,
                    self._spatial_provider, self._scheduled_event)
        elif self._research_v2:
            from .research_scheduler import CausalScheduler
            from .research_tracking_v2 import S6BTracker
            self._scheduler = CausalScheduler(S6BTracker(self._research_profile.tracker),
                spatial_provider=self._spatial_provider,
                cues_enabled=self._research_profile.xvf.mode in {"tracking_only", "both"},
                revision_horizon_sec=self._research_profile.scheduler.revision_horizon_sec,
                evidence_expiry_sec=self._research_profile.scheduler.evidence_expiry_sec,
                max_pending_events=self._research_profile.scheduler.max_pending_events,
                max_events=self._research_profile.scheduler.max_events,
                max_utterances=self._research_profile.scheduler.max_utterances,
                max_revisions_per_utterance=self._research_profile.scheduler.max_revisions_per_utterance,
                emit=self._scheduled_event)
        self._state = "LOADING"
        self._started_monotonic = time.perf_counter()
        self._telemetry.update({"audio_frames_dropped": 0, "portaudio_input_overflows": 0, "raw_capture_reserve_failures": 0, "asr_cursor_sec": 0.0, "speaker_cursor_sec": 0.0, "speaker_analyzed_through_sec": 0.0, "speaker_unanalyzed_short_tail_sec": 0.0, "asr_lag_sec": 0.0, "speaker_lag_sec": 0.0, "punctuation_utterances": 0, "punctuation_total_ms": 0.0, "punctuation_max_ms": 0.0, "punctuation_fallbacks": 0, "punctuation_terminal_fallbacks": 0, "punctuation_inference_failures": 0})
        self._emit("session_created", 0.0, {"mode": mode, "session_dir": str(self._session_dir), "xvf_result_effects_enabled": self._research_profile is not None and self._research_profile.xvf.mode != "none"})
        if self._s6d is not None:
            self._emit("s6d_configuration", 0., self._s6d.receipt())
        if self._s7 is not None:
            self._emit("s7_configuration", 0., self._s7.receipt())
        if self._research_profile is not None:
            effective = self._research_profile.effective(self.config)
            effective["telemetry_sha256"] = getattr(self._spatial_provider, "sha256", None)
            self._emit("research_effective_config", 0.0, effective)
        if self._research_v3:
            self._emit("research_gallery_loaded", 0., self._research_gallery.receipt if self._research_gallery is not None else
                {"mode": "none", "loaded_count": 0, "private_gallery_accessed": False})

    def _make_audio_journal(self, path):
        return AudioJournal(path, self.config.sample_rate)

    def _open_journal_text(self, path):
        return path.open("a", encoding="utf-8", buffering=1)

    def _prepare_native_models(self, caption_only):
        if caption_only:
            return None, SherpaStream(self.config)
        if self._model_bundle is None:
            return self._ensure_speaker_models(), SherpaStream(self.config)
        models, asr = self._model_bundle.acquire(self.config)
        self._bundle_acquired = True
        return models, asr

    def _launch(self, source: MicrophoneSource | WavSource) -> Path:
        assert self._session_dir is not None
        try:
            model_load_started = time.perf_counter()
            caption_only = self._s7 is not None and self._s7.mode == "M0"
            if caption_only:
                if self._model_bundle is not None:
                    raise ValueError("M0 requires an ASR-only load; a full resident speaker bundle is not admitted")
                models, asr = self._prepare_native_models(True)
                self._telemetry["s7_optional_speaker_work"] = "BYPASSED_NO_SPEAKER_MODELS_OR_LANE"
            elif self._model_bundle is None:
                models, asr = self._prepare_native_models(False)
            else:
                models, asr = self._model_bundle.acquire(self.config)
                self._bundle_acquired = True
            if self._research_profile is not None:
                self._emit("research_models_ready", 0.0, {"model_load_elapsed_sec": time.perf_counter() - model_load_started, "session_elapsed_sec": time.perf_counter() - self._started_monotonic, "capture_not_started": True, "modeled_availability_origin": "source start after model loading; warm-resident serial lanes, loading excluded and separately measured"})
                if self._model_bundle is not None:
                    self._emit("research_resident_bundle", 0.0, {"bundle_admission_elapsed_sec": getattr(self._model_bundle, "admission_elapsed_sec", None),
                        "session_index": getattr(self._model_bundle, "sessions_created", None), "fresh_asr_stream": True,
                        "fresh_tracker_scheduler_endpoint_state": True, "weights_reused": True,
                        "admitted_files_must_remain_immutable": True})
            self._source = source
            if self._s6d is not None and self._s6d.text_delivery:
                from .research_s6d import BoundedWorker
                self._s6d_punctuation = BoundedWorker("edge-s6d-punctuation", self._s6d_punctuate,
                    self._s6d.punctuation_queue_capacity)
            self._threads = [
                threading.Thread(target=self._asr_loop, args=(asr,), name="edge-asr", daemon=True),
            ]
            if not caption_only:
                self._threads.append(threading.Thread(target=self._speaker_loop, args=(models,), name="edge-speaker", daemon=True))
            else:
                # No synthetic voice evidence: explicitly close the absent optional lane.
                self._scheduler_advance("speaker", float("inf"), 0.0)
            # Publish startup before any worker can report a terminal failure.
            self._state = "RUNNING"
            self._emit("session_started", 0.0, {"state": self._state})
            for thread in self._threads:
                thread.start()
            source.start()
            watcher = threading.Thread(target=self._watch_session, name="edge-session-watcher", daemon=True)
            self._finalization_thread = watcher
            self._threads.append(watcher)
            watcher.start()
            return self._session_dir
        except Exception as exc:
            self._fail(f"session launch failed: {exc}")
            cleanup = threading.Thread(
                target=self._watch_session,
                name="edge-failed-launch-cleanup",
                daemon=True,
            )
            self._finalization_thread = cleanup
            self._threads.append(cleanup)
            cleanup.start()
            raise

    def pause(self) -> None:
        if self._source is None or self._state != "RUNNING":
            return
        self._source.pause()
        self._state = "PAUSED"
        self._emit("session_paused", self._source_time(), {"intentional_audio_exclusion": True})

    def resume(self) -> None:
        if self._source is None or self._state != "PAUSED":
            return
        self._source.resume()
        self._state = "RUNNING"
        self._emit("session_resumed", self._source_time(), {})

    def stop(self) -> None:
        if self._state in {"IDLE", "COMPLETED", "FAILED"}:
            return
        self._state = "STOPPING"
        self._stop_event.set()
        if self._source is not None:
            self._source.stop()

    def _admit_research_gallery(self, gallery, maximum_profiles):
        """Baseline admission; model-specific adapters override this boundary."""
        from .research_identity_v3 import ResearchGallery
        admitted = gallery if isinstance(gallery, ResearchGallery) else ResearchGallery(
            gallery, self.config.asset("redimnet2_b2_fp32").sha256, maximum_profiles)
        if admitted.receipt["backend_sha256"] != self.config.asset("redimnet2_b2_fp32").sha256:
            raise ValueError("resident research gallery has a different backend")
        if admitted.receipt["loaded_count"] > maximum_profiles:
            raise ValueError("resident research gallery exceeds this profile's configured count bound")
        return admitted

    def _asr_loop(self, asr: SherpaStream) -> None:
        assert self._journal is not None
        cursor = 0
        read_size = round(self.config.sample_rate * self.config.journal_read_ms / 1000)
        last_partial = ""
        pending = np.empty(0, dtype=np.float32)
        last_display_sec = float("-inf")
        utterance_start_sec = 0.0
        advisor = None
        if self._research_v2 and self._research_profile.xvf.mode in {"endpoint_only", "both"}:
            from .research_profiles import EndpointAdvisorV2
            advisor = EndpointAdvisorV2(self._research_profile)
        elif self._research_profile is not None and "advisory" in self._research_profile.xvf.mode:
            from .research_profiles import EndpointAdvisor
            advisor = EndpointAdvisor(self._research_profile)
        try:
            while True:
                if self._research_v3 and self._state == "FAILED":
                    raise RuntimeError("S6C ASR lane aborts after session failure")
                audio = self._journal.read(cursor, read_size)
                if audio.size:
                    cursor += int(audio.size)
                    pending = np.concatenate((pending, audio))
                    while pending.size >= read_size:
                        if self._research_v3 and self._state == "FAILED":
                            raise RuntimeError("S6C ASR dispatch aborts after session failure")
                        block, pending = pending[:read_size], pending[read_size:]
                        source_sec = (cursor - pending.size) / self.config.sample_rate
                        if self.config.input_gain != 1.0:
                            block = block * np.float32(self.config.input_gain)
                        decode_started = time.perf_counter()
                        if self._s7_trace is not None and self._s7.instrumentation == "full":
                            self._s7_trace.record("asr_dispatch_start", source_end_sec=source_sec,
                                source_start_sec=source_sec - block.size / self.config.sample_rate,
                                producer_cursor_sec=self._source_time(), model_start_monotonic_sec=decode_started)
                        text, endpoint = asr.accept(block)
                        if self._s7_trace is not None and self._s7.instrumentation == "full":
                            self._s7_trace.record("asr_dispatch_end", source_end_sec=source_sec,
                                producer_cursor_sec=self._source_time(), model_start_monotonic_sec=decode_started,
                                model_end_monotonic_sec=time.perf_counter(), decode_ms=asr.decode_ms)
                        if self._research_profile is not None:
                            self._research_asr_available_sec = max(self._research_asr_available_sec, source_sec) + asr.decode_ms / 1000.0
                        native_endpoint = endpoint
                        advisory_endpoint = False
                        advisor_sec = 0.0
                        if advisor is not None:
                            advisor_started = time.perf_counter()
                            observation = self._spatial_provider.evidence(source_sec - block.size / self.config.sample_rate, source_sec)
                            advisory_endpoint = advisor.observe(observation, source_sec, float(np.sqrt(np.mean(np.square(block), dtype=np.float64))), block.size / self.config.sample_rate, utterance_start_sec)
                            endpoint = endpoint or advisory_endpoint
                            advisor_sec = time.perf_counter() - advisor_started
                            if self._research_v2:
                                self._research_asr_available_sec += advisor_sec
                        if self._research_profile is not None:
                            self._emit("research_asr_dispatch", source_sec, {"source_start_sec": source_sec - block.size / self.config.sample_rate, "source_end_sec": source_sec, "receptive_start_sec": utterance_start_sec, "available_source_cursor_sec": source_sec, "modeled_available_at_sec": self._research_asr_available_sec, "availability_method": "serial lane max(previous available, input end) + measured compute; modeled, not calibrated live latency", "compute_ms": asr.decode_ms, "compute_started_elapsed_sec": decode_started - self._started_monotonic, "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic, "native_endpoint": native_endpoint, "advisory_endpoint": advisory_endpoint, "reset_requested": endpoint})
                        self._telemetry["asr_cursor_sec"] = source_sec
                        self._telemetry["asr_lag_sec"] = max(0.0, self._journal.duration_sec - source_sec)
                        if text and text != last_partial and source_sec - last_display_sec >= self.config.partial_display_min_interval_sec:
                            self._transcript_event(text, source_sec, final=False, utterance=asr.utterance_index, decode_ms=asr.decode_ms)
                            last_partial = text
                            last_display_sec = source_sec
                        if endpoint:
                            reset_started = time.perf_counter()
                            final = asr.reset_endpoint()
                            if self._research_v2:
                                reset_sec = time.perf_counter() - reset_started
                                self._research_asr_available_sec += reset_sec
                                self._emit("research_asr_reset", source_sec, {"compute_ms": reset_sec * 1000, "available_at_sec": self._research_asr_available_sec, "native_endpoint": native_endpoint, "advisory_endpoint": advisory_endpoint, "advisor": getattr(advisor, "last_status", None)})
                            if final:
                                self._publish_final(asr, final, source_sec, asr.utterance_index - 1, asr.decode_ms)
                            last_partial = ""
                            utterance_start_sec = source_sec
                            self._research_utterance_start_sec = source_sec
                        if self._research_v2:
                            self._scheduler_advance("asr", source_sec, self._research_asr_available_sec)
                            self._emit("research_asr_full_dispatch_cost", source_sec, {"source_start_sec": source_sec - block.size / self.config.sample_rate,
                                "source_end_sec": source_sec, "decode_compute_ms": asr.decode_ms,
                                "advisor_compute_ms": advisor_sec * 1000.0, "advisor": getattr(advisor, "last_status", None),
                                "full_dispatch_elapsed_ms": (time.perf_counter() - decode_started) * 1000.0,
                                "modeled_available_at_sec": self._research_asr_available_sec,
                                "policy_export_in_full_elapsed_not_shared_clock": True})
                elif self._journal.finished and cursor >= self._journal.committed_samples:
                    break
            if pending.size:
                if self.config.input_gain != 1.0:
                    pending = pending * np.float32(self.config.input_gain)
                asr.accept(pending)
                if self._research_profile is not None:
                    source_sec = cursor / self.config.sample_rate
                    self._research_asr_available_sec = max(self._research_asr_available_sec, source_sec) + asr.decode_ms / 1000.0
                    self._emit("research_asr_tail_dispatch", source_sec, {"source_start_sec": source_sec - pending.size / self.config.sample_rate, "source_end_sec": source_sec, "samples": int(pending.size), "compute_ms": asr.decode_ms, "modeled_available_at_sec": self._research_asr_available_sec, "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic})
            self._telemetry["asr_cursor_sec"] = cursor / self.config.sample_rate
            self._telemetry["asr_lag_sec"] = 0.0
            drain_started = time.perf_counter()
            final = asr.finish()
            drain_ms = (time.perf_counter() - drain_started) * 1000.0
            if self._research_profile is not None:
                self._research_asr_available_sec = max(self._research_asr_available_sec, cursor / self.config.sample_rate) + drain_ms / 1000.0
                self._emit("research_asr_drain", cursor / self.config.sample_rate, {"source_end_sec": cursor / self.config.sample_rate, "synthetic_right_padding_sec": 0.66, "padding_is_observed_audio": False, "compute_ms": drain_ms, "modeled_available_at_sec": self._research_asr_available_sec, "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic})
            if final:
                self._publish_final(asr, final, cursor / self.config.sample_rate, asr.utterance_index,
                    drain_ms if self._research_profile is not None else asr.decode_ms)
        except Exception as exc:
            self._fail(f"ASR lane failed: {exc}")
        finally:
            if self._research_v2 and self._scheduler is not None:
                self._scheduler_advance("asr", float("inf"), self._research_asr_available_sec)

    def _speaker_loop(self, models: SpeakerModels) -> None:
        if self._research_v3:
            from .research_evidence_v3 import run_speaker_lane_v3
            return run_speaker_lane_v3(self, models)
        if self._research_v2:
            return self._speaker_loop_v2(models)
        assert self._journal is not None
        cursor = 0
        read_size = round(self.config.sample_rate * self.config.embedding_hop_sec)
        segmentation_hop = round(self.config.sample_rate * self.config.segmentation_hop_sec)
        segmentation_window = round(self.config.sample_rate * self.config.segmentation_window_sec)
        embedding_window = round(self.config.sample_rate * self.config.embedding_window_sec)
        rolling = np.empty(0, dtype=np.float32)
        pending = np.empty(0, dtype=np.float32)
        since_segment = 0
        speech = False
        overlap = False
        speaker_available_sec = 0.0
        tracker = SpeakerTracker(
            self.config,
            ProfileStore(
                self.config.profile_root,
                expected_backend_sha256=self.config.asset("redimnet2_b2_fp32").sha256,
            ),
        )
        research_tracker = None
        if self._research_profile is not None and self._research_profile.tracker.mode != "baseline":
            from dataclasses import asdict
            from .research_tracking import ResearchTracker, TrackingConfig
            values = asdict(self._research_profile.tracker)
            values = {key: value for key, value in values.items() if not key.startswith("identity_")}
            research_tracker = ResearchTracker(TrackingConfig(**values))
        try:
            while True:
                audio = self._journal.read(cursor, read_size)
                if audio.size:
                    cursor += int(audio.size)
                    pending = np.concatenate((pending, audio))
                    while pending.size >= read_size:
                        block, pending = pending[:read_size], pending[read_size:]
                        source_sec = (cursor - pending.size) / self.config.sample_rate
                        if self.config.input_gain != 1.0:
                            block = block * np.float32(self.config.input_gain)
                        rolling = np.concatenate((rolling, block))[-segmentation_window:]
                        since_segment += int(block.size)
                        if since_segment >= segmentation_hop:
                            since_segment %= segmentation_hop
                            padded = np.pad(rolling, (segmentation_window - rolling.size, 0))
                            views = models.segment(padded)
                            speaker_available_sec = max(speaker_available_sec, source_sec) + models.last_segment_ms / 1000.0
                            from .research_profiles import segmentation_gate, spatial_is_fresh
                            assist = 0.0
                            if self._research_profile is not None and "soft_energy" in self._research_profile.xvf.mode:
                                observation = self._spatial_provider.evidence(max(0.0, source_sec - self.config.segmentation_hop_sec), source_sec)
                                if spatial_is_fresh(observation, speaker_available_sec, self._research_profile) and observation.energy is not None and np.isfinite(observation.energy) and observation.energy > 0:
                                    assist = self._research_profile.xvf.speech_assist_delta
                            gate = segmentation_gate(views, self.config, speech, speech_assist_delta=assist)
                            speech, overlap = gate["speech"], gate["overlap"]
                            speech_fraction, overlap_fraction = gate["speech_fraction"], gate["overlap_fraction"]
                            with self._speaker_lock:
                                self._overlap_active = overlap
                                if self._research_profile is not None:
                                    self._research_segmentation_history.append((source_sec, overlap, speaker_available_sec))
                            self._emit("segmentation", source_sec, {"speech": speech, "overlap": overlap, "speech_fraction": speech_fraction, "overlap_fraction": overlap_fraction, "compute_ms": models.last_segment_ms})
                            if self._research_profile is not None:
                                self._emit("research_segmentation", source_sec, {**gate, "source_start_sec": max(0.0, source_sec - self.config.segmentation_hop_sec), "source_end_sec": source_sec, "receptive_start_sec": max(0.0, source_sec - 10.0), "receptive_end_sec": source_sec, "left_padding_sec": max(0.0, 10.0 - source_sec), "available_source_cursor_sec": source_sec, "modeled_available_at_sec": speaker_available_sec, "compute_ms": models.last_segment_ms, "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic, "frame_step_sec": 0.016875, "frame_duration_sec": 0.0619375, "local_speakers_are_per_invocation": True})
                        rms = float(np.sqrt(np.mean(np.square(block), dtype=np.float64)))
                        if speech and not overlap and rolling.size >= embedding_window and rms >= self.config.minimum_rms:
                            vector = models.embed(rolling[-embedding_window:])
                            speaker_available_sec = max(speaker_available_sec, source_sec) + models.last_embed_ms / 1000.0
                            research_decision = None
                            if research_tracker is not None:
                                from .research_tracking import decision_to_speaker
                                observation = self._spatial_provider.evidence(max(0.0, source_sec - self.config.embedding_window_sec), source_sec) if self._spatial_provider is not None and self._research_profile.xvf.mode != "none" else None
                                research_decision = research_tracker.update(vector, max(0.0, source_sec - self.config.embedding_window_sec), source_sec, speaker_available_sec, spatial=observation, speech=speech, overlap=overlap)
                                decision = decision_to_speaker(research_decision)
                            else:
                                decision = tracker.update(vector, source_sec)
                            with self._speaker_lock:
                                self._current_speaker = decision
                                if self._research_profile is not None:
                                    self._research_speaker_history.append((source_sec, decision, overlap, speaker_available_sec))
                            self._emit("speaker_decision", source_sec, {**decision.to_jsonable(), "embedding_compute_ms": models.last_embed_ms, "spatial_evidence": SpatialEvidence(max(0.0, source_sec - self.config.embedding_window_sec), source_sec).to_jsonable()})
                            if self._research_profile is not None:
                                self._emit("research_embedding", source_sec, {"source_start_sec": max(0.0, source_sec - self.config.embedding_window_sec), "source_end_sec": source_sec, "receptive_start_sec": max(0.0, source_sec - self.config.embedding_window_sec), "receptive_end_sec": source_sec, "available_source_cursor_sec": source_sec, "modeled_available_at_sec": speaker_available_sec, "availability_method": "serial speaker lane with segmentation and embedding compute charged", "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic, "compute_ms": models.last_embed_ms, "block_rms": rms, "normalized_embedding": vector.tolist(), "decision": research_decision or decision.to_jsonable()})
                        self._telemetry["speaker_cursor_sec"] = source_sec
                        self._telemetry["speaker_analyzed_through_sec"] = source_sec
                        self._telemetry["speaker_lag_sec"] = max(0.0, self._journal.duration_sec - source_sec)
                elif self._journal.finished and cursor >= self._journal.committed_samples:
                    break
            self._telemetry["speaker_cursor_sec"] = cursor / self.config.sample_rate
            self._telemetry["speaker_unanalyzed_short_tail_sec"] = pending.size / self.config.sample_rate
            self._telemetry["speaker_lag_sec"] = 0.0
        except Exception as exc:
            self._fail(f"speaker lane failed: {exc}")

    def _speaker_loop_v2(self, models):
        from .research_profiles import segmentation_gate
        from .research_scheduler import EmbeddingAdmission
        assert self._journal is not None and self._scheduler is not None
        cursor = 0
        size = round(self.config.sample_rate * self.config.embedding_hop_sec)
        seg_hop = round(self.config.sample_rate * self.config.segmentation_hop_sec)
        rolling = np.empty(0, dtype=np.float32)
        pending = np.empty(0, dtype=np.float32)
        since_segment = 0
        speech = overlap = False
        ready = 0.0
        seg_serial = embed_serial = 0
        admission = EmbeddingAdmission(self._research_profile)
        try:
            while True:
                audio = self._journal.read(cursor, size)
                if audio.size:
                    cursor += int(audio.size)
                    pending = np.concatenate((pending, audio))
                    while pending.size >= size:
                        block_started = time.perf_counter()
                        block, pending = pending[:size], pending[size:]
                        end = (cursor - pending.size) / self.config.sample_rate
                        if self.config.input_gain != 1.0:
                            block = block * np.float32(self.config.input_gain)
                        rolling = np.concatenate((rolling, block))[-160000:]
                        since_segment += int(block.size)
                        segment_ms = 0.0
                        if since_segment >= seg_hop:
                            since_segment %= seg_hop
                            segment_call_started = time.perf_counter()
                            views = models.segment(np.pad(rolling, (160000 - rolling.size, 0)), include_posteriors=True)
                            segment_ms = models.last_segment_ms
                            segment_api_sec = time.perf_counter() - segment_call_started
                            post_started = time.perf_counter()
                            gate = segmentation_gate(views, self.config, speech)
                            speech, overlap = gate["speech"], gate["overlap"]
                            admission.segmentation(views, end)
                            post_sec = time.perf_counter() - post_started
                            ready = max(ready, end) + segment_api_sec + post_sec
                            seg_serial += 1
                            payload = {**gate, "source_start_sec": max(0.0, end - self.config.segmentation_hop_sec),
                                "source_end_sec": end, "receptive_start_sec": max(0.0, end - 10.0), "receptive_end_sec": end,
                                "left_padding_sec": max(0.0, 10.0 - end), "modeled_available_at_sec": ready,
                                "compute_ms": segment_ms, "postprocess_compute_ms": post_sec * 1000.0,
                                "model_api_elapsed_ms": segment_api_sec * 1000.0,
                                "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic,
                                "frame_step_sec": .016875, "frame_duration_sec": .0619375,
                                "speech_frames": np.asarray(views["speech"]).tolist(), "overlap_frames": np.asarray(views["overlap"]).tolist(),
                                "speech_probability_frames": np.asarray(views["speech_probability"]).tolist(),
                                "overlap_probability_frames": np.asarray(views["overlap_probability"]).tolist()}
                            self._emit("research_segmentation", end, payload)
                            self._emit("segmentation", end, {**gate, "compute_ms": segment_ms})
                            self._scheduler.push({"kind": "segmentation", "event_id": f"seg:{seg_serial:08d}",
                                "source_start_sec": payload["source_start_sec"], "source_end_sec": end,
                                "available_at_sec": ready, "speech": speech, "overlap": overlap}, lane="speaker")
                        gate_started = time.perf_counter()
                        observation = self._spatial_provider.evidence(max(0.0, end - self.config.embedding_window_sec), end) if self._research_profile.embedding.cadence_cues_enabled else None
                        embedding_size, diagnostic = admission.candidate(rolling, block, end, speech, overlap, observation)
                        gate_sec = time.perf_counter() - gate_started
                        ready = max(ready, end) + gate_sec
                        self._emit("research_embedding_admission", end, {**diagnostic, "compute_ms": gate_sec * 1000.0, "modeled_available_at_sec": ready})
                        embed_ms = 0.0
                        if embedding_size is not None:
                            embed_call_started = time.perf_counter()
                            vector = models.embed(rolling[-embedding_size:])
                            embed_ms = models.last_embed_ms
                            embed_api_sec = time.perf_counter() - embed_call_started
                            ready += embed_api_sec
                            admission.admitted(vector, end)
                            embed_serial += 1
                            start = end - embedding_size / self.config.sample_rate
                            self._emit("research_embedding", end, {"source_start_sec": start, "source_end_sec": end,
                                "receptive_start_sec": start, "receptive_end_sec": end,
                                "available_source_cursor_sec": end, "modeled_available_at_sec": ready,
                                "availability_method": "serial neural+postprocess+gate lane; scheduler policy cost separate",
                                "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic,
                                "compute_ms": embed_ms, "normalized_embedding": vector.tolist(), "admission": diagnostic,
                                "model_api_elapsed_ms": embed_api_sec * 1000.0,
                                "speech": speech, "overlap": overlap, "evidence_event_id": f"embedding:{embed_serial:08d}"})
                            self._scheduler.push({"kind": "embedding", "event_id": f"embedding:{embed_serial:08d}",
                                "vector": vector.tolist(), "source_start_sec": start, "source_end_sec": end,
                                "available_at_sec": ready, "speech": speech, "overlap": overlap}, lane="speaker")
                        before_scheduler = time.perf_counter()
                        self._scheduler_advance("speaker", end, ready)
                        self._emit("research_speaker_dispatch_cost", end, {"source_start_sec": end - size / self.config.sample_rate,
                            "source_end_sec": end, "segment_compute_ms": segment_ms, "embedding_compute_ms": embed_ms,
                            "gate_compute_ms": gate_sec * 1000.0,
                            "scheduler_dispatch_ms": (time.perf_counter() - before_scheduler) * 1000.0,
                            "full_dispatch_elapsed_ms": (time.perf_counter() - block_started) * 1000.0,
                            "modeled_available_at_sec": ready})
                        self._telemetry.update(speaker_cursor_sec=end, speaker_analyzed_through_sec=end,
                            speaker_lag_sec=max(0.0, self._journal.duration_sec - end))
                elif self._journal.finished and cursor >= self._journal.committed_samples:
                    break
            self._telemetry.update(speaker_cursor_sec=cursor / self.config.sample_rate,
                speaker_unanalyzed_short_tail_sec=pending.size / self.config.sample_rate, speaker_lag_sec=0.0)
        except Exception as exc:
            self._fail(f"S6B speaker lane failed: {exc}")
        finally:
            self._scheduler_advance("speaker", float("inf"), ready)

    def _scheduler_advance(self, lane, lower_bound, modeled_lane_ready):
        closed = lower_bound == float("inf")
        self._emit("research_scheduler_watermark", self._source_time() if closed else lower_bound,
            {"lane": lane, "lower_bound_sec": None if closed else lower_bound, "lane_closed": closed,
             "modeled_lane_ready_sec": modeled_lane_ready,
             "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic})
        return self._scheduler.advance({lane: lower_bound})

    def _scheduled_event(self, record):
        kind = record["event_type"]
        source_sec = record["source_end_sec"]
        payload = {**record, "modeled_available_at_sec": record.get("modeled_available_at_sec", record["available_at_sec"]),
                   "compute_finished_elapsed_sec": time.perf_counter() - self._started_monotonic}
        if kind == "speaker_decision":
            payload.update(record["decision"])
            if self._s7_observed_clock is not None:
                for key in ("available_at_sec", "input_available_at_sec", "modeled_available_at_sec"):
                    payload[key] = record[key]
        self._emit(kind, source_sec, payload)
        if kind == "transcript_final":
            with (nullcontext() if self._s6d is not None and self._s6d.text_delivery else self._event_lock):
                if self._transcript_handle is not None:
                    self._transcript_handle.write(json.dumps({"schema_version": "edge-labelled-transcript.v3" if self._research_v3 else "edge-labelled-transcript.v2", **payload}, ensure_ascii=False) + "\n")
                if self._readable_transcript_handle is not None:
                    self._readable_transcript_handle.write(f'**{payload["first_final_label"]}:** {payload["display_text"]}\n\n')

    def _write_revised_transcript(self):
        if self._session_dir is None or self._scheduler is None:
            return
        snapshot = self._scheduler.snapshot()
        path = self._session_dir / "latest_labelled_transcript.jsonl"
        with path.open("x", encoding="utf-8") as handle:
            for row in snapshot["utterances"]:
                if row["is_final"]:
                    punctuated = self._s6d_punctuated.get(row["utterance_id"])
                    if punctuated is not None and punctuated["raw_text"] == row["text"]:
                        row = {**row, "display_text": punctuated["text"], "punctuation": punctuated}
                    handle.write(json.dumps({"schema_version": "edge-latest-labelled-transcript.v3" if self._research_v3 else "edge-latest-labelled-transcript.v2", **row}, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _record_punctuation(self, result: dict[str, object]) -> None:
        compute_ms = float(result.get("compute_ms", 0.0))
        if self._research_profile is not None and not (self._s6d is not None and self._s6d.text_delivery):
            self._research_asr_available_sec += compute_ms / 1000.0
        self._telemetry["punctuation_utterances"] = int(
            self._telemetry["punctuation_utterances"]
        ) + 1
        self._telemetry["punctuation_total_ms"] = float(
            self._telemetry["punctuation_total_ms"]
        ) + compute_ms
        self._telemetry["punctuation_max_ms"] = max(
            float(self._telemetry["punctuation_max_ms"]), compute_ms
        )
        terminal_fallback = result.get("terminal_fallback") is not None
        inference_failure = result.get("status") == "fallback"
        if terminal_fallback or inference_failure:
            self._telemetry["punctuation_fallbacks"] = int(
                self._telemetry["punctuation_fallbacks"]
            ) + 1
        if terminal_fallback:
            self._telemetry["punctuation_terminal_fallbacks"] = int(
                self._telemetry["punctuation_terminal_fallbacks"]
            ) + 1
        if inference_failure:
            self._telemetry["punctuation_inference_failures"] = int(
                self._telemetry["punctuation_inference_failures"]
            ) + 1

    def _publish_final(self, asr, text, source_sec, utterance, decode_ms):
        if self._s6d_punctuation is not None:
            self._transcript_event(text, source_sec, final=True, utterance=utterance, decode_ms=decode_ms)
            self._s6d_punctuation.submit((asr, text, source_sec, utterance))
        else:
            punctuation = asr.punctuate(text)
            self._record_punctuation(punctuation)
            self._transcript_event(text, source_sec, final=True, utterance=utterance, decode_ms=decode_ms, punctuation=punctuation)

    def _s6d_punctuate(self, job):
        asr, text, source_sec, utterance = job
        started = time.perf_counter()
        punctuation = asr.punctuate(text)
        self._s6d_punctuated[f"utterance:{utterance:06d}"] = {**punctuation, "raw_text": text}
        self._record_punctuation(punctuation)
        self._emit("s6d_punctuation_revision", source_sec, {"utterance_id": f"utterance:{utterance:06d}",
            "text": text, "display_text": punctuation["text"], "punctuation": punctuation,
            "compute_started_monotonic_sec": started, "compute_finished_monotonic_sec": time.perf_counter(),
            "changes_raw_words": False})

    def _transcript_event(self, text: str, source_sec: float, *, final: bool, utterance: int, decode_ms: float, punctuation: dict[str, object] | None = None) -> None:
        if self._research_v2:
            self._research_asr_event_serial += 1
            observation = {"kind": "asr", "event_id": f"asr:{self._research_asr_event_serial:08d}",
                "utterance_id": f"utterance:{utterance:06d}", "source_start_sec": self._research_utterance_start_sec,
                "source_end_sec": source_sec, "available_at_sec": self._research_asr_available_sec,
                "text": text, "final": final, "display_text": str(punctuation["text"]) if final and punctuation else format_partial_display(text),
                "punctuation": punctuation, "asr_decode_ms": decode_ms}
            self._emit("research_asr_observation", source_sec, observation)
            if self._s6d is not None and self._s6d.text_delivery:
                observed_text = {}
                if self._s7_observed_clock is not None:
                    now = self._s7_observed_clock.relative()
                    if now < source_sec:
                        raise ValueError("Observed raw text precedes source support; no clock clamp")
                    observed_text = {"available_at_sec": now, "observed_text_ready_at_sec": now,
                        "modeled_available_at_sec": observation["available_at_sec"],
                        "availability_clock": "observed_text_publication_before_policy_admission"}
                self._emit("s6d_text_ready", source_sec, {**observation, **observed_text, "speaker": "Pending identity",
                    "token_ids": self._s6d_presentation.token_ids(observation["utterance_id"], text, self._research_asr_event_serial),
                    "text_revision_id": observation["event_id"],
                    "token_timing": "untimed hypothesis revision positions; not phonetic alignment",
                    "identity_pending": True, "publication_path": "independent_asr_before_policy"})
            self._scheduler.push(observation, lane="asr")
            return
        with self._speaker_lock:
            decision = self._current_speaker
            overlap_active = self._overlap_active
            if self._research_profile is not None and self._research_profile.tracker.mode != "baseline":
                eligible = [item for item in self._research_speaker_history if item[0] <= source_sec and item[3] <= self._research_asr_available_sec]
                decision = eligible[-1][1] if eligible else None
                eligible_segmentation = [item for item in self._research_segmentation_history if item[0] <= source_sec and item[2] <= self._research_asr_available_sec]
                overlap_active = eligible_segmentation[-1][1] if eligible_segmentation else False
        base_label = decision.display_label if decision is not None else "Speaker_?"
        label = (
            f"{base_label} + overlapping speaker"
            if overlap_active
            else base_label
        )
        payload = {
            "text": text,
            "display_text": (
                str(punctuation["text"])
                if final and punctuation is not None
                else format_partial_display(text)
            ),
            "punctuation": punctuation,
            "is_final": final,
            "utterance_index": utterance,
            "speaker": label,
            "speaker_state": (
                "overlap_uncertain"
                if overlap_active
                else decision.state if decision else "pending"
            ),
            "overlap_detected": overlap_active,
            "asr_decode_ms": decode_ms,
        }
        if self._research_profile is not None:
            payload["modeled_available_at_sec"] = self._research_asr_available_sec
            payload["compute_finished_elapsed_sec"] = time.perf_counter() - self._started_monotonic
            payload["label_revision_of"] = None
            payload["first_display_is_preserved"] = True
        self._emit("transcript_final" if final else "transcript_partial", source_sec, payload)
        if final:
            row = {"schema_version": "edge-labelled-transcript.v1", "source_end_sec": source_sec, **payload}
            with self._event_lock:
                if self._transcript_handle is not None:
                    self._transcript_handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                if self._readable_transcript_handle is not None:
                    self._readable_transcript_handle.write(
                        f'**{label}:** {payload["display_text"]}\n\n'
                    )

    def _source_status(self, kind: str, payload: dict[str, object]) -> None:
        if kind == "source_started" and self._s7_observed_clock is not None:
            self._s7_observed_clock.set_origin(payload["source_epoch_monotonic_sec"])
        if kind == "fatal":
            self._fail(str(payload.get("reason", "audio source failed")), payload)
        else:
            self._emit(kind, self._source_time(), payload)

    def _watch_session(self) -> None:
        # Source completion closes the journal; model lanes then drain their own cursors.
        try:
            while self._journal is not None and not self._journal.finished and self._state not in {"FAILED"}:
                time.sleep(0.1)
            if self._state == "FAILED" and self._source is not None:
                try:
                    self._source.stop()
                except Exception as exc:
                    # A live source can re-raise its already reported input
                    # failure after releasing capture. It must not bypass lane
                    # drainage, recoverable transcript output or writer closure.
                    self._finalization_error = self._finalization_error or exc
                    self._telemetry["failed_source_stop_error"] = str(exc)
            for thread in list(self._threads):
                if thread is threading.current_thread() or thread.name == "edge-session-watcher":
                    continue
                drain_timeout = self._research_profile.runtime.lane_drain_timeout_sec if self._research_v3 else 30.0
                thread.join(timeout=drain_timeout)
                if thread.is_alive():
                    raise TimeoutError(f"session lane {thread.name} did not finish within {drain_timeout:g} seconds")
            if self._research_v2 and self._scheduler is not None:
                self._scheduler.finish()
                if self._s6d_punctuation is not None:
                    self._s6d_punctuation.close()
                self._telemetry["scheduler"] = self._scheduler.snapshot()
                self._write_revised_transcript()
            if isinstance(self._source, MicrophoneSource):
                self._telemetry["portaudio_input_overflows"] = self._source.input_overflow_events
                self._telemetry["raw_capture_reserve_failures"] = self._source.raw_reserve_failures
                self._telemetry["intentional_pause_samples"] = self._source.intentional_pause_samples
            if self._state != "FAILED":
                self._state = "COMPLETED"
                self._emit("session_completed", self._source_time(), {"telemetry": self.telemetry()})
            self._write_summary()
        except Exception as exc:
            self._finalization_error = exc
            try:
                self._fail(f"session finalization failed: {exc}")
            except Exception:
                # A failed event writer must still prevent successful CLI exit.
                self._state = "FAILED"
        finally:
            for worker in (self._s6d_punctuation, self._scheduler.worker if hasattr(self._scheduler, "worker") else None):
                if worker is not None and not worker.closed:
                    try:
                        worker.close()
                    except Exception as exc:
                        self._state = "FAILED"
                        self._finalization_error = self._finalization_error or exc
            if self._s6d_writer is not None:
                try:
                    self._s6d_writer.close()
                except Exception as exc:
                    self._state = "FAILED"
                    self._finalization_error = self._finalization_error or exc
            live_lanes = []
            if self._research_v3:
                for thread in self._threads:
                    if thread is threading.current_thread() or thread.name == "edge-session-watcher":
                        continue
                    if thread.is_alive() and self._state == "FAILED":
                        thread.join(timeout=min(1., self._research_profile.runtime.lane_drain_timeout_sec))
                    if thread.is_alive():
                        live_lanes.append(thread.name)
                self._telemetry["live_lanes_at_finalization"] = live_lanes
                self._telemetry["bundle_retained_due_live_lanes"] = bool(live_lanes and self._bundle_acquired)
            if self._bundle_acquired:
                if not live_lanes:
                    self._model_bundle.release()
                    self._bundle_acquired = False
            handle_close_results = {}
            for attribute in ("_event_handle", "_transcript_handle", "_readable_transcript_handle"):
                handle = getattr(self, attribute)
                try:
                    if handle is not None:
                        handle.close()
                    if self._research_v3:
                        closed = True if handle is None else getattr(handle, "closed", None)
                        handle_close_results[attribute] = {
                            "closed": closed if isinstance(closed, bool) else None,
                            "error": None, "was_opened": handle is not None}
                except Exception as exc:
                    if self._research_v3:
                        handle_close_results[attribute] = {
                            "closed": False, "error": str(exc), "was_opened": handle is not None}
                    if self._finalization_error is None:
                        self._finalization_error = exc
                    self._state = "FAILED"
                finally:
                    setattr(self, attribute, None)
            if self._research_v3 and self._session_dir is not None:
                # Written after lane/lease checks and writer closure, including failures.
                # Earlier session_summary telemetry is not claimed to contain these facts.
                destination = self._session_dir / "session_finalization_v3.json"
                temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
                try:
                    if destination.exists():
                        raise RuntimeError("S6C finalization receipt already exists")
                    receipt = {"schema_version": "edge-session-finalization.v3", "state": self._state,
                        "finished_utc": datetime.now(timezone.utc).isoformat(),
                        "live_lanes_at_finalization": live_lanes,
                        "resident_bundle_lease_retained": bool(self._bundle_acquired),
                        "resident_bundle_reuse_allowed": not bool(live_lanes),
                        "event_and_transcript_handles_closed": all(
                            row["closed"] is True for row in handle_close_results.values()),
                        "handle_close_results": handle_close_results,
                        "lane_drain_timeout_sec": self._research_profile.runtime.lane_drain_timeout_sec,
                        "finalization_error": str(self._finalization_error) if self._finalization_error else None,
                        "source_samples": self._journal.committed_samples if self._journal else 0,
                        "identity_samples": self._identity_journal.committed_samples if self._identity_journal else 0}
                    with temporary.open("x", encoding="utf-8") as handle:
                        json.dump(receipt, handle, indent=2, allow_nan=False)
                        handle.write("\n")
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(temporary, destination)
                except Exception as exc:
                    self._state = "FAILED"
                    if self._finalization_error is None:
                        self._finalization_error = exc

    def wait_for_completion(self, timeout: float = 65.0) -> None:
        """Join the artifact writer before a caller reports successful exit."""
        writer = self._finalization_thread
        if writer is not None:
            if writer is threading.current_thread():
                raise RuntimeError("the session writer cannot join itself")
            writer.join(timeout=timeout)
            if writer.is_alive():
                raise TimeoutError(f"session finalization did not finish within {timeout:g} seconds")
        if self._finalization_error is not None:
            raise RuntimeError(f"session finalization failed: {self._finalization_error}") from self._finalization_error

    def _fail(self, reason: str, detail: dict[str, object] | None = None) -> None:
        if self._state == "FAILED":
            return
        self._state = "FAILED"
        self._stop_event.set()
        if self._source is not None:
            self._source.stop_event.set()
        if self._journal is not None:
            self._journal.finish(reason)
        self._emit("failure", self._source_time(), {"reason": reason, **(detail or {})})

    def _s6d_write_event(self, event):
        if self._event_handle is None:
            raise RuntimeError("S6D event handle closed before writer drained")
        row = event.to_jsonable()
        row["journal_write_monotonic_sec"] = time.perf_counter()
        self._event_handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def publish_s6d_direction(self, observations, speech, identities, available_at_sec):
        """Native integration hook for independently verified beam/voice observations."""
        if self._s6d_presentation is None:
            raise RuntimeError("S6D direction hook is not enabled")
        result = self._s6d_presentation.directions(observations, speech, identities, available_at_sec)
        self._emit("s6d_direction", self._source_time(), result)
        return result

    def record_s6d_consumer_closure(self, consumer):
        """Called by the actual event consumer after finalization and full drain."""
        if self._s6d is None or self._session_dir is None:
            return
        if not self.events.empty() or self._finalization_thread is not None and self._finalization_thread.is_alive():
            raise RuntimeError("consumer closure requires finalization and complete event drainage")
        path = self._session_dir / "s6d_consumer_closure.json"
        if not path.exists():
            path.write_text(json.dumps({"consumer": consumer, "monotonic_sec": time.perf_counter(),
                "state": self._state, "queues": self.telemetry()["s6d"],
                "full_event_consumer_drained": True}, indent=2) + "\n", encoding="utf-8")

    def _emit(self, event_type: str, source_sec: float, payload: dict[str, object]) -> None:
        if self._s6d is not None:
            from copy import deepcopy
            entered = time.perf_counter()
            with self._event_lock:
                acquired = time.perf_counter()
                self._s6d_event_serial += 1
                stamped = {**payload, "publication_monotonic_sec": time.perf_counter(),
                    "publication_sequence": self._s6d_event_serial,
                    "session_id": self._session_dir.name if self._session_dir is not None else None,
                    "publication_source_cursor_sec": self._source_time()}
                if self._s7_observed_clock is not None and "observed_policy_decision_ready_at_sec" in stamped:
                    from .research_s7_policy import publication_freshness
                    stamped.update(publication_freshness(stamped, self._s7_observed_clock.origin,
                        stamped["publication_monotonic_sec"]))
                event = PipelineEvent(event_type, source_sec, stamped)
                if self._s6d_writer is not None:
                    self._s6d_writer.submit(deepcopy(event))
                elif self._event_handle is not None:
                    self._s6d_write_event(event)
                self.events.put(event)
                shown = self._s6d_presentation.consume(event_type, stamped) if self._s6d_presentation is not None else None
                if shown is not None:
                    self._emit("s6d_display", source_sec, shown)
            if self._s7_trace is not None and (self._s7.instrumentation == "full" or event_type in {"s6d_text_ready", "source_started", "session_completed"}):
                self._s7_trace.record("event_publication", event_type=event_type,
                    source_end_sec=source_sec, emit_enter_monotonic_sec=entered,
                    event_lock_acquired_monotonic_sec=acquired,
                    publication_monotonic_sec=stamped["publication_monotonic_sec"],
                    publication_sequence=stamped["publication_sequence"],
                    input_event_id=stamped.get("input_event_id"),
                    observed_policy_decision_ready_at_sec=stamped.get("observed_policy_decision_ready_at_sec"),
                    producer_cursor_sec=stamped["publication_source_cursor_sec"],
                    utterance_id=stamped.get("utterance_id"), event_id=stamped.get("event_id"),
                    emit_complete_monotonic_sec=time.perf_counter())
            return
        event = PipelineEvent(event_type, source_sec, payload)
        self.events.put(event)
        with self._event_lock:
            if self._event_handle is not None:
                self._event_handle.write(json.dumps(event.to_jsonable(), ensure_ascii=False) + "\n")

    def _source_time(self) -> float:
        return self._journal.duration_sec if self._journal is not None else 0.0

    def _s7_model_call(self, kind, source_end_sec, function, *args, **kwargs):
        """Measure real API boundaries, excluding vectors from the timing trace."""
        if self._s7_trace is None or self._s7.instrumentation != "full":
            return function(*args, **kwargs)
        started = time.perf_counter()
        self._s7_trace.record("model_dispatch_start", model_kind=kind, source_end_sec=source_end_sec,
            model_start_monotonic_sec=started, producer_cursor_sec=self._source_time())
        try:
            return function(*args, **kwargs)
        finally:
            self._s7_trace.record("model_dispatch_end", model_kind=kind, source_end_sec=source_end_sec,
                model_start_monotonic_sec=started, model_end_monotonic_sec=time.perf_counter(),
                producer_cursor_sec=self._source_time())

    def telemetry(self) -> dict[str, object]:
        data = dict(self._telemetry)
        if self._s7_trace is not None:
            data["s7_trace"] = self._s7_trace.snapshot()
        if self._s6d is not None:
            data["s6d"] = {"settings": self._s6d.receipt(),
                "event_consumer": self.events.snapshot() if hasattr(self.events, "snapshot") else None,
                "journal": self._s6d_writer.snapshot() if self._s6d_writer else None,
                "punctuation": self._s6d_punctuation.snapshot() if self._s6d_punctuation else None,
                "policy": self._scheduler.worker.snapshot() if hasattr(self._scheduler, "worker") else None}
        data.update({"state": self._state, "source_duration_sec": self._source_time(), "elapsed_wall_sec": max(0.0, time.perf_counter() - self._started_monotonic) if self._started_monotonic else 0.0, "session_dir": str(self._session_dir) if self._session_dir else None})
        return data

    def _write_summary(self) -> None:
        if self._session_dir is None:
            return
        summary = {
            "schema_version": "edge-speech-session.v1",
            "state": self._state,
            "telemetry": self.telemetry(),
            "assets": [{"component_id": asset.component_id, "sha256": asset.sha256} for asset in self.config.assets],
            "scientific_policy": {"identity_score_threshold": self.config.identity_score_threshold, "identity_margin_threshold": self.config.identity_margin_threshold, "identity_minimum_evidence_sec": self.config.identity_minimum_evidence_sec, "clustering_threshold": self.config.clustering_threshold},
            "xvf": {"contract_available": True, "result_effects_enabled": False},
        }
        if self._research_profile is not None:
            summary["research"] = self._research_profile.effective(self.config)
            summary["research"]["telemetry_sha256"] = getattr(self._spatial_provider, "sha256", None)
            summary["xvf"]["result_effects_enabled"] = self._research_profile.xvf.mode != "none"
        if self._research_v3:
            summary["scientific_policy"]["scope"] = "Historical PipelineConfig values; actual S6C anonymous/naming policies are bound in research.profile.tracker and research.profile.identity"
        destination = self._session_dir / "session_summary.json"
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, indent=2))
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(4):
            try:
                os.replace(temporary, destination)
                break
            except OSError as exc:
                if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 3:
                    raise
                # Bounded Windows sharing/access retry; never delete the destination.
                time.sleep(0.01 * (2 ** attempt))
