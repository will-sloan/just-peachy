"""Silero VAD adapter backed by locally installed package assets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import torch

from app.inference_pipeline.audio_io import LoadedAudio
from app.inference_pipeline.contracts import SpeechRegion
from app.inference_pipeline.errors import InferencePipelineError
from app.inference_pipeline.vad.base import VADBase, VADParameters


class SileroVADUnavailableError(InferencePipelineError):
    """Raised when Silero VAD is selected without local assets."""


@dataclass
class SileroVAD(VADBase):
    """Lazy Silero adapter that does not download model assets."""

    params: VADParameters | dict[str, object] | None = None
    model: Any | None = None
    timestamp_fn: Callable[..., list[Mapping[str, object]]] | None = None
    load_model_fn: Callable[[], Any] | None = None

    name = "silero_vad"

    def __post_init__(self) -> None:
        VADBase.__init__(self, self.params)

    def detect(self, audio: LoadedAudio) -> list[SpeechRegion]:
        waveform = _mono_waveform(audio.waveform)
        sample_rate = int(audio.sample_rate or self.params.sample_rate)
        if sample_rate < 1:
            raise SileroVADUnavailableError("audio sample_rate must be >= 1")
        if waveform.numel() == 0:
            return []

        timestamps = self._timestamp_fn()(
            waveform,
            self._model(),
            threshold=self.params.threshold,
            sampling_rate=sample_rate,
            min_speech_duration_ms=self.params.min_speech_ms,
            min_silence_duration_ms=self.params.min_silence_ms,
            speech_pad_ms=self.params.pad_ms,
            return_seconds=True,
        )
        return _timestamps_to_regions(timestamps, waveform.numel() / sample_rate)

    def _model(self) -> Any:
        if self.model is not None:
            return self.model
        loader = self.load_model_fn or _load_packaged_silero_model
        try:
            self.model = loader()
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SileroVADUnavailableError(
                "Silero VAD model assets are not available locally."
            ) from exc
        return self.model

    def _timestamp_fn(self) -> Callable[..., list[Mapping[str, object]]]:
        if self.timestamp_fn is not None:
            return self.timestamp_fn
        try:
            from silero_vad import get_speech_timestamps
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SileroVADUnavailableError("silero_vad is not importable.") from exc
        return get_speech_timestamps


def _load_packaged_silero_model() -> Any:
    try:
        from silero_vad import load_silero_vad
    except Exception as exc:  # pragma: no cover - dependency boundary
        raise SileroVADUnavailableError("silero_vad is not importable.") from exc
    return load_silero_vad()


def _mono_waveform(waveform: torch.Tensor) -> torch.Tensor:
    if waveform.ndim == 1:
        return waveform.detach().cpu().float()
    if waveform.ndim == 2:
        return waveform.detach().cpu().float().mean(dim=0)
    raise SileroVADUnavailableError(
        "silero vad waveform must have shape [samples] or [channels, samples]"
    )


def _timestamps_to_regions(
    timestamps: list[Mapping[str, object]],
    duration_sec: float,
) -> list[SpeechRegion]:
    regions: list[SpeechRegion] = []
    for item in timestamps:
        start_sec = _timestamp_value(item, "start")
        end_sec = _timestamp_value(item, "end")
        start_sec = max(0.0, min(duration_sec, start_sec))
        end_sec = max(0.0, min(duration_sec, end_sec))
        if end_sec <= start_sec:
            continue
        regions.append(
            SpeechRegion(
                start_sec=start_sec,
                end_sec=end_sec,
                confidence=None,
                label="speech",
            )
        )
    return regions


def _timestamp_value(item: Mapping[str, object], key: str) -> float:
    try:
        return float(item[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise InferencePipelineError(f"silero timestamp missing numeric {key!r}") from exc
