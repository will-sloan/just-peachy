"""Lazy, offline-safe Faster-Whisper ASR adapter."""

from __future__ import annotations

import importlib.util
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from app.inference_pipeline.asr.audio_utils import load_segment_audio, resolve_model_path
from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    normalize_text,
    validate_allowed_whisper_model_size,
)
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment, WordTiming
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError


class FasterWhisperASRUnavailableError(InferencePipelineError):
    """Raised when Faster-Whisper dependencies or local assets are unavailable."""


@dataclass
class FasterWhisperASR(ASRBase):
    """Run Faster-Whisper on an already selected, in-memory audio segment.

    Passing a 16 kHz float32 waveform avoids an FFmpeg subprocess and guarantees
    that ``AudioSegment`` crop and channel metadata are honored consistently with
    the other ASR adapters.
    """

    params: Mapping[str, object] | None = None
    model: Any | None = None

    name = "faster_whisper"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})
        self.model_size = validate_allowed_whisper_model_size(
            self.params.get("model_size", "tiny")
        )
        self.model_name = str(
            self.params.get("model_name", f"faster_whisper_{self.model_size}")
        )
        self.model_path = _optional_path(self.params.get("model_path"))
        if self.model_path is not None and not _path_declares_model_size(
            self.model_path,
            self.model_size,
        ):
            raise ContractValidationError(
                "model_path must identify the configured permitted model_size in its "
                f"final path component; got {self.model_path.name!r} for {self.model_size!r}"
            )
        self.cache_dir = _optional_path(self.params.get("cache_dir"))
        self.allow_model_downloads = bool(self.params.get("allow_model_downloads", False))
        self.device = str(self.params.get("device", "cpu"))
        self.device_index = _non_negative_int(
            self.params.get("device_index", 0),
            "device_index",
        )
        self.compute_type = str(self.params.get("compute_type", "int8"))
        self.cpu_threads = _non_negative_int(
            self.params.get("cpu_threads", 0),
            "cpu_threads",
        )
        self.num_workers = _positive_int(
            self.params.get("num_workers", 1),
            "num_workers",
        )
        self.language = _optional_string(self.params.get("language"))
        self.task = str(self.params.get("task", "transcribe"))
        if self.task not in {"transcribe", "translate"}:
            raise ContractValidationError("task must be 'transcribe' or 'translate'")
        self.beam_size = _positive_int(self.params.get("beam_size", 1), "beam_size")
        self.word_timestamps = bool(self.params.get("word_timestamps", False))
        self.vad_filter = bool(self.params.get("vad_filter", False))
        self.condition_on_previous_text = bool(
            self.params.get("condition_on_previous_text", False)
        )
        self._load_sec: float | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        model = self._model(context)
        audio = load_segment_audio(audio_segment, target_sample_rate=16000)
        kwargs: dict[str, object] = {
            "language": self.language or context.language,
            "task": self.task,
            "beam_size": self.beam_size,
            "word_timestamps": self.word_timestamps,
            "vad_filter": self.vad_filter,
            "condition_on_previous_text": self.condition_on_previous_text,
        }

        started_at = time.perf_counter()
        try:
            raw_segments, info = model.transcribe(audio.samples, **kwargs)
            segments = tuple(raw_segments)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise FasterWhisperASRUnavailableError(
                f"Faster-Whisper transcription failed: {exc}"
            ) from exc
        inference_sec = time.perf_counter() - started_at

        raw_text = " ".join(
            text for text in (_segment_text(segment) for segment in segments) if text
        ).strip()
        normalized_text = normalize_text(raw_text)
        words = (
            _words_from_segments(
                segments,
                offset_sec=float(audio_segment.start_sec or 0.0),
            )
            if self.word_timestamps
            else ()
        )
        language = _info_language(info) or self.language or context.language
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio.duration_sec,
            device=self.device,
            dtype=self.compute_type,
        )
        return ASRTranscript(
            text=normalized_text,
            words=words,
            language=language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _model(self, context: ASRContext | None = None) -> Any:
        if self.model is not None:
            return self.model
        if importlib.util.find_spec("faster_whisper") is None:
            raise FasterWhisperASRUnavailableError(
                "faster-whisper is not installed in the active environment."
            )

        model_source: str = self.model_size
        if self.model_path is not None:
            try:
                resolved_model_path = resolve_model_path(self.model_path, context)
                _validate_local_model_assets(resolved_model_path)
                model_source = str(resolved_model_path)
            except (ContractValidationError, FileNotFoundError) as exc:
                raise FasterWhisperASRUnavailableError(
                    f"Faster-Whisper local model assets are unavailable: {exc}"
                ) from exc

        download_root: str | None = None
        if self.cache_dir is not None:
            if self.allow_model_downloads:
                download_root = str(_download_cache_path(self.cache_dir))
            else:
                try:
                    download_root = str(resolve_model_path(self.cache_dir, context))
                except (ContractValidationError, FileNotFoundError) as exc:
                    if self.model_path is None:
                        raise FasterWhisperASRUnavailableError(
                            f"Faster-Whisper local cache is unavailable: {exc}"
                        ) from exc

        import faster_whisper  # type: ignore[import-not-found]

        started_at = time.perf_counter()
        try:
            self.model = faster_whisper.WhisperModel(
                model_source,
                device=self.device,
                device_index=self.device_index,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                num_workers=self.num_workers,
                download_root=download_root,
                local_files_only=not self.allow_model_downloads,
            )
        except Exception as exc:  # pragma: no cover - dependency boundary
            mode = "local-only" if not self.allow_model_downloads else "download-enabled"
            raise FasterWhisperASRUnavailableError(
                f"Faster-Whisper model load failed ({mode}): {exc}"
            ) from exc
        self._load_sec = time.perf_counter() - started_at
        return self.model


def _segment_text(segment: object) -> str:
    if isinstance(segment, Mapping):
        value = segment.get("text", "")
    else:
        value = getattr(segment, "text", "")
    return str(value).strip()


def _validate_local_model_assets(model_path: Path) -> None:
    if not model_path.is_dir():
        raise FileNotFoundError(f"Faster-Whisper model path is not a directory: {model_path}")
    required = ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt")
    missing = [filename for filename in required if not (model_path / filename).is_file()]
    if missing:
        raise FileNotFoundError(
            "Faster-Whisper model directory is incomplete; missing " + ", ".join(missing)
        )


def _words_from_segments(
    segments: Iterable[object],
    *,
    offset_sec: float = 0.0,
) -> tuple[WordTiming, ...]:
    words: list[WordTiming] = []
    for segment in segments:
        raw_words = (
            segment.get("words")
            if isinstance(segment, Mapping)
            else getattr(segment, "words", None)
        )
        if raw_words is None:
            continue
        for raw_word in raw_words:
            text = str(_value(raw_word, "word") or "").strip()
            if not text:
                continue
            words.append(
                WordTiming(
                    word=text,
                    start_sec=_offset_time(_value(raw_word, "start"), offset_sec),
                    end_sec=_offset_time(_value(raw_word, "end"), offset_sec),
                    confidence=_optional_float(_value(raw_word, "probability")),
                )
            )
    return tuple(words)


def _info_language(info: object) -> str | None:
    return _optional_string(_value(info, "language"))


def _value(value: object, key: str) -> object | None:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _download_cache_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    repository_root = Path(__file__).resolve().parents[5]
    return repository_root / path


def _optional_path(value: object) -> Path | None:
    if value is None or not str(value).strip():
        return None
    return Path(str(value)).expanduser()


def _path_declares_model_size(path: Path, model_size: str) -> bool:
    return re.search(
        rf"(^|[-_.]){re.escape(model_size)}($|[-_.])",
        path.name.lower(),
    ) is not None


def _optional_string(value: object) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(value)


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


def _positive_int(value: object, field_name: str) -> int:
    parsed = _integer(value, field_name)
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed


def _non_negative_int(value: object, field_name: str) -> int:
    parsed = _integer(value, field_name)
    if parsed < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    return parsed


def _integer(value: object, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
