"""WebRTC VAD adapter using fixed-duration PCM16 frames."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from app.inference_pipeline.audio_io import LoadedAudio
from app.inference_pipeline.audio_io.resample import resample_audio
from app.inference_pipeline.contracts import SpeechRegion
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.vad.base import VADBase, VADParameters


class WebRTCVADUnavailableError(InferencePipelineError):
    """Raised when WebRTC VAD cannot be loaded or process configured audio."""


@dataclass
class WebRTCVAD(VADBase):
    """CPU-only WebRTC VAD with common region merging and padding semantics."""

    params: Mapping[str, object] | None = None
    engine: Any | None = None

    name = "webrtc_vad"

    def __post_init__(self) -> None:
        raw = dict(self.params or {})
        VADBase.__init__(self, raw)
        self.mode = _bounded_int(raw.get("mode", 2), "mode", minimum=0, maximum=3)
        self.frame_ms = _choice_int(raw.get("frame_ms", 30), "frame_ms", {10, 20, 30})
        if self.params.sample_rate not in {8000, 16000, 32000, 48000}:
            raise ContractValidationError(
                "WebRTC VAD sample_rate must be one of 8000, 16000, 32000, or 48000"
            )

    def detect(self, audio: LoadedAudio) -> list[SpeechRegion]:
        samples = _mono_samples(audio)
        source_rate = int(audio.sample_rate or self.params.sample_rate)
        samples = _resample_mono(samples, source_rate, self.params.sample_rate)
        if samples.size == 0:
            return []
        engine = self._engine()
        frame_samples = self.params.sample_rate * self.frame_ms // 1000
        decisions: list[tuple[float, float]] = []
        pcm = np.clip(samples, -1.0, 1.0)
        pcm = (pcm * 32767.0).astype("<i2", copy=False)
        try:
            for offset in range(0, len(pcm), frame_samples):
                frame = pcm[offset : offset + frame_samples]
                if len(frame) < frame_samples:
                    frame = np.pad(frame, (0, frame_samples - len(frame)))
                if engine.is_speech(frame.tobytes(), self.params.sample_rate):
                    decisions.append(
                        (
                            offset / self.params.sample_rate,
                            min(len(pcm), offset + frame_samples) / self.params.sample_rate,
                        )
                    )
        except Exception as exc:
            raise WebRTCVADUnavailableError(f"WebRTC VAD inference failed: {exc}") from exc
        return _merge_voiced_frames(
            decisions,
            duration_sec=len(samples) / self.params.sample_rate,
            min_speech_sec=self.params.min_speech_ms / 1000.0,
            max_gap_sec=self.params.min_silence_ms / 1000.0,
            pad_sec=self.params.pad_ms / 1000.0,
        )

    def _engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        if importlib.util.find_spec("webrtcvad") is None:
            raise WebRTCVADUnavailableError(
                "webrtcvad is not installed; install the webrtcvad-wheels package."
            )
        try:
            import webrtcvad  # type: ignore[import-not-found]

            self.engine = webrtcvad.Vad(self.mode)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise WebRTCVADUnavailableError(f"WebRTC VAD load failed: {exc}") from exc
        return self.engine


def _mono_samples(audio: LoadedAudio) -> np.ndarray:
    waveform = audio.waveform.detach().cpu().float()
    if waveform.ndim == 1:
        mono = waveform
    elif waveform.ndim == 2:
        mono = waveform.mean(dim=0)
    else:
        raise ContractValidationError(
            "WebRTC VAD waveform must have shape [samples] or [channels, samples]"
        )
    return np.ascontiguousarray(mono.numpy(), dtype=np.float32)


def _resample_mono(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return samples
    resampled = resample_audio(samples[:, None], source_rate, target_rate)
    return np.ascontiguousarray(resampled[:, 0], dtype=np.float32)


def _merge_voiced_frames(
    frames: list[tuple[float, float]],
    *,
    duration_sec: float,
    min_speech_sec: float,
    max_gap_sec: float,
    pad_sec: float,
) -> list[SpeechRegion]:
    if not frames:
        return []
    merged: list[tuple[float, float]] = []
    start_sec, end_sec = frames[0]
    for next_start, next_end in frames[1:]:
        if next_start - end_sec <= max_gap_sec + 1e-9:
            end_sec = max(end_sec, next_end)
        else:
            merged.append((start_sec, end_sec))
            start_sec, end_sec = next_start, next_end
    merged.append((start_sec, end_sec))
    return [
        SpeechRegion(
            start_sec=max(0.0, start - pad_sec),
            end_sec=min(duration_sec, end + pad_sec),
            label="speech",
        )
        for start, end in merged
        if end - start + 1e-9 >= min_speech_sec
    ]


def _bounded_int(
    value: object,
    field_name: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ContractValidationError(
            f"{field_name} must be between {minimum} and {maximum}"
        )
    return parsed


def _choice_int(value: object, field_name: str, choices: set[int]) -> int:
    parsed = _bounded_int(value, field_name, minimum=min(choices), maximum=max(choices))
    if parsed not in choices:
        raise ContractValidationError(
            f"{field_name} must be one of {', '.join(str(item) for item in sorted(choices))}"
        )
    return parsed
