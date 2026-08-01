"""Sherpa-ONNX VAD adapter backed by a local Silero ONNX model."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.inference_pipeline.audio_io import LoadedAudio
from app.inference_pipeline.audio_io.resample import resample_audio
from app.inference_pipeline.contracts import SpeechRegion
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.vad.base import VADBase, VADParameters


class SherpaOnnxVADUnavailableError(InferencePipelineError):
    """Raised when the Sherpa-ONNX VAD runtime or model is unavailable."""


@dataclass
class SherpaOnnxVAD(VADBase):
    """Sherpa-ONNX Silero VAD producing pipeline-native speech regions."""

    params: Mapping[str, object] | None = None
    detector: Any | None = None

    name = "sherpa_onnx_vad"

    def __post_init__(self) -> None:
        raw = dict(self.params or {})
        VADBase.__init__(self, raw)
        self.model_path = raw.get("model_path") or raw.get("model")
        self.num_threads = _positive_int(raw.get("num_threads", 1), "num_threads")
        self.provider = str(raw.get("provider") or "cpu")
        self.window_size = _positive_int(raw.get("window_size", 512), "window_size")
        self.max_speech_duration_sec = _positive_float(
            raw.get("max_speech_duration_sec", 20.0),
            "max_speech_duration_sec",
        )
        self.buffer_size_sec = _positive_float(
            raw.get("buffer_size_sec", 60.0),
            "buffer_size_sec",
        )

    def detect(self, audio: LoadedAudio) -> list[SpeechRegion]:
        samples = _mono_samples(audio)
        source_rate = int(audio.sample_rate or self.params.sample_rate)
        if source_rate != self.params.sample_rate:
            samples = resample_audio(
                samples[:, None], source_rate, self.params.sample_rate
            )[:, 0]
        samples = np.ascontiguousarray(samples, dtype=np.float32)
        if samples.size == 0:
            return []
        detector = self._detector()
        try:
            if hasattr(detector, "reset"):
                detector.reset()
            detector.accept_waveform(samples)
            detector.flush()
            segments: list[SpeechRegion] = []
            while not detector.empty():
                segment = detector.front
                start_sec = float(segment.start) / self.params.sample_rate
                end_sec = start_sec + len(segment.samples) / self.params.sample_rate
                detector.pop()
                if end_sec > start_sec:
                    segments.append(
                        SpeechRegion(
                            start_sec=start_sec,
                            end_sec=end_sec,
                            label="speech",
                        )
                    )
            return segments
        except Exception as exc:
            raise SherpaOnnxVADUnavailableError(
                f"Sherpa-ONNX VAD inference failed: {exc}"
            ) from exc

    def _detector(self) -> Any:
        if self.detector is not None:
            return self.detector
        if importlib.util.find_spec("sherpa_onnx") is None:
            raise SherpaOnnxVADUnavailableError(
                "sherpa-onnx is not installed in the active environment."
            )
        try:
            model_path = resolve_model_path(self.model_path)
        except (ContractValidationError, FileNotFoundError) as exc:
            raise SherpaOnnxVADUnavailableError(
                f"Sherpa-ONNX VAD model is unavailable: {exc}"
            ) from exc
        try:
            import sherpa_onnx  # type: ignore[import-not-found]

            silero = sherpa_onnx.SileroVadModelConfig(
                model=str(model_path),
                threshold=self.params.threshold,
                min_silence_duration=self.params.min_silence_ms / 1000.0,
                min_speech_duration=self.params.min_speech_ms / 1000.0,
                window_size=self.window_size,
                max_speech_duration=self.max_speech_duration_sec,
            )
            config = sherpa_onnx.VadModelConfig(
                silero_vad=silero,
                sample_rate=self.params.sample_rate,
                num_threads=self.num_threads,
                provider=self.provider,
            )
            self.detector = sherpa_onnx.VoiceActivityDetector(
                config,
                buffer_size_in_seconds=self.buffer_size_sec,
            )
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SherpaOnnxVADUnavailableError(
                f"Sherpa-ONNX VAD load failed: {exc}"
            ) from exc
        return self.detector


def _mono_samples(audio: LoadedAudio) -> np.ndarray:
    waveform = audio.waveform.detach().cpu().float()
    if waveform.ndim == 1:
        mono = waveform
    elif waveform.ndim == 2:
        mono = waveform.mean(dim=0)
    else:
        raise ContractValidationError(
            "Sherpa-ONNX VAD waveform must have shape [samples] or [channels, samples]"
        )
    return np.ascontiguousarray(mono.numpy(), dtype=np.float32)


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed


def _positive_float(value: object, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if parsed <= 0:
        raise ContractValidationError(f"{field_name} must be > 0")
    return parsed
