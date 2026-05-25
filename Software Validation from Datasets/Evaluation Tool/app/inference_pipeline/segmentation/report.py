"""Segmentation diagnostics and component report writing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.segmentation.windowing import (
    TimeInterval,
    covered_duration,
    starts_are_monotonic,
)


@dataclass(frozen=True)
class SegmentationMetrics:
    """Summary metrics for one segmentation run."""

    audio_duration_sec: float
    segment_count: int
    utterance_count: int
    average_segment_duration_sec: float
    min_segment_duration_sec: float | None
    max_segment_duration_sec: float | None
    segment_count_per_utterance: float
    audio_coverage_percent: float
    over_fragmentation_score: float
    ordering_correct: bool

    def to_markdown_rows(self) -> list[str]:
        return [
            f"- Average segment duration sec: `{_format_metric(self.average_segment_duration_sec)}`",
            f"- Min segment duration sec: `{_format_metric(self.min_segment_duration_sec)}`",
            f"- Max segment duration sec: `{_format_metric(self.max_segment_duration_sec)}`",
            f"- Segment count: `{self.segment_count}`",
            f"- Segment count per utterance: `{_format_metric(self.segment_count_per_utterance)}`",
            f"- Percent of audio covered by segments: `{_format_metric(self.audio_coverage_percent)}`",
            f"- Over-fragmentation score: `{_format_metric(self.over_fragmentation_score)}`",
            f"- Ordering correctness: `{self.ordering_correct}`",
        ]


def summarize_segments(
    segments: Sequence[AudioSegment],
    *,
    audio_duration_sec: float,
    utterance_count: int = 1,
) -> SegmentationMetrics:
    """Compute deterministic segmentation diagnostics."""

    duration = max(0.0, float(audio_duration_sec))
    utterances = max(1, int(utterance_count))
    intervals = _segment_intervals(segments)
    durations = [end - start for start, end in intervals if end > start]
    total_segment_duration = sum(durations)
    segment_count = len(intervals)
    segment_count_per_utterance = segment_count / utterances
    coverage = covered_duration(intervals) / duration * 100.0 if duration else 0.0
    return SegmentationMetrics(
        audio_duration_sec=duration,
        segment_count=segment_count,
        utterance_count=utterances,
        average_segment_duration_sec=(
            total_segment_duration / segment_count if segment_count else 0.0
        ),
        min_segment_duration_sec=min(durations) if durations else None,
        max_segment_duration_sec=max(durations) if durations else None,
        segment_count_per_utterance=segment_count_per_utterance,
        audio_coverage_percent=coverage,
        over_fragmentation_score=max(0.0, segment_count_per_utterance - 1.0),
        ordering_correct=starts_are_monotonic(intervals),
    )


def write_segmentation_report(
    path: Path,
    *,
    run_id: str,
    backend_name: str,
    metrics: SegmentationMetrics | None,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_command: str,
    runner_contract: str,
    enabled_disabled_status: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the M6 segmentation component report artifact."""

    lines = [
        "# Segmentation Component Report",
        "",
        "## Milestone",
        "",
        "M6 - Segmentation and Chunking Policy",
        "",
        f"- Run id: `{run_id}`",
        f"- Selected segmentation backend/policy: `{backend_name}`",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M6 adds a swappable segmentation interface plus a deterministic VAD chunker.",
        "The chunker converts SpeechRegion rows into existing AudioSegment objects.",
        "",
        "## Runner Contract Preservation",
        "",
        runner_contract,
        "",
        "## Commands",
        "",
        *[f"- `{command}`" for command in test_commands],
        f"- `{smoke_command}`",
        "",
        "## Segmentation Metrics",
        "",
    ]
    if metrics is None:
        lines.append("Segmentation metrics were not produced because the smoke command was blocked.")
    else:
        lines.extend(metrics.to_markdown_rows())
    lines.extend(
        [
            "",
            "## Enabled Disabled Status",
            "",
            enabled_disabled_status,
            "",
            "## Blockers",
            "",
        ]
    )
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None known.")
    lines.extend(["", "## Incomplete", ""])
    if incomplete:
        lines.extend(f"- {item}" for item in incomplete)
    else:
        lines.append("- None known.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _segment_intervals(segments: Sequence[AudioSegment]) -> list[TimeInterval]:
    intervals: list[TimeInterval] = []
    for segment in segments:
        if segment.start_sec is None or segment.end_sec is None:
            continue
        intervals.append((float(segment.start_sec), float(segment.end_sec)))
    return intervals


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
