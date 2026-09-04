from __future__ import annotations

import json
from pathlib import Path
import queue
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from app.full_pipeline.cache import ContentAddressedCache, make_cache_key
from app.full_pipeline.clustering import OnlineClusterManager
from app.full_pipeline.coordinator import StreamingPipelineCoordinator
from app.full_pipeline.alignment import SpeakerRegion
from app.full_pipeline.models import EmbeddingResult, EmbeddingWindow
from app.full_pipeline.runtime_components import (
    WorkerEmbeddingAdapter,
    WorkerStreamingSegmenter,
)
from app.full_pipeline.segmentation import (
    CausalDiarizationWindowPlanner,
    CausalSpeechRegionTracker,
    RollingSegmentationConfig,
    RollingSegmentationPlanner,
    SegmentationCommit,
    SpeechBoundary,
)
from app.full_pipeline.workers import (
    PersistentWorker,
    WorkerExitedError,
    WorkerRequestError,
    WorkerSpec,
    WorkerStartupError,
    WorkerTimeoutError,
)


def _cache_key(**updates: object):
    values = {
        "artifact_kind": "embedding",
        "role": "anonymous_diarization_window",
        "source_audio_sha256": "a" * 64,
        "source_start_sample": 0,
        "source_end_sample": 24_000,
        "sample_rate_hz": 16_000,
        "window_identity": {"duration_sec": 1.5, "step_sec": 0.75},
        "preprocessing_identity": {"mono": True, "normalizer": "pcm16k.v1"},
        "model_identity": {"backend": "wespeaker", "hash": "model-a"},
        "configuration_identity": {"config_sha256": "b" * 64},
    }
    values.update(updates)
    return make_cache_key(**values)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("role", "identity_probe"),
        ("window_identity", {"duration_sec": 1.5, "step_sec": 0.5}),
        ("preprocessing_identity", {"mono": True, "normalizer": "pcm16k.v2"}),
        ("model_identity", {"backend": "wespeaker", "hash": "model-b"}),
        ("configuration_identity", {"config_sha256": "c" * 64}),
    ],
)
def test_cache_key_binds_role_window_model_preprocessing_and_config(
    field: str, value: object
) -> None:
    assert _cache_key().digest != _cache_key(**{field: value}).digest


def test_content_cache_round_trip_and_checksum_validation(tmp_path: Path) -> None:
    cache = ContentAddressedCache(tmp_path / "cache")
    key = _cache_key()
    path = cache.publish(key, {"vector": [1.0, 0.0], "status": "ok"})
    assert cache.load(key) == {"vector": [1.0, 0.0], "status": "ok"}
    value = json.loads(path.read_text(encoding="utf-8"))
    value["payload"]["status"] = "tampered"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        cache.load(key)


def test_rolling_segmentation_has_ten_second_chunks_and_five_second_commit_delay() -> (
    None
):
    config = RollingSegmentationConfig(sample_rate_hz=8)
    planner = RollingSegmentationPlanner(config)
    first = planner.add(np.zeros(80, dtype=np.float32))
    assert len(first) == 1
    assert first[0].audio.size == 80
    assert first[0].commit_start_sample == 0
    assert first[0].commit_end_sample == 40
    assert first[0].algorithmic_lookahead_sec == 5.0
    assert first[0].lookahead_complete is True

    second = planner.add(np.zeros(6, dtype=np.float32))
    assert len(second) == 1
    assert second[0].commit_start_sample == 40
    assert second[0].commit_end_sample == 46
    tail = planner.flush()
    assert len(tail) == 1
    assert tail[0].commit_start_sample == 46
    assert tail[0].commit_end_sample == 86
    assert tail[0].final_tail is True
    assert tail[0].lookahead_complete is False


def test_segmentation_reset_preserves_absolute_clock_after_discontinuity() -> None:
    config = RollingSegmentationConfig(sample_rate_hz=8)
    planner = RollingSegmentationPlanner(config)
    tracker = CausalSpeechRegionTracker()
    planner.reset(origin_sample=800)
    tracker.reset(origin_sec=100.0)

    chunk = planner.add(np.zeros(80, dtype=np.float32))[0]
    assert chunk.input_start_sample == 800
    assert chunk.commit_start_sample == 800
    assert chunk.commit_end_sample == 840
    commit = tracker.commit(chunk, [(100.5, 105.0)], sample_rate_hz=8)
    assert commit.commit_start_sec == 100.0
    assert commit.commit_end_sec == 105.0
    assert commit.speech_regions == ((100.5, 105.0),)

    segmenter = object.__new__(WorkerStreamingSegmenter)
    segmenter.config = config
    segmenter.planner = planner
    segmenter.tracker = tracker
    segmenter._active_region_id = "speech_1"
    segmenter._active_region_start = 100.5
    segmenter._active_region_announced = True
    segmenter._state = "finalized"
    segmenter.worker = SimpleNamespace(reset=lambda: None)
    segmenter.reset(origin_sample=880)
    assert segmenter._state == "running"
    assert segmenter.planner.total_samples == 880


def test_segmentation_regions_are_cropped_to_monotonic_commit_frontier() -> None:
    planner = RollingSegmentationPlanner(RollingSegmentationConfig(sample_rate_hz=8))
    tracker = CausalSpeechRegionTracker()
    first = planner.add(np.zeros(80, dtype=np.float32))[0]
    update = tracker.commit(first, [(1.0, 6.0)], sample_rate_hz=8)
    assert update.speech_regions == ((1.0, 5.0),)
    assert [(row.event, row.timestamp_sec) for row in update.boundaries] == [
        ("speech_start", 1.0)
    ]
    second = planner.add(np.zeros(6, dtype=np.float32))[0]
    update = tracker.commit(second, [(1.0, 5.5)], sample_rate_hz=8)
    assert update.speech_regions == ((5.0, 5.5),)
    assert [(row.event, row.timestamp_sec) for row in update.boundaries] == [
        ("speech_end", 5.5)
    ]


def test_same_commit_silence_gap_closes_old_region_before_new_speech() -> None:
    segmenter = object.__new__(WorkerStreamingSegmenter)
    segmenter._active_region_id = None
    segmenter._active_region_start = None
    segmenter._active_region_announced = False
    segmenter._region_counter = 0

    first = SegmentationCommit(
        commit_start_sec=0.0,
        commit_end_sec=1.0,
        speech_regions=((0.2, 1.0),),
        boundaries=(SpeechBoundary("speech_start", 0.2),),
        algorithmic_lookahead_sec=5.0,
        final_tail=False,
    )
    first_updates = segmenter._updates_from_commit(first, 2.0)
    assert [
        (row.region_id, row.state, row.start_sec, row.end_sec) for row in first_updates
    ] == [("speech_000001", "speech_start", 0.2, 1.0)]

    after_gap = SegmentationCommit(
        commit_start_sec=1.0,
        commit_end_sec=2.0,
        speech_regions=((1.5, 2.0),),
        boundaries=(
            SpeechBoundary("speech_end", 1.0),
            SpeechBoundary("speech_start", 1.5),
        ),
        algorithmic_lookahead_sec=5.0,
        final_tail=False,
    )
    updates = segmenter._updates_from_commit(after_gap, 3.0)
    assert [
        (row.region_id, row.state, row.start_sec, row.end_sec) for row in updates
    ] == [
        ("speech_000001", "speech_end", 0.2, 1.0),
        ("speech_000002", "speech_start", 1.5, 2.0),
    ]


def test_causal_window_planner_emits_midpoint_revisions_on_region_close() -> None:
    planner = CausalDiarizationWindowPlanner()
    first = planner.advance(
        region_id="speech-1", start_sec=0.0, end_sec=2.0, final=False
    )
    assert len(first.new_windows) == 1
    assert first.new_windows[0].provisional is True
    closed = planner.advance(
        region_id="speech-1", start_sec=0.0, end_sec=3.0, final=True
    )
    assert len(closed.new_windows) == 2
    assert closed.revised_windows
    assert all(
        not row.provisional for row in (*closed.new_windows, *closed.revised_windows)
    )
    assert [(row.start_sec, row.end_sec) for row in closed.new_windows] == [
        (0.75, 2.25),
        (1.5, 3.0),
    ]


def test_online_clusters_are_stable_support_reentry_short_turns_and_revision() -> None:
    manager = OnlineClusterManager()
    first = manager.observe(
        window_id="w1", start_sec=0.0, end_sec=1.0, embedding=[1.0, 0.0]
    )
    second = manager.observe(
        window_id="w2", start_sec=1.0, end_sec=2.0, embedding=[0.0, 1.0]
    )
    assert first.assignment.cluster_id == "anon_0001"
    assert second.assignment.cluster_id == "anon_0002"

    short = manager.observe(
        window_id="w3",
        start_sec=2.1,
        end_sec=2.5,
        embedding=None,
    )
    assert short.assignment.cluster_id == "anon_0002"
    assert short.assignment.short_turn and short.assignment.provisional

    revised = manager.observe(
        window_id="w3",
        start_sec=2.1,
        end_sec=3.1,
        embedding=[1.0, 0.0],
    )
    assert revised.assignment.cluster_id == "anon_0001"
    assert revised.revisions[0].previous_cluster_id == "anon_0002"
    reentry = manager.observe(
        window_id="w4", start_sec=10.0, end_sec=11.0, embedding=[1.0, 0.0]
    )
    assert reentry.assignment.cluster_id == "anon_0001"
    assert reentry.assignment.reentry is True

    manager.release("anon_0001")
    after_release = manager.observe(
        window_id="w5", start_sec=12.0, end_sec=13.0, embedding=[1.0, 0.0]
    )
    assert after_release.assignment.cluster_id == "anon_0003"


def test_online_cluster_manager_implements_common_runtime_protocol() -> None:
    manager = OnlineClusterManager()
    window = EmbeddingWindow(
        window_id="protocol-window",
        start_sec=0.0,
        end_sec=1.5,
        assignment_start_sec=0.0,
        assignment_end_sec=1.5,
        samples=np.zeros(24_000, dtype=np.float32),
        role="anonymous_diarization_window",
    )
    embedding = EmbeddingResult(
        window_id=window.window_id,
        backend_id="fixture",
        model_id="fixture",
        model_sha256=None,
        vector=np.asarray([1.0, 0.0]),
        duration_sec=1.5,
        role=window.role,
    )
    update = manager.update(embedding, window)
    assert update.anonymous_speaker_id == "anon_0001"
    assert update.created is True
    assert manager.finalize()[0].state == "FINAL"


def _test_worker_spec(**updates: object) -> WorkerSpec:
    values = {
        "worker_id": "model-free-test-worker",
        "kind": "test",
        "component_id": "protocol_test",
        "environment_profile": "core-cpu",
        "startup_timeout_sec": 5.0,
        "request_timeout_sec": 2.0,
        "shutdown_timeout_sec": 1.0,
        "restart_limit": 0,
        "command_override": (
            sys.executable,
            "-u",
            "-m",
            "app.full_pipeline.worker_main",
            "--worker-id",
            "model-free-test-worker",
            "--kind",
            "test",
            "--component",
            "protocol_test",
        ),
    }
    values.update(updates)
    return WorkerSpec(**values)


def test_persistent_worker_health_failure_reset_and_clean_shutdown() -> None:
    worker = PersistentWorker(_test_worker_spec())
    identity = worker.start()
    assert identity["component_id"] == "protocol_test"
    assert worker.health()["status"] == "HEALTHY"
    assert worker.call("echo", {"value": 7}) == {"echo": {"value": 7}}
    with pytest.raises(WorkerRequestError, match="requested test failure"):
        worker.call("fail")
    assert worker.reset()["reset"] is True
    pid = worker.pid
    assert pid is not None
    worker.shutdown()
    assert not worker.running
    assert worker.status()["identity"] == identity


def test_persistent_worker_runs_declared_warmup_before_ready_use() -> None:
    worker = PersistentWorker(
        _test_worker_spec(warmup_request={"purpose": "model-free-warmup"})
    )
    worker.start()
    health = worker.health()
    assert health["warmed_up"] is True
    assert health["request_count"] >= 2
    worker.shutdown()


def test_failed_warmup_cleans_up_worker_generation() -> None:
    worker = PersistentWorker(
        _test_worker_spec(warmup_request={"force_status": "failed"})
    )
    with pytest.raises(WorkerRequestError, match="model warmup failed"):
        worker.start()
    assert not worker.running
    assert worker.ready_identity is None


def test_embedding_response_identity_is_revalidated_before_cache_publish(
    tmp_path: Path,
) -> None:
    expected_config = "a" * 64

    class Worker:
        spec = SimpleNamespace(component_id="fixture_backend")

        def start(self) -> dict[str, object]:
            return {
                "component_id": "fixture_backend",
                "declared_backend": {"config_hash": expected_config},
            }

        def call(self, _operation: str, _payload: object) -> dict[str, object]:
            return {
                "identity": {
                    "component_id": "fixture_backend",
                    "declared_backend": {"config_hash": "b" * 64},
                },
                "embedding": {
                    "status": "ok",
                    "dimension": 2,
                    "vector": [1.0, 0.0],
                },
            }

        def status(self) -> dict[str, object]:
            return {}

        def shutdown(self) -> None:
            pass

    cache = ContentAddressedCache(tmp_path / "cache")
    adapter = WorkerEmbeddingAdapter(
        worker=Worker(),
        work_root=tmp_path / "work",
        backend_config_sha256=expected_config,
        model_id="fixture_model",
        model_sha256="c" * 64,
        cache=cache,
    )
    adapter.start("session")
    with pytest.raises(RuntimeError, match="worker config mismatch"):
        adapter.embed(
            EmbeddingWindow(
                window_id="window",
                start_sec=0.0,
                end_sec=1.0,
                assignment_start_sec=0.0,
                assignment_end_sec=1.0,
                samples=np.zeros(16_000, dtype=np.float32),
                role="identity_matching",
            )
        )
    assert not list((tmp_path / "cache").rglob("*.json"))


def test_persistent_worker_propagates_exit_and_can_restart() -> None:
    worker = PersistentWorker(_test_worker_spec())
    worker.start()
    with pytest.raises(WorkerExitedError):
        worker.call("crash", retry_on_worker_failure=False)
    identity = worker.restart()
    assert identity["component_id"] == "protocol_test"
    assert worker.health()["status"] == "HEALTHY"
    worker.shutdown()


def test_worker_reader_eof_is_bound_to_the_process_generation() -> None:
    entered = threading.Event()
    release = threading.Event()

    class BlockingEOF:
        def __iter__(self):
            return self

        def __next__(self) -> str:
            entered.set()
            assert release.wait(timeout=1.0)
            raise StopIteration

    worker = PersistentWorker(_test_worker_spec())
    old_responses: queue.Queue[dict[str, object]] = queue.Queue()
    replacement_responses: queue.Queue[dict[str, object]] = queue.Queue()
    process = SimpleNamespace(stdout=BlockingEOF())
    reader = threading.Thread(
        target=worker._read_stdout,
        args=(process, old_responses),
    )
    reader.start()
    assert entered.wait(timeout=1.0)
    worker._responses = replacement_responses
    release.set()
    reader.join(timeout=1.0)
    assert not reader.is_alive()
    assert old_responses.get_nowait() == {"type": "eof"}
    with pytest.raises(queue.Empty):
        replacement_responses.get_nowait()


def test_revised_diar_window_replaces_interval_and_identity_observation() -> None:
    coordinator = object.__new__(StreamingPipelineCoordinator)
    coordinator._speaker_regions = []
    coordinator._speaker_regions_by_window = {}
    coordinator._window_cluster_intervals = {}
    coordinator._cluster_intervals = {}
    coordinator._identity_vectors = {}

    first = SpeakerRegion(0.0, 2.0, "anon_0001", "Unknown_1", "event-1")
    revised = SpeakerRegion(0.0, 1.125, "anon_0001", "Unknown_1", "event-2")
    assert coordinator._replace_window_region("window-1", "anon_0001", first) is None
    assert (
        coordinator._replace_window_region("window-1", "anon_0001", revised)
        == "anon_0001"
    )
    assert coordinator._speaker_regions == [revised]
    assert coordinator._cluster_intervals == {"anon_0001": [(0.0, 1.125)]}

    vector = np.asarray([1.0, 0.0], dtype=np.float32)
    changed, rows = coordinator._upsert_identity_observation(
        "anon_0001", "window-1", vector, 1.5
    )
    assert changed and len(rows) == 1
    changed, rows = coordinator._upsert_identity_observation(
        "anon_0001", "window-1", vector.copy(), 1.5
    )
    assert not changed and len(rows) == 1


def test_worker_startup_and_request_timeouts_are_bounded() -> None:
    startup = PersistentWorker(
        _test_worker_spec(
            worker_id="startup-timeout",
            startup_timeout_sec=0.05,
            command_override=(sys.executable, "-c", "import time; time.sleep(2)"),
        )
    )
    with pytest.raises(WorkerStartupError, match="timed out"):
        startup.start()
    assert not startup.running

    worker = PersistentWorker(_test_worker_spec(worker_id="request-timeout"))
    worker.start()
    with pytest.raises(WorkerTimeoutError, match="timed out"):
        worker.call(
            "sleep",
            {"seconds": 0.25},
            timeout_sec=0.02,
            retry_on_worker_failure=False,
        )
    assert not worker.running
