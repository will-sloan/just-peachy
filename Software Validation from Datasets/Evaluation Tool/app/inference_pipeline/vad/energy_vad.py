"""Deterministic energy-based VAD backend."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import torch

from app.inference_pipeline.audio_io import LoadedAudio
from app.inference_pipeline.contracts import SpeechRegion
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.vad.base import VADBase, VADParameters


@dataclass
class EnergyVAD(VADBase):
    """Simple frame-RMS VAD suitable for offline smoke tests."""

    params: VADParameters | dict[str, object] | None = None
    frame_ms: int = 10

    name = "energy_vad"

    def __post_init__(self) -> None:
        VADBase.__init__(self, self.params)
        if self.frame_ms < 1:
            raise ContractValidationError("frame_ms must be >= 1")

    def detect(self, audio: LoadedAudio) -> list[SpeechRegion]:
        waveform = _mono_waveform(audio.waveform)
        sample_rate = int(audio.sample_rate)
        if sample_rate < 1:
            raise ContractValidationError("audio sample_rate must be >= 1")
        if waveform.numel() == 0:
            return []

        frame_size = max(1, round(sample_rate * self.frame_ms / 1000))
        frame_flags, frame_energies = _frame_flags(
            waveform,
            frame_size=frame_size,
            threshold=float(self.params.threshold),
        )
        if not any(frame_flags):
            return []

        min_speech_frames = _ms_to_frames(self.params.min_speech_ms, self.frame_ms)
        min_silence_frames = _ms_to_frames(self.params.min_silence_ms, self.frame_ms)
        pad_sec = self.params.pad_ms / 1000.0
        duration_sec = waveform.numel() / sample_rate

        merged = _fill_short_silences(frame_flags, min_silence_frames)
        speech_runs = _speech_runs(merged, min_speech_frames)
        regions: list[SpeechRegion] = []
        for start_frame, end_frame in speech_runs:
            start_sec = max(0.0, start_frame * frame_size / sample_rate - pad_sec)
            end_sec = min(duration_sec, min(waveform.numel(), end_frame * frame_size) / sample_rate + pad_sec)
            if end_sec <= start_sec:
                continue
            confidence = _region_confidence(
                frame_energies[start_frame:end_frame],
                float(self.params.threshold),
            )
            regions.append(
                SpeechRegion(
                    start_sec=start_sec,
                    end_sec=end_sec,
                    confidence=confidence,
                    label="speech",
                )
            )
        return _merge_overlapping(regions)


def _mono_waveform(waveform: torch.Tensor) -> torch.Tensor:
    if waveform.ndim == 1:
        return waveform.float()
    if waveform.ndim == 2:
        return waveform.float().mean(dim=0)
    raise ContractValidationError("vad waveform must have shape [samples] or [channels, samples]")


def _frame_flags(
    waveform: torch.Tensor,
    *,
    frame_size: int,
    threshold: float,
) -> tuple[list[bool], list[float]]:
    frame_count = ceil(waveform.numel() / frame_size)
    flags: list[bool] = []
    energies: list[float] = []
    for frame_index in range(frame_count):
        start = frame_index * frame_size
        end = min(waveform.numel(), start + frame_size)
        frame = waveform[start:end]
        energy = float(torch.sqrt(torch.mean(frame * frame)).item()) if frame.numel() else 0.0
        energies.append(energy)
        flags.append(energy >= threshold)
    return flags, energies


def _fill_short_silences(flags: list[bool], min_silence_frames: int) -> list[bool]:
    if min_silence_frames <= 0:
        return list(flags)
    result = list(flags)
    index = 0
    while index < len(result):
        if result[index]:
            index += 1
            continue
        start = index
        while index < len(result) and not result[index]:
            index += 1
        end = index
        touches_speech = start > 0 and end < len(result) and result[start - 1] and result[end]
        if touches_speech and end - start < min_silence_frames:
            for gap_index in range(start, end):
                result[gap_index] = True
    return result


def _speech_runs(flags: list[bool], min_speech_frames: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    index = 0
    while index < len(flags):
        if not flags[index]:
            index += 1
            continue
        start = index
        while index < len(flags) and flags[index]:
            index += 1
        end = index
        if end - start >= max(1, min_speech_frames):
            runs.append((start, end))
    return runs


def _ms_to_frames(value_ms: int, frame_ms: int) -> int:
    if value_ms <= 0:
        return 0
    return max(1, ceil(value_ms / frame_ms))


def _region_confidence(energies: list[float], threshold: float) -> float | None:
    if not energies:
        return None
    mean_energy = sum(energies) / len(energies)
    if threshold <= 0:
        return 1.0 if mean_energy > 0 else 0.0
    return max(0.0, min(1.0, mean_energy / (mean_energy + threshold)))


def _merge_overlapping(regions: list[SpeechRegion]) -> list[SpeechRegion]:
    if not regions:
        return []
    merged: list[SpeechRegion] = [regions[0]]
    for region in regions[1:]:
        previous = merged[-1]
        if region.start_sec > previous.end_sec:
            merged.append(region)
            continue
        confidence_values = [
            value for value in (previous.confidence, region.confidence) if value is not None
        ]
        confidence = (
            sum(confidence_values) / len(confidence_values)
            if confidence_values
            else None
        )
        merged[-1] = SpeechRegion(
            start_sec=previous.start_sec,
            end_sec=max(previous.end_sec, region.end_sec),
            confidence=confidence,
            label=previous.label or region.label,
        )
    return merged
