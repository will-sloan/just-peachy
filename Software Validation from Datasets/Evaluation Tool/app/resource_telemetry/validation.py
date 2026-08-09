"""Validation and relationship analysis for completed component spans."""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from app.resource_telemetry.contracts import COMPONENT_SPANS_SCHEMA_VERSION


REQUIRED_SPAN_FIELDS = frozenset(
    {
        "schema_version",
        "campaign_id",
        "scenario_id",
        "attempt",
        "worker_id",
        "host",
        "pid",
        "thread_id",
        "span_id",
        "parent_span_id",
        "name",
        "phase",
        "start_timestamp_utc",
        "start_monotonic_ns",
        "end_monotonic_ns",
        "duration_ns",
        "status",
        "cuda_timing_requested",
        "cuda_timing_available",
        "cuda_elapsed_ms",
        "cuda_availability_reason",
        "recording_id",
        "utt_id",
        "segment_index",
    }
)


def validate_spans(
    rows: Iterable[Mapping[str, object]],
    *,
    scenario_id: str | None = None,
) -> tuple[str, ...]:
    """Validate span identities/bounds and report non-fatal overlap warnings."""

    materialized = [dict(row) for row in rows]
    ids = [str(row.get("span_id") or "") for row in materialized]
    duplicates = [span_id for span_id, count in Counter(ids).items() if not span_id or count > 1]
    if duplicates:
        raise ValueError(f"component spans contain duplicate or empty IDs: {duplicates}")
    by_id = {str(row["span_id"]): row for row in materialized}
    for row in materialized:
        missing = REQUIRED_SPAN_FIELDS - set(row)
        if missing:
            raise ValueError(f"component span missing fields: {sorted(missing)}")
        if row.get("schema_version") != COMPONENT_SPANS_SCHEMA_VERSION:
            raise ValueError("component span uses an unsupported schema")
        if scenario_id is not None and row.get("scenario_id") != scenario_id:
            raise ValueError("component span scenario identity mismatch")
        start = _integer(row.get("start_monotonic_ns"), "start_monotonic_ns")
        end = _integer(row.get("end_monotonic_ns"), "end_monotonic_ns")
        duration = _integer(row.get("duration_ns"), "duration_ns")
        if end < start or duration != end - start:
            raise ValueError("component span duration does not match monotonic bounds")
        parent_id = row.get("parent_span_id")
        if parent_id is not None:
            parent = by_id.get(str(parent_id))
            if parent is None:
                raise ValueError(f"component span parent {parent_id!r} is missing")
            parent_start = _integer(parent.get("start_monotonic_ns"), "start_monotonic_ns")
            parent_end = _integer(parent.get("end_monotonic_ns"), "end_monotonic_ns")
            if start < parent_start or end > parent_end:
                raise ValueError("child component span falls outside parent bounds")
    return _crossing_overlap_warnings(materialized)


def _crossing_overlap_warnings(rows: list[dict[str, object]]) -> tuple[str, ...]:
    warnings: list[str] = []
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            if left.get("thread_id") != right.get("thread_id"):
                continue
            left_start = int(left["start_monotonic_ns"])
            left_end = int(left["end_monotonic_ns"])
            right_start = int(right["start_monotonic_ns"])
            right_end = int(right["end_monotonic_ns"])
            crossing = (
                left_start < right_start < left_end < right_end
                or right_start < left_start < right_end < left_end
            )
            if crossing:
                warnings.append(
                    "crossing spans on one thread: "
                    f"{left.get('name')} ({left.get('span_id')}) and "
                    f"{right.get('name')} ({right.get('span_id')})"
                )
    return tuple(warnings)


def _integer(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"component span {field} must be an integer")
    return value
