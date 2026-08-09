"""Lazy Vosk ASR adapter."""

from __future__ import annotations

import importlib.util
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import numpy as np

from app.inference_pipeline.asr.audio_utils import load_segment_audio, resolve_model_path
from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    normalize_text,
)
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment, WordTiming
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.resource_telemetry.context import telemetry_span


class VoskASRUnavailableError(InferencePipelineError):
    """Raised when Vosk or its configured local model is unavailable."""


@dataclass
class VoskASR(ASRBase):
    """Offline Vosk adapter using a fresh recognizer per audio segment."""

    params: Mapping[str, object] | None = None
    model: Any | None = None
    recognizer_factory: Callable[[Any, float], Any] | None = None

    name = "vosk"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})
        self.model_name = str(self.params.get("model_name", "vosk"))
        self.sample_rate = _positive_int(self.params.get("sample_rate", 16000), "sample_rate")
        self.chunk_frames = _positive_int(
            self.params.get("chunk_frames", 4000),
            "chunk_frames",
        )
        self.words = bool(self.params.get("words", True))
        self.partial_words = bool(self.params.get("partial_words", False))
        self.language = _optional_string(self.params.get("language"))
        self._load_sec: float | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        audio = load_segment_audio(audio_segment, target_sample_rate=self.sample_rate)
        model = self._model(context)
        factory = self._recognizer_factory()
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
            ):
                recognizer = factory(model, float(audio.sample_rate))
                if hasattr(recognizer, "SetWords"):
                    recognizer.SetWords(self.words)
                if hasattr(recognizer, "SetPartialWords"):
                    recognizer.SetPartialWords(self.partial_words)
                pcm16 = np.clip(audio.samples, -1.0, 1.0)
                pcm16 = (pcm16 * 32767.0).astype("<i2", copy=False)
                payload = pcm16.tobytes()
                bytes_per_chunk = self.chunk_frames * 2
                for offset in range(0, len(payload), bytes_per_chunk):
                    recognizer.AcceptWaveform(payload[offset : offset + bytes_per_chunk])
                result = _json_result(recognizer.FinalResult())
        except Exception as exc:
            raise VoskASRUnavailableError(f"Vosk transcription failed: {exc}") from exc

        inference_sec = time.perf_counter() - started_at
        raw_text = str(result.get("text", ""))
        normalized_text = normalize_text(raw_text)
        word_timings = (
            _word_timings(
                result,
                offset_sec=float(audio_segment.start_sec or 0.0),
            )
            if self.words
            else ()
        )
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio.duration_sec,
            device="cpu",
            dtype="float32",
        )
        return ASRTranscript(
            text=normalized_text,
            words=word_timings,
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _model(self, context: ASRContext | None = None) -> Any:
        if self.model is not None:
            return self.model
        if importlib.util.find_spec("vosk") is None:
            raise VoskASRUnavailableError(
                "Vosk is not installed in the active environment."
            )
        try:
            model_path = resolve_model_path(self.params.get("model_path"), context)
        except (ContractValidationError, FileNotFoundError) as exc:
            raise VoskASRUnavailableError(
                f"Vosk local model assets are unavailable: {exc}"
            ) from exc

        import vosk  # type: ignore[import-not-found]

        started_at = time.perf_counter()
        try:
            with telemetry_span("asr_model_load", phase="cold_initialization"):
                self.model = vosk.Model(str(model_path))
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise VoskASRUnavailableError(f"Vosk model load failed: {exc}") from exc
        self._load_sec = time.perf_counter() - started_at
        return self.model

    def _recognizer_factory(self) -> Callable[[Any, float], Any]:
        if self.recognizer_factory is not None:
            return self.recognizer_factory
        if importlib.util.find_spec("vosk") is None:
            raise VoskASRUnavailableError(
                "Vosk is not installed in the active environment."
            )
        import vosk  # type: ignore[import-not-found]

        return vosk.KaldiRecognizer


def _json_result(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError("Vosk FinalResult did not return valid JSON") from exc
    if not isinstance(parsed, Mapping):
        raise ValueError("Vosk FinalResult JSON must be an object")
    return parsed


def _word_timings(
    result: Mapping[str, object],
    *,
    offset_sec: float = 0.0,
) -> tuple[WordTiming, ...]:
    values = result.get("result")
    if not isinstance(values, list):
        return ()
    words: list[WordTiming] = []
    for value in values:
        if not isinstance(value, Mapping):
            continue
        word = str(value.get("word", "")).strip()
        if not word:
            continue
        words.append(
            WordTiming(
                word=word,
                start_sec=_offset_time(value.get("start"), offset_sec),
                end_sec=_offset_time(value.get("end"), offset_sec),
                confidence=_optional_float(value.get("conf")),
            )
        )
    return tuple(words)


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed


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


def _optional_string(value: object) -> str | None:
    return None if value is None or not str(value).strip() else str(value)
