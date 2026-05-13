"""Timestamp validation and sample-frame slicing helpers."""

from __future__ import annotations

from dataclasses import dataclass

from app.inference_pipeline.errors import ContractValidationError


@dataclass(frozen=True)
class SegmentFrames:
    """Validated source-frame range for an audio load."""

    start_sec: float | None
    end_sec: float | None
    start_frame: int
    frame_count: int
    duration_sec: float


def resolve_segment_frames(
    start_value: object,
    end_value: object,
    sample_rate: int,
    total_frames: int,
) -> SegmentFrames:
    """Convert optional start/end seconds into a checked source-frame slice."""

    if sample_rate < 1:
        raise ContractValidationError("sample_rate must be >= 1")
    if total_frames < 0:
        raise ContractValidationError("total_frames must be >= 0")

    start_sec = optional_seconds(start_value, "start_sec")
    end_sec = optional_seconds(end_value, "end_sec")

    if start_sec is not None and start_sec < 0:
        raise ContractValidationError("start_sec must be >= 0")
    if end_sec is not None and end_sec < 0:
        raise ContractValidationError("end_sec must be >= 0")
    if start_sec is not None and end_sec is not None and end_sec <= start_sec:
        raise ContractValidationError("end_sec must be greater than start_sec")

    start_frame = seconds_to_frame(start_sec or 0.0, sample_rate)
    end_frame = (
        seconds_to_frame(end_sec, sample_rate)
        if end_sec is not None
        else total_frames
    )

    if start_frame > total_frames:
        raise ContractValidationError("start_sec exceeds available audio duration")
    if end_frame > total_frames:
        raise ContractValidationError("end_sec exceeds available audio duration")
    if end_frame <= start_frame:
        raise ContractValidationError("requested audio segment is empty")

    frame_count = end_frame - start_frame
    return SegmentFrames(
        start_sec=start_sec,
        end_sec=end_sec,
        start_frame=start_frame,
        frame_count=frame_count,
        duration_sec=frame_count / sample_rate,
    )


def optional_seconds(value: object, field_name: str) -> float | None:
    """Parse optional timestamp fields from selected metadata rows."""

    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric when present") from exc


def seconds_to_frame(seconds: float, sample_rate: int) -> int:
    """Map seconds to the nearest sample frame in the source audio."""

    return int(round(seconds * sample_rate))
