"""Strict, deterministic RTTM and UEM parsing and writing."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable

from app.diarization_evaluation.contracts import DiarizationEvaluationError


@dataclass(frozen=True, order=True)
class RttmTurn:
    """One standards-compatible RTTM SPEAKER interval."""

    recording_id: str
    channel: str
    start_sec: float
    end_sec: float
    speaker_label: str

    def __post_init__(self) -> None:
        _token(self.recording_id, "RTTM recording_id")
        _token(self.channel, "RTTM channel")
        _token(self.speaker_label, "RTTM speaker_label")
        _interval(self.start_sec, self.end_sec, "RTTM")

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec

    def to_line(self) -> str:
        return (
            f"SPEAKER {self.recording_id} {self.channel} {self.start_sec:.6f} "
            f"{self.duration_sec:.6f} <NA> <NA> {self.speaker_label} <NA> <NA>"
        )


@dataclass(frozen=True, order=True)
class UemRegion:
    """One UEM scored region in source-recording coordinates."""

    recording_id: str
    channel: str
    start_sec: float
    end_sec: float

    def __post_init__(self) -> None:
        _token(self.recording_id, "UEM recording_id")
        _token(self.channel, "UEM channel")
        _interval(self.start_sec, self.end_sec, "UEM")

    def to_line(self) -> str:
        return f"{self.recording_id} {self.channel} {self.start_sec:.6f} {self.end_sec:.6f}"


def parse_rttm(value: Path | str, *, from_text: bool = False) -> list[RttmTurn]:
    text = value if from_text else Path(value).read_text(encoding="utf-8")
    turns: list[RttmTurn] = []
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 10 or fields[0] != "SPEAKER":
            raise DiarizationEvaluationError(f"invalid RTTM row at line {line_number}")
        try:
            start = float(fields[3])
            duration = float(fields[4])
        except ValueError as exc:
            raise DiarizationEvaluationError(
                f"non-numeric RTTM time at line {line_number}"
            ) from exc
        if not math.isfinite(duration) or duration <= 0:
            raise DiarizationEvaluationError(
                f"RTTM duration must be finite and positive at line {line_number}"
            )
        turns.append(
            RttmTurn(
                fields[1],
                fields[2],
                start,
                round(start + duration, 6),
                fields[7],
            )
        )
    return sorted(turns)


def parse_uem(value: Path | str, *, from_text: bool = False) -> list[UemRegion]:
    text = value if from_text else Path(value).read_text(encoding="utf-8")
    regions: list[UemRegion] = []
    for line_number, raw in enumerate(str(text).splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 4:
            raise DiarizationEvaluationError(f"invalid UEM row at line {line_number}")
        try:
            start = float(fields[2])
            end = float(fields[3])
        except ValueError as exc:
            raise DiarizationEvaluationError(
                f"non-numeric UEM time at line {line_number}"
            ) from exc
        regions.append(UemRegion(fields[0], fields[1], start, end))
    _reject_overlapping_uem(regions)
    return sorted(regions)


def write_rttm(path: Path, turns: Iterable[RttmTurn]) -> Path:
    rows = [turn.to_line() for turn in sorted(set(turns))]
    _write_text(path, "\n".join(rows) + ("\n" if rows else ""))
    return path


def write_uem(path: Path, regions: Iterable[UemRegion]) -> Path:
    materialized = sorted(set(regions))
    _reject_overlapping_uem(materialized)
    rows = [region.to_line() for region in materialized]
    _write_text(path, "\n".join(rows) + ("\n" if rows else ""))
    return path


def _reject_overlapping_uem(regions: Iterable[UemRegion]) -> None:
    by_key: dict[tuple[str, str], list[UemRegion]] = {}
    for region in regions:
        by_key.setdefault((region.recording_id, region.channel), []).append(region)
    for key, rows in by_key.items():
        ordered = sorted(rows)
        for left, right in zip(ordered, ordered[1:], strict=False):
            if right.start_sec < left.end_sec:
                raise DiarizationEvaluationError(f"overlapping UEM regions for {key}")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _token(value: object, label: str) -> None:
    text = str(value).strip()
    if not text or any(character.isspace() for character in text):
        raise DiarizationEvaluationError(f"{label} must be a non-empty token")


def _interval(start: float, end: float, label: str) -> None:
    if not math.isfinite(float(start)) or not math.isfinite(float(end)):
        raise DiarizationEvaluationError(f"{label} times must be finite")
    if float(start) < 0 or float(end) <= float(start):
        raise DiarizationEvaluationError(f"{label} interval must satisfy 0 <= start < end")
