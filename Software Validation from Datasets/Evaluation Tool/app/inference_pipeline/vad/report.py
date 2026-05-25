"""VAD metric summaries and component report writing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.inference_pipeline.contracts import SpeechRegion


@dataclass(frozen=True)
class VADMetrics:
    """Summary metrics for one VAD run."""

    audio_duration_sec: float
    speech_coverage_ratio: float
    region_count: int
    segment_count_per_minute: float
    runtime_sec: float
    realtime_factor: float | None
    false_speech_rate: float | None = None
    missed_speech_rate: float | None = None
    boundary_error_sec: float | None = None

    def to_markdown_rows(self) -> list[str]:
        return [
            f"- Speech coverage ratio: `{_format_metric(self.speech_coverage_ratio)}`",
            f"- Region count: `{self.region_count}`",
            f"- Segment count per minute: `{_format_metric(self.segment_count_per_minute)}`",
            f"- VAD runtime sec: `{_format_metric(self.runtime_sec)}`",
            f"- VAD runtime real-time factor: `{_format_metric(self.realtime_factor)}`",
            f"- False speech rate: `{_format_metric(self.false_speech_rate)}`",
            f"- Missed speech rate: `{_format_metric(self.missed_speech_rate)}`",
            f"- Boundary error sec: `{_format_metric(self.boundary_error_sec)}`",
        ]


def summarize_vad(
    regions: Sequence[SpeechRegion],
    *,
    audio_duration_sec: float,
    runtime_sec: float,
    reference_regions: Sequence[SpeechRegion] | None = None,
) -> VADMetrics:
    """Compute VAD summary metrics without requiring scorer changes."""

    duration = max(0.0, float(audio_duration_sec))
    runtime = max(0.0, float(runtime_sec))
    predicted_duration = _covered_duration(regions, duration)
    coverage = predicted_duration / duration if duration else 0.0
    region_count = len(regions)
    segment_count_per_minute = region_count / (duration / 60.0) if duration else 0.0
    realtime_factor = runtime / duration if duration else None

    false_speech_rate = None
    missed_speech_rate = None
    boundary_error_sec = None
    if reference_regions is not None:
        reference_duration = _covered_duration(reference_regions, duration)
        overlap = _overlap_duration(regions, reference_regions, duration)
        missed_speech_rate = (
            max(0.0, reference_duration - overlap) / reference_duration
            if reference_duration
            else None
        )
        non_speech_duration = max(0.0, duration - reference_duration)
        false_speech_rate = (
            max(0.0, predicted_duration - overlap) / non_speech_duration
            if non_speech_duration
            else None
        )
        boundary_error_sec = _boundary_error(regions, reference_regions)

    return VADMetrics(
        audio_duration_sec=duration,
        speech_coverage_ratio=coverage,
        region_count=region_count,
        segment_count_per_minute=segment_count_per_minute,
        runtime_sec=runtime,
        realtime_factor=realtime_factor,
        false_speech_rate=false_speech_rate,
        missed_speech_rate=missed_speech_rate,
        boundary_error_sec=boundary_error_sec,
    )


def write_vad_report(
    path: Path,
    *,
    run_id: str,
    backend_name: str,
    metrics: VADMetrics | None,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_command: str,
    silero_status: str,
    runner_contract: str,
    enabled_disabled_status: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the M5 VAD component report artifact."""

    lines = [
        "# VAD Component Report",
        "",
        "## Milestone",
        "",
        "M5 - VAD Interface and First VAD Adapter",
        "",
        f"- Run id: `{run_id}`",
        f"- Selected VAD backend: `{backend_name}`",
        f"- Silero status: {silero_status}",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M5 adds a swappable VAD interface plus a deterministic energy-based backend.",
        "The Silero adapter remains a lazy boundary because local model assets are unavailable.",
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
        "## VAD Metrics",
        "",
    ]
    if metrics is None:
        lines.append("VAD metrics were not produced because the smoke command was blocked.")
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


def _covered_duration(regions: Sequence[SpeechRegion], audio_duration_sec: float) -> float:
    intervals = _merged_intervals(regions, audio_duration_sec)
    return sum(end - start for start, end in intervals)


def _overlap_duration(
    predicted: Sequence[SpeechRegion],
    reference: Sequence[SpeechRegion],
    audio_duration_sec: float,
) -> float:
    predicted_intervals = _merged_intervals(predicted, audio_duration_sec)
    reference_intervals = _merged_intervals(reference, audio_duration_sec)
    overlap = 0.0
    for pred_start, pred_end in predicted_intervals:
        for ref_start, ref_end in reference_intervals:
            overlap += max(0.0, min(pred_end, ref_end) - max(pred_start, ref_start))
    return overlap


def _boundary_error(
    predicted: Sequence[SpeechRegion],
    reference: Sequence[SpeechRegion],
) -> float | None:
    if not predicted or not reference:
        return None
    errors: list[float] = []
    for ref in reference:
        best = min(
            predicted,
            key=lambda pred: abs(pred.start_sec - ref.start_sec) + abs(pred.end_sec - ref.end_sec),
        )
        errors.append(
            (abs(best.start_sec - ref.start_sec) + abs(best.end_sec - ref.end_sec)) / 2.0
        )
    return sum(errors) / len(errors) if errors else None


def _merged_intervals(
    regions: Sequence[SpeechRegion],
    audio_duration_sec: float,
) -> list[tuple[float, float]]:
    intervals = sorted(
        (
            max(0.0, min(audio_duration_sec, region.start_sec)),
            max(0.0, min(audio_duration_sec, region.end_sec)),
        )
        for region in regions
        if region.end_sec > region.start_sec
    )
    merged: list[tuple[float, float]] = []
    for start, end in intervals:
        if end <= start:
            continue
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
    return merged


def _format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
