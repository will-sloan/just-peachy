"""Independent-lane runtime: capture, ASR, and speaker work never share a queue."""

from __future__ import annotations

from datetime import datetime, timezone
import json
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

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self.events: queue.SimpleQueue[PipelineEvent] = queue.SimpleQueue()
        self._event_lock = threading.Lock()
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

    def _begin_session(self, mode: str) -> None:
        if self._enrollment_recorder is not None:
            raise RuntimeError(
                "stop or cancel enrollment recording before starting transcription"
            )
        if self._state not in {"IDLE", "COMPLETED", "FAILED"}:
            raise RuntimeError(f"a session is already {self._state.lower()}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self._session_dir = self.config.session_root / f"edge_{mode}_{stamp}_{uuid.uuid4().hex[:8]}"
        self._session_dir.mkdir(parents=True, exist_ok=False)
        self._journal = AudioJournal(self._session_dir / "audio_spool.pcm16", self.config.sample_rate)
        self._event_handle = (self._session_dir / "events.jsonl").open("a", encoding="utf-8", buffering=1)
        self._transcript_handle = (self._session_dir / "labelled_transcript.jsonl").open("a", encoding="utf-8", buffering=1)
        self._readable_transcript_handle = (self._session_dir / "transcript.md").open("a", encoding="utf-8", buffering=1)
        self._readable_transcript_handle.write("# Session transcript\n\n")
        self._stop_event.clear()
        self._current_speaker = None
        self._overlap_active = False
        self._state = "LOADING"
        self._started_monotonic = time.perf_counter()
        self._telemetry.update({"audio_frames_dropped": 0, "portaudio_input_overflows": 0, "raw_capture_reserve_failures": 0, "asr_cursor_sec": 0.0, "speaker_cursor_sec": 0.0, "speaker_analyzed_through_sec": 0.0, "speaker_unanalyzed_short_tail_sec": 0.0, "asr_lag_sec": 0.0, "speaker_lag_sec": 0.0, "punctuation_utterances": 0, "punctuation_total_ms": 0.0, "punctuation_max_ms": 0.0, "punctuation_fallbacks": 0, "punctuation_terminal_fallbacks": 0, "punctuation_inference_failures": 0})
        self._emit("session_created", 0.0, {"mode": mode, "session_dir": str(self._session_dir), "xvf_result_effects_enabled": False})

    def _launch(self, source: MicrophoneSource | WavSource) -> Path:
        assert self._session_dir is not None
        try:
            models = self._ensure_speaker_models()
            asr = SherpaStream(self.config)
            self._source = source
            self._threads = [
                threading.Thread(target=self._asr_loop, args=(asr,), name="edge-asr", daemon=True),
                threading.Thread(target=self._speaker_loop, args=(models,), name="edge-speaker", daemon=True),
            ]
            for thread in self._threads:
                thread.start()
            source.start()
            watcher = threading.Thread(target=self._watch_session, name="edge-session-watcher", daemon=True)
            watcher.start()
            self._threads.append(watcher)
            self._state = "RUNNING"
            self._emit("session_started", 0.0, {"state": self._state})
            return self._session_dir
        except Exception as exc:
            self._fail(f"session launch failed: {exc}")
            cleanup = threading.Thread(
                target=self._watch_session,
                name="edge-failed-launch-cleanup",
                daemon=True,
            )
            cleanup.start()
            self._threads.append(cleanup)
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

    def _asr_loop(self, asr: SherpaStream) -> None:
        assert self._journal is not None
        cursor = 0
        read_size = round(self.config.sample_rate * self.config.journal_read_ms / 1000)
        last_partial = ""
        pending = np.empty(0, dtype=np.float32)
        try:
            while True:
                audio = self._journal.read(cursor, read_size)
                if audio.size:
                    cursor += int(audio.size)
                    pending = np.concatenate((pending, audio))
                    while pending.size >= read_size:
                        block, pending = pending[:read_size], pending[read_size:]
                        source_sec = (cursor - pending.size) / self.config.sample_rate
                        text, endpoint = asr.accept(block)
                        self._telemetry["asr_cursor_sec"] = source_sec
                        self._telemetry["asr_lag_sec"] = max(0.0, self._journal.duration_sec - source_sec)
                        if text and text != last_partial:
                            self._transcript_event(text, source_sec, final=False, utterance=asr.utterance_index, decode_ms=asr.decode_ms)
                            last_partial = text
                        if endpoint:
                            final = asr.reset_endpoint()
                            if final:
                                punctuation = asr.punctuate(final)
                                self._record_punctuation(punctuation)
                                self._transcript_event(final, source_sec, final=True, utterance=asr.utterance_index - 1, decode_ms=asr.decode_ms, punctuation=punctuation)
                            last_partial = ""
                elif self._journal.finished and cursor >= self._journal.committed_samples:
                    break
            if pending.size:
                asr.accept(pending)
            self._telemetry["asr_cursor_sec"] = cursor / self.config.sample_rate
            self._telemetry["asr_lag_sec"] = 0.0
            final = asr.finish()
            if final:
                punctuation = asr.punctuate(final)
                self._record_punctuation(punctuation)
                self._transcript_event(final, cursor / self.config.sample_rate, final=True, utterance=asr.utterance_index, decode_ms=asr.decode_ms, punctuation=punctuation)
        except Exception as exc:
            self._fail(f"ASR lane failed: {exc}")

    def _speaker_loop(self, models: SpeakerModels) -> None:
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
        tracker = SpeakerTracker(
            self.config,
            ProfileStore(
                self.config.profile_root,
                expected_backend_sha256=self.config.asset("redimnet2_b2_fp32").sha256,
            ),
        )
        try:
            while True:
                audio = self._journal.read(cursor, read_size)
                if audio.size:
                    cursor += int(audio.size)
                    pending = np.concatenate((pending, audio))
                    while pending.size >= read_size:
                        block, pending = pending[:read_size], pending[read_size:]
                        source_sec = (cursor - pending.size) / self.config.sample_rate
                        rolling = np.concatenate((rolling, block))[-segmentation_window:]
                        since_segment += int(block.size)
                        if since_segment >= segmentation_hop:
                            since_segment %= segmentation_hop
                            padded = np.pad(rolling, (segmentation_window - rolling.size, 0))
                            views = models.segment(padded)
                            tail_frames = max(1, round(self.config.segmentation_hop_sec / 0.016875))
                            speech_fraction = float(np.mean(views["speech"][-tail_frames:]))
                            overlap_fraction = float(np.mean(views["overlap"][-tail_frames:]))
                            speech = speech_fraction >= 0.20
                            overlap = overlap_fraction >= 0.20
                            with self._speaker_lock:
                                self._overlap_active = overlap
                            self._emit("segmentation", source_sec, {"speech": speech, "overlap": overlap, "speech_fraction": speech_fraction, "overlap_fraction": overlap_fraction, "compute_ms": models.last_segment_ms})
                        rms = float(np.sqrt(np.mean(np.square(block), dtype=np.float64)))
                        if speech and not overlap and rolling.size >= embedding_window and rms >= self.config.minimum_rms:
                            decision = tracker.update(models.embed(rolling[-embedding_window:]), source_sec)
                            with self._speaker_lock:
                                self._current_speaker = decision
                            self._emit("speaker_decision", source_sec, {**decision.to_jsonable(), "embedding_compute_ms": models.last_embed_ms, "spatial_evidence": SpatialEvidence(max(0.0, source_sec - self.config.embedding_window_sec), source_sec).to_jsonable()})
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

    def _record_punctuation(self, result: dict[str, object]) -> None:
        compute_ms = float(result.get("compute_ms", 0.0))
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

    def _transcript_event(self, text: str, source_sec: float, *, final: bool, utterance: int, decode_ms: float, punctuation: dict[str, object] | None = None) -> None:
        with self._speaker_lock:
            decision = self._current_speaker
            overlap_active = self._overlap_active
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
        if kind == "fatal":
            self._fail(str(payload.get("reason", "audio source failed")), payload)
        else:
            self._emit(kind, self._source_time(), payload)

    def _watch_session(self) -> None:
        # Source completion closes the journal; model lanes then drain their own cursors.
        while self._journal is not None and not self._journal.finished and self._state not in {"FAILED"}:
            time.sleep(0.1)
        if self._state == "FAILED" and self._source is not None:
            self._source.stop()
        for thread in list(self._threads):
            if thread is threading.current_thread() or thread.name == "edge-session-watcher":
                continue
            thread.join(timeout=30.0)
        if isinstance(self._source, MicrophoneSource):
            self._telemetry["portaudio_input_overflows"] = self._source.input_overflow_events
            self._telemetry["raw_capture_reserve_failures"] = self._source.raw_reserve_failures
            self._telemetry["intentional_pause_samples"] = self._source.intentional_pause_samples
        if self._state != "FAILED":
            self._state = "COMPLETED"
            self._emit("session_completed", self._source_time(), {"telemetry": self.telemetry()})
        self._write_summary()
        if self._event_handle is not None:
            self._event_handle.close()
            self._event_handle = None
        if self._transcript_handle is not None:
            self._transcript_handle.close()
            self._transcript_handle = None
        if self._readable_transcript_handle is not None:
            self._readable_transcript_handle.close()
            self._readable_transcript_handle = None

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

    def _emit(self, event_type: str, source_sec: float, payload: dict[str, object]) -> None:
        event = PipelineEvent(event_type, source_sec, payload)
        self.events.put(event)
        with self._event_lock:
            if self._event_handle is not None:
                self._event_handle.write(json.dumps(event.to_jsonable(), ensure_ascii=False) + "\n")

    def _source_time(self) -> float:
        return self._journal.duration_sec if self._journal is not None else 0.0

    def telemetry(self) -> dict[str, object]:
        data = dict(self._telemetry)
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
        (self._session_dir / "session_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
