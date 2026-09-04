from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import numpy as np
import pytest
import soundfile as sf

from app.full_pipeline.factory import _speaker_embedding_worker_partitions
from app.full_pipeline.models import EmbeddingWindow, NormalizedAudioFrame
from app.full_pipeline.runtime_components import WorkerEmbeddingAdapter
from app.full_pipeline.workers import WorkerSpec
from app.full_pipeline_development import shared_execution
from app.full_pipeline_development.shared_execution import (
    ASRStreamTraceAdapter,
    ASRStreamTraceStore,
    SharedWorkerPool,
    build_asr_stream_trace_identity,
)


def _frame(
    sequence: int, *, source_sample_rate_hz: int = 16000
) -> NormalizedAudioFrame:
    start = (sequence - 1) * 1600
    end = start + 1600
    source_start = (sequence - 1) * round(source_sample_rate_hz / 10)
    source_end = source_start + round(source_sample_rate_hz / 10)
    return NormalizedAudioFrame(
        frame_id=f"frame-{sequence}",
        sequence=sequence,
        samples=np.full(1600, sequence / 10.0, dtype=np.float32),
        sample_rate_hz=16000,
        sample_start=start,
        sample_end=end,
        audio_start_sec=start / 16000.0,
        audio_end_sec=end / 16000.0,
        source_sample_rate_hz=source_sample_rate_hz,
        source_channel_count=1,
        source_sample_start=source_start,
        source_sample_end=source_end,
        source_audio_start_sec=source_start / source_sample_rate_hz,
        source_audio_end_sec=source_end / source_sample_rate_hz,
        capture_start_monotonic_ns=None,
        capture_end_monotonic_ns=None,
        capture_start_utc=None,
        capture_end_utc=None,
        source_clock_id="fixture-clock",
        source_clock_type="audio_sample",
    )


class _NativeFixture:
    backend_id = "fixture_asr"

    def __init__(
        self,
        *,
        starts: list[str] | None = None,
        accepted: threading.Event | None = None,
        release: threading.Event | None = None,
        forbid_compute: bool = False,
    ) -> None:
        self.starts = starts if starts is not None else []
        self.accepted = accepted
        self.release = release
        self.forbid_compute = forbid_compute
        self.closed = False
        self.session_id: str | None = None

    def start(self, session_id: str) -> None:
        if self.forbid_compute:
            raise AssertionError("replay started the native worker")
        self.starts.append(session_id)
        self.session_id = session_id

    def accept_audio(
        self, frame: NormalizedAudioFrame
    ) -> tuple[dict[str, object], ...]:
        if self.forbid_compute:
            raise AssertionError("replay decoded audio")
        if self.accepted is not None:
            self.accepted.set()
        if self.release is not None:
            assert self.release.wait(timeout=3.0)
        return (
            {
                "kind": "partial",
                "session_id": self.session_id,
                "hypothesis_id": f"{self.session_id}:asr:{frame.sequence}",
                "utterance_index": frame.sequence,
                "text": f"partial-{frame.sequence}",
                "audio_consumed_through_sec": frame.audio_end_sec,
                "decode_latency_ms": 12.5 + frame.sequence,
            },
        )

    def finalize(self, reason: str) -> tuple[dict[str, object], ...]:
        if self.forbid_compute:
            raise AssertionError("replay finalized the native worker")
        return (
            {
                "kind": "final",
                "finalization_reason": reason,
                "audio_consumed_through_sec": 0.2,
                "decode_latency_ms": 19.75,
            },
        )

    def reset(self, reason: str) -> tuple[dict[str, object], ...]:
        if self.forbid_compute:
            raise AssertionError("replay reset the native worker")
        return ({"kind": "reset", "reason": reason, "decode_latency_ms": 0.25},)

    def status(self) -> dict[str, object]:
        return {"delegate_closed": self.closed}

    def close(self) -> None:
        self.closed = True


def _identity(*, expected_sample_end: int = 3200) -> dict[str, object]:
    return {
        "schema_version": "full-pipeline-native-asr-stream-trace-identity.v2",
        "source_audio_sha256": "a" * 64,
        "source_audio_contract": {
            "decoder_id": "soundfile.SoundFile.v1",
            "source_frame_count": expected_sample_end,
            "source_sample_rate_hz": 16000,
            "source_channel_count": 1,
            "expected_source_sample_start": 0,
            "expected_source_sample_end": expected_sample_end,
        },
        "native_stream": {
            "component_id": "fixture_asr",
            "config_sha256": "b" * 64,
        },
    }


def _exercise(
    adapter: ASRStreamTraceAdapter, session_id: str
) -> list[tuple[dict[str, object], ...]]:
    adapter.start(session_id)
    rows = [tuple(dict(row) for row in adapter.accept_audio(_frame(1)))]
    rows.append(tuple(dict(row) for row in adapter.finalize("audio_discontinuity")))
    rows.append(tuple(dict(row) for row in adapter.reset("audio_discontinuity")))
    rows.append(tuple(dict(row) for row in adapter.accept_audio(_frame(2))))
    rows.append(tuple(dict(row) for row in adapter.finalize("input_finished")))
    return rows


def test_cold_and_replayed_native_streams_are_byte_and_semantically_identical(
    tmp_path: Path,
) -> None:
    store = ASRStreamTraceStore(tmp_path / "traces")
    primary = ASRStreamTraceAdapter(
        _NativeFixture(), store=store, identity=_identity(), usage_mode="accuracy"
    )
    primary_rows = _exercise(primary, "primary-session")
    primary_status = primary.status()["shared_execution"]
    assert primary_status["execution_origin"] == "primary_computed"
    assert primary_status["worker_started"] is True
    path = store.path_for(primary.trace_key_sha256)
    before = path.read_bytes()

    replay = ASRStreamTraceAdapter(
        _NativeFixture(forbid_compute=True),
        store=store,
        identity=_identity(),
        usage_mode="accuracy",
    )
    replay_rows = _exercise(replay, "replay-session")
    replay_status = replay.status()["shared_execution"]

    assert _without_session_fields(replay_rows) == _without_session_fields(primary_rows)
    assert primary_rows[0][0]["session_id"] == "primary-session"
    assert replay_rows[0][0]["session_id"] == "replay-session"
    assert replay_rows[0][0]["hypothesis_id"] == "replay-session:asr:1"
    assert path.read_bytes() == before
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == hashlib.sha256(before).hexdigest()
    )
    assert replay_status["execution_origin"] == "accuracy_replayed"
    assert replay_status["worker_started"] is False
    assert replay_status["native_processing_latency_preserved"] is True
    assert replay_rows[-1][0]["decode_latency_ms"] == 19.75


def test_trace_identity_uses_exact_full_and_duration_limited_source_horizon(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.wav"
    sf.write(source, np.zeros(4410, dtype=np.float32), 44100)
    selection = SimpleNamespace(
        asr={
            "component_id": "fixture_asr",
            "config_sha256": "b" * 64,
            "model_asset": {
                "asset_id": "fixture_asset",
                "installed_tree_sha256": "c" * 64,
            },
            "requirements_sha256": "d" * 64,
            "package_identity": "fixture-package",
            "implementation_path": "app/full_pipeline/asr.py",
        },
        runtime_config_sha256="e" * 64,
    )

    full = build_asr_stream_trace_identity(
        source_audio_path=source,
        selection=selection,
        duration_sec=None,
    )
    limited = build_asr_stream_trace_identity(
        source_audio_path=source,
        selection=selection,
        duration_sec=0.05,
    )

    assert full["source_audio_contract"]["expected_source_sample_end"] == 4410
    assert limited["source_audio_contract"]["expected_source_sample_end"] == 2205


def test_duration_limited_terminal_horizon_is_publishable_and_replayable(
    tmp_path: Path,
) -> None:
    store = ASRStreamTraceStore(tmp_path / "traces")
    identity = _identity(expected_sample_end=1600)
    primary = ASRStreamTraceAdapter(
        _NativeFixture(), store=store, identity=identity, usage_mode="accuracy"
    )
    primary.start("limited-primary")
    primary.accept_audio(_frame(1))
    primary.finalize("input_finished")
    assert store.path_for(primary.trace_key_sha256).is_file()

    replay = ASRStreamTraceAdapter(
        _NativeFixture(forbid_compute=True),
        store=store,
        identity=identity,
        usage_mode="accuracy",
    )
    replay.start("limited-replay")
    replay.accept_audio(_frame(1))
    replay.finalize("input_finished")
    assert (
        replay.status()["shared_execution"]["execution_origin"] == "accuracy_replayed"
    )


def test_terminal_guard_uses_source_horizon_not_normalized_horizon(
    tmp_path: Path,
) -> None:
    store = ASRStreamTraceStore(tmp_path / "traces")
    identity = _identity(expected_sample_end=4410)
    source_contract = identity["source_audio_contract"]
    assert isinstance(source_contract, dict)
    source_contract["source_frame_count"] = 4410
    source_contract["source_sample_rate_hz"] = 44100
    adapter = ASRStreamTraceAdapter(
        _NativeFixture(), store=store, identity=identity, usage_mode="accuracy"
    )
    adapter.start("source-rate-primary")
    adapter.accept_audio(_frame(1, source_sample_rate_hz=44100))
    adapter.finalize("input_finished")

    assert adapter.status()["shared_execution"]["trace_published"] is True
    assert store.path_for(adapter.trace_key_sha256).is_file()


def test_partial_terminal_finalize_does_not_publish_and_next_run_computes_fresh(
    tmp_path: Path,
) -> None:
    store = ASRStreamTraceStore(tmp_path / "traces")
    identity = _identity(expected_sample_end=3200)
    starts: list[str] = []
    partial = ASRStreamTraceAdapter(
        _NativeFixture(starts=starts),
        store=store,
        identity=identity,
        usage_mode="accuracy",
    )
    partial.start("partial")
    partial.accept_audio(_frame(1))
    partial.finalize("input_finished")
    partial_status = partial.status()["shared_execution"]

    assert partial_status["trace_published"] is False
    assert partial_status["terminal_completeness"]["complete"] is False
    assert (
        partial_status["terminal_completeness"]["failure_reason"]
        == "source_horizon_incomplete"
    )
    assert not store.path_for(partial.trace_key_sha256).exists()

    fresh = ASRStreamTraceAdapter(
        _NativeFixture(starts=starts),
        store=store,
        identity=identity,
        usage_mode="accuracy",
    )
    fresh.start("fresh")
    fresh.accept_audio(_frame(1))
    fresh.accept_audio(_frame(2))
    fresh.finalize("input_finished")

    assert starts == ["partial", "fresh"]
    assert fresh.status()["shared_execution"]["execution_origin"] == "primary_computed"
    assert store.path_for(fresh.trace_key_sha256).is_file()


def test_two_accuracy_threads_have_exactly_one_primary_trace_producer(
    tmp_path: Path,
) -> None:
    store = ASRStreamTraceStore(tmp_path / "traces")
    starts: list[str] = []
    accepted = threading.Event()
    release = threading.Event()
    outputs: list[tuple[str, tuple[dict[str, object], ...]]] = []
    failures: list[BaseException] = []

    def run(delegate: _NativeFixture, label: str) -> None:
        try:
            adapter = ASRStreamTraceAdapter(
                delegate,
                store=store,
                identity=_identity(expected_sample_end=1600),
                usage_mode="accuracy",
            )
            adapter.start(label)
            rows = tuple(dict(row) for row in adapter.accept_audio(_frame(1)))
            adapter.finalize("input_finished")
            origin = str(adapter.status()["shared_execution"]["execution_origin"])
            outputs.append((origin, rows))
        except BaseException as exc:  # pragma: no cover - surfaced below
            failures.append(exc)

    first = threading.Thread(
        target=run,
        args=(
            _NativeFixture(starts=starts, accepted=accepted, release=release),
            "primary",
        ),
    )
    second = threading.Thread(
        target=run,
        args=(_NativeFixture(starts=starts), "racer"),
    )
    first.start()
    assert accepted.wait(timeout=2.0)
    second.start()
    time.sleep(0.05)
    assert second.is_alive(), (
        "racing consumer did not wait for complete trace publication"
    )
    release.set()
    first.join(timeout=3.0)
    second.join(timeout=3.0)

    assert not failures
    assert not first.is_alive() and not second.is_alive()
    assert starts == ["primary"]
    assert sorted(origin for origin, _ in outputs) == [
        "accuracy_replayed",
        "primary_computed",
    ]
    assert _without_session_fields(outputs[0][1]) == _without_session_fields(
        outputs[1][1]
    )


def test_resource_measurement_hard_refuses_asr_stream_trace(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="accuracy-only"):
        ASRStreamTraceAdapter(
            _NativeFixture(),
            store=ASRStreamTraceStore(tmp_path),
            identity=_identity(),
            usage_mode="resources",
        )


def _without_session_fields(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_session_fields(item)
            for key, item in value.items()
            if key not in {"session_id", "hypothesis_id"}
        }
    if isinstance(value, (list, tuple)):
        return tuple(_without_session_fields(item) for item in value)
    return value


def test_shared_worker_pool_reuses_process_and_lease_close_only_ends_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[object] = []

    class Worker:
        def __init__(self, spec: WorkerSpec) -> None:
            self.spec = spec
            self.calls: list[tuple[str, object]] = []
            self.shutdown_count = 0
            instances.append(self)

        def start(self) -> dict[str, object]:
            return {"component_id": self.spec.component_id}

        def call(
            self, operation: str, payload: object, **_kwargs: object
        ) -> dict[str, object]:
            self.calls.append((operation, payload))
            return {"status": "ok"}

        def reset(self) -> dict[str, object]:
            return {"status": "ok"}

        def status(self) -> dict[str, object]:
            return {"component_id": self.spec.component_id}

        def shutdown(self) -> None:
            self.shutdown_count += 1

    monkeypatch.setattr(shared_execution, "PersistentWorker", Worker)
    first_spec = WorkerSpec(
        worker_id="one",
        kind="native_sherpa_asr",
        component_id="sherpa_onnx",
        environment_profile="onnx",
    )
    second_spec = WorkerSpec(
        worker_id="two",
        kind="native_sherpa_asr",
        component_id="sherpa_onnx",
        environment_profile="onnx",
    )
    pool = SharedWorkerPool("job")
    first = pool.acquire(first_spec)
    second = pool.acquire(second_spec)
    assert first.worker is second.worker
    first.call("start_session", {"session_id": "case"})
    first.shutdown()
    assert instances[0].shutdown_count == 0
    assert instances[0].calls[-1] == (
        "finalize",
        {"reason": "pooled_lease_release"},
    )
    pool.close()
    assert instances[0].shutdown_count == 1


def test_shared_worker_pool_partitions_independent_roles_but_reuses_each_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instances: list[object] = []

    class Worker:
        def __init__(self, spec: WorkerSpec) -> None:
            self.spec = spec
            self.shutdown_count = 0
            instances.append(self)

        def status(self) -> dict[str, object]:
            return {
                "component_id": self.spec.component_id,
                "pool_partition_id": self.spec.pool_partition_id,
            }

        def shutdown(self) -> None:
            self.shutdown_count += 1

    monkeypatch.setattr(shared_execution, "PersistentWorker", Worker)
    common = {
        "kind": "speaker_embedding",
        "component_id": "redimnet2_b2_speaker_embedding",
        "environment_profile": "wespeaker",
    }
    pool = SharedWorkerPool("resource-ablation")
    first_diar = pool.acquire(
        WorkerSpec(
            worker_id="case-one-diar",
            pool_partition_id="speaker_embedding:diarization",
            **common,
        )
    )
    first_identity = pool.acquire(
        WorkerSpec(
            worker_id="case-one-identity",
            pool_partition_id="speaker_embedding:identity",
            **common,
        )
    )
    second_diar = pool.acquire(
        WorkerSpec(
            worker_id="case-two-diar",
            pool_partition_id="speaker_embedding:diarization",
            **common,
        )
    )
    second_identity = pool.acquire(
        WorkerSpec(
            worker_id="case-two-identity",
            pool_partition_id="speaker_embedding:identity",
            **common,
        )
    )

    assert first_diar.worker is second_diar.worker
    assert first_identity.worker is second_identity.worker
    assert first_diar.worker is not first_identity.worker
    assert len(instances) == 2
    assert {
        row["pool_partition_id"] for row in pool.status()["workers"]
    } == {
        "speaker_embedding:diarization",
        "speaker_embedding:identity",
    }
    pool.close()
    assert [worker.shutdown_count for worker in instances] == [1, 1]


def test_r1_and_r2_embedding_partitions_are_gallery_cache_independent() -> None:
    r1_diar, r1_identity = _speaker_embedding_worker_partitions(False)
    r2_diar, r2_identity = _speaker_embedding_worker_partitions(True)

    assert r1_diar == "speaker_embedding:diarization"
    assert r1_identity == "speaker_embedding:identity"
    assert r1_diar != r1_identity
    assert r2_diar == r2_identity == "speaker_embedding:identity"


def test_lazy_embedding_worker_does_not_start_on_cache_hit(tmp_path: Path) -> None:
    class Worker:
        spec = SimpleNamespace(component_id="fixture_embedding")

        def start(self) -> dict[str, object]:
            raise AssertionError("cache replay started worker")

        def status(self) -> dict[str, object]:
            return {}

        def shutdown(self) -> None:
            pass

    class Cache:
        def load(self, _key: object) -> dict[str, object]:
            return {
                "vector": [1.0, 0.0],
                "status": "ok",
                "dimension": 2,
                "worker_wall_sec": 1.0,
            }

        def publish(self, _key: object, _payload: object) -> None:
            raise AssertionError("cache hit was republished")

    adapter = WorkerEmbeddingAdapter(
        worker=Worker(),
        work_root=tmp_path,
        backend_config_sha256="b" * 64,
        model_id="fixture",
        model_sha256="c" * 64,
        cache=Cache(),  # type: ignore[arg-type]
        lazy_worker_start=True,
    )
    adapter.start("session")
    result = adapter.embed(
        EmbeddingWindow(
            window_id="window",
            start_sec=0.0,
            end_sec=1.0,
            assignment_start_sec=0.0,
            assignment_end_sec=1.0,
            samples=np.zeros(16000, dtype=np.float32),
            role="identity_matching",
        )
    )
    assert result.vector.tolist() == [1.0, 0.0]
    assert adapter.status()["shared_execution"] == {
        "lazy_worker_start": True,
        "worker_started": False,
        "cache_hits": 1,
        "cache_misses": 0,
        "execution_origin": "cache_replayed",
    }
