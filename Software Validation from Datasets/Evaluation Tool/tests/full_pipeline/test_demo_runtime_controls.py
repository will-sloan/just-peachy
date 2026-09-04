from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import threading
import time

import numpy as np
import pytest
import soundfile as sf

from app.full_pipeline.alignment import (
    ALIGNMENT_ALIGNED,
    SpeakerRegion,
    TranscriptSpeakerAligner,
    TranscriptSpan,
)
from app.full_pipeline.asr import ACCEPTED_AUDIO_INTERVAL_PROVENANCE
from app.full_pipeline.audio import (
    DurationLimitedAudioSource,
    FileAudioSource,
    MicrophoneAudioSource,
    PlaybackAudioSource,
    RecordingAudioSource,
    StreamingAudioNormalizer,
)
from app.full_pipeline.clustering import OnlineClusterManager
from app.full_pipeline.coordinator import CoordinatorConfig, StreamingPipelineCoordinator
from app.full_pipeline.enrollment import (
    ProtectedEnrollmentStore,
    RuntimeEnrollmentProfile,
)
from app.full_pipeline import factory as runtime_factory
from app.full_pipeline.identity import (
    FROZEN_IDENTITY_POLICIES,
    IdentityState,
    IdentityTransition,
    SessionIdentityManager,
)
from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.models import ComponentRuntimeIdentity, RawAudioFrame


EVALUATION_ROOT = Path(__file__).resolve().parents[2]


def _raw(sequence: int, samples: int = 1600) -> RawAudioFrame:
    start = (sequence - 1) * samples
    end = start + samples
    return RawAudioFrame(
        frame_id=f"frame_{sequence}",
        sequence=sequence,
        samples=np.full((samples, 1), sequence, dtype=np.float32),
        sample_rate_hz=16_000,
        channel_count=1,
        source_sample_start=start,
        source_sample_end=end,
        audio_start_sec=start / 16_000,
        audio_end_sec=end / 16_000,
        capture_start_monotonic_ns=sequence,
        capture_end_monotonic_ns=sequence,
        capture_start_utc="2026-01-01T00:00:00Z",
        capture_end_utc="2026-01-01T00:00:00Z",
        source_clock_id="test",
        source_clock_type="audio_sample",
    )


def test_file_pause_shifts_realtime_pacing_epoch(tmp_path: Path) -> None:
    audio_path = tmp_path / "paced.wav"
    sf.write(audio_path, np.zeros(3200, dtype=np.float32), 16_000, subtype="FLOAT")
    now = [1_000_000_000]
    source = FileAudioSource(audio_path, pace=1.0, clock_ns=lambda: now[0])
    source.start()
    source.pause()
    rows: list[RawAudioFrame | None] = []
    reader = threading.Thread(target=lambda: rows.append(source.read()))
    reader.start()
    deadline = time.monotonic() + 1.0
    while source._pause_effective_ns is None and time.monotonic() < deadline:
        time.sleep(0.005)
    assert source._pause_effective_ns == 1_000_000_000
    now[0] = 6_000_000_000
    source.resume()
    reader.join(timeout=1.0)
    assert not reader.is_alive()
    assert source._started_ns == 6_000_000_000
    assert rows and rows[0] is not None
    source.stop()


def test_file_stop_is_idempotent_while_read_and_cleanup_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio_path = tmp_path / "concurrent-stop.wav"
    audio_path.write_bytes(b"test-placeholder")
    read_started = threading.Event()
    release_read = threading.Event()

    class BlockingSoundFile:
        samplerate = 16_000
        channels = 1

        def __init__(self) -> None:
            self.close_calls = 0
            self._close_lock = threading.Lock()

        def read(
            self, count: int, *, dtype: str, always_2d: bool
        ) -> np.ndarray:
            assert dtype == "float32"
            assert always_2d is True
            read_started.set()
            assert release_read.wait(timeout=2.0)
            return np.zeros((count, 1), dtype=np.float32)

        def close(self) -> None:
            with self._close_lock:
                self.close_calls += 1
                if self.close_calls > 1:
                    raise TypeError("sf_close(None)")

    stream = BlockingSoundFile()
    monkeypatch.setattr(
        "app.full_pipeline.audio.sf.SoundFile",
        lambda *_args, **_kwargs: stream,
    )
    source = FileAudioSource(audio_path, pace=0)
    source.start()
    read_results: list[RawAudioFrame | None] = []
    errors: list[BaseException] = []

    def read_once() -> None:
        try:
            read_results.append(source.read())
        except BaseException as exc:  # pragma: no cover - regression capture
            errors.append(exc)

    def stop_once() -> None:
        try:
            source.stop()
        except BaseException as exc:  # pragma: no cover - regression capture
            errors.append(exc)

    reader = threading.Thread(target=read_once)
    reader.start()
    assert read_started.wait(timeout=1.0)
    stoppers = [threading.Thread(target=stop_once) for _ in range(2)]
    for stopper in stoppers:
        stopper.start()
    assert source._stop.wait(timeout=1.0)
    release_read.set()
    reader.join(timeout=2.0)
    for stopper in stoppers:
        stopper.join(timeout=2.0)

    assert not reader.is_alive()
    assert all(not stopper.is_alive() for stopper in stoppers)
    assert errors == []
    assert read_results == [None]
    assert stream.close_calls == 1
    assert source.read() is None
    assert source.status()["running"] is False


def test_microphone_pause_accounts_dropped_samples_and_discontinuity() -> None:
    streams: list[object] = []

    class InputStream:
        def __init__(self, **kwargs: object) -> None:
            self.callback = kwargs["callback"]
            streams.append(self)

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def close(self) -> None:
            pass

    module = SimpleNamespace(
        query_devices=lambda *_args: {
            "default_samplerate": 16_000,
            "max_input_channels": 1,
        },
        InputStream=InputStream,
    )
    source = MicrophoneAudioSource(
        source_sample_rate_hz=16_000,
        source_channels=1,
        module_importer=lambda _name: module,
    )
    source.start()
    callback = streams[0].callback  # type: ignore[attr-defined]
    callback(np.zeros((1600, 1), dtype=np.float32), 1600, None, None)
    first = source.read(timeout_sec=0.1)
    assert first is not None and first.source_sample_end == 1600

    source.pause()
    callback(np.zeros((1600, 1), dtype=np.float32), 1600, None, None)
    callback(np.zeros((800, 1), dtype=np.float32), 800, None, None)
    assert source.status()["paused_dropped_source_samples_total"] == 2400
    source.resume()
    callback(np.zeros((1600, 1), dtype=np.float32), 1600, None, None)
    resumed = source.read(timeout_sec=0.1)
    assert resumed is not None
    assert resumed.discontinuity_before
    assert resumed.dropped_source_samples_before == 2400
    assert resumed.source_sample_start == 4000
    source.stop()


def test_duration_wrapper_proxies_pause_and_resume() -> None:
    class Source:
        paused = False

        def pause(self) -> None:
            self.paused = True

        def resume(self) -> None:
            self.paused = False

    source = Source()
    limited = DurationLimitedAudioSource(source, 1.0)
    limited.pause()
    assert source.paused
    limited.resume()
    assert not source.paused


def test_playback_is_lazy_forwards_exact_frames_and_proxies_controls() -> None:
    class Source:
        def __init__(self) -> None:
            self.frames = [_raw(1), _raw(2, 800)]
            self.started = False
            self.paused = False

        def start(self) -> None:
            self.started = True

        def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
            del timeout_sec
            return self.frames.pop(0) if self.frames else None

        def pause(self) -> None:
            self.paused = True

        def resume(self) -> None:
            self.paused = False

        def stop(self) -> None:
            self.started = False

        def status(self) -> dict[str, object]:
            return {"running": self.started, "paused": self.paused}

    writes: list[np.ndarray] = []

    class OutputStream:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["samplerate"] == 16_000
            assert kwargs["channels"] == 1
            self.started = False

        def start(self) -> None:
            self.started = True

        def write(self, samples: np.ndarray) -> None:
            assert self.started
            writes.append(samples.copy())

        def stop(self) -> None:
            self.started = False

        def close(self) -> None:
            pass

    imports: list[str] = []

    def importer(name: str) -> object:
        imports.append(name)
        return SimpleNamespace(OutputStream=OutputStream)

    wrapped = PlaybackAudioSource(Source(), module_importer=importer)
    wrapped.start()
    assert imports == []
    first = wrapped.read()
    second = wrapped.read()
    assert first is not None and second is not None
    assert imports == ["sounddevice"]
    np.testing.assert_array_equal(writes[0], first.samples)
    np.testing.assert_array_equal(writes[1], second.samples)
    wrapped.pause()
    assert wrapped.status()["paused"] is True
    wrapped.resume()
    assert wrapped.status()["paused"] is False
    wrapped.stop()


def test_playback_write_failure_propagates() -> None:
    class Source:
        def start(self) -> None:
            pass

        def read(self, timeout_sec: float | None = None) -> RawAudioFrame:
            del timeout_sec
            return _raw(1)

        def stop(self) -> None:
            pass

        def status(self) -> dict[str, object]:
            return {}

    class OutputStream:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def start(self) -> None:
            pass

        def write(self, _samples: np.ndarray) -> None:
            raise OSError("playback device failed")

        def stop(self) -> None:
            pass

        def close(self) -> None:
            pass

    wrapped = PlaybackAudioSource(
        Source(),
        module_importer=lambda _name: SimpleNamespace(OutputStream=OutputStream),
    )
    wrapped.start()
    with pytest.raises(OSError, match="playback device failed"):
        wrapped.read()
    wrapped.stop()


def test_recording_source_is_local_opt_in_and_forwards_exact_frames(
    tmp_path: Path,
) -> None:
    class Source:
        def __init__(self) -> None:
            self.frames = [_raw(1), _raw(2, 800)]
            self.started = False

        def start(self) -> None:
            self.started = True

        def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
            del timeout_sec
            return self.frames.pop(0) if self.frames else None

        def stop(self) -> None:
            self.started = False

        def status(self) -> dict[str, object]:
            return {"running": self.started}

    path = tmp_path / "private" / "source.wav"
    wrapped = RecordingAudioSource(Source(), path)
    wrapped.start()
    forwarded = [wrapped.read(), wrapped.read()]
    wrapped.stop()

    recorded, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    assert sample_rate == 16_000
    expected = np.concatenate([row.samples for row in forwarded if row is not None])
    np.testing.assert_array_equal(recorded, expected)
    assert wrapped.status()["input_recording_upload_performed"] is False
    with pytest.raises(FileExistsError):
        wrapped.start()


def test_file_runtime_playback_is_explicit_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio_path = tmp_path / "input.wav"
    sf.write(audio_path, np.zeros(1600, dtype=np.float32), 16_000, subtype="FLOAT")
    monkeypatch.setattr(
        runtime_factory,
        "_build",
        lambda **kwargs: kwargs["source"],
    )
    default_source = runtime_factory.build_file_runtime(
        pipeline_id="unused_by_fake_build",
        input_path=audio_path,
    )
    assert isinstance(default_source, FileAudioSource)
    assert default_source.pace == 0.0

    playback_source = runtime_factory.build_file_runtime(
        pipeline_id="unused_by_fake_build",
        input_path=audio_path,
        realtime=True,
        play_audio=True,
    )
    assert isinstance(playback_source, PlaybackAudioSource)
    assert isinstance(playback_source.source, FileAudioSource)
    assert playback_source.source.pace == 0.0


class _ControlledSource:
    def __init__(self) -> None:
        self._control = threading.Condition()
        self.started = threading.Event()
        self.paused = False
        self.stopped = False
        self.sequence = 0

    def start(self) -> None:
        with self._control:
            self.stopped = False
            self.started.set()

    def read(self, timeout_sec: float | None = None) -> RawAudioFrame | None:
        del timeout_sec
        with self._control:
            while self.paused and not self.stopped:
                self._control.wait(timeout=0.05)
            if self.stopped:
                return None
        time.sleep(0.01)
        with self._control:
            if self.stopped:
                return None
            self.sequence += 1
            return _raw(self.sequence)

    def pause(self) -> None:
        with self._control:
            self.paused = True

    def resume(self) -> None:
        with self._control:
            self.paused = False
            self._control.notify_all()

    def stop(self) -> None:
        with self._control:
            self.stopped = True
            self.paused = False
            self._control.notify_all()

    def status(self) -> dict[str, object]:
        with self._control:
            return {"running": not self.stopped, "paused": self.paused}


class _FakeAsr:
    def __init__(self) -> None:
        self.state = "created"

    def start(self, _session_id: str) -> None:
        self.state = "running"

    def accept_audio(self, _frame: object) -> tuple[object, ...]:
        return ()

    def finalize(self, _reason: str) -> tuple[object, ...]:
        self.state = "finalized"
        return ()

    def reset(self, _reason: str) -> tuple[object, ...]:
        return ()

    def status(self) -> dict[str, object]:
        return {"state": self.state}

    def close(self) -> None:
        self.state = "closed"


class _FakeSegmenter:
    algorithmic_lookahead_sec = 5.0

    def start(self, _session_id: str) -> None:
        pass

    def accept_audio(self, _frame: object) -> tuple[object, ...]:
        return ()

    def finalize(self) -> tuple[object, ...]:
        return ()

    def status(self) -> dict[str, object]:
        return {"state": "ready"}

    def close(self) -> None:
        pass


class _UnusedEmbedder:
    def start(self, _session_id: str) -> None:
        pass

    def status(self) -> dict[str, object]:
        return {"state": "ready"}

    def close(self) -> None:
        pass


def _coordinator(tmp_path: Path, source: _ControlledSource) -> StreamingPipelineCoordinator:
    matrix = FullPipelineMatrix(
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml",
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml",
    )
    selection = matrix.resolve("fullpipe_v1_ao_dr_ir")
    families = {
        "capture",
        "asr",
        "segmentation",
        "diarization",
        "clustering",
        "speaker_embedding",
        "transcript",
        "telemetry",
        "pipeline",
    }
    identities = {
        key: ComponentRuntimeIdentity(
            component_family=(
                "speaker_matching"
                if key == "speaker_matching"
                else key
                if key in families
                else "pipeline"
            ),
            backend_id=key,
            backend_config_id=key,
            backend_config_sha256="0" * 64,
            pipeline_config_sha256=selection.pipeline_config_sha256,
            model_id=None,
            model_asset_sha256s=(),
        )
        for key in (*sorted(families), "speaker_matching")
    }
    embedder = _UnusedEmbedder()
    return StreamingPipelineCoordinator(
        config=CoordinatorConfig(
            session_id="control_test",
            recording_id="controlled",
            output_root=tmp_path,
            telemetry_enabled=False,
        ),
        selection=selection,
        source=source,
        normalizer=StreamingAudioNormalizer(),
        asr=_FakeAsr(),
        segmenter=_FakeSegmenter(),
        diarization_embedder=embedder,
        cluster_manager=OnlineClusterManager(),
        identity_embedder=embedder,
        enrollment_store=ProtectedEnrollmentStore(tmp_path / "enrollment"),
        identity_manager=SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H2"]),
        transcript_aligner=TranscriptSpeakerAligner("transcript:controls"),
        identities=identities,
        resource_monitor=None,
    )


def test_coordinator_pause_resume_and_graceful_user_stop(tmp_path: Path) -> None:
    source = _ControlledSource()
    coordinator = _coordinator(tmp_path, source)
    results: list[object] = []
    runner = threading.Thread(target=lambda: results.append(coordinator.run()))
    runner.start()
    assert source.started.wait(timeout=1.0)
    deadline = time.monotonic() + 2.0
    while coordinator.status()["counts"]["audio_frames"] < 2:  # type: ignore[index]
        assert time.monotonic() < deadline
        time.sleep(0.01)

    coordinator.request_pause()
    assert coordinator.status()["state"] == "paused"
    assert source.paused
    time.sleep(0.08)
    paused_count = coordinator.status()["counts"]["audio_frames"]  # type: ignore[index]
    time.sleep(0.08)
    assert coordinator.status()["counts"]["audio_frames"] == paused_count  # type: ignore[index]

    coordinator.request_resume()
    assert coordinator.status()["state"] == "running"
    deadline = time.monotonic() + 1.0
    while coordinator.status()["counts"]["audio_frames"] <= paused_count:  # type: ignore[index,operator]
        assert time.monotonic() < deadline
        time.sleep(0.01)

    coordinator.request_stop()
    runner.join(timeout=3.0)
    assert not runner.is_alive()
    assert results
    result = results[0]
    assert isinstance(result, dict)
    assert result["completion_state"] == "stopped"
    assert coordinator.status()["state"] == "stopped"
    assert coordinator.status()["stop_requested"] is True
    assert coordinator.status()["paused"] is False


def test_final_asr_accepted_interval_aligns_without_inventing_word_times(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path, _ControlledSource())
    coordinator._speaker_regions = [
        SpeakerRegion(
            start_sec=0.0,
            end_sec=1.0,
            anonymous_speaker_id="anon-1",
            speaker_label="Unknown_1",
            source_event_id="anonymous-event-1",
        )
    ]
    coordinator._handle_asr(
        {
            "adapter_event_type": "asr_final",
            "hypothesis_id": "hypothesis:1",
            "utterance_index": 1,
            "revision_number": 0,
            "normalized_text": "hello world",
            "words": ["hello", "world"],
            "token_timestamps_sec": [],
            "audio_consumed_through_sec": 1.0,
            "decode_latency_ms": 1.0,
            "finalization_reason": "input_finished",
            "endpoint_policy_id": "test",
            "is_final": True,
            "accepted_audio_interval": {
                "sample_start_index": 0,
                "sample_end_index": 16000,
                "audio_start_sec": 0.0,
                "audio_end_sec": 1.0,
                "sample_rate_hz": 16000,
                "source_clock_id": "test",
                "source_clock_type": "audio_sample",
                "timing_provenance": ACCEPTED_AUDIO_INTERVAL_PROVENANCE,
                "interval_role": "utterance_input_since_stream_or_reset",
                "word_timestamps_inferred": False,
            },
        },
        None,
    )

    asr_event = coordinator._event_groups["asr"][-1]
    assert asr_event["capture_timestamps"]["sample_start_index"] == 0
    assert asr_event["capture_timestamps"]["sample_end_index"] == 16000
    assert [row["start_sec"] for row in asr_event["words"]] == [None, None]
    assert [row["end_sec"] for row in asr_event["words"]] == [None, None]
    assert "word_timestamps_inferred=false" in asr_event["event_reason"]["detail"]
    assert len(coordinator.transcript_aligner.spans) == 1
    span = coordinator.transcript_aligner.spans[0]
    assert span.start_sec == pytest.approx(0.0)
    assert span.end_sec == pytest.approx(1.0)
    assert span.timing_provenance == "accepted_audio_interval"
    assert span.alignment_status == ALIGNMENT_ALIGNED
    assert span.anonymous_speaker_id == "anon-1"
    assert span.speaker_label == "Unknown_1"


def test_public_identity_and_transcript_use_profile_display_but_keep_opaque_id(
    tmp_path: Path,
) -> None:
    coordinator = _coordinator(tmp_path, _ControlledSource())
    profile = RuntimeEnrollmentProfile(
        profile_id="profile-friendly-v1",
        profile_sha256="a" * 64,
        speaker_id="speaker_opaque_123",
        display_label="Local Friendly Name",
        backend_id="fixture_backend",
        backend_config_sha256="b" * 64,
        model_id="fixture_model",
        model_sha256="c" * 64,
        aggregation_method="normalized_mean",
        aggregation_top_k=None,
        template_artifact=tmp_path / "profile-friendly-v1.npz",
        template_sha256="d" * 64,
        templates=(),
        total_duration_sec=10.0,
        within_enrollment_consistency=0.9,
    )
    coordinator._profiles = (profile,)
    transition = IdentityTransition(
        anonymous_speaker_id="anon-friendly",
        source_time_sec=1.0,
        prior_state=IdentityState.UNKNOWN_INSTANCE,
        state=IdentityState.CONFIRMED_KNOWN,
        prior_speaker_label="Unknown_1",
        speaker_label="speaker_opaque_123",
        unknown_label="Unknown_1",
        known_speaker_id="speaker_opaque_123",
        top1_candidate_id="speaker_opaque_123",
        top1_score=0.9,
        top2_candidate_id=None,
        top2_score=None,
        margin=None,
        confirmation_count=2,
        required_confirmation_count=2,
        evidence_event_ids=("evidence-friendly",),
        decision_reason="known_identity_confirmed",
        hysteresis_applied=False,
        policy_id=coordinator.identity_manager.policy.policy_id,
        calibration_resolved=True,
        revision_number=1,
        changed=True,
    )
    label_event = coordinator._emit_identity_label(
        transition,
        {"event_id": "evidence-friendly", "evidence_duration_sec": 3.0},
        coordinator._threshold_contract(1),
    )

    assert label_event["speaker_label"] == {
        "label_kind": "known",
        "display_label": "Local Friendly Name",
        "enrolled_speaker_id": "speaker_opaque_123",
    }
    coordinator.transcript_aligner.append_spans(
        [
            TranscriptSpan(
                span_id="span-friendly",
                text="hello",
                start_sec=0.0,
                end_sec=1.0,
                state="final",
                timing_provenance="accepted_audio_interval",
                anonymous_speaker_id="anon-friendly",
                speaker_label="Unknown_1",
                alignment_status=ALIGNMENT_ALIGNED,
                source_event_ids=("asr-friendly",),
            )
        ],
        caused_by_event_ids=["asr-friendly"],
        source_time_sec=1.0,
    )
    region = SpeakerRegion(
        start_sec=0.0,
        end_sec=1.0,
        anonymous_speaker_id="anon-friendly",
        speaker_label="Unknown_1",
        source_event_id="anonymous-friendly",
    )
    coordinator._speaker_regions_by_window = {"window-friendly": region}
    coordinator._speaker_regions = [region]
    coordinator._cluster_intervals = {"anon-friendly": [(0.0, 1.0)]}
    coordinator._relabel_transcript(
        "anon-friendly",
        "speaker_opaque_123",
        label_event,
        1.0,
        known_speaker_id="speaker_opaque_123",
    )

    assert coordinator.transcript_aligner.spans[0].speaker_label == (
        "Local Friendly Name"
    )
    assert coordinator._speaker_regions[0].speaker_label == "Local Friendly Name"
    transcript_event = coordinator._event_groups["transcript"][-1]
    assert transcript_event["spans"][0]["speaker_label"] == {
        "label_kind": "known",
        "display_label": "Local Friendly Name",
        "enrolled_speaker_id": "speaker_opaque_123",
    }
    assert coordinator._profiles[0].profile_id == "profile-friendly-v1"
