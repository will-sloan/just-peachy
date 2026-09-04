"""Causal wrappers around the existing Pyannote segmentation engine.

The installed Segmentation 3.0 checkpoint was trained on 10-second chunks and
its PyanNet uses a bidirectional LSTM.  It is therefore not a zero-lookahead
model.  The default runtime feeds rolling 10-second chunks and commits only up
to the chunk midpoint: a truthful 5-second algorithmic lookahead.  Compute
latency must be recorded separately.  End-of-stream tail output is marked as
reduced-lookahead evidence rather than being presented as equivalent.

This module plans/crops chunks and causal windows.  Neural inference remains in
the existing ``ModularClusteringDiarizer`` inside the isolated worker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Sequence

import numpy as np


ROLLING_SEGMENTATION_POLICY_ID = (
    "pyannote_segmentation_3_0_rolling_10s_lookahead_5s_speech_overlap.v2"
)
DIARIZATION_WINDOW_POLICY_ID = "diarization_midpoint_windows_1p5s_step_0p75s.v1"


class SegmentationContractError(ValueError):
    """Raised when streaming segmentation time/sample contracts are invalid."""


@dataclass(frozen=True)
class RollingSegmentationConfig:
    sample_rate_hz: int = 16_000
    chunk_duration_sec: float = 10.0
    hop_duration_sec: float = 0.75
    algorithmic_lookahead_sec: float = 5.0
    onset: float = 0.5
    offset: float = 0.5
    minimum_speech_duration_sec: float = 0.0
    minimum_silence_duration_sec: float = 0.0
    policy_id: str = ROLLING_SEGMENTATION_POLICY_ID

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise SegmentationContractError("sample_rate_hz must be positive")
        if self.chunk_duration_sec <= 0 or self.hop_duration_sec <= 0:
            raise SegmentationContractError("chunk and hop durations must be positive")
        if self.hop_duration_sec > self.chunk_duration_sec:
            raise SegmentationContractError(
                "hop_duration_sec must not exceed chunk_duration_sec"
            )
        if not 0 <= self.algorithmic_lookahead_sec < self.chunk_duration_sec:
            raise SegmentationContractError(
                "algorithmic_lookahead_sec must be non-negative and shorter than the chunk"
            )
        if not 0 <= self.onset <= 1 or not 0 <= self.offset <= 1:
            raise SegmentationContractError("onset and offset must be in [0, 1]")
        if (
            self.minimum_speech_duration_sec < 0
            or self.minimum_silence_duration_sec < 0
        ):
            raise SegmentationContractError(
                "minimum speech/silence durations must be >= 0"
            )
        # The frozen checkpoint is explicitly a 10 s bidirectional model.  A
        # different rolling policy needs a new identity, not a quiet override.
        if self.policy_id == ROLLING_SEGMENTATION_POLICY_ID and (
            not math.isclose(self.chunk_duration_sec, 10.0)
            or not math.isclose(self.algorithmic_lookahead_sec, 5.0)
        ):
            raise SegmentationContractError(
                "the v2 rolling Pyannote speech/overlap policy is fixed to 10 s chunks "
                "and 5 s lookahead"
            )

    @property
    def chunk_samples(self) -> int:
        return round(self.chunk_duration_sec * self.sample_rate_hz)

    @property
    def hop_samples(self) -> int:
        return round(self.hop_duration_sec * self.sample_rate_hz)

    @property
    def lookahead_samples(self) -> int:
        return round(self.algorithmic_lookahead_sec * self.sample_rate_hz)

    def to_jsonable(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "model_training_chunk_duration_sec": 10.0,
            "model_temporal_architecture": "bidirectional_lstm",
            "sample_rate_hz": self.sample_rate_hz,
            "chunk_duration_sec": self.chunk_duration_sec,
            "hop_duration_sec": self.hop_duration_sec,
            "algorithmic_lookahead_sec": self.algorithmic_lookahead_sec,
            "compute_latency_included_in_lookahead": False,
            "end_of_stream_tail_has_reduced_lookahead": True,
            "onset": self.onset,
            "offset": self.offset,
            "minimum_speech_duration_sec": self.minimum_speech_duration_sec,
            "minimum_silence_duration_sec": self.minimum_silence_duration_sec,
        }


@dataclass(frozen=True)
class RollingSegmentationChunk:
    chunk_index: int
    input_start_sample: int
    input_end_sample: int
    valid_input_end_sample: int
    commit_start_sample: int
    commit_end_sample: int
    audio: np.ndarray
    sample_rate_hz: int
    algorithmic_lookahead_sec: float
    final_tail: bool = False
    lookahead_complete: bool = True

    @property
    def input_start_sec(self) -> float:
        return self.input_start_sample / self.sample_rate_hz

    @property
    def input_end_sec(self) -> float:
        return self.input_end_sample / self.sample_rate_hz

    @property
    def commit_start_sec(self) -> float:
        return self.commit_start_sample / self.sample_rate_hz

    @property
    def commit_end_sec(self) -> float:
        return self.commit_end_sample / self.sample_rate_hz


class RollingSegmentationPlanner:
    """Turn normalized mono frames into overlapping chunks and commit horizons."""

    def __init__(self, config: RollingSegmentationConfig | None = None) -> None:
        self.config = config or RollingSegmentationConfig()
        self._origin_sample = 0
        self._buffer = np.empty(0, dtype=np.float32)
        self._buffer_start_sample = 0
        self._total_samples = 0
        self._next_chunk_end_sample = self.config.chunk_samples
        self._committed_sample = 0
        self._chunk_index = 0
        self._flushed = False

    @property
    def total_samples(self) -> int:
        return self._total_samples

    def add(
        self, frames: Sequence[float] | np.ndarray
    ) -> tuple[RollingSegmentationChunk, ...]:
        if self._flushed:
            raise SegmentationContractError("cannot add audio after flush")
        values = np.asarray(frames, dtype=np.float32).reshape(-1)
        if values.size and not np.isfinite(values).all():
            raise SegmentationContractError("audio frames must be finite")
        if values.size:
            self._buffer = np.concatenate((self._buffer, values))
            self._total_samples += int(values.size)
        chunks: list[RollingSegmentationChunk] = []
        while self._next_chunk_end_sample <= self._total_samples:
            start = self._next_chunk_end_sample - self.config.chunk_samples
            commit_end = self._next_chunk_end_sample - self.config.lookahead_samples
            if commit_end > self._committed_sample:
                chunks.append(
                    self._chunk(
                        start=start,
                        end=self._next_chunk_end_sample,
                        valid_end=self._next_chunk_end_sample,
                        commit_end=commit_end,
                        final_tail=False,
                    )
                )
            self._next_chunk_end_sample += self.config.hop_samples
        self._trim_buffer()
        return tuple(chunks)

    def flush(self) -> tuple[RollingSegmentationChunk, ...]:
        """Commit the uncommitted tail and label its reduced future context."""

        if self._flushed:
            return ()
        self._flushed = True
        if self._total_samples <= self._committed_sample:
            return ()
        valid_end = self._total_samples
        start = max(self._origin_sample, valid_end - self.config.chunk_samples)
        end = start + self.config.chunk_samples
        return (
            self._chunk(
                start=start,
                end=end,
                valid_end=valid_end,
                commit_end=valid_end,
                final_tail=True,
            ),
        )

    def reset(self, *, origin_sample: int = 0) -> None:
        if origin_sample < 0:
            raise SegmentationContractError("origin_sample must be non-negative")
        self.__init__(self.config)
        self._origin_sample = int(origin_sample)
        self._buffer_start_sample = int(origin_sample)
        self._total_samples = int(origin_sample)
        self._next_chunk_end_sample = int(origin_sample) + self.config.chunk_samples
        self._committed_sample = int(origin_sample)

    def _chunk(
        self,
        *,
        start: int,
        end: int,
        valid_end: int,
        commit_end: int,
        final_tail: bool,
    ) -> RollingSegmentationChunk:
        self._chunk_index += 1
        audio = self._slice(start, min(end, valid_end))
        if audio.size < end - start:
            audio = np.pad(audio, (0, end - start - audio.size))
        commit_start = self._committed_sample
        self._committed_sample = commit_end
        return RollingSegmentationChunk(
            chunk_index=self._chunk_index,
            input_start_sample=start,
            input_end_sample=end,
            valid_input_end_sample=valid_end,
            commit_start_sample=commit_start,
            commit_end_sample=commit_end,
            audio=np.asarray(audio, dtype=np.float32),
            sample_rate_hz=self.config.sample_rate_hz,
            algorithmic_lookahead_sec=self.config.algorithmic_lookahead_sec,
            final_tail=final_tail,
            lookahead_complete=not final_tail,
        )

    def _slice(self, start: int, end: int) -> np.ndarray:
        relative_start = start - self._buffer_start_sample
        relative_end = end - self._buffer_start_sample
        if relative_start < 0 or relative_end > self._buffer.size:
            raise SegmentationContractError(
                "rolling buffer no longer contains requested chunk"
            )
        return np.array(self._buffer[relative_start:relative_end], copy=True)

    def _trim_buffer(self) -> None:
        keep_from = max(0, self._total_samples - self.config.chunk_samples)
        if keep_from <= self._buffer_start_sample:
            return
        trim = keep_from - self._buffer_start_sample
        self._buffer = np.array(self._buffer[trim:], copy=True)
        self._buffer_start_sample = keep_from


@dataclass(frozen=True)
class SpeechBoundary:
    event: str
    timestamp_sec: float


@dataclass(frozen=True)
class SegmentationCommit:
    commit_start_sec: float
    commit_end_sec: float
    speech_regions: tuple[tuple[float, float], ...]
    boundaries: tuple[SpeechBoundary, ...]
    algorithmic_lookahead_sec: float
    final_tail: bool


class CausalSpeechRegionTracker:
    """Crop overlapping worker regions to the monotonic commit frontier."""

    def __init__(self) -> None:
        self._committed_sec = 0.0
        self._speech_active = False

    def commit(
        self,
        chunk: RollingSegmentationChunk,
        regions: Sequence[Mapping[str, object] | Sequence[float]],
        *,
        sample_rate_hz: int = 16_000,
    ) -> SegmentationCommit:
        start = chunk.commit_start_sample / sample_rate_hz
        end = chunk.commit_end_sample / sample_rate_hz
        if start + 1e-9 < self._committed_sec:
            raise SegmentationContractError("segmentation commits must be monotonic")
        cropped = _crop_regions(regions, start, end)
        boundaries: list[SpeechBoundary] = []
        cursor = start
        active = self._speech_active
        for region_start, region_end in cropped:
            if region_start > cursor + 1e-9 and active:
                boundaries.append(SpeechBoundary("speech_end", cursor))
                active = False
            if not active:
                boundaries.append(SpeechBoundary("speech_start", region_start))
                active = True
            cursor = region_end
            if region_end < end - 1e-9:
                boundaries.append(SpeechBoundary("speech_end", region_end))
                active = False
        if not cropped and active:
            boundaries.append(SpeechBoundary("speech_end", start))
            active = False
        self._speech_active = active
        self._committed_sec = end
        return SegmentationCommit(
            commit_start_sec=start,
            commit_end_sec=end,
            speech_regions=tuple(cropped),
            boundaries=tuple(boundaries),
            algorithmic_lookahead_sec=chunk.algorithmic_lookahead_sec,
            final_tail=chunk.final_tail,
        )

    def reset(self, *, origin_sec: float = 0.0) -> None:
        if origin_sec < 0 or not math.isfinite(origin_sec):
            raise SegmentationContractError(
                "origin_sec must be finite and non-negative"
            )
        self._committed_sec = float(origin_sec)
        self._speech_active = False


@dataclass(frozen=True)
class DiarizationWindow:
    window_id: str
    region_id: str
    start_sec: float
    end_sec: float
    assignment_start_sec: float
    assignment_end_sec: float
    provisional: bool
    revision: int


@dataclass(frozen=True)
class WindowPlanUpdate:
    new_windows: tuple[DiarizationWindow, ...]
    revised_windows: tuple[DiarizationWindow, ...]


class CausalDiarizationWindowPlanner:
    """Incrementally reproduce the locked 1.5/0.75 midpoint window policy."""

    def __init__(
        self,
        *,
        duration_sec: float = 1.5,
        step_sec: float = 0.75,
        minimum_sec: float = 0.75,
    ) -> None:
        if duration_sec <= 0 or step_sec <= 0 or minimum_sec <= 0:
            raise SegmentationContractError("window durations must be positive")
        if step_sec > duration_sec or minimum_sec > duration_sec:
            raise SegmentationContractError("invalid diarization window policy")
        self.duration_sec = duration_sec
        self.step_sec = step_sec
        self.minimum_sec = minimum_sec
        self._regions: dict[str, dict[str, object]] = {}

    def advance(
        self, *, region_id: str, start_sec: float, end_sec: float, final: bool
    ) -> WindowPlanUpdate:
        if end_sec <= start_sec:
            raise SegmentationContractError("speech region must be increasing")
        state = self._regions.setdefault(
            region_id, {"start": start_sec, "end": start_sec, "windows": {}}
        )
        if not math.isclose(float(state["start"]), start_sec, abs_tol=1e-9):
            raise SegmentationContractError(
                "region start changed during incremental planning"
            )
        if end_sec + 1e-9 < float(state["end"]):
            raise SegmentationContractError("region end moved backwards")
        state["end"] = end_sec
        intervals = _window_intervals(
            start_sec,
            end_sec,
            duration_sec=self.duration_sec,
            step_sec=self.step_sec,
            minimum_sec=self.minimum_sec,
            final=final,
        )
        centers = [(left + right) / 2.0 for left, right in intervals]
        boundaries = [start_sec]
        boundaries.extend(
            (left + right) / 2.0 for left, right in zip(centers, centers[1:])
        )
        boundaries.append(end_sec)
        previous = dict(state["windows"])
        current: dict[str, DiarizationWindow] = {}
        new: list[DiarizationWindow] = []
        revised: list[DiarizationWindow] = []
        for index, (left, right) in enumerate(intervals):
            window_id = f"{region_id}_window_{index:06d}"
            old = previous.get(window_id)
            new_provisional = not final and index == len(intervals) - 1
            revision = (
                int(old.revision + 1)
                if old
                and (
                    not math.isclose(
                        old.assignment_start_sec, boundaries[index], abs_tol=1e-9
                    )
                    or not math.isclose(
                        old.assignment_end_sec, boundaries[index + 1], abs_tol=1e-9
                    )
                    or old.provisional != new_provisional
                )
                else int(old.revision if old else 0)
            )
            row = DiarizationWindow(
                window_id=window_id,
                region_id=region_id,
                start_sec=left,
                end_sec=right,
                assignment_start_sec=boundaries[index],
                assignment_end_sec=boundaries[index + 1],
                provisional=new_provisional,
                revision=revision,
            )
            current[window_id] = row
            if old is None:
                new.append(row)
            elif row != old:
                revised.append(row)
        state["windows"] = current
        return WindowPlanUpdate(tuple(new), tuple(revised))

    def cache_state(self, region_id: str) -> dict[str, object]:
        """Return the complete result-affecting state for one speech region."""

        state = self._regions.get(region_id)
        if state is None:
            return {"exists": False}
        windows = dict(state["windows"])
        return {
            "exists": True,
            "start": float(state["start"]),
            "end": float(state["end"]),
            "windows": [asdict(windows[key]) for key in sorted(windows)],
        }

    def restore_cached(
        self, region_id: str, payload: Mapping[str, object]
    ) -> WindowPlanUpdate:
        """Restore a checksum-validated cached advance without recomputation."""

        state_payload = payload.get("next_state")
        if not isinstance(state_payload, Mapping) or not state_payload.get("exists"):
            raise SegmentationContractError("cached window plan lacks next state")

        def rows(name: str) -> tuple[DiarizationWindow, ...]:
            raw = payload.get(name)
            if not isinstance(raw, Sequence):
                raise SegmentationContractError(f"cached window plan lacks {name}")
            return tuple(DiarizationWindow(**dict(value)) for value in raw)

        all_windows = tuple(
            DiarizationWindow(**dict(value))
            for value in state_payload.get("windows", [])
        )
        self._regions[region_id] = {
            "start": float(state_payload["start"]),
            "end": float(state_payload["end"]),
            "windows": {value.window_id: value for value in all_windows},
        }
        return WindowPlanUpdate(rows("new_windows"), rows("revised_windows"))


def _crop_regions(
    regions: Sequence[Mapping[str, object] | Sequence[float]],
    start: float,
    end: float,
) -> list[tuple[float, float]]:
    values: list[tuple[float, float]] = []
    for row in regions:
        if isinstance(row, Mapping):
            left, right = float(row["start_sec"]), float(row["end_sec"])
        else:
            left, right = float(row[0]), float(row[1])
        left, right = max(start, left), min(end, right)
        if right > left:
            values.append((left, right))
    merged: list[tuple[float, float]] = []
    for left, right in sorted(values):
        if not merged or left > merged[-1][1] + 1e-9:
            merged.append((left, right))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], right))
    return merged


def _window_intervals(
    start: float,
    end: float,
    *,
    duration_sec: float,
    step_sec: float,
    minimum_sec: float,
    final: bool,
) -> list[tuple[float, float]]:
    length = end - start
    if length < minimum_sec:
        return []
    if length <= duration_sec:
        return [(start, end)] if final else []
    starts: list[float] = []
    current = start
    while current + duration_sec <= end + 1e-9:
        starts.append(round(current, 9))
        current += step_sec
    if final:
        starts.append(round(end - duration_sec, 9))
    return [(left, min(end, left + duration_sec)) for left in sorted(set(starts))]
