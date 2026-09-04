from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from app.full_pipeline.asr import (
    ACCEPTED_AUDIO_INTERVAL_PROVENANCE,
    SherpaStreamingASRAdapter,
    StreamingASRAdapter,
    build_sherpa_streaming_adapter,
)
from app.full_pipeline.models import NormalizedAudioFrame
from app.inference_pipeline.asr.sherpa_onnx_adapter import (
    STABLE_PREFIX_METHOD,
    SherpaOnnxASR,
)
from app.inference_pipeline.errors import ContractValidationError


class FakeSherpaStream:
    def __init__(self) -> None:
        self.chunk_count = 0
        self.pending_decode_steps = 0
        self.generation = 0
        self.finished = False
        self.accepted_sample_rates: list[int] = []

    def accept_waveform(self, sample_rate: int, samples: np.ndarray) -> None:
        assert samples.dtype == np.float32
        self.accepted_sample_rates.append(sample_rate)
        self.chunk_count += 1
        self.pending_decode_steps += 1

    def input_finished(self) -> None:
        self.finished = True
        self.pending_decode_steps += 1


class FakeSherpaRecognizer:
    def __init__(self, *, endpoint_after_chunks: int | None = None) -> None:
        self.endpoint_after_chunks = endpoint_after_chunks
        self.streams: list[FakeSherpaStream] = []
        self.decode_count = 0
        self.reset_count = 0

    def create_stream(self) -> FakeSherpaStream:
        stream = FakeSherpaStream()
        self.streams.append(stream)
        return stream

    def is_ready(self, stream: FakeSherpaStream) -> bool:
        return stream.pending_decode_steps > 0

    def decode_stream(self, stream: FakeSherpaStream) -> None:
        stream.pending_decode_steps -= 1
        self.decode_count += 1

    def get_result_all(self, stream: FakeSherpaStream) -> SimpleNamespace:
        if stream.generation > 0:
            text = "again" if stream.chunk_count else ""
        elif stream.chunk_count >= 2:
            text = "hello world"
        elif stream.chunk_count == 1:
            text = "hello"
        else:
            text = ""
        words = text.split()
        return SimpleNamespace(
            text=text,
            tokens=words,
            timestamps=[0.1 * (index + 1) for index in range(len(words))],
            words=words,
        )

    def is_endpoint(self, stream: FakeSherpaStream) -> bool:
        return (
            self.endpoint_after_chunks is not None
            and stream.generation == 0
            and stream.chunk_count >= self.endpoint_after_chunks
        )

    def reset(self, stream: FakeSherpaStream) -> bool:
        self.reset_count += 1
        stream.chunk_count = 0
        stream.pending_decode_steps = 0
        stream.finished = False
        stream.generation += 1
        return True


def _chunk() -> np.ndarray:
    return np.zeros(1600, dtype=np.float32)


def _frame(sequence: int, start_sec: float) -> NormalizedAudioFrame:
    samples = _chunk()
    start_sample = int(round(start_sec * 16000))
    return NormalizedAudioFrame(
        frame_id=f"frame-{sequence}",
        sequence=sequence,
        samples=samples,
        sample_rate_hz=16000,
        sample_start=start_sample,
        sample_end=start_sample + len(samples),
        audio_start_sec=start_sec,
        audio_end_sec=start_sec + 0.1,
        source_sample_rate_hz=16000,
        source_channel_count=1,
        source_sample_start=start_sample,
        source_sample_end=start_sample + len(samples),
        source_audio_start_sec=start_sec,
        source_audio_end_sec=start_sec + 0.1,
        capture_start_monotonic_ns=None,
        capture_end_monotonic_ns=None,
        capture_start_utc=None,
        capture_end_utc=None,
        source_clock_id="test-clock",
        source_clock_type="file",
    )


def test_native_session_preserves_decoder_state_and_reports_stable_prefix() -> None:
    recognizer = FakeSherpaRecognizer()
    backend = SherpaOnnxASR(
        {"sample_rate": 16000, "tail_padding_sec": 0},
        recognizer=recognizer,
    )
    session = backend.open_stream(source_start_sec=5.0)

    first = session.accept_audio(_chunk(), sample_rate=16000)
    second = session.accept_audio(_chunk(), sample_rate=16000)
    final = session.finalize()

    assert len(recognizer.streams) == 1
    assert [row.text for row in (*first, *second, final)] == [
        "hello",
        "hello world",
        "hello world",
    ]
    assert first[0].is_first_partial is True
    assert first[0].stable_prefix_text == ""
    assert second[0].stable_prefix_text == "hello"
    assert second[0].stable_prefix_token_count == 1
    assert second[0].stable_prefix_method == STABLE_PREFIX_METHOD
    assert second[0].revision_number == 1
    assert second[0].token_timestamps_sec == pytest.approx((5.1, 5.2))
    assert final.is_final is True
    assert final.finalization_reason == "input_finished"
    assert final.stable_prefix_text == "hello world"
    assert final.finalization_latency_ms is not None
    assert session.closed is True
    assert recognizer.streams[0].finished is True


def test_ag_uses_runtime_endpoint_overlay_without_changing_frozen_segment_flag() -> (
    None
):
    recognizer = FakeSherpaRecognizer(endpoint_after_chunks=2)
    adapter = build_sherpa_streaming_adapter(
        "sherpa_onnx_libri_giga_zipformer_2023_06_21",
        {
            "sample_rate": 16000,
            "tail_padding_sec": 0,
            "native_streaming_replay": False,
        },
        recognizer=recognizer,
        endpoint_overlay={
            "enabled": True,
            "policy_id": "test_backend_endpoint.v1",
            "rule2_min_trailing_silence": 0.5,
        },
    )

    assert isinstance(adapter, StreamingASRAdapter)
    assert adapter.backend.native_streaming_replay is False
    adapter.start("session-ag")
    assert [
        row.text for row in adapter.accept_samples(_chunk(), sample_rate=16000)
    ] == ["hello"]
    endpoint_updates = adapter.accept_samples(_chunk(), sample_rate=16000)

    assert [row.is_final for row in endpoint_updates] == [False, True]
    assert endpoint_updates[-1].endpoint_detected is True
    assert endpoint_updates[-1].finalization_reason == "backend_endpoint"
    assert endpoint_updates[-1].stream_reset_performed is True
    assert recognizer.reset_count == 1
    assert len(recognizer.streams) == 1
    following = adapter.accept_samples(_chunk(), sample_rate=16000)
    assert following[0].text == "again"
    assert following[0].utterance_index == 2
    assert following[0].revision_number == 0
    assert following[0].is_first_partial is True
    assert adapter.status_record().reset_count == 1


def test_manual_reset_creates_fresh_stream_but_keeps_loaded_recognizer() -> None:
    recognizer = FakeSherpaRecognizer()
    adapter = SherpaStreamingASRAdapter(
        SherpaOnnxASR(
            {"sample_rate": 16000, "tail_padding_sec": 0},
            recognizer=recognizer,
        )
    )
    adapter.start("session-reset")
    adapter.accept_samples(_chunk(), sample_rate=16000)

    reset = adapter.reset_one(reason="new_record")
    following = adapter.accept_samples(_chunk(), sample_rate=16000)

    assert reset.reason == "new_record"
    assert reset.backend_reset_used is False
    assert reset.prior_utterance_index == 1
    assert reset.next_utterance_index == 2
    assert len(recognizer.streams) == 2
    assert following[0].revision_number == 0
    assert following[0].is_first_partial is True
    assert adapter.status_record().recognizer_loaded is True


def test_endpoint_enable_requires_a_provenance_policy_id() -> None:
    backend = SherpaOnnxASR(
        {"sample_rate": 16000, "tail_padding_sec": 0},
        recognizer=FakeSherpaRecognizer(),
    )

    with pytest.raises(ContractValidationError, match="explicit policy_id"):
        backend.open_stream(endpoint_overlay={"enabled": True})


def test_runtime_rejects_audio_before_start_and_after_finalize() -> None:
    adapter = SherpaStreamingASRAdapter(
        SherpaOnnxASR(
            {"sample_rate": 16000, "tail_padding_sec": 0},
            recognizer=FakeSherpaRecognizer(),
        )
    )

    with pytest.raises(ContractValidationError, match="not running"):
        adapter.accept_samples(_chunk(), sample_rate=16000)

    adapter.start("session-state")
    adapter.accept_samples(_chunk(), sample_rate=16000)
    adapter.finalize_one()

    with pytest.raises(ContractValidationError, match="not running"):
        adapter.accept_samples(_chunk(), sample_rate=16000)


def test_common_interface_accepts_normalized_frame_and_returns_adapter_record() -> None:
    adapter = SherpaStreamingASRAdapter(
        SherpaOnnxASR(
            {"sample_rate": 16000, "tail_padding_sec": 0},
            recognizer=FakeSherpaRecognizer(),
        )
    )
    adapter.start("session-common")

    rows = adapter.accept_audio(_frame(1, 4.0))
    final_rows = adapter.finalize("input_finished")

    assert rows[0]["adapter_event_type"] == "asr_partial"
    assert rows[0]["session_id"] == "session-common"
    assert rows[0]["audio_consumed_through_sec"] == pytest.approx(4.1)
    assert rows[0]["token_timestamps_sec"] == pytest.approx([4.1])
    assert final_rows[0]["adapter_event_type"] == "asr_final"
    interval = final_rows[0]["accepted_audio_interval"]
    assert interval == {
        "sample_start_index": 64000,
        "sample_end_index": 65600,
        "audio_start_sec": 4.0,
        "audio_end_sec": 4.1,
        "sample_rate_hz": 16000,
        "source_clock_id": "test-clock",
        "source_clock_type": "file",
        "timing_provenance": ACCEPTED_AUDIO_INTERVAL_PROVENANCE,
        "interval_role": "utterance_input_since_stream_or_reset",
        "word_timestamps_inferred": False,
    }
    assert adapter.status()["state"] == "finalized"


def test_endpoint_reset_starts_a_new_truthful_accepted_audio_interval() -> None:
    adapter = SherpaStreamingASRAdapter(
        SherpaOnnxASR(
            {"sample_rate": 16000, "tail_padding_sec": 0},
            recognizer=FakeSherpaRecognizer(endpoint_after_chunks=1),
        ),
        endpoint_overlay={
            "enabled": True,
            "policy_id": "test_endpoint_interval.v1",
        },
    )
    adapter.start("session-endpoint-interval")

    first = adapter.accept_audio(_frame(1, 4.0))
    second = adapter.accept_audio(_frame(2, 4.1))
    final = adapter.finalize("input_finished")

    endpoint = next(row for row in first if row["adapter_event_type"] == "asr_final")
    assert endpoint["utterance_index"] == 1
    assert endpoint["accepted_audio_interval"]["audio_start_sec"] == pytest.approx(
        4.0
    )
    assert endpoint["accepted_audio_interval"]["audio_end_sec"] == pytest.approx(
        4.1
    )
    assert second[0]["utterance_index"] == 2
    assert final[0]["utterance_index"] == 2
    assert final[0]["accepted_audio_interval"]["sample_start_index"] == 65600
    assert final[0]["accepted_audio_interval"]["sample_end_index"] == 67200
    assert final[0]["accepted_audio_interval"]["audio_start_sec"] == pytest.approx(4.1)
    assert final[0]["accepted_audio_interval"]["audio_end_sec"] == pytest.approx(4.2)
