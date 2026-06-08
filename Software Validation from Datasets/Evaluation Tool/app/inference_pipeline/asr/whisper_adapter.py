"""Lazy OpenAI Whisper ASR adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    normalize_text,
)
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment, WordTiming
from app.inference_pipeline.errors import InferencePipelineError


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
        self.model_size = str(self.params.get("model_size", "tiny"))
        self.model_name = str(self.params.get("model_name", f"whisper_{self.model_size}"))
        self.device = str(self.params.get("device", "cpu"))
        self.dtype = str(self.params.get("dtype", "float32"))
        self.language = _optional_string(self.params.get("language"))
        self.cache_dir = _optional_path(self.params.get("cache_dir"))
        self.allow_model_downloads = bool(self.params.get("allow_model_downloads", False))
        self.word_timestamps = bool(self.params.get("word_timestamps", False))
        self._load_sec: float | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        started_at = time.perf_counter()
        model = self._model(context)
        kwargs: dict[str, object] = {
            "language": self.language or context.language,
            "word_timestamps": self.word_timestamps,
            "fp16": _use_fp16(self.device, self.dtype, context),
        }
        if audio_segment.start_sec is not None or audio_segment.end_sec is not None:
            kwargs["clip_timestamps"] = _clip_timestamps(audio_segment)
        try:
            result = model.transcribe(str(audio_segment.audio_path), **kwargs)
        except TypeError:
            result = model.transcribe(str(audio_segment.audio_path), language=self.language)
        inference_sec = time.perf_counter() - started_at
        raw_text = str(result.get("text", ""))
        normalized_text = normalize_text(raw_text)
        words = _words_from_result(result)
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio_segment.duration_sec,
            device=self.device,
            dtype=self.dtype,
            peak_gpu_memory_mb=_peak_gpu_memory_mb(self.device),
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

        started_at = time.perf_counter()
        download_root = _download_root(self.cache_dir, model_asset)
        try:
            self.model = whisper.load_model(
                self.model_size,
                device=self.device,
                download_root=str(download_root) if download_root is not None else None,
            )
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise WhisperASRUnavailableError(f"Whisper model load failed: {exc}") from exc
        self._load_sec = time.perf_counter() - started_at
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
    return cache_dir


def _cache_dir_candidates(cache_dir: Path | None, context: ASRContext | None) -> list[Path]:
    candidates: list[Path] = []
    if cache_dir is not None:
        candidates.append(cache_dir)
        if not cache_dir.is_absolute():
            candidates.append(Path.cwd() / cache_dir)
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


def _clip_timestamps(audio_segment: AudioSegment) -> str:
    start = audio_segment.start_sec or 0.0
    end = audio_segment.end_sec
    if end is None:
        return f"{start}"
    return f"{start},{end}"


def _words_from_result(result: Mapping[str, object]) -> tuple[WordTiming, ...]:
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
                    start_sec=_optional_float(raw_word.get("start")),
                    end_sec=_optional_float(raw_word.get("end")),
                    confidence=_optional_float(raw_word.get("probability")),
                )
            )
    return tuple(words)


def _peak_gpu_memory_mb(device: str) -> float | None:
    if device == "cuda" and torch.cuda.is_available():
        return torch.cuda.max_memory_allocated() / (1024 * 1024)
    return None


def _use_fp16(device: str, dtype: str, context: ASRContext) -> bool:
    runtime_device = str(context.device or device)
    runtime_dtype = str(context.dtype or dtype)
    return runtime_device == "cuda" and runtime_dtype == "float16"


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
