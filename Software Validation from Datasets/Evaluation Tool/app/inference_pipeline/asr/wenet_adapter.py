"""Lazy WeNet ASR adapter."""

from __future__ import annotations

import importlib.util
import inspect
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app.inference_pipeline.asr.audio_utils import (
    load_segment_audio,
    resolve_model_path,
    temporary_pcm16_wav,
)
from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    normalize_text,
)
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.resource_telemetry.context import telemetry_span


class WeNetASRUnavailableError(InferencePipelineError):
    """Raised when WeNet or its configured model is unavailable."""


@dataclass
class WeNetASR(ASRBase):
    """WeNet Python API adapter using a local checkpoint directory by default."""

    params: Mapping[str, object] | None = None
    model: Any | None = None

    name = "wenet"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})
        self.model_name = str(self.params.get("model_name", "wenet"))
        self.sample_rate = _positive_int(self.params.get("sample_rate", 16000), "sample_rate")
        self.device = str(self.params.get("device", "cpu"))
        self.language = _optional_string(self.params.get("language"))
        self.allow_model_downloads = bool(self.params.get("allow_model_downloads", False))
        self.audio_backend = str(self.params.get("audio_backend", "soundfile"))
        if self.audio_backend not in {"soundfile", "wenet"}:
            raise ContractValidationError(
                "WeNet audio_backend must be either 'soundfile' or 'wenet'"
            )
        self._load_sec: float | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        audio = load_segment_audio(audio_segment, target_sample_rate=self.sample_rate)
        model = self._model(context)
        started_at = time.perf_counter()
        try:
            with telemetry_span(
                "asr_inference",
                phase="warm_inference",
                identifiers={
                    "recording_id": context.recording_id,
                    "utt_id": context.utt_id,
                    "segment_index": context.segment_index,
                },
                cuda=self.device == "cuda",
            ):
                with temporary_pcm16_wav(audio, prefix="wenet-asr-") as wav_path:
                    result = model.transcribe(str(wav_path))
        except Exception as exc:
            raise WeNetASRUnavailableError(f"WeNet transcription failed: {exc}") from exc

        inference_sec = time.perf_counter() - started_at
        raw_text = _result_text(result)
        normalized_text = normalize_text(raw_text)
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio.duration_sec,
            device=self.device,
            dtype="float32",
        )
        return ASRTranscript(
            text=normalized_text,
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _model(self, context: ASRContext | None = None) -> Any:
        if self.model is not None:
            return self.model
        if importlib.util.find_spec("wenet") is None:
            raise WeNetASRUnavailableError(
                "WeNet is not installed in the active environment."
            )

        configured_path = self.params.get("model_path")
        if self.allow_model_downloads:
            model_reference = str(configured_path or self.model_name)
        else:
            try:
                model_reference = str(resolve_model_path(configured_path, context))
            except (ContractValidationError, FileNotFoundError) as exc:
                raise WeNetASRUnavailableError(
                    f"WeNet local model assets are unavailable: {exc}"
                ) from exc

        _prepare_wenet_torch_compatibility()
        import wenet  # type: ignore[import-not-found]

        started_at = time.perf_counter()
        try:
            with telemetry_span(
                "asr_model_load",
                phase="cold_initialization",
                cuda=self.device == "cuda",
            ):
                self.model = _load_wenet_model(
                    wenet.load_model,
                    model_reference=model_reference,
                    device=self.device,
                )
                if self.audio_backend == "soundfile":
                    _attach_soundfile_feature_loader(self.model, Path(model_reference))
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise WeNetASRUnavailableError(f"WeNet model load failed: {exc}") from exc
        self._load_sec = time.perf_counter() - started_at
        return self.model


def _result_text(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        return str(result.get("text") or result.get("sentence") or "")
    return str(getattr(result, "text", ""))


def _attach_soundfile_feature_loader(model: Any, model_dir: Path) -> None:
    """Use project-native WAV loading while retaining WeNet feature extraction."""

    import numpy as np
    import soundfile as sf
    import torch
    import yaml
    import wenet.dataset.processor as processor  # type: ignore[import-not-found]

    config_path = model_dir / "train.yaml"
    with config_path.open("r", encoding="utf-8") as stream:
        configs = yaml.safe_load(stream)
    dataset_conf = configs["dataset_conf"]
    feature_type = str(dataset_conf.get("feats_type", "fbank"))
    if feature_type not in {"fbank", "mfcc", "log_mel_spectrogram"}:
        raise ValueError(f"Unsupported WeNet feature type: {feature_type}")
    feature_conf = dict(dataset_conf.get(f"{feature_type}_conf", {}))
    feature_function = getattr(processor, f"compute_{feature_type}")

    def compute_feature(wav_file: str) -> Any:
        samples, sample_rate = sf.read(
            wav_file,
            dtype="float32",
            always_2d=True,
        )
        sample = {
            "key": str(wav_file),
            "wav": torch.from_numpy(np.ascontiguousarray(samples.T)),
            "sample_rate": int(sample_rate),
        }
        sample = processor.resample(sample, 16000)
        sample = feature_function(sample, **feature_conf)
        return sample["feat"]

    setattr(model, "compute_feature", compute_feature)


def _prepare_wenet_torch_compatibility() -> None:
    """Restore Torch typing re-exports expected by current WeNet on newer Torch."""

    from typing import Optional, Union

    from torch import Tensor
    import torch.nn.modules.conv as torch_conv

    compatibility_names = {
        "Optional": Optional,
        "Tensor": Tensor,
        "Union": Union,
    }
    for name, value in compatibility_names.items():
        if not hasattr(torch_conv, name):
            setattr(torch_conv, name, value)


def _load_wenet_model(
    loader: Any,
    *,
    model_reference: str,
    device: str,
) -> Any:
    """Call the pinned v3.1 API while retaining compatibility with wrappers.

    WeNet v3.1 names the local path ``model_dir`` and selects devices through
    an integer ``gpu`` argument. Some downstream wrappers expose the simpler
    ``load_model(path, device=...)`` API that the original adapter targeted.
    Signature inspection avoids a failed load or an implicit language lookup.
    """

    parameters = inspect.signature(loader).parameters
    if "model_dir" in parameters:
        gpu = 0 if device == "cuda" else -1
        return loader(model_dir=model_reference, gpu=gpu)
    return loader(model_reference, device=device)


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed


def _optional_string(value: object) -> str | None:
    return None if value is None or not str(value).strip() else str(value)
