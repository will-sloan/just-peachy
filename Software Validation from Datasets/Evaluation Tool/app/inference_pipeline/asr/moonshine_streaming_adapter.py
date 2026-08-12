"""Moonshine Voice native streaming ASR adapter with offline-safe assets."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from typing import Any, Mapping

from app.inference_pipeline.asr.audio_utils import load_segment_audio, resolve_model_path
from app.inference_pipeline.asr.base import (
    ASRBase,
    ASRContext,
    ASRRuntimeStats,
    normalize_text,
)
from app.inference_pipeline.asr.streaming import (
    StreamingReplayConfig,
    StreamingUpdate,
    build_streaming_diagnostics,
    iter_audio_chunks,
)
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment, WordTiming
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.typing import JsonObject


class MoonshineStreamingASRUnavailableError(InferencePipelineError):
    """Raised when Moonshine or its explicitly local model is unavailable."""


MOONSHINE_ARCH_NAMES = {
    "tiny-streaming": "TINY_STREAMING",
    "small-streaming": "SMALL_STREAMING",
    "medium-streaming": "MEDIUM_STREAMING",
}


@dataclass
class MoonshineStreamingASR(ASRBase):
    """Replay one segment incrementally through Moonshine's native stream API."""

    params: Mapping[str, object] | None = None
    transcriber: Any | None = None

    name = "moonshine_streaming"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})
        self.model_name = str(self.params.get("model_name") or self.name)
        self.model_path = self.params.get("model_path")
        self.model_arch = str(
            self.params.get("model_arch") or "tiny-streaming"
        ).strip().lower()
        if self.model_arch not in MOONSHINE_ARCH_NAMES:
            raise ContractValidationError(
                f"unsupported Moonshine streaming architecture: {self.model_arch!r}"
            )
        self.sample_rate = _positive_int(
            self.params.get("sample_rate", 16000), "sample_rate"
        )
        self.language = str(self.params.get("language") or "en")
        if self.language != "en":
            raise ContractValidationError(
                "this commercial edge component is restricted to Moonshine English"
            )
        if self.params.get("allow_model_downloads") not in (None, False):
            raise ContractValidationError(
                "Moonshine campaign inference prohibits implicit model downloads"
            )
        replay = self.params.get("streaming")
        if replay is not None and not isinstance(replay, Mapping):
            raise ContractValidationError("Moonshine streaming params must be a mapping")
        self.replay = StreamingReplayConfig.from_mapping(replay)
        self.options = {
            str(key): value
            for key, value in _mapping(self.params.get("options")).items()
        }
        self._load_sec: float | None = None
        self.last_streaming_diagnostics: JsonObject | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        audio = load_segment_audio(audio_segment, target_sample_rate=self.sample_rate)
        transcriber = self._transcriber(context)
        updates: list[StreamingUpdate] = []
        final_transcript: object | None = None
        started_at = time.perf_counter()
        end_of_input_wall_sec = 0.0
        final_emitted_wall_sec: float | None = None
        chunk_count = 0
        latest_audio_sec = 0.0
        try:
            stream = transcriber.create_stream(
                update_interval=self.replay.update_interval_ms / 1000.0
            )
            stream.start()

            def listener(event: object) -> None:
                line = getattr(event, "line", None)
                if line is None:
                    return
                updates.append(
                    StreamingUpdate(
                        sequence=len(updates) + 1,
                        audio_end_sec=latest_audio_sec,
                        wall_time_sec=time.perf_counter() - started_at,
                        text=str(getattr(line, "text", "")),
                        is_final=bool(getattr(line, "is_complete", False)),
                        backend_latency_ms=_optional_float(
                            getattr(line, "last_transcription_latency_ms", None)
                        ),
                        line_id=_optional_int(getattr(line, "line_id", None)),
                        event_type=type(event).__name__,
                    )
                )

            stream.add_listener(listener)
            for chunk, audio_end_sec in iter_audio_chunks(
                audio.samples,
                sample_rate=audio.sample_rate,
                chunk_duration_ms=self.replay.chunk_duration_ms,
            ):
                latest_audio_sec = audio_end_sec
                stream.add_audio(chunk.tolist(), audio.sample_rate)
                chunk_count += 1
            end_of_input_wall_sec = time.perf_counter() - started_at
            final_transcript = stream.stop()
            final_emitted_wall_sec = time.perf_counter() - started_at
            stream.close()
        except Exception as exc:
            raise MoonshineStreamingASRUnavailableError(
                f"Moonshine streaming transcription failed: {exc}"
            ) from exc

        processing_sec = time.perf_counter() - started_at
        lines = list(getattr(final_transcript, "lines", ()) or ())
        raw_text = " ".join(
            str(getattr(line, "text", "")).strip()
            for line in lines
            if str(getattr(line, "text", "")).strip()
        ).strip()
        if not any(item.is_final for item in updates):
            updates.append(
                StreamingUpdate(
                    sequence=len(updates) + 1,
                    audio_end_sec=audio.duration_sec,
                    wall_time_sec=final_emitted_wall_sec or processing_sec,
                    text=raw_text,
                    is_final=True,
                    event_type="stream_stopped",
                )
            )
        normalized_text = normalize_text(raw_text)
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=processing_sec,
            audio_duration_sec=audio.duration_sec,
            device="cpu",
            dtype="float32",
        )
        self.last_streaming_diagnostics = build_streaming_diagnostics(
            backend_id=self.model_name,
            replay=self.replay,
            updates=updates,
            audio_duration_sec=audio.duration_sec,
            processing_sec=processing_sec,
            initialization_sec=self._load_sec,
            end_of_input_wall_sec=end_of_input_wall_sec,
            final_emitted_wall_sec=final_emitted_wall_sec,
            chunk_count=chunk_count,
        )
        return ASRTranscript(
            text=normalized_text,
            words=_word_timings(lines, audio_segment),
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _transcriber(self, context: ASRContext) -> Any:
        if self.transcriber is not None:
            return self.transcriber
        if importlib.util.find_spec("moonshine_voice") is None:
            raise MoonshineStreamingASRUnavailableError(
                "moonshine-voice is not installed in the active environment"
            )
        try:
            model_path = resolve_model_path(self.model_path, context)
        except (ContractValidationError, FileNotFoundError) as exc:
            raise MoonshineStreamingASRUnavailableError(
                f"Moonshine local model assets are unavailable: {exc}"
            ) from exc
        try:
            from moonshine_voice.moonshine_api import ModelArch
            from moonshine_voice.transcriber import Transcriber

            architecture = getattr(ModelArch, MOONSHINE_ARCH_NAMES[self.model_arch])
            started_at = time.perf_counter()
            self.transcriber = Transcriber(
                model_path=str(model_path),
                model_arch=architecture,
                update_interval=self.replay.update_interval_ms / 1000.0,
                options=self.options,
            )
            self._load_sec = time.perf_counter() - started_at
        except Exception as exc:  # pragma: no cover - native dependency boundary
            raise MoonshineStreamingASRUnavailableError(
                f"Moonshine model load failed: {exc}"
            ) from exc
        return self.transcriber


def _word_timings(
    lines: list[object], audio_segment: AudioSegment
) -> tuple[WordTiming, ...]:
    offset = float(audio_segment.start_sec or 0.0)
    result: list[WordTiming] = []
    for line in lines:
        for word in getattr(line, "words", ()) or ():
            start = float(getattr(word, "start", 0.0)) + offset
            end = float(getattr(word, "end", start)) + offset
            if end < start:
                continue
            text = str(getattr(word, "word", "")).strip()
            if not text:
                continue
            result.append(
                WordTiming(
                    word=text,
                    start_sec=start,
                    end_sec=end,
                    confidence=_optional_float(getattr(word, "confidence", None)),
                )
            )
    return tuple(result)


def _mapping(value: object) -> Mapping[str, object]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ContractValidationError("Moonshine options must be a mapping")
    return value


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


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
