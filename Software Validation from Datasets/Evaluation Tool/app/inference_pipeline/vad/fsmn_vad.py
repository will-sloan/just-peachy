"""FunASR FSMN-VAD adapter using a pinned local quantized ONNX checkpoint."""

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
from app.inference_pipeline.vad.base import VADBase


class FSMNVADUnavailableError(InferencePipelineError):
    """Raised when FunASR FSMN-VAD or its local model directory is unavailable."""


@dataclass
class FSMNVAD(VADBase):
    """Map FunASR millisecond regions into pipeline-native speech regions."""

    params: Mapping[str, object] | None = None
    detector: Any | None = None

    name = "fsmn_vad"

    def __post_init__(self) -> None:
        raw = dict(self.params or {})
        VADBase.__init__(self, raw)
        self.model_path = raw.get("model_path")
        self.quantize = bool(raw.get("quantize", True))
        self.device_id = str(raw.get("device_id", "-1"))
        if self.device_id != "-1":
            raise ContractValidationError(
                "the qualified FSMN-VAD component is CPU-only (device_id=-1)"
            )
        self.intra_op_num_threads = _positive_int(
            raw.get("intra_op_num_threads", 2), "intra_op_num_threads"
        )
        self.max_end_sil = _optional_positive_int(
            raw.get("max_end_sil"), "max_end_sil"
        )
        if raw.get("allow_model_downloads") not in (None, False):
            raise ContractValidationError(
                "FSMN-VAD campaign inference prohibits implicit model downloads"
            )

    def detect(self, audio: LoadedAudio) -> list[SpeechRegion]:
        samples = _mono_samples(audio)
        if audio.sample_rate != self.params.sample_rate:
            samples = resample_audio(
                samples[:, None], audio.sample_rate, self.params.sample_rate
            )[:, 0]
        if samples.size == 0:
            return []
        try:
            raw_segments = self._detector()(samples)
        except Exception as exc:
            raise FSMNVADUnavailableError(f"FSMN-VAD inference failed: {exc}") from exc
        if raw_segments in (None, ""):
            return []
        first = raw_segments[0] if isinstance(raw_segments, list) and raw_segments else []
        if not isinstance(first, list):
            raise FSMNVADUnavailableError("FSMN-VAD returned an unexpected segment shape")
        duration = samples.size / self.params.sample_rate
        regions: list[SpeechRegion] = []
        for value in first:
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                raise FSMNVADUnavailableError("FSMN-VAD emitted a malformed region")
            start_sec = max(0.0, float(value[0]) / 1000.0)
            end_sec = min(duration, float(value[1]) / 1000.0)
            if end_sec > start_sec:
                regions.append(
                    SpeechRegion(start_sec=start_sec, end_sec=end_sec, label="speech")
                )
        regions.sort(key=lambda item: (item.start_sec, item.end_sec))
        return regions

    def _detector(self) -> Any:
        if self.detector is not None:
            return self.detector
        if importlib.util.find_spec("funasr_onnx") is None:
            raise FSMNVADUnavailableError(
                "funasr-onnx is not installed in the active environment"
            )
        try:
            model_path = resolve_model_path(self.model_path)
            required = ("am.mvn", "config.yaml", "model_quant.onnx")
            missing = [name for name in required if not (model_path / name).is_file()]
            if missing:
                raise FileNotFoundError(
                    "FSMN-VAD model directory is missing: " + ", ".join(missing)
                )
            from funasr_onnx import Fsmn_vad

            kwargs: dict[str, object] = {
                "model_dir": str(model_path),
                "device_id": self.device_id,
                "quantize": self.quantize,
                "intra_op_num_threads": self.intra_op_num_threads,
            }
            if self.max_end_sil is not None:
                kwargs["max_end_sil"] = self.max_end_sil
            self.detector = Fsmn_vad(**kwargs)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise FSMNVADUnavailableError(f"FSMN-VAD model load failed: {exc}") from exc
        return self.detector


def _mono_samples(audio: LoadedAudio) -> np.ndarray:
    waveform = audio.waveform.detach().cpu().float()
    if waveform.ndim == 1:
        mono = waveform
    elif waveform.ndim == 2:
        mono = waveform.mean(dim=0)
    else:
        raise ContractValidationError(
            "FSMN-VAD waveform must have shape [samples] or [channels, samples]"
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


def _optional_positive_int(value: object, field_name: str) -> int | None:
    return None if value is None else _positive_int(value, field_name)
