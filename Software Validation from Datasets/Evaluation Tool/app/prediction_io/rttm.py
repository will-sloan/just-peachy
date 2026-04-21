"""Helpers for optional future RTTM diarization outputs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RttmSegment:
    """A minimal RTTM speaker segment."""

    recording_id: str
    start_sec: float
    end_sec: float
    speaker_label: str


def read_rttm_lines(path: Path) -> list[str]:
    """Read a plain RTTM file without interpreting speaker segments yet."""

    if not path.exists():
        return []
    return [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_rttm_lines(path: Path, lines: list[str]) -> None:
    """Write optional RTTM lines for future diarization datasets."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_rttm_segments(path: Path) -> list[RttmSegment]:
    """Parse SPEAKER rows from an RTTM file.

    This is intentionally a small parser for first-phase AMI support. It keeps
    the recording/file id, start time, duration-derived end time, and speaker
    label used by the standard RTTM SPEAKER line.
    """

    segments: list[RttmSegment] = []
    for line in read_rttm_lines(path):
        parts = line.split()
        if len(parts) < 8 or parts[0].upper() != "SPEAKER":
            continue
        try:
            start_sec = float(parts[3])
            duration_sec = float(parts[4])
        except ValueError:
            continue
        segments.append(
            RttmSegment(
                recording_id=parts[1],
                start_sec=start_sec,
                end_sec=start_sec + max(0.0, duration_sec),
                speaker_label=parts[7],
            )
        )
    return segments
