from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.inference_pipeline.config import PipelineConfig
from app.inference_pipeline.contracts import AudioSegment, EvaluationRecord, SpeechRegion
from app.inference_pipeline.dummy_components import DummyASRComponent, DummySpeakerLabeler
from app.inference_pipeline.pipeline import PipelineRunner
from app.inference_pipeline.registry import resolve_components
from app.inference_pipeline.segmentation.base import (
    NoOpSegmenter,
    build_segmenter_from_config,
    trace_segments,
)
from app.inference_pipeline.segmentation.report import (
    summarize_segments,
    write_segmentation_report,
)
from app.inference_pipeline.segmentation.vad_chunker import VADChunker
from app.inference_pipeline.segmentation.windowing import split_interval_evenly
from app.inference_pipeline.vad.base import FixedVAD


TOOL_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = TOOL_ROOT / "configs" / "inference"
LOGGER = logging.getLogger(__name__)


def evaluation_record(
    *,
    start_sec: float | None = 0.0,
    end_sec: float | None = 10.0,
    duration_sec: float | None = 10.0,
) -> EvaluationRecord:
    return EvaluationRecord(
        recording_id="rec-001",
        utt_id="utt-001",
        inference_audio_path=Path("synthetic.wav"),
        start_sec=start_sec,
        end_sec=end_sec,
        sample_rate_hz=16000,
        duration_sec=duration_sec,
    )


def chunker(**params: object) -> VADChunker:
    defaults: dict[str, object] = {
        "min_chunk_sec": 0.2,
        "max_chunk_sec": 30.0,
        "merge_gap_sec": 0.2,
        "left_pad_sec": 0.0,
        "right_pad_sec": 0.0,
        "clip_to_record_bounds": True,
    }
    defaults.update(params)
    return VADChunker(defaults)


def regions(*spans: tuple[float, float]) -> list[SpeechRegion]:
    return [
        SpeechRegion(start_sec=start, end_sec=end, confidence=0.8, label="speech")
        for start, end in spans
    ]


def test_empty_vad_regions_return_no_segments() -> None:
    segments = chunker().segment(evaluation_record(), [])

    assert segments == []


def test_one_speech_region_becomes_one_audio_segment() -> None:
    segments = chunker().segment(evaluation_record(), regions((0.2, 0.6)))

    assert len(segments) == 1
    segment = segments[0]
    assert isinstance(segment, AudioSegment)
    assert segment.audio_path == Path("synthetic.wav")
    assert segment.start_sec == pytest.approx(0.2)
    assert segment.end_sec == pytest.approx(0.6)
    assert segment.duration_sec == pytest.approx(0.4)
    assert segment.sample_rate_hz == 16000


def test_adjacent_regions_merge_when_gap_is_small_enough() -> None:
    segments = chunker(merge_gap_sec=0.15).segment(
        evaluation_record(),
        regions((0.1, 0.4), (0.5, 0.9)),
    )

    assert len(segments) == 1
    assert segments[0].start_sec == pytest.approx(0.1)
    assert segments[0].end_sec == pytest.approx(0.9)


def test_adjacent_regions_do_not_merge_when_gap_is_too_large() -> None:
    segments = chunker(merge_gap_sec=0.05).segment(
        evaluation_record(),
        regions((0.1, 0.4), (0.5, 0.9)),
    )

    assert [(segment.start_sec, segment.end_sec) for segment in segments] == [
        (pytest.approx(0.1), pytest.approx(0.4)),
        (pytest.approx(0.5), pytest.approx(0.9)),
    ]


def test_long_regions_split_deterministically() -> None:
    segments = chunker(max_chunk_sec=2.0).segment(
        evaluation_record(end_sec=5.0, duration_sec=5.0),
        regions((0.0, 5.0)),
    )

    assert len(segments) == 3
    assert all(segment.duration_sec <= 2.0 for segment in segments)
    assert segments[0].start_sec == pytest.approx(0.0)
    assert segments[-1].end_sec == pytest.approx(5.0)
    assert split_interval_evenly((0.0, 5.0), max_chunk_sec=2.0) == [
        (pytest.approx(0.0), pytest.approx(5.0 / 3.0)),
        (pytest.approx(5.0 / 3.0), pytest.approx(10.0 / 3.0)),
        (pytest.approx(10.0 / 3.0), pytest.approx(5.0)),
    ]


def test_tiny_regions_are_rejected_after_merge_policy() -> None:
    segments = chunker(min_chunk_sec=0.25, merge_gap_sec=0.02).segment(
        evaluation_record(),
        regions((0.1, 0.2), (0.5, 0.6)),
    )

    assert segments == []


def test_tiny_regions_can_survive_when_merging_makes_them_valid() -> None:
    segments = chunker(min_chunk_sec=0.25, merge_gap_sec=0.15).segment(
        evaluation_record(),
        regions((0.1, 0.2), (0.3, 0.45)),
    )

    assert len(segments) == 1
    assert segments[0].start_sec == pytest.approx(0.1)
    assert segments[0].end_sec == pytest.approx(0.45)


def test_padding_is_applied_and_clipped_to_record_boundaries() -> None:
    segments = chunker(left_pad_sec=0.2, right_pad_sec=0.2).segment(
        evaluation_record(start_sec=10.0, end_sec=11.0, duration_sec=1.0),
        regions((0.05, 0.95)),
    )

    assert len(segments) == 1
    assert segments[0].start_sec == pytest.approx(10.0)
    assert segments[0].end_sec == pytest.approx(11.0)


def test_output_segments_are_sorted_with_valid_ordered_timestamps() -> None:
    segments = chunker(merge_gap_sec=0.0).segment(
        evaluation_record(),
        regions((1.0, 1.4), (0.1, 0.4), (0.6, 0.9)),
    )

    starts = [segment.start_sec for segment in segments]
    assert starts == sorted(starts)
    assert all(segment.end_sec > segment.start_sec for segment in segments)


def test_segmenter_can_be_selected_by_config() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["segmentation"] = {
        "name": "vad_chunks",
        "enabled": True,
        "adapter": "VADChunkerAdapter",
        "params": {
            "min_chunk_sec": 0.2,
            "max_chunk_sec": 3.0,
            "merge_gap_sec": 0.1,
            "left_pad_sec": 0.0,
            "right_pad_sec": 0.0,
            "clip_to_record_bounds": True,
        },
    }
    config = PipelineConfig.from_mapping(mapping)
    resolved = resolve_components(config)
    segmenter = build_segmenter_from_config(config)
    pipeline = PipelineRunner.with_dummy_components(config=config)

    assert resolved["segmentation"].adapter_class.__name__ == "VADChunkerAdapter"
    assert isinstance(segmenter, VADChunker)
    assert isinstance(pipeline.segmenter, VADChunker)
    assert segmenter.params.max_chunk_sec == 3.0


def test_segmentation_component_file_loads_by_reference() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["segmentation"] = "components/segmentation/vad_chunks.yaml"

    config = PipelineConfig.from_mapping(
        mapping,
        config_dir=CONFIG_ROOT,
        tool_root=TOOL_ROOT,
    )
    resolved = resolve_components(config)

    assert resolved["segmentation"].adapter_class.__name__ == "VADChunkerAdapter"


def test_segmentation_disabled_and_no_op_paths_remain_supported() -> None:
    mapping = PipelineConfig.from_yaml_path(CONFIG_ROOT / "cpu_smoke.yaml").to_jsonable()
    mapping["components"]["segmentation"]["enabled"] = False
    config = PipelineConfig.from_mapping(mapping)
    resolved = resolve_components(config)

    assert resolved["segmentation"].adapter_class.__name__ == "DisabledComponentAdapter"
    assert build_segmenter_from_config(config) is None
    assert NoOpSegmenter().segment(evaluation_record(), regions((0.2, 0.6))) == []


def test_trace_rows_preserve_recording_id_and_utt_id() -> None:
    record = evaluation_record(start_sec=10.0, end_sec=12.0, duration_sec=2.0)
    segments = chunker(merge_gap_sec=0.05).segment(record, regions((0.2, 0.8), (1.0, 1.4)))
    traces = trace_segments(record, segments, target="asr")

    assert [trace.recording_id for trace in traces] == ["rec-001", "rec-001"]
    assert [trace.utt_id for trace in traces] == ["utt-001", "utt-001"]
    assert [trace.segment_index for trace in traces] == [0, 1]
    assert traces[0].start_sec == pytest.approx(10.2)
    assert traces[0].end_sec == pytest.approx(10.8)


class StaticAudioReader:
    def __init__(self, duration_sec: float) -> None:
        self.audio = SimpleNamespace(
            audio_path=Path("synthetic.wav"),
            duration_sec=duration_sec,
            sample_rate=16000,
            num_channels=1,
        )

    def load(self, record: EvaluationRecord, run_config=None):
        _ = (record, run_config)
        return self.audio


def test_pipeline_runs_with_segmentation_enabled_and_disabled() -> None:
    record = {
        "recording_id": "rec-001",
        "utt_id": "utt-001",
        "inference_audio_path": "synthetic.wav",
        "duration_sec": 1.0,
    }
    enabled_pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(1.0),
        asr=DummyASRComponent(),
        speaker_labeler=DummySpeakerLabeler(),
        vad=FixedVAD([SpeechRegion(start_sec=0.25, end_sec=0.75)]),
        segmenter=chunker(),
    )
    disabled_pipeline = PipelineRunner(
        audio_reader=StaticAudioReader(1.0),
        asr=DummyASRComponent(),
        speaker_labeler=DummySpeakerLabeler(),
        vad=FixedVAD([SpeechRegion(start_sec=0.25, end_sec=0.75)]),
    )

    enabled_output = enabled_pipeline.run_one(record, {}, LOGGER)
    disabled_output = disabled_pipeline.run_one(record, {}, LOGGER)

    assert enabled_output.runtime_stats is not None
    assert enabled_output.runtime_stats.counters is not None
    assert enabled_output.runtime_stats.counters["vad_region_count"] == 1
    assert enabled_output.runtime_stats.counters["segment_count"] == 1
    assert enabled_output.runtime_stats.counters["segmentation_sec"] >= 0.0
    assert disabled_output.runtime_stats is not None
    assert disabled_output.runtime_stats.counters == {"vad_region_count": 1}
    assert enabled_output.recording_id == "rec-001"
    assert enabled_output.utt_id == "utt-001"
    assert enabled_output.start_sec is None
    assert enabled_output.end_sec is None


def test_segmentation_report_metrics_and_writer(tmp_path: Path) -> None:
    segments = [
        AudioSegment(audio_path=Path("synthetic.wav"), start_sec=0.0, end_sec=1.0),
        AudioSegment(audio_path=Path("synthetic.wav"), start_sec=1.5, end_sec=2.0),
    ]

    metrics = summarize_segments(segments, audio_duration_sec=2.0, utterance_count=1)
    report_path = write_segmentation_report(
        tmp_path / "segmentation_report_test.md",
        run_id="test",
        backend_name="vad_chunks",
        metrics=metrics,
        files_changed=["app/inference_pipeline/segmentation/base.py"],
        test_commands=["python -m pytest tests/inference_pipeline/test_segmentation.py"],
        smoke_command="direct synthetic smoke",
        runner_contract="recording_id and utt_id are preserved through trace rows.",
        enabled_disabled_status="enabled and disabled paths tested.",
    )

    assert metrics.average_segment_duration_sec == pytest.approx(0.75)
    assert metrics.segment_count_per_utterance == pytest.approx(2.0)
    assert metrics.audio_coverage_percent == pytest.approx(75.0)
    assert metrics.over_fragmentation_score == pytest.approx(1.0)
    assert metrics.ordering_correct is True
    assert "M6 - Segmentation and Chunking Policy" in report_path.read_text(encoding="utf-8")
