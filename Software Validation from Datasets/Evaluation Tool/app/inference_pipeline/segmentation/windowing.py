"""Deterministic time-window helpers for segmentation."""

from __future__ import annotations

from math import ceil
from typing import Sequence

from app.inference_pipeline.errors import ContractValidationError


TimeInterval = tuple[float, float]


def merge_intervals(
    intervals: Sequence[TimeInterval],
    *,
    merge_gap_sec: float,
) -> list[TimeInterval]:
    """Merge sorted or unsorted intervals separated by a short enough gap."""

    if merge_gap_sec < 0:
        raise ContractValidationError("merge_gap_sec must be >= 0")
    ordered = sorted(
        (float(start), float(end))
        for start, end in intervals
        if float(end) > float(start)
    )
    merged: list[TimeInterval] = []
    for start, end in ordered:
        if not merged:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        if start - previous_end <= merge_gap_sec:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def clip_interval(
    interval: TimeInterval,
    *,
    min_start_sec: float | None,
    max_end_sec: float | None,
) -> TimeInterval | None:
    """Clip one interval to optional bounds."""

    start, end = interval
    if min_start_sec is not None:
        start = max(start, min_start_sec)
    if max_end_sec is not None:
        end = min(end, max_end_sec)
    if end <= start:
        return None
    return (start, end)


def split_interval_evenly(
    interval: TimeInterval,
    *,
    max_chunk_sec: float,
) -> list[TimeInterval]:
    """Split an interval into deterministic contiguous chunks no longer than max."""

    if max_chunk_sec <= 0:
        raise ContractValidationError("max_chunk_sec must be > 0")
    start, end = interval
    if end <= start:
        return []
    duration = end - start
    if duration <= max_chunk_sec:
        return [(start, end)]

    chunk_count = ceil(duration / max_chunk_sec)
    chunk_duration = duration / chunk_count
    chunks: list[TimeInterval] = []
    for index in range(chunk_count):
        chunk_start = start + index * chunk_duration
        chunk_end = end if index == chunk_count - 1 else start + (index + 1) * chunk_duration
        if chunk_end > chunk_start:
            chunks.append((chunk_start, chunk_end))
    return chunks


def covered_duration(intervals: Sequence[TimeInterval]) -> float:
    """Return covered duration after merging overlaps."""

    return sum(end - start for start, end in merge_intervals(intervals, merge_gap_sec=0.0))


def starts_are_monotonic(intervals: Sequence[TimeInterval]) -> bool:
    """Return whether interval starts are monotonically increasing."""

    return all(
        intervals[index][0] <= intervals[index + 1][0]
        for index in range(len(intervals) - 1)
    )
