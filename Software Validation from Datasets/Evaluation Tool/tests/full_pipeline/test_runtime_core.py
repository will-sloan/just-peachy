from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time

import numpy as np
import pytest
import soundfile as sf

from app.full_pipeline.alignment import TranscriptSpeakerAligner
from app.full_pipeline.audio import (
    AudioReadTimeout,
    BoundedFrameQueue,
    FileAudioSource,
    MicrophoneAudioSource,
    StreamingAudioNormalizer,
)
from app.full_pipeline.clustering import OnlineClusterManager
from app.full_pipeline.coordinator import (
    CoordinatorConfig,
    StreamingPipelineCoordinator,
    _AudioHistory,
)
from app.full_pipeline.cli import main as runtime_cli_main
from app.full_pipeline.enrollment import EnrollmentTemplate, ProtectedEnrollmentStore
from app.full_pipeline.events import EventFactory, OrderedJsonlEventSink
from app.full_pipeline.identity import FROZEN_IDENTITY_POLICIES, SessionIdentityManager
from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.models import (
    ComponentRuntimeIdentity,
    NormalizedAudioFrame,
    RawAudioFrame,
)
from app.full_pipeline.runtime_components import NativeASRWorkerAdapter


EVALUATION_ROOT = Path(__file__).resolve().parents[2]


def _raw(sequence: int, samples: int = 1600) -> RawAudioFrame:
    start = (sequence - 1) * samples
    end = start + samples
    return RawAudioFrame(
        frame_id=f"frame_{sequence}",
        sequence=sequence,
        samples=np.zeros((samples, 1), dtype=np.float32),
        sample_rate_hz=16000,
        channel_count=1,
        source_sample_start=start,
        source_sample_end=end,
        audio_start_sec=start / 16000,
        audio_end_sec=end / 16000,
        capture_start_monotonic_ns=sequence,
        capture_end_monotonic_ns=sequence,
        capture_start_utc="2026-01-01T00:00:00Z",
        capture_end_utc="2026-01-01T00:00:00Z",
        source_clock_id="test",
        source_clock_type="audio_sample",
    )


def test_audio_history_preserves_exact_duration_at_float_boundary() -> None:
    start_sec = 4.87096875
    end_sec = 5.370968749999999
    assert round(end_sec * 16000) - round(start_sec * 16000) == 7999

    history = _AudioHistory(sample_rate_hz=16000, maximum_sec=10.0)
    history.add(
        NormalizedAudioFrame(
            frame_id="frame-boundary",
            sequence=1,
            samples=np.arange(160000, dtype=np.float32),
            sample_rate_hz=16000,
            sample_start=0,
            sample_end=160000,
            audio_start_sec=0.0,
            audio_end_sec=10.0,
            source_sample_rate_hz=16000,
            source_channel_count=1,
            source_sample_start=0,
            source_sample_end=160000,
            source_audio_start_sec=0.0,
            source_audio_end_sec=10.0,
            capture_start_monotonic_ns=1,
            capture_end_monotonic_ns=2,
            capture_start_utc="2026-01-01T00:00:00Z",
            capture_end_utc="2026-01-01T00:00:10Z",
            source_clock_id="test",
            source_clock_type="audio_sample",
        )
    )

    samples = history.slice(start_sec, end_sec)
    assert samples is not None
    assert samples.size == 8000


def test_queue_overflow_modes_and_blocked_producer_wakes_on_close() -> None:
    oldest = BoundedFrameQueue(1, drop_policy="drop_oldest")
    assert oldest.put(_raw(1)).accepted
    result = oldest.put(_raw(2))
    assert result.accepted and result.reason == "drop_oldest"
    observed = oldest.get()
    assert observed.sequence == 2
    assert observed.discontinuity_before
    assert observed.dropped_source_samples_before == 1600

    newest = BoundedFrameQueue(1, drop_policy="drop_newest")
    newest.put(_raw(1))
    result = newest.put(_raw(2))
    assert not result.accepted and result.reason == "drop_newest"
    assert newest.get().sequence == 1
    accepted = newest.put(_raw(3))
    assert accepted.accepted
    observed = newest.get()
    assert observed.discontinuity_before
    assert observed.dropped_source_samples_before == 1600

    blocking = BoundedFrameQueue(1, drop_policy="block")
    blocking.put(_raw(1))
    rows: list[object] = []
    thread = threading.Thread(target=lambda: rows.append(blocking.put(_raw(2))))
    thread.start()
    time.sleep(0.03)
    assert thread.is_alive()
    blocking.close()
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert rows[0].closed
    assert rows[0].blocked_sec >= 0.02


def test_drop_oldest_marks_first_survivor_and_preserves_chained_gap() -> None:
    frames = BoundedFrameQueue(3, drop_policy="drop_oldest")
    for sequence in (1, 2, 3):
        assert frames.put(_raw(sequence)).accepted
    assert frames.put(_raw(4)).reason == "drop_oldest"
    assert frames.put(_raw(5)).reason == "drop_oldest"
    first_survivor = frames.get()
    assert first_survivor.sequence == 3
    assert first_survivor.discontinuity_before
    assert first_survivor.dropped_source_samples_before == 3200


def test_microphone_timeout_is_not_end_of_stream() -> None:
    source = MicrophoneAudioSource()
    source._stream = object()
    with pytest.raises(AudioReadTimeout):
        source.read(timeout_sec=0.001)


def test_microphone_source_clock_preserves_quantified_dropped_gap() -> None:
    source = MicrophoneAudioSource()
    source._stream = object()
    source.source_sample_rate_hz = 16_000
    source.source_channels = 1
    source._queue.put_nowait(
        (
            np.zeros((1600, 1), dtype=np.float32),
            1,
            "2026-01-01T00:00:00Z",
            True,
            800,
        )
    )
    first = source.read(timeout_sec=0.01)
    assert first is not None
    assert first.source_sample_start == 800
    assert first.source_sample_end == 2400
    assert first.audio_start_sec == 0.05
    assert first.dropped_source_samples_before == 800


def test_stateful_asr_operations_never_retry_without_audio_replay(
    tmp_path: Path,
) -> None:
    class Worker:
        spec = type("Spec", (), {"component_id": "sherpa_onnx"})()

        def __init__(self) -> None:
            self.calls: list[tuple[str, bool]] = []
            self.payloads: list[tuple[str, object]] = []

        def start(self) -> dict[str, object]:
            return {"component_id": "sherpa_onnx"}

        def call(
            self,
            operation: str,
            _payload: object,
            *,
            retry_on_worker_failure: bool = True,
        ) -> dict[str, object]:
            self.calls.append((operation, retry_on_worker_failure))
            self.payloads.append((operation, _payload))
            return {"updates": []}

        def status(self) -> dict[str, object]:
            return {}

        def shutdown(self) -> None:
            pass

    worker = Worker()
    adapter = NativeASRWorkerAdapter(worker, tmp_path)
    adapter.start("session")
    adapter.accept_audio(StreamingAudioNormalizer().normalize(_raw(1)))
    adapter.finalize("input_finished")
    adapter.reset("discontinuity")
    assert worker.calls == [
        ("start_session", True),
        ("accept_audio", False),
        ("finalize", False),
        ("start_session", True),
    ]
    accept_payload = next(
        payload for operation, payload in worker.payloads if operation == "accept_audio"
    )
    assert accept_payload["source_sample_start"] == 0
    assert accept_payload["source_sample_end"] == 1600
    assert accept_payload["source_clock_id"] == "test"
    assert accept_payload["source_clock_type"] == "audio_sample"


def test_event_factory_orders_concurrent_delivery_and_preserves_timestamps(
    tmp_path: Path,
) -> None:
    ticks = iter((10, 20, 30, 40))
    factory = EventFactory(
        session_id="session",
        pipeline_id="pipeline",
        protocol_version="protocol",
        stream_id="stream",
        recording_id="recording",
        source_clock={
            "clock_id": "clock",
            "clock_type": "audio_sample",
            "sample_rate_hz": 16000,
            "utc_epoch": "2026-01-01T00:00:00Z",
            "monotonic_epoch_ns": 1,
        },
        monotonic_ns=lambda: next(ticks),
        utc_now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    identity = ComponentRuntimeIdentity(
        component_family="pipeline",
        backend_id="test",
        backend_config_id="test",
        backend_config_sha256="0" * 64,
        pipeline_config_sha256="1" * 64,
        model_id=None,
        model_asset_sha256s=(),
    )
    first = factory.create(
        contract_type="PipelineStatusEvent",
        event_type="pipeline_status",
        component_identity=identity,
        capture_timestamps={
            "sample_start_index": 0,
            "sample_end_index": 1600,
            "audio_start_sec": 0.0,
            "audio_end_sec": 0.1,
        },
        payload={},
    )
    second = factory.create(
        contract_type="PipelineStatusEvent",
        event_type="pipeline_status",
        component_identity=identity,
        capture_timestamps={
            "sample_start_index": 1600,
            "sample_end_index": 3200,
            "audio_start_sec": 0.1,
            "audio_end_sec": 0.2,
        },
        payload={},
    )
    sink = OrderedJsonlEventSink(tmp_path / "events.jsonl")
    sink.emit(second)
    sink.emit(first)
    sink.close()
    assert [row["event_sequence"] for row in sink.events()] == [1, 2]
    assert sink.events()[0]["capture_timestamps"]["sample_start_index"] == 0


def test_accelerated_file_replay_and_normalization_are_deterministic(
    tmp_path: Path,
) -> None:
    path = tmp_path / "stereo_8k.wav"
    left = np.linspace(-0.5, 0.5, 4000, dtype=np.float32)
    sf.write(path, np.stack((left, -left), axis=1), 8000, subtype="FLOAT")

    def replay() -> list[tuple[int, int, bytes]]:
        source = FileAudioSource(path, frame_duration_ms=100, pace=0)
        normalizer = StreamingAudioNormalizer()
        rows = []
        source.start()
        while (raw := source.read()) is not None:
            frame = normalizer.normalize(raw)
            rows.append((frame.sample_start, frame.sample_end, frame.samples.tobytes()))
        source.stop()
        return rows

    assert replay() == replay()


@dataclass
class _FakeASR:
    backend_id: str = "sherpa_onnx"
    running: bool = False
    partial_emitted: bool = False

    def start(self, _session_id: str) -> None:
        self.running = True

    def accept_audio(self, frame: object) -> tuple[dict[str, object], ...]:
        if self.partial_emitted:
            return ()
        self.partial_emitted = True
        return (
            {
                "adapter_event_type": "asr_partial",
                "hypothesis_id": "hypothesis:1",
                "utterance_index": 1,
                "revision_number": 1,
                "normalized_text": "hello",
                "words": ["hello"],
                "token_timestamps_sec": [],
                "audio_consumed_through_sec": frame.audio_end_sec,
                "decode_latency_ms": 1.0,
                "stable_prefix_method": "test_lcp",
                "is_final": False,
            },
        )

    def finalize(self, _reason: str) -> tuple[dict[str, object], ...]:
        if not self.running:
            return ()
        self.running = False
        return (
            {
                "adapter_event_type": "asr_final",
                "hypothesis_id": "hypothesis:1",
                "utterance_index": 1,
                "revision_number": 2,
                "normalized_text": "hello",
                "words": ["hello"],
                "token_timestamps_sec": [],
                "audio_consumed_through_sec": 0.5,
                "decode_latency_ms": 1.0,
                "finalization_latency_ms": 2.0,
                "finalization_reason": "input_finished",
                "endpoint_policy_id": "test",
                "is_final": True,
            },
        )

    def reset(self, _reason: str) -> tuple[dict[str, object], ...]:
        self.running = True
        return ()

    def status(self) -> dict[str, object]:
        return {"state": "running" if self.running else "ready"}

    def close(self) -> None:
        self.running = False


class _FakeSegmenter:
    algorithmic_lookahead_sec = 5.0

    def start(self, _session_id: str) -> None:
        pass

    def accept_audio(self, _frame: object) -> tuple[object, ...]:
        return ()

    def finalize(self) -> tuple[object, ...]:
        return ()

    def reset(self) -> None:
        pass

    def status(self) -> dict[str, object]:
        return {"state": "ready"}

    def close(self) -> None:
        pass


class _UnusedEmbedder:
    def start(self, _session_id: str) -> None:
        pass

    def embed(self, _window: object) -> object:
        raise AssertionError("no speech windows expected")

    def status(self) -> dict[str, object]:
        return {"state": "ready"}

    def close(self) -> None:
        pass


def test_coordinator_clean_shutdown_and_deterministic_semantic_replay(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "quiet.wav"
    sf.write(audio, np.zeros(8000, dtype=np.float32), 16000, subtype="FLOAT")
    matrix = FullPipelineMatrix(
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml",
        EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml",
    )
    selection = matrix.resolve("fullpipe_v1_ao_dr_ir")

    def run(root: Path) -> list[tuple[str, object]]:
        identities = {
            key: ComponentRuntimeIdentity(
                component_family=(
                    "speaker_matching"
                    if key == "speaker_matching"
                    else key
                    if key
                    in {
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
                    else "pipeline"
                ),
                backend_id=key,
                backend_config_id=key,
                backend_config_sha256="0" * 64,
                pipeline_config_sha256=selection.pipeline_config_sha256,
                model_id=None,
                model_asset_sha256s=(),
            )
            for key in (
                "capture",
                "asr",
                "segmentation",
                "diarization",
                "clustering",
                "speaker_embedding",
                "speaker_matching",
                "transcript",
                "telemetry",
                "pipeline",
            )
        }
        coordinator = StreamingPipelineCoordinator(
            config=CoordinatorConfig(
                session_id="deterministic_session",
                recording_id="quiet",
                output_root=root,
                telemetry_enabled=False,
            ),
            selection=selection,
            source=FileAudioSource(audio, pace=0),
            normalizer=StreamingAudioNormalizer(),
            asr=_FakeASR(),
            segmenter=_FakeSegmenter(),
            diarization_embedder=_UnusedEmbedder(),
            cluster_manager=OnlineClusterManager(),
            identity_embedder=_UnusedEmbedder(),
            enrollment_store=ProtectedEnrollmentStore(root / "enrollment"),
            identity_manager=SessionIdentityManager(FROZEN_IDENTITY_POLICIES["H2"]),
            transcript_aligner=TranscriptSpeakerAligner("transcript:test"),
            identities=identities,
            resource_monitor=None,
        )
        result = coordinator.run()
        assert result["completion_state"] == "complete"
        assert (root / "result.json").is_file()
        session_state = json.loads((root / "session_state.json").read_text("utf-8"))
        assert session_state["contract_type"] == "SessionState"
        assert session_state["lifecycle_state"] == "completed"
        assert session_state["source_mode"] == "incremental_audio_file"
        assert (
            session_state["next_event_sequence"] == len(coordinator.sink.events()) + 1
        )
        assert session_state["last_event_sequence"] == len(coordinator.sink.events())
        assert session_state["transcript_state_artifact"]["logical_path"] == (
            "transcript/final_transcript.json"
        )
        return [
            (str(row["event_type"]), row["capture_timestamps"]["audio_end_sec"])
            for row in coordinator.sink.events()
        ]

    assert run(tmp_path / "one") == run(tmp_path / "two")


def test_live_status_snapshot_has_one_lock_order_under_telemetry_concurrency(
    tmp_path: Path,
) -> None:
    coordinator = object.__new__(StreamingPipelineCoordinator)
    coordinator.output_root = tmp_path
    coordinator._processing_lock = threading.RLock()
    coordinator._status_lock = threading.Lock()
    coordinator._last_status_write_monotonic = 0.0
    processing_held = threading.Event()
    telemetry_waiting_for_processing = threading.Event()

    def status() -> dict[str, object]:
        if threading.current_thread().name == "test-telemetry-status":
            telemetry_waiting_for_processing.set()
        with coordinator._processing_lock:
            return {"schema_version": "test-status.v1", "state": "running"}

    coordinator.status = status

    def processing_writer() -> None:
        with coordinator._processing_lock:
            processing_held.set()
            assert telemetry_waiting_for_processing.wait(timeout=1.0)
            coordinator._maybe_write_live_status(force=True)

    processing_thread = threading.Thread(
        target=processing_writer,
        name="test-processing-status",
        daemon=True,
    )
    telemetry_thread = threading.Thread(
        target=lambda: coordinator._maybe_write_live_status(force=True),
        name="test-telemetry-status",
        daemon=True,
    )
    processing_thread.start()
    assert processing_held.wait(timeout=1.0)
    telemetry_thread.start()
    processing_thread.join(timeout=2.0)
    telemetry_thread.join(timeout=2.0)

    assert not processing_thread.is_alive()
    assert not telemetry_thread.is_alive()
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8")) == {
        "schema_version": "test-status.v1",
        "state": "running",
    }


def test_status_cli_returns_failure_for_failed_runtime_state(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "status.json").write_text(
        json.dumps(
            {"schema_version": "full-pipeline-runtime-status.v1", "state": "failed"}
        ),
        encoding="utf-8",
    )
    assert runtime_cli_main(["status", "--output-root", str(tmp_path)]) == 1
    assert '"state": "failed"' in capsys.readouterr().out


def test_enrollment_quality_gate_and_profile_identity_are_enforced(
    tmp_path: Path,
) -> None:
    store = ProtectedEnrollmentStore(tmp_path / "enrollment")

    def template(sample_id: str, vector: list[float]) -> EnrollmentTemplate:
        return EnrollmentTemplate(
            sample_id=sample_id,
            vector=np.asarray(vector, dtype=np.float32),
            duration_sec=1.0,
            audio_sha256=sample_id[-1] * 64,
            quality={"status": "accepted"},
        )

    active = store.create_profile(
        profile_id="active_v1",
        speaker_id="speaker_active",
        display_label="Active",
        backend_id="fixture_backend",
        backend_config_sha256="a" * 64,
        model_id="fixture_model",
        model_sha256="b" * 64,
        aggregation_method="normalized_mean",
        templates=(
            template("sample_1", [1.0, 0.0]),
            template("sample_2", [1.0, 0.0]),
        ),
    )
    rejected = store.create_profile(
        profile_id="rejected_v1",
        speaker_id="speaker_rejected",
        display_label="Rejected",
        backend_id="fixture_backend",
        backend_config_sha256="a" * 64,
        model_id="fixture_model",
        model_sha256="b" * 64,
        aggregation_method="normalized_mean",
        templates=(
            template("sample_3", [1.0, 0.0]),
            template("sample_4", [0.0, 1.0]),
        ),
    )
    assert active.state == "active"
    assert rejected.state == "invalidated"
    assert [row.profile_id for row in store.load_profiles("fixture_backend")] == [
        "active_v1"
    ]
    with pytest.raises(ValueError, match="new versioned ID"):
        store.create_profile(
            profile_id="active_v1",
            speaker_id="speaker_active",
            display_label="Active",
            backend_id="fixture_backend",
            backend_config_sha256="a" * 64,
            model_id="fixture_model",
            model_sha256="b" * 64,
            aggregation_method="normalized_mean",
            templates=(template("sample_5", [1.0, 0.0]),),
        )
