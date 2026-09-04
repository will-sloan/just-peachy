"""Backend-neutral runtime glue for native persistent Sherpa-ONNX ASR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from app.inference_pipeline.asr.base import ASRContext
from app.inference_pipeline.asr.sherpa_onnx_adapter import (
    SherpaEndpointConfig,
    SherpaOnnxASR,
    SherpaOnnxLibriGigaZipformer20230621ASR,
    SherpaOnnxStreamingSession,
    SherpaStreamingHypothesis,
    SherpaStreamingReset,
)
from app.inference_pipeline.errors import ContractValidationError

from .interfaces import StreamingASRAdapter
from .models import NormalizedAudioFrame


FULL_PIPELINE_SHERPA_COMPONENTS = frozenset(
    {
        "sherpa_onnx",
        "sherpa_onnx_libri_giga_zipformer_2023_06_21",
    }
)

ACCEPTED_AUDIO_INTERVAL_PROVENANCE = (
    "native_stream_accepted_audio_since_stream_or_reset.v1"
)


@dataclass(frozen=True)
class StreamingASRStatus:
    """Small coordinator-facing status record for one native ASR adapter."""

    backend_id: str
    state: str
    session_id: str | None
    sample_rate_hz: int
    recognizer_loaded: bool
    endpoint: SherpaEndpointConfig
    utterance_index: int | None
    reset_count: int
    audio_consumed_through_sec: float | None
    detail: str | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "backend_id": self.backend_id,
            "state": self.state,
            "session_id": self.session_id,
            "sample_rate_hz": self.sample_rate_hz,
            "recognizer_loaded": self.recognizer_loaded,
            "endpoint": self.endpoint.to_jsonable(),
            "utterance_index": self.utterance_index,
            "reset_count": self.reset_count,
            "audio_consumed_through_sec": self.audio_consumed_through_sec,
            "detail": self.detail,
        }


class SherpaStreamingASRAdapter:
    """Expose AO/AG through the common full-pipeline streaming interface.

    All model operations are delegated to the existing :class:`SherpaOnnxASR`.
    This wrapper never changes ``native_streaming_replay`` and therefore does
    not mutate AG's frozen segment-study configuration.
    """

    def __init__(
        self,
        backend: SherpaOnnxASR,
        *,
        endpoint_overlay: Mapping[str, object] | None = None,
        auto_reset_on_endpoint: bool = True,
        max_decode_steps_per_accept: int = 10000,
    ) -> None:
        backend_id = str(backend.name)
        if backend_id not in FULL_PIPELINE_SHERPA_COMPONENTS:
            raise ContractValidationError(
                f"unsupported full-pipeline Sherpa ASR component: {backend_id}"
            )
        self.backend = backend
        self.backend_id = backend_id
        self.component_id = backend_id
        self.sample_rate_hz = int(backend.sample_rate)
        self.endpoint_overlay = dict(endpoint_overlay or {})
        self.endpoint = SherpaEndpointConfig.from_mapping(
            self.endpoint_overlay,
            base=backend.endpoint,
        )
        self.auto_reset_on_endpoint = auto_reset_on_endpoint
        self.max_decode_steps_per_accept = max_decode_steps_per_accept
        self._session: SherpaOnnxStreamingSession | None = None
        self._session_id: str | None = None
        self._state = "created"
        self._detail: str | None = None
        self._accepted_audio_interval: dict[str, object] | None = None
        self._accepted_interval_by_update: dict[
            tuple[int, int, int], dict[str, object]
        ] = {}

    def start(
        self,
        session_id: str,
        *,
        context: ASRContext | None = None,
        source_start_sec: float = 0.0,
    ) -> None:
        """Warm/load the recognizer and create exactly one persistent stream."""

        if not session_id.strip():
            raise ContractValidationError("streaming ASR session_id must not be empty")
        if self._session is not None and not self._session.closed:
            raise ContractValidationError("streaming ASR adapter is already running")
        self._session_id = session_id
        self._state = "starting"
        self._detail = None
        self._accepted_audio_interval = None
        self._accepted_interval_by_update.clear()
        try:
            self._session = self.backend.open_stream(
                context=context,
                endpoint_overlay=self.endpoint_overlay,
                source_start_sec=source_start_sec,
                auto_reset_on_endpoint=self.auto_reset_on_endpoint,
                max_decode_steps_per_accept=self.max_decode_steps_per_accept,
            )
        except Exception as exc:
            self._state = "failed"
            self._detail = f"{type(exc).__name__}: {exc}"
            raise
        self._state = "running"

    def accept_audio(
        self,
        frame: NormalizedAudioFrame,
    ) -> tuple[Mapping[str, object], ...]:
        """Accept a normalized frame and return ordered adapter event records."""

        if not isinstance(frame, NormalizedAudioFrame):
            raise ContractValidationError(
                "full-pipeline Sherpa ASR requires a NormalizedAudioFrame"
            )
        return tuple(
            self._hypothesis_record(update)
            for update in self._accept_samples(
                frame.samples,
                sample_rate=frame.sample_rate_hz,
                source_start_sec=frame.audio_start_sec,
                source_end_sec=frame.audio_end_sec,
                source_sample_start=frame.sample_start,
                source_sample_end=frame.sample_end,
                source_clock_id=frame.source_clock_id,
                source_clock_type=frame.source_clock_type,
            )
        )

    def accept_samples(
        self,
        samples: np.ndarray | Sequence[float],
        *,
        sample_rate: int,
        source_start_sec: float | None = None,
        source_end_sec: float | None = None,
        source_sample_start: int | None = None,
        source_sample_end: int | None = None,
        source_clock_id: str = "normalized_audio_sample_clock",
        source_clock_type: str = "audio_sample",
    ) -> tuple[SherpaStreamingHypothesis, ...]:
        """Accept already-normalized samples inside an isolated worker."""

        return self._accept_samples(
            samples,
            sample_rate=sample_rate,
            source_start_sec=source_start_sec,
            source_end_sec=source_end_sec,
            source_sample_start=source_sample_start,
            source_sample_end=source_sample_end,
            source_clock_id=source_clock_id,
            source_clock_type=source_clock_type,
        )

    def finalize(self, reason: str) -> tuple[Mapping[str, object], ...]:
        result = self.finalize_one(reason=reason)
        return (self._hypothesis_record(result),)

    def finalize_one(
        self,
        *,
        reason: str = "input_finished",
    ) -> SherpaStreamingHypothesis:
        session = self._running_session()
        self._state = "stopping"
        try:
            result = session.finalize(reason=reason)
        except Exception as exc:
            self._mark_failed(exc)
            raise
        self._remember_update_interval(result)
        self._accepted_audio_interval = None
        self._state = "finalized"
        return result

    def reset(self, reason: str) -> tuple[Mapping[str, object], ...]:
        result = self.reset_one(reason=reason)
        return (self._reset_record(result),)

    def reset_one(self, *, reason: str = "manual") -> SherpaStreamingReset:
        session = self._running_session()
        try:
            result = session.reset(reason=reason)
        except Exception as exc:
            self._mark_failed(exc)
            raise
        self._accepted_audio_interval = None
        return result

    def status(self) -> Mapping[str, object]:
        return self.status_record().to_jsonable()

    def status_record(self) -> StreamingASRStatus:
        session = self._session
        return StreamingASRStatus(
            backend_id=self.backend_id,
            state=self._state,
            session_id=self._session_id,
            sample_rate_hz=self.sample_rate_hz,
            recognizer_loaded=self.backend.recognizer is not None,
            endpoint=self.endpoint,
            utterance_index=(session.utterance_index if session is not None else None),
            reset_count=(session.reset_count if session is not None else 0),
            audio_consumed_through_sec=(
                session.audio_consumed_through_sec if session is not None else None
            ),
            detail=self._detail,
        )

    def close(self) -> None:
        """Release session state; coordinators should call ``finalize`` first."""

        if self._session is not None and not self._session.closed:
            self._session.reset(reason="adapter_close_without_finalize")
        self._session = None
        self._state = "closed"

    def stop(self, *, finalize: bool = True) -> tuple[Mapping[str, object], ...]:
        """Convenience lifecycle used by direct workers and smoke commands."""

        if self._session is None:
            self._state = "stopped"
            return ()
        if self._session.closed:
            self._state = "stopped"
            return ()
        if finalize:
            rows = self.finalize("graceful_stop")
            self._state = "stopped"
            return rows
        rows = self.reset("stop_without_finalize")
        self._session = None
        self._state = "stopped"
        return rows

    def _accept_samples(
        self,
        samples: np.ndarray | Sequence[float],
        *,
        sample_rate: int,
        source_start_sec: float | None,
        source_end_sec: float | None,
        source_sample_start: int | None = None,
        source_sample_end: int | None = None,
        source_clock_id: str = "normalized_audio_sample_clock",
        source_clock_type: str = "audio_sample",
    ) -> tuple[SherpaStreamingHypothesis, ...]:
        session = self._running_session()
        chunk = np.ascontiguousarray(samples, dtype=np.float32).reshape(-1)
        accepted_start_sec = (
            float(source_start_sec)
            if source_start_sec is not None
            else float(session.audio_consumed_through_sec)
        )
        accepted_end_sec = (
            float(source_end_sec)
            if source_end_sec is not None
            else accepted_start_sec + (len(chunk) / sample_rate)
        )
        self._extend_accepted_audio_interval(
            start_sec=accepted_start_sec,
            end_sec=accepted_end_sec,
            sample_rate=sample_rate,
            sample_start=source_sample_start,
            sample_end=source_sample_end,
            source_clock_id=source_clock_id,
            source_clock_type=source_clock_type,
        )
        try:
            updates = session.accept_audio(
                chunk,
                sample_rate=sample_rate,
                source_start_sec=source_start_sec,
                source_end_sec=source_end_sec,
            )
        except Exception as exc:
            self._mark_failed(exc)
            raise
        for update in updates:
            self._remember_update_interval(update)
        if any(
            update.is_final and update.stream_reset_performed for update in updates
        ):
            self._accepted_audio_interval = None
        return updates

    def _hypothesis_record(
        self,
        update: SherpaStreamingHypothesis,
    ) -> Mapping[str, object]:
        session_id = self._session_id or "unstarted"
        payload = update.to_jsonable()
        payload.update(
            {
                "adapter_event_schema_version": "full-pipeline-asr-adapter-event.v1",
                "adapter_event_type": "asr_final" if update.is_final else "asr_partial",
                "backend_id": self.backend_id,
                "session_id": session_id,
                "hypothesis_id": f"{session_id}:asr:{update.utterance_index}",
                "hypothesis_state": "final" if update.is_final else "partial",
                "endpoint_policy_id": self.endpoint.policy_id,
            }
        )
        interval = self._accepted_interval_by_update.pop(
            self._update_key(update), None
        )
        if interval is not None:
            payload["accepted_audio_interval"] = interval
        return payload

    def _reset_record(self, update: SherpaStreamingReset) -> Mapping[str, object]:
        payload = update.to_jsonable()
        payload.update(
            {
                "adapter_event_schema_version": "full-pipeline-asr-adapter-event.v1",
                "adapter_event_type": "asr_reset",
                "backend_id": self.backend_id,
                "session_id": self._session_id,
                "endpoint_policy_id": self.endpoint.policy_id,
            }
        )
        return payload

    def _running_session(self) -> SherpaOnnxStreamingSession:
        if self._state != "running" or self._session is None or self._session.closed:
            raise ContractValidationError("streaming ASR adapter is not running")
        return self._session

    def _mark_failed(self, exc: Exception) -> None:
        self._state = "failed"
        self._detail = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _update_key(update: SherpaStreamingHypothesis) -> tuple[int, int, int]:
        return (
            int(update.sequence),
            int(update.utterance_index),
            int(update.revision_number),
        )

    def _remember_update_interval(self, update: SherpaStreamingHypothesis) -> None:
        if self._accepted_audio_interval is None:
            return
        self._accepted_interval_by_update[self._update_key(update)] = dict(
            self._accepted_audio_interval
        )

    def _extend_accepted_audio_interval(
        self,
        *,
        start_sec: float,
        end_sec: float,
        sample_rate: int,
        sample_start: int | None,
        sample_end: int | None,
        source_clock_id: str,
        source_clock_type: str,
    ) -> None:
        """Track the causal input range without claiming backend word timing."""

        if sample_rate < 1 or end_sec < start_sec:
            raise ContractValidationError("accepted ASR audio interval is invalid")
        start_index = (
            int(sample_start)
            if sample_start is not None
            else int(round(start_sec * sample_rate))
        )
        end_index = (
            int(sample_end)
            if sample_end is not None
            else int(round(end_sec * sample_rate))
        )
        if end_index < start_index:
            raise ContractValidationError("accepted ASR sample interval is reversed")
        if self._accepted_audio_interval is None:
            self._accepted_audio_interval = {
                "sample_start_index": start_index,
                "sample_end_index": end_index,
                "audio_start_sec": start_sec,
                "audio_end_sec": end_sec,
                "sample_rate_hz": int(sample_rate),
                "source_clock_id": str(source_clock_id),
                "source_clock_type": str(source_clock_type),
                "timing_provenance": ACCEPTED_AUDIO_INTERVAL_PROVENANCE,
                "interval_role": "utterance_input_since_stream_or_reset",
                "word_timestamps_inferred": False,
            }
            return
        current = self._accepted_audio_interval
        if int(current["sample_rate_hz"]) != int(sample_rate):
            raise ContractValidationError("ASR sample rate changed inside an utterance")
        if str(current["source_clock_id"]) != str(source_clock_id):
            raise ContractValidationError("ASR source clock changed inside an utterance")
        current["sample_end_index"] = end_index
        current["audio_end_sec"] = end_sec


def build_sherpa_streaming_adapter(
    component_id: str,
    params: Mapping[str, object],
    *,
    recognizer: Any | None = None,
    endpoint_overlay: Mapping[str, object] | None = None,
    auto_reset_on_endpoint: bool = True,
) -> SherpaStreamingASRAdapter:
    """Build exact AO/AG runtime glue without changing their source YAML."""

    if component_id == "sherpa_onnx":
        backend: SherpaOnnxASR = SherpaOnnxASR(params, recognizer=recognizer)
    elif component_id == "sherpa_onnx_libri_giga_zipformer_2023_06_21":
        backend = SherpaOnnxLibriGigaZipformer20230621ASR(
            params,
            recognizer=recognizer,
        )
    else:
        raise ContractValidationError(
            f"unsupported full-pipeline Sherpa ASR component: {component_id}"
        )
    return SherpaStreamingASRAdapter(
        backend,
        endpoint_overlay=endpoint_overlay,
        auto_reset_on_endpoint=auto_reset_on_endpoint,
    )


__all__ = [
    "FULL_PIPELINE_SHERPA_COMPONENTS",
    "SherpaStreamingASRAdapter",
    "StreamingASRAdapter",
    "StreamingASRStatus",
    "build_sherpa_streaming_adapter",
]
