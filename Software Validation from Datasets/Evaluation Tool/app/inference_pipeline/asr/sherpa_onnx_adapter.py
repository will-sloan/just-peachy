"""Lazy sherpa-onnx streaming ASR adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

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
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError


class SherpaOnnxASRUnavailableError(InferencePipelineError):
    """Raised when sherpa-onnx or its configured local assets are unavailable."""


@dataclass
class SherpaOnnxASR(ASRBase):
    """Streaming sherpa-onnx adapter using an online transducer recognizer."""

    params: Mapping[str, object] | None = None
    recognizer: Any | None = None

    name = "sherpa_onnx"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})
        self.model_name = str(self.params.get("model_name", "sherpa_onnx"))
        self.model_type = str(self.params.get("model_type", "transducer"))
        if self.model_type != "transducer":
            raise ContractValidationError(
                "sherpa_onnx model_type must be 'transducer' for this adapter"
            )
        self.sample_rate = _positive_int(self.params.get("sample_rate", 16000), "sample_rate")
        self.feature_dim = _positive_int(self.params.get("feature_dim", 80), "feature_dim")
        self.num_threads = _positive_int(self.params.get("num_threads", 2), "num_threads")
        self.provider = str(self.params.get("provider", "cpu"))
        self.decoding_method = str(self.params.get("decoding_method", "greedy_search"))
        self.max_active_paths = _positive_int(
            self.params.get("max_active_paths", 4),
            "max_active_paths",
        )
        self.tail_padding_sec = _non_negative_float(
            self.params.get("tail_padding_sec", 0.66),
            "tail_padding_sec",
        )
        self.language = _optional_string(self.params.get("language"))
        replay = self.params.get("streaming")
        if replay is not None and not isinstance(replay, Mapping):
            raise ContractValidationError("sherpa streaming params must be a mapping")
        self.replay = StreamingReplayConfig.from_mapping(replay)
        self.native_streaming_replay = bool(
            self.params.get("native_streaming_replay", False)
        )
        self._load_sec: float | None = None
        self.last_streaming_diagnostics: dict[str, object] | None = None

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        audio = load_segment_audio(audio_segment, target_sample_rate=self.sample_rate)
        recognizer = self._recognizer(context)
        if self.native_streaming_replay:
            return self._transcribe_streaming(audio_segment, context, audio, recognizer)
        started_at = time.perf_counter()
        try:
            stream = recognizer.create_stream()
            stream.accept_waveform(audio.sample_rate, audio.samples)
            if self.tail_padding_sec:
                stream.accept_waveform(
                    audio.sample_rate,
                    np.zeros(
                        int(round(self.tail_padding_sec * audio.sample_rate)),
                        dtype=np.float32,
                    ),
                )
            stream.input_finished()
            decode_steps = 0
            max_decode_steps = max(1000, len(audio.samples) + 1)
            while recognizer.is_ready(stream):
                _decode_stream(recognizer, stream)
                decode_steps += 1
                if decode_steps > max_decode_steps:
                    raise RuntimeError("sherpa-onnx recognizer did not finish decoding")
            result = recognizer.get_result(stream)
        except Exception as exc:
            raise SherpaOnnxASRUnavailableError(
                f"sherpa-onnx transcription failed: {exc}"
            ) from exc

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
            device="cuda" if self.provider.lower().startswith("cuda") else "cpu",
            dtype="float32",
        )
        return ASRTranscript(
            text=normalized_text,
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _transcribe_streaming(
        self,
        audio_segment: AudioSegment,
        context: ASRContext,
        audio: Any,
        recognizer: Any,
    ) -> ASRTranscript:
        started_at = time.perf_counter()
        updates: list[StreamingUpdate] = []
        chunk_count = 0
        end_of_input_wall_sec = 0.0
        try:
            stream = recognizer.create_stream()
            for chunk, audio_end_sec in iter_audio_chunks(
                audio.samples,
                sample_rate=audio.sample_rate,
                chunk_duration_ms=self.replay.chunk_duration_ms,
            ):
                stream.accept_waveform(audio.sample_rate, chunk)
                chunk_count += 1
                while recognizer.is_ready(stream):
                    _decode_stream(recognizer, stream)
                raw_partial = _result_text(recognizer.get_result(stream))
                if raw_partial:
                    updates.append(
                        StreamingUpdate(
                            sequence=len(updates) + 1,
                            audio_end_sec=audio_end_sec,
                            wall_time_sec=time.perf_counter() - started_at,
                            text=raw_partial,
                            is_final=False,
                            event_type="chunk_decoded",
                        )
                    )
            end_of_input_wall_sec = time.perf_counter() - started_at
            if self.tail_padding_sec:
                stream.accept_waveform(
                    audio.sample_rate,
                    np.zeros(
                        int(round(self.tail_padding_sec * audio.sample_rate)),
                        dtype=np.float32,
                    ),
                )
            stream.input_finished()
            decode_steps = 0
            max_decode_steps = max(1000, len(audio.samples) + 1)
            while recognizer.is_ready(stream):
                _decode_stream(recognizer, stream)
                decode_steps += 1
                if decode_steps > max_decode_steps:
                    raise RuntimeError("sherpa-onnx recognizer did not finish decoding")
            result = recognizer.get_result(stream)
        except Exception as exc:
            raise SherpaOnnxASRUnavailableError(
                f"sherpa-onnx streaming replay failed: {exc}"
            ) from exc

        final_emitted_wall_sec = time.perf_counter() - started_at
        raw_text = _result_text(result)
        updates.append(
            StreamingUpdate(
                sequence=len(updates) + 1,
                audio_end_sec=audio.duration_sec,
                wall_time_sec=final_emitted_wall_sec,
                text=raw_text,
                is_final=True,
                event_type="input_finished",
            )
        )
        normalized_text = normalize_text(raw_text)
        self.last_raw_text = raw_text
        self.last_normalized_text = normalized_text
        self.last_runtime_stats = ASRRuntimeStats.from_timings(
            model_name=self.model_name,
            load_sec=self._load_sec,
            inference_sec=final_emitted_wall_sec,
            audio_duration_sec=audio.duration_sec,
            device="cuda" if self.provider.lower().startswith("cuda") else "cpu",
            dtype="float32",
        )
        self.last_streaming_diagnostics = build_streaming_diagnostics(
            backend_id=self.model_name,
            replay=self.replay,
            updates=updates,
            audio_duration_sec=audio.duration_sec,
            processing_sec=final_emitted_wall_sec,
            initialization_sec=self._load_sec,
            end_of_input_wall_sec=end_of_input_wall_sec,
            final_emitted_wall_sec=final_emitted_wall_sec,
            chunk_count=chunk_count,
        )
        return ASRTranscript(
            text=normalized_text,
            language=self.language or context.language,
            start_sec=audio_segment.start_sec,
            end_sec=audio_segment.end_sec,
        )

    def _recognizer(self, context: ASRContext | None = None) -> Any:
        if self.recognizer is not None:
            return self.recognizer
        if importlib.util.find_spec("sherpa_onnx") is None:
            raise SherpaOnnxASRUnavailableError(
                "sherpa-onnx is not installed in the active environment."
            )
        try:
            tokens = resolve_model_path(self.params.get("tokens"), context)
            encoder = resolve_model_path(self.params.get("encoder"), context)
            decoder = resolve_model_path(self.params.get("decoder"), context)
            joiner = resolve_model_path(self.params.get("joiner"), context)
        except (ContractValidationError, FileNotFoundError) as exc:
            raise SherpaOnnxASRUnavailableError(
                f"sherpa-onnx local model assets are unavailable: {exc}"
            ) from exc

        import sherpa_onnx  # type: ignore[import-not-found]

        started_at = time.perf_counter()
        try:
            self.recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
                tokens=str(tokens),
                encoder=str(encoder),
                decoder=str(decoder),
                joiner=str(joiner),
                num_threads=self.num_threads,
                provider=self.provider,
                sample_rate=self.sample_rate,
                feature_dim=self.feature_dim,
                decoding_method=self.decoding_method,
                max_active_paths=self.max_active_paths,
            )
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SherpaOnnxASRUnavailableError(
                f"sherpa-onnx model load failed: {exc}"
            ) from exc
        self._load_sec = time.perf_counter() - started_at
        return self.recognizer


def _decode_stream(recognizer: Any, stream: Any) -> None:
    if hasattr(recognizer, "decode_stream"):
        recognizer.decode_stream(stream)
    elif hasattr(recognizer, "decode_streams"):
        recognizer.decode_streams([stream])
    else:
        raise AttributeError("sherpa-onnx recognizer has no stream decode method")


def _result_text(result: object) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, Mapping):
        return str(result.get("text", ""))
    return str(getattr(result, "text", ""))


def _positive_int(value: object, field_name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be an integer") from exc
    if parsed < 1:
        raise ContractValidationError(f"{field_name} must be >= 1")
    return parsed


def _non_negative_float(value: object, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(f"{field_name} must be numeric") from exc
    if parsed < 0:
        raise ContractValidationError(f"{field_name} must be >= 0")
    return parsed


def _optional_string(value: object) -> str | None:
    return None if value is None or not str(value).strip() else str(value)


class SherpaOnnxStreamingZipformer20MInt8ASR(SherpaOnnxASR):
    """Distinct edge component retaining the existing Sherpa ASR as a control."""

    name = "sherpa_onnx_streaming_zipformer_20m_int8"

    def __post_init__(self) -> None:
        super().__post_init__()
        if not self.native_streaming_replay:
            raise ContractValidationError(
                "the 20M edge component requires native_streaming_replay=true"
            )
