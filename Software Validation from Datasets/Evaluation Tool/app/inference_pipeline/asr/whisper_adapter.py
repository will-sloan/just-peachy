"""Lazy OpenAI Whisper ASR adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

from app.inference_pipeline.asr.audio_utils import load_segment_audio
from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    normalize_text,
    validate_allowed_whisper_model_size,
)
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment, WordTiming
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.resource_telemetry.context import telemetry_span


class WhisperASRUnavailableError(InferencePipelineError):
    """Raised when Whisper dependencies or local assets are unavailable."""


@dataclass
class WhisperASR(ASRBase):
    """Whisper adapter that avoids silent model downloads."""

    params: Mapping[str, object] | None = None
    model: Any | None = None

    name = "whisper_asr"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})
        self.model_size = validate_allowed_whisper_model_size(
            self.params.get("model_size", "tiny")
        )
        self.model_name = str(self.params.get("model_name", f"whisper_{self.model_size}"))
        self.device = str(self.params.get("device", "cpu"))
        self.dtype = str(self.params.get("dtype", "float32"))
        self.language = _optional_string(self.params.get("language"))
        self.cache_dir = _optional_path(self.params.get("cache_dir"))
        self.allow_model_downloads = bool(self.params.get("allow_model_downloads", False))
        self.word_timestamps = bool(self.params.get("word_timestamps", False))
        self.beam_size = _optional_int(self.params.get("beam_size"))
        self._load_sec: float | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        model = self._model(context)
        audio = load_segment_audio(audio_segment, target_sample_rate=16000)
        kwargs: dict[str, object] = {
            "language": self.language or context.language,
            "word_timestamps": self.word_timestamps,
            "fp16": _use_fp16(self.device, self.dtype, context),
        }
        if self.beam_size is not None:
            kwargs["beam_size"] = self.beam_size
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
                cuda=_is_cuda_device(self.device),
            ):
                result = model.transcribe(audio.samples, **kwargs)
                _synchronize_cuda(self.device)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise WhisperASRUnavailableError(f"Whisper transcription failed: {exc}") from exc
        inference_sec = time.perf_counter() - started_at
        raw_text = str(result.get("text", ""))
        normalized_text = normalize_text(raw_text)
        words = (
            _words_from_result(
                result,
                offset_sec=float(audio_segment.start_sec or 0.0),
            )
            if self.word_timestamps
            else ()
        )
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        gpu_memory = _gpu_memory_snapshot(self.device)
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio.duration_sec,
            device=self.device,
            dtype=self.dtype,
            gpu_memory_allocated_mb=gpu_memory["allocated_mb"],
            gpu_memory_reserved_mb=gpu_memory["reserved_mb"],
            peak_gpu_memory_mb=gpu_memory["peak_allocated_mb"],
            peak_gpu_memory_reserved_mb=gpu_memory["peak_reserved_mb"],
            cpu_memory_mb=None,
        )
        return ASRTranscript(
            text=normalized_text,
            words=words,
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _model(self, context: ASRContext | None = None) -> Any:
        if self.model is not None:
            return self.model
        if importlib.util.find_spec("whisper") is None:
            raise WhisperASRUnavailableError(
                "OpenAI Whisper package is not installed in the active environment."
            )
        model_asset = _local_model_asset_path(self.model_size, self.cache_dir, context)
        if not self.allow_model_downloads and model_asset is None:
            raise WhisperASRUnavailableError(
                "Whisper model assets are not available locally and downloads are disabled."
            )

        import whisper  # type: ignore[import-not-found]

        _reset_peak_gpu_memory(self.device)
        started_at = time.perf_counter()
        download_root = _download_root(self.cache_dir, model_asset)
        try:
            with telemetry_span(
                "asr_model_load",
                phase="cold_initialization",
                cuda=_is_cuda_device(self.device),
            ):
                self.model = whisper.load_model(
                    self.model_size,
                    device=self.device,
                    download_root=str(download_root) if download_root is not None else None,
                )
                _synchronize_cuda(self.device)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise WhisperASRUnavailableError(f"Whisper model load failed: {exc}") from exc
        self._load_sec = time.perf_counter() - started_at
        _validate_model_device(self.model, self.device)
        return self.model


def _local_model_asset_path(
    model_size: str,
    cache_dir: Path | None,
    context: ASRContext | None,
) -> Path | None:
    expected_name = f"{model_size}.pt"
    for candidate in _cache_dir_candidates(cache_dir, context):
        model_path = candidate / expected_name
        if model_path.is_file():
            return model_path
    return None


def _download_root(cache_dir: Path | None, model_asset: Path | None) -> Path | None:
    if model_asset is not None:
        return model_asset.parent
    if cache_dir is None or cache_dir.is_absolute():
        return cache_dir
    repository_root = Path(__file__).resolve().parents[5]
    return repository_root / cache_dir


def _cache_dir_candidates(cache_dir: Path | None, context: ASRContext | None) -> list[Path]:
    candidates: list[Path] = []
    if cache_dir is not None:
        candidates.append(cache_dir)
        if not cache_dir.is_absolute():
            candidates.append(Path.cwd() / cache_dir)
            tool_root = Path(__file__).resolve().parents[3]
            candidates.append(tool_root / cache_dir)
            candidates.append(tool_root.parent / cache_dir)
            candidates.append(tool_root.parent.parent / cache_dir)
            project_root = _project_root_from_context(context)
            if project_root is not None:
                candidates.append(project_root / "Evaluation Tool" / cache_dir)
                candidates.append(project_root / cache_dir)
                candidates.append(project_root.parent / cache_dir)
    candidates.append(Path.home() / ".cache" / "whisper")
    return _dedupe_paths(candidates)


def _project_root_from_context(context: ASRContext | None) -> Path | None:
    if context is None or not isinstance(context.run_config, Mapping):
        return None
    value = context.run_config.get("project_root")
    if value is None:
        return None
    return Path(str(value)).expanduser()


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path.expanduser())
    return unique


def _words_from_result(
    result: Mapping[str, object],
    *,
    offset_sec: float = 0.0,
) -> tuple[WordTiming, ...]:
    words: list[WordTiming] = []
    segments = result.get("segments")
    if not isinstance(segments, list):
        return ()
    for segment in segments:
        if not isinstance(segment, Mapping):
            continue
        raw_words = segment.get("words")
        if not isinstance(raw_words, list):
            continue
        for raw_word in raw_words:
            if not isinstance(raw_word, Mapping):
                continue
            text = str(raw_word.get("word", "")).strip()
            if not text:
                continue
            words.append(
                WordTiming(
                    word=text,
                    start_sec=_offset_time(raw_word.get("start"), offset_sec),
                    end_sec=_offset_time(raw_word.get("end"), offset_sec),
                    confidence=_optional_float(raw_word.get("probability")),
                )
            )
    return tuple(words)


def _gpu_memory_snapshot(device: str) -> dict[str, float | None]:
    torch_device = _cuda_device(device)
    if torch_device is None:
        return {
            "allocated_mb": None,
            "reserved_mb": None,
            "peak_allocated_mb": None,
            "peak_reserved_mb": None,
        }
    divisor = 1024 * 1024
    device_index = torch_device.index if torch_device.index is not None else 0
    return {
        "allocated_mb": torch.cuda.memory_allocated(device_index) / divisor,
        "reserved_mb": torch.cuda.memory_reserved(device_index) / divisor,
        "peak_allocated_mb": torch.cuda.max_memory_allocated(device_index) / divisor,
        "peak_reserved_mb": torch.cuda.max_memory_reserved(device_index) / divisor,
    }


def _reset_peak_gpu_memory(device: str) -> None:
    torch_device = _cuda_device(device)
    if torch_device is not None:
        device_index = torch_device.index if torch_device.index is not None else 0
        with torch.cuda.device(device_index):
            # PyTorch 2.11's Windows CUDA allocator rejects an explicit device
            # argument here even though the default-device form is supported.
            torch.cuda.reset_peak_memory_stats()


def _synchronize_cuda(device: str) -> None:
    torch_device = _cuda_device(device)
    if torch_device is not None:
        torch.cuda.synchronize(torch_device.index if torch_device.index is not None else 0)


def _validate_model_device(model: object, configured_device: str) -> None:
    expected = _cuda_device(configured_device)
    if expected is None:
        return
    parameters = getattr(model, "parameters", None)
    if not callable(parameters):
        raise WhisperASRUnavailableError(
            "Whisper model does not expose parameters for CUDA placement verification."
        )
    try:
        observed = next(parameters()).device
    except (StopIteration, TypeError, AttributeError) as exc:
        raise WhisperASRUnavailableError(
            "Whisper model device placement could not be verified."
        ) from exc
    if observed.type != "cuda" or observed.index not in (None, expected.index):
        raise WhisperASRUnavailableError(
            f"Whisper model resolved to {observed}, expected {expected}; CPU fallback is prohibited."
        )


def _cuda_device(device: str) -> torch.device | None:
    if not _is_cuda_device(device) or not torch.cuda.is_available():
        return None
    try:
        return torch.device(device)
    except (RuntimeError, ValueError) as exc:
        raise WhisperASRUnavailableError(f"Invalid CUDA device {device!r}") from exc


def _is_cuda_device(device: str) -> bool:
    return str(device).strip().lower() == "cuda" or str(device).strip().lower().startswith(
        "cuda:"
    )


def _use_fp16(device: str, dtype: str, context: ASRContext) -> bool:
    runtime_device = str(context.device or device)
    runtime_dtype = str(context.dtype or dtype)
    return _is_cuda_device(runtime_device) and runtime_dtype == "float16"


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_path(value: object) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return Path(str(value)).expanduser()


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _offset_time(value: object, offset_sec: float) -> float | None:
    parsed = _optional_float(value)
    return None if parsed is None else parsed + offset_sec


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError("beam_size must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError("beam_size must be >= 1")
    return parsed
