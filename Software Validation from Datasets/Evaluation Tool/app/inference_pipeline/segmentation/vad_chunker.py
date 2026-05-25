"""VAD-region chunker for model-friendly audio segments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from app.inference_pipeline.contracts import AudioSegment, EvaluationRecord, SpeechRegion
from app.inference_pipeline.segmentation.base import SegmenterBase, SegmenterParameters
from app.inference_pipeline.segmentation.windowing import (
    TimeInterval,
    clip_interval,
    merge_intervals,
    split_interval_evenly,
)


@dataclass
class VADChunker(SegmenterBase):
    """Convert speech regions into deterministic chunk intervals."""

    params: SegmenterParameters | Mapping[str, object] | None = None

    name = "vad_chunks"

    def __post_init__(self) -> None:
        SegmenterBase.__init__(self, self.params)

    def segment(
        self,
        record: EvaluationRecord,
        speech_regions: Sequence[SpeechRegion],
        audio: object | None = None,
    ) -> list[AudioSegment]:
        origin_sec = record.start_sec or 0.0
        source_intervals = [
            (origin_sec + region.start_sec, origin_sec + region.end_sec)
            for region in speech_regions
            if region.end_sec > region.start_sec
        ]
        merged = merge_intervals(source_intervals, merge_gap_sec=self.params.merge_gap_sec)
        speech_sized = [
            interval
            for interval in merged
            if interval[1] - interval[0] >= self.params.min_chunk_sec
        ]

        bound_start, bound_end = _segment_bounds(record, audio, origin_sec)
        output_intervals: list[TimeInterval] = []
        for start_sec, end_sec in speech_sized:
            padded = (
                start_sec - self.params.left_pad_sec,
                end_sec + self.params.right_pad_sec,
            )
            clipped = (
                clip_interval(
                    padded,
                    min_start_sec=bound_start,
                    max_end_sec=bound_end,
                )
                if self.params.clip_to_record_bounds
                else padded
            )
            if clipped is None or clipped[1] <= clipped[0]:
                continue
            output_intervals.extend(
                split_interval_evenly(
                    clipped,
                    max_chunk_sec=self.params.max_chunk_sec,
                )
            )

        return [
            _audio_segment_from_interval(record, audio, interval)
            for interval in sorted(output_intervals)
            if interval[1] > interval[0]
        ]


def _segment_bounds(
    record: EvaluationRecord,
    audio: object | None,
    origin_sec: float,
) -> tuple[float | None, float | None]:
    lower = record.start_sec if record.start_sec is not None else 0.0
    if record.end_sec is not None:
        return lower, record.end_sec

    duration = _audio_duration_sec(record, audio)
    if duration is not None:
        return lower, origin_sec + duration
    return lower, None


def _audio_duration_sec(record: EvaluationRecord, audio: object | None) -> float | None:
    value = getattr(audio, "duration_sec", None)
    if value is None:
        value = record.duration_sec
    if value is None and record.start_sec is not None and record.end_sec is not None:
        value = record.end_sec - record.start_sec
    if value is None:
        return None
    return max(0.0, float(value))


def _audio_segment_from_interval(
    record: EvaluationRecord,
    audio: object | None,
    interval: TimeInterval,
) -> AudioSegment:
    start_sec, end_sec = interval
    channel_count = (
        record.channel_count
        if record.channel_count is not None
        else int(getattr(audio, "num_channels", 1) or 1)
    )
    sample_rate_hz = (
        record.sample_rate_hz
        if record.sample_rate_hz is not None
        else _optional_int(getattr(audio, "sample_rate", None))
    )
    return AudioSegment(
        audio_path=record.inference_audio_path,
        start_sec=start_sec,
        end_sec=end_sec,
        sample_rate_hz=sample_rate_hz,
        channel_index=record.channel_index,
        channel_count=channel_count,
        is_mono=channel_count == 1,
        duration_sec=end_sec - start_sec,
    )


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)
