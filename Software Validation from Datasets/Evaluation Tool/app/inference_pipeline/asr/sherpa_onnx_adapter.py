"""Lazy sherpa-onnx streaming ASR adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from app.inference_pipeline.asr.audio_utils import (
    load_segment_audio,
    resolve_model_path,
)
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
from app.inference_pipeline.errors import (
    ContractValidationError,
    InferencePipelineError,
)


class SherpaOnnxASRUnavailableError(InferencePipelineError):
    """Raised when sherpa-onnx or its configured local assets are unavailable."""


STABLE_PREFIX_METHOD = "consecutive_hypothesis_token_lcp.v1"


@dataclass(frozen=True)
class SherpaEndpointConfig:
    """Runtime-only endpoint settings for one recognizer instance.

    The frozen AO/AG component YAML files intentionally do not enable endpoint
    detection.  A true-streaming worker may supply this explicit overlay before
    the recognizer is loaded, and must retain ``policy_id`` in its provenance.
    """

    enabled: bool = False
    policy_id: str = "sherpa_onnx_endpoint_disabled.v1"
    rule1_min_trailing_silence: float = 2.4
    rule2_min_trailing_silence: float = 1.2
    rule3_min_utterance_length: float = 20.0

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ContractValidationError("sherpa endpoint policy_id must not be empty")
        for name in (
            "rule1_min_trailing_silence",
            "rule2_min_trailing_silence",
            "rule3_min_utterance_length",
        ):
            if float(getattr(self, name)) < 0:
                raise ContractValidationError(f"sherpa endpoint {name} must be >= 0")

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, object] | None = None,
        *,
        base: "SherpaEndpointConfig | None" = None,
    ) -> "SherpaEndpointConfig":
        current = base or cls()
        data = dict(value or {})
        enabled = bool(data.get("enabled", current.enabled))
        if (
            enabled
            and not current.enabled
            and not str(data.get("policy_id") or "").strip()
        ):
            raise ContractValidationError(
                "enabling sherpa endpoint detection requires an explicit policy_id"
            )
        return cls(
            enabled=enabled,
            policy_id=str(data.get("policy_id") or current.policy_id),
            rule1_min_trailing_silence=_non_negative_float(
                data.get(
                    "rule1_min_trailing_silence",
                    current.rule1_min_trailing_silence,
                ),
                "endpoint.rule1_min_trailing_silence",
            ),
            rule2_min_trailing_silence=_non_negative_float(
                data.get(
                    "rule2_min_trailing_silence",
                    current.rule2_min_trailing_silence,
                ),
                "endpoint.rule2_min_trailing_silence",
            ),
            rule3_min_utterance_length=_non_negative_float(
                data.get(
                    "rule3_min_utterance_length",
                    current.rule3_min_utterance_length,
                ),
                "endpoint.rule3_min_utterance_length",
            ),
        )

    def to_jsonable(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "policy_id": self.policy_id,
            "rule1_min_trailing_silence": self.rule1_min_trailing_silence,
            "rule2_min_trailing_silence": self.rule2_min_trailing_silence,
            "rule3_min_utterance_length": self.rule3_min_utterance_length,
        }


@dataclass(frozen=True)
class SherpaStreamingHypothesis:
    """One changed partial or final hypothesis from a persistent Sherpa stream."""

    sequence: int
    utterance_index: int
    revision_number: int
    text: str
    normalized_text: str
    tokens: tuple[str, ...]
    token_timestamps_sec: tuple[float, ...]
    words: tuple[str, ...]
    audio_consumed_through_sec: float
    emitted_elapsed_sec: float
    decode_latency_ms: float
    is_final: bool
    is_first_partial: bool
    endpoint_detected: bool
    finalization_reason: str | None
    finalization_latency_ms: float | None
    stable_prefix_text: str
    stable_prefix_token_count: int
    stable_prefix_method: str = STABLE_PREFIX_METHOD
    stream_reset_performed: bool = False

    def to_jsonable(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "utterance_index": self.utterance_index,
            "revision_number": self.revision_number,
            "text": self.text,
            "normalized_text": self.normalized_text,
            "tokens": list(self.tokens),
            "token_timestamps_sec": list(self.token_timestamps_sec),
            "words": list(self.words),
            "audio_consumed_through_sec": self.audio_consumed_through_sec,
            "emitted_elapsed_sec": self.emitted_elapsed_sec,
            "decode_latency_ms": self.decode_latency_ms,
            "is_final": self.is_final,
            "is_first_partial": self.is_first_partial,
            "endpoint_detected": self.endpoint_detected,
            "finalization_reason": self.finalization_reason,
            "finalization_latency_ms": self.finalization_latency_ms,
            "stable_prefix_text": self.stable_prefix_text,
            "stable_prefix_token_count": self.stable_prefix_token_count,
            "stable_prefix_method": self.stable_prefix_method,
            "stream_reset_performed": self.stream_reset_performed,
        }


@dataclass(frozen=True)
class SherpaStreamingReset:
    """Audit record for an explicit stream-state reset."""

    reset_count: int
    prior_utterance_index: int
    next_utterance_index: int
    reason: str
    audio_consumed_through_sec: float
    backend_reset_used: bool

    def to_jsonable(self) -> dict[str, object]:
        return {
            "reset_count": self.reset_count,
            "prior_utterance_index": self.prior_utterance_index,
            "next_utterance_index": self.next_utterance_index,
            "reason": self.reason,
            "audio_consumed_through_sec": self.audio_consumed_through_sec,
            "backend_reset_used": self.backend_reset_used,
        }


class SherpaOnnxStreamingSession:
    """Persistent per-source decoder state backed by one online recognizer.

    The model/recognizer remains loaded on the owning :class:`SherpaOnnxASR`.
    A session owns exactly one mutable Sherpa stream at a time and accepts
    incremental normalized waveform chunks.  It never re-runs independent
    offline utterances.
    """

    def __init__(
        self,
        *,
        recognizer: Any,
        sample_rate: int,
        tail_padding_sec: float,
        endpoint: SherpaEndpointConfig,
        source_start_sec: float = 0.0,
        auto_reset_on_endpoint: bool = True,
        max_decode_steps_per_accept: int = 10000,
    ) -> None:
        if source_start_sec < 0:
            raise ContractValidationError("stream source_start_sec must be >= 0")
        if max_decode_steps_per_accept < 1:
            raise ContractValidationError(
                "stream max_decode_steps_per_accept must be >= 1"
            )
        if endpoint.enabled and not hasattr(recognizer, "is_endpoint"):
            raise ContractValidationError(
                "endpoint detection was enabled but the recognizer has no is_endpoint API"
            )
        self.recognizer = recognizer
        self.sample_rate = sample_rate
        self.tail_padding_sec = tail_padding_sec
        self.endpoint = endpoint
        self.auto_reset_on_endpoint = auto_reset_on_endpoint
        self.max_decode_steps_per_accept = max_decode_steps_per_accept
        self.stream = recognizer.create_stream()
        self.started_monotonic = time.perf_counter()
        self.source_start_sec = float(source_start_sec)
        self.audio_consumed_through_sec = float(source_start_sec)
        self.utterance_index = 1
        self.reset_count = 0
        self.sequence = 0
        self._revision_number = 0
        self._previous_tokens: tuple[str, ...] = ()
        self._previous_text = ""
        self._partial_emitted = False
        self._audio_accepted = False
        self._endpoint_waiting_for_reset = False
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def accept_audio(
        self,
        samples: np.ndarray | Sequence[float],
        *,
        sample_rate: int,
        source_start_sec: float | None = None,
        source_end_sec: float | None = None,
    ) -> tuple[SherpaStreamingHypothesis, ...]:
        """Accept one chunk and emit a changed partial and/or endpoint final."""

        self._require_open()
        if self._endpoint_waiting_for_reset:
            raise ContractValidationError(
                "sherpa endpoint was finalized; reset the stream before accepting audio"
            )
        if sample_rate < 1:
            raise ContractValidationError("stream sample_rate must be >= 1")
        chunk = np.ascontiguousarray(samples, dtype=np.float32).reshape(-1)
        if not np.all(np.isfinite(chunk)):
            raise ContractValidationError("stream audio contains non-finite samples")
        if source_start_sec is not None:
            if source_start_sec + 1e-9 < self.audio_consumed_through_sec:
                raise ContractValidationError(
                    "stream source timestamps must be monotonic and non-overlapping"
                )
            if not self._audio_accepted:
                self.source_start_sec = float(source_start_sec)
            self.audio_consumed_through_sec = float(source_start_sec)
        derived_end = self.audio_consumed_through_sec + (len(chunk) / sample_rate)
        if source_end_sec is not None:
            if source_end_sec + 1e-9 < self.audio_consumed_through_sec:
                raise ContractValidationError(
                    "stream source_end_sec must not precede source_start_sec"
                )
            derived_end = float(source_end_sec)
        self.stream.accept_waveform(sample_rate, chunk)
        self._audio_accepted = True
        self.audio_consumed_through_sec = derived_end
        decode_latency_ms = self._decode_ready()
        payload = _stream_result_payload(self.recognizer, self.stream)
        updates: list[SherpaStreamingHypothesis] = []
        text = str(payload["text"])
        if text != self._previous_text and (text or self._partial_emitted):
            updates.append(
                self._hypothesis(
                    payload,
                    decode_latency_ms=decode_latency_ms,
                    is_final=False,
                )
            )

        endpoint_detected = bool(
            self.endpoint.enabled
            and hasattr(self.recognizer, "is_endpoint")
            and self.recognizer.is_endpoint(self.stream)
        )
        if endpoint_detected:
            final = self._hypothesis(
                payload,
                decode_latency_ms=decode_latency_ms,
                is_final=True,
                endpoint_detected=True,
                finalization_reason="backend_endpoint",
                finalization_latency_ms=0.0,
                stream_reset_performed=self.auto_reset_on_endpoint,
            )
            updates.append(final)
            if self.auto_reset_on_endpoint:
                self._reset_after_endpoint()
            else:
                self._endpoint_waiting_for_reset = True
        return tuple(updates)

    def accept_waveform(
        self,
        sample_rate: int,
        samples: np.ndarray | Sequence[float],
        *,
        source_start_sec: float | None = None,
        source_end_sec: float | None = None,
    ) -> tuple[SherpaStreamingHypothesis, ...]:
        """Sherpa-shaped alias for :meth:`accept_audio`."""

        return self.accept_audio(
            samples,
            sample_rate=sample_rate,
            source_start_sec=source_start_sec,
            source_end_sec=source_end_sec,
        )

    def finalize(
        self,
        *,
        reason: str = "input_finished",
    ) -> SherpaStreamingHypothesis:
        """Flush buffered features exactly once and return the final hypothesis."""

        self._require_open()
        if not reason.strip():
            raise ContractValidationError(
                "stream finalization reason must not be empty"
            )
        finalization_started = time.perf_counter()
        if self.tail_padding_sec:
            self.stream.accept_waveform(
                self.sample_rate,
                np.zeros(
                    int(round(self.tail_padding_sec * self.sample_rate)),
                    dtype=np.float32,
                ),
            )
        self.stream.input_finished()
        decode_latency_ms = self._decode_ready()
        payload = _stream_result_payload(self.recognizer, self.stream)
        finalization_latency_ms = (time.perf_counter() - finalization_started) * 1000.0
        result = self._hypothesis(
            payload,
            decode_latency_ms=decode_latency_ms,
            is_final=True,
            finalization_reason=reason,
            finalization_latency_ms=finalization_latency_ms,
        )
        self._closed = True
        return result

    def reset(self, *, reason: str = "manual") -> SherpaStreamingReset:
        """Discard current decoder state and create a fresh stream on the same model."""

        self._require_open()
        if not reason.strip():
            raise ContractValidationError("stream reset reason must not be empty")
        prior = self.utterance_index
        self.stream = self.recognizer.create_stream()
        self._advance_utterance()
        return SherpaStreamingReset(
            reset_count=self.reset_count,
            prior_utterance_index=prior,
            next_utterance_index=self.utterance_index,
            reason=reason,
            audio_consumed_through_sec=self.audio_consumed_through_sec,
            backend_reset_used=False,
        )

    def _decode_ready(self) -> float:
        started = time.perf_counter()
        steps = 0
        while self.recognizer.is_ready(self.stream):
            if steps >= self.max_decode_steps_per_accept:
                raise SherpaOnnxASRUnavailableError(
                    "sherpa-onnx recognizer exceeded the per-chunk decode-step guard"
                )
            _decode_stream(self.recognizer, self.stream)
            steps += 1
        return (time.perf_counter() - started) * 1000.0

    def _hypothesis(
        self,
        payload: Mapping[str, object],
        *,
        decode_latency_ms: float,
        is_final: bool,
        endpoint_detected: bool = False,
        finalization_reason: str | None = None,
        finalization_latency_ms: float | None = None,
        stream_reset_performed: bool = False,
    ) -> SherpaStreamingHypothesis:
        text = str(payload["text"])
        tokens = tuple(str(item) for item in payload.get("tokens", ()))
        if not tokens:
            tokens = tuple(text.split())
        comparison_tokens = tuple(normalize_text(text).split())
        stable_tokens = (
            comparison_tokens
            if is_final
            else _common_prefix(self._previous_tokens, comparison_tokens)
        )
        first_partial = not is_final and not self._partial_emitted
        self.sequence += 1
        revision = self._revision_number
        self._revision_number += 1
        result = SherpaStreamingHypothesis(
            sequence=self.sequence,
            utterance_index=self.utterance_index,
            revision_number=revision,
            text=text,
            normalized_text=normalize_text(text),
            tokens=tokens,
            token_timestamps_sec=tuple(
                self.source_start_sec + float(item)
                for item in payload.get("timestamps", ())
            ),
            words=tuple(str(item) for item in payload.get("words", ())),
            audio_consumed_through_sec=self.audio_consumed_through_sec,
            emitted_elapsed_sec=time.perf_counter() - self.started_monotonic,
            decode_latency_ms=decode_latency_ms,
            is_final=is_final,
            is_first_partial=first_partial,
            endpoint_detected=endpoint_detected,
            finalization_reason=finalization_reason,
            finalization_latency_ms=finalization_latency_ms,
            stable_prefix_text=" ".join(stable_tokens),
            stable_prefix_token_count=len(stable_tokens),
            stream_reset_performed=stream_reset_performed,
        )
        self._previous_tokens = comparison_tokens
        self._previous_text = text
        if not is_final:
            self._partial_emitted = True
        return result

    def _reset_after_endpoint(self) -> None:
        backend_reset_used = False
        if hasattr(self.recognizer, "reset"):
            backend_reset_used = self.recognizer.reset(self.stream) is not False
        if not backend_reset_used:
            self.stream = self.recognizer.create_stream()
        self._advance_utterance()

    def _advance_utterance(self) -> None:
        self.reset_count += 1
        self.utterance_index += 1
        self.source_start_sec = self.audio_consumed_through_sec
        self._revision_number = 0
        self._previous_tokens = ()
        self._previous_text = ""
        self._partial_emitted = False
        self._audio_accepted = False
        self._endpoint_waiting_for_reset = False

    def _require_open(self) -> None:
        if self._closed:
            raise ContractValidationError(
                "sherpa streaming session is already finalized"
            )


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
        self.sample_rate = _positive_int(
            self.params.get("sample_rate", 16000), "sample_rate"
        )
        self.feature_dim = _positive_int(
            self.params.get("feature_dim", 80), "feature_dim"
        )
        self.num_threads = _positive_int(
            self.params.get("num_threads", 2), "num_threads"
        )
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
        endpoint = self.params.get("endpoint")
        if endpoint is not None and not isinstance(endpoint, Mapping):
            raise ContractValidationError("sherpa endpoint params must be a mapping")
        self.endpoint = SherpaEndpointConfig.from_mapping(endpoint)
        self._recognizer_endpoint: SherpaEndpointConfig | None = None
        self._recognizer_injected = self.recognizer is not None
        self._load_sec: float | None = None
        self.last_streaming_diagnostics: dict[str, object] | None = None

    def open_stream(
        self,
        *,
        context: ASRContext | None = None,
        endpoint_overlay: Mapping[str, object] | None = None,
        source_start_sec: float = 0.0,
        auto_reset_on_endpoint: bool = True,
        max_decode_steps_per_accept: int = 10000,
    ) -> SherpaOnnxStreamingSession:
        """Open a persistent native stream without changing segment-mode flags.

        In particular, callers must leave AG's frozen
        ``native_streaming_replay=false`` setting untouched.  This method is a
        separate runtime surface and records any endpoint behavior as an
        explicit overlay.
        """

        endpoint = SherpaEndpointConfig.from_mapping(
            endpoint_overlay,
            base=self.endpoint,
        )
        recognizer = self._recognizer(context, endpoint=endpoint)
        return SherpaOnnxStreamingSession(
            recognizer=recognizer,
            sample_rate=self.sample_rate,
            tail_padding_sec=self.tail_padding_sec,
            endpoint=endpoint,
            source_start_sec=source_start_sec,
            auto_reset_on_endpoint=auto_reset_on_endpoint,
            max_decode_steps_per_accept=max_decode_steps_per_accept,
        )

    def transcribe(
        self, audio_segment: AudioSegment, context: ASRContext
    ) -> ASRTranscript:
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

    def _recognizer(
        self,
        context: ASRContext | None = None,
        *,
        endpoint: SherpaEndpointConfig | None = None,
    ) -> Any:
        requested_endpoint = endpoint or self.endpoint
        if self.recognizer is not None:
            if (
                not self._recognizer_injected
                and self._recognizer_endpoint is not None
                and self._recognizer_endpoint != requested_endpoint
            ):
                raise ContractValidationError(
                    "the loaded sherpa recognizer has different endpoint settings; "
                    "create a dedicated adapter instance for this runtime policy"
                )
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
                enable_endpoint_detection=requested_endpoint.enabled,
                rule1_min_trailing_silence=(
                    requested_endpoint.rule1_min_trailing_silence
                ),
                rule2_min_trailing_silence=(
                    requested_endpoint.rule2_min_trailing_silence
                ),
                rule3_min_utterance_length=(
                    requested_endpoint.rule3_min_utterance_length
                ),
            )
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SherpaOnnxASRUnavailableError(
                f"sherpa-onnx model load failed: {exc}"
            ) from exc
        self._load_sec = time.perf_counter() - started_at
        self._recognizer_endpoint = requested_endpoint
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


def _stream_result_payload(recognizer: Any, stream: Any) -> dict[str, object]:
    """Read the richest available result without depending on one binding version."""

    result = (
        recognizer.get_result_all(stream)
        if hasattr(recognizer, "get_result_all")
        else recognizer.get_result(stream)
    )
    return {
        "text": _result_text(result),
        "tokens": _result_sequence(result, "tokens"),
        "timestamps": _result_float_sequence(result, "timestamps"),
        "words": _result_sequence(result, "words"),
    }


def _result_sequence(result: object, key: str) -> tuple[str, ...]:
    if isinstance(result, Mapping):
        value = result.get(key, ())
    else:
        value = getattr(result, key, ())
    if value is None or isinstance(value, (str, bytes)):
        return () if value is None else (str(value),)
    try:
        return tuple(str(item) for item in value)
    except TypeError:
        return ()


def _result_float_sequence(result: object, key: str) -> tuple[float, ...]:
    if isinstance(result, Mapping):
        value = result.get(key, ())
    else:
        value = getattr(result, key, ())
    if value is None or isinstance(value, (str, bytes)):
        return ()
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return ()


def _common_prefix(left: Sequence[str], right: Sequence[str]) -> tuple[str, ...]:
    common: list[str] = []
    for left_item, right_item in zip(left, right, strict=False):
        if left_item != right_item:
            break
        common.append(left_item)
    return tuple(common)


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


class SherpaOnnxLibriGigaZipformer20230621ASR(SherpaOnnxASR):
    """LibriSpeech+GigaSpeech checkpoint using the comparable segment contract."""

    name = "sherpa_onnx_libri_giga_zipformer_2023_06_21"

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.native_streaming_replay:
            raise ContractValidationError(
                "the Libri+Giga large-study component requires "
                "native_streaming_replay=false"
            )
