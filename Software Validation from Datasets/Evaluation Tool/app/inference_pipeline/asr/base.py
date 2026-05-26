"""ASR interfaces and lightweight adapters."""

from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.contracts import ASRTranscript, AudioSegment, WordTiming
from app.inference_pipeline.errors import ContractValidationError
from app.inference_pipeline.typing import JsonObject


@dataclass(frozen=True)
class ASRContext:
    """Context needed to transcribe one segment without changing core contracts."""

    recording_id: str
    utt_id: str
    source_audio_path: Path
    segment_index: int = 0
    segment_start_sec: float | None = None
    segment_end_sec: float | None = None
    device: str = "cpu"
    dtype: str = "float32"
    language: str | None = None
    run_config: JsonObject | None = None

    @classmethod
    def from_record_segment(
        cls,
        record: object,
        segment: AudioSegment,
        *,
        segment_index: int = 0,
        run_config: Mapping[str, object] | None = None,
        device: str = "cpu",
        dtype: str = "float32",
        language: str | None = None,
    ) -> "ASRContext":
        return cls(
            recording_id=str(getattr(record, "recording_id")),
            utt_id=str(getattr(record, "utt_id")),
            source_audio_path=segment.audio_path,
            segment_index=segment_index,
            segment_start_sec=segment.start_sec,
            segment_end_sec=segment.end_sec,
            device=device,
            dtype=dtype,
            language=language,
            run_config=dict(run_config or {}),
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "recording_id": self.recording_id,
            "utt_id": self.utt_id,
            "source_audio_path": str(self.source_audio_path),
            "segment_index": self.segment_index,
            "segment_start_sec": self.segment_start_sec,
            "segment_end_sec": self.segment_end_sec,
            "device": self.device,
            "dtype": self.dtype,
            "language": self.language,
            "run_config": dict(self.run_config or {}),
        }


@dataclass(frozen=True)
class ASRRuntimeStats:
    """Runtime and resource stats for one ASR call."""

    model_name: str
    load_sec: float | None = None
    inference_sec: float | None = None
    audio_duration_sec: float | None = None
    realtime_factor: float | None = None
    device: str = "cpu"
    dtype: str = "float32"
    peak_gpu_memory_mb: float | None = None
    cpu_memory_mb: float | None = None

    @classmethod
    def from_timings(
        cls,
        *,
        model_name: str,
        load_sec: float | None,
        inference_sec: float | None,
        audio_duration_sec: float | None,
        device: str,
        dtype: str,
        peak_gpu_memory_mb: float | None = None,
        cpu_memory_mb: float | None = None,
    ) -> "ASRRuntimeStats":
        duration = audio_duration_sec if audio_duration_sec and audio_duration_sec > 0 else None
        realtime_factor = inference_sec / duration if inference_sec is not None and duration else None
        return cls(
            model_name=model_name,
            load_sec=load_sec,
            inference_sec=inference_sec,
            audio_duration_sec=audio_duration_sec,
            realtime_factor=realtime_factor,
            device=device,
            dtype=dtype,
            peak_gpu_memory_mb=peak_gpu_memory_mb,
            cpu_memory_mb=cpu_memory_mb,
        )

    def to_jsonable(self) -> JsonObject:
        return {
            "model_name": self.model_name,
            "load_sec": self.load_sec,
            "inference_sec": self.inference_sec,
            "audio_duration_sec": self.audio_duration_sec,
            "realtime_factor": self.realtime_factor,
            "device": self.device,
            "dtype": self.dtype,
            "peak_gpu_memory_mb": self.peak_gpu_memory_mb,
            "cpu_memory_mb": self.cpu_memory_mb,
        }


class ASRBase(ABC):
    """Backend-swappable speech recognizer interface."""

    name = "asr_base"

    def __init__(self) -> None:
        self.last_runtime_stats: ASRRuntimeStats | None = None
        self.last_raw_text: str | None = None
        self.last_normalized_text: str | None = None

    @abstractmethod
    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        """Transcribe one model-ready audio segment."""


class NoOpASR(ASRBase):
    """Configurable no-op ASR adapter."""

    name = "no_op_asr"

    def __init__(self, text: str = "") -> None:
        super().__init__()
        self.text = text

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        started_at = time.perf_counter()
        _ = context
        normalized = normalize_text(self.text)
        self.last_raw_text = self.text
        self.last_normalized_text = normalized
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.name,
            load_sec=0.0,
            inference_sec=time.perf_counter() - started_at,
            audio_duration_sec=audio_segment.duration_sec,
            device=context.device,
            dtype=context.dtype,
        )
        return ASRTranscript(
            text=normalized,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
            language=context.language,
        )


class FixedASR(ASRBase):
    """Deterministic adapter for tests and direct smoke checks."""

    name = "fixed_asr"

    def __init__(
        self,
        raw_text: str,
        *,
        words: Sequence[WordTiming] = (),
        language: str | None = "en",
    ) -> None:
        super().__init__()
        self.raw_text = raw_text
        self.words = tuple(words)
        self.language = language

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        started_at = time.perf_counter()
        normalized = normalize_text(self.raw_text)
        self.last_raw_text = self.raw_text
        self.last_normalized_text = normalized
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.name,
            load_sec=0.0,
            inference_sec=time.perf_counter() - started_at,
            audio_duration_sec=audio_segment.duration_sec,
            device=context.device,
            dtype=context.dtype,
        )
        return ASRTranscript(
            text=normalized,
            words=self.words,
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )


def build_asr_from_config(config: object) -> ASRBase | None:
    """Instantiate configured ASR without loading model weights during config resolution."""

    component = _asr_component(config)
    if component is None or not _component_enabled(component):
        return None

    name = _component_name(component)
    params = _component_params(component)
    if name == "no_op_asr":
        return NoOpASR(str(params.get("transcript", "")))
    if name in {"whisper_tiny", "whisper_base"}:
        from app.inference_pipeline.asr.whisper_adapter import WhisperASR

        return WhisperASR(params)
    if name == "faster_whisper":
        from app.inference_pipeline.asr.faster_whisper_adapter import FasterWhisperASR

        return FasterWhisperASR(params)
    raise ContractValidationError(f"unknown asr component {name!r}")


def normalize_text(text: str) -> str:
    """Normalize ASR text for evaluator-compatible utterance predictions."""

    normalized = text.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def transcript_to_jsonable(transcript: ASRTranscript) -> JsonObject:
    """Return JSON-safe transcript details."""

    return transcript.to_jsonable()


def _asr_component(config: object) -> object | None:
    components = getattr(config, "components", None)
    if isinstance(components, Mapping):
        return components.get("asr")
    if isinstance(config, Mapping):
        raw_components = config.get("components")
        if isinstance(raw_components, Mapping):
            return raw_components.get("asr")
        return config.get("asr")
    return None


def _component_name(component: object) -> str:
    if isinstance(component, Mapping):
        return str(component.get("name") or "")
    return str(getattr(component, "name", ""))


def _component_enabled(component: object) -> bool:
    if isinstance(component, Mapping):
        return bool(component.get("enabled", True))
    return bool(getattr(component, "enabled", True))


def _component_params(component: object) -> Mapping[str, object]:
    if isinstance(component, Mapping):
        value = component.get("params") or {}
    else:
        value = getattr(component, "params", {}) or {}
    if not isinstance(value, Mapping):
        raise ContractValidationError("asr params must be a mapping")
    return value
