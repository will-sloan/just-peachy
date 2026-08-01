"""Resemblyzer speaker-embedding adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from typing import Any, Mapping

from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.errors import InferencePipelineError
from app.inference_pipeline.speaker_embedding.adapter_utils import (
    load_segment_samples,
    non_negative_float,
    resolve_embedding_model_path,
    successful_embedding,
)
from app.inference_pipeline.speaker_embedding.base import (
    DEFAULT_MIN_DURATION_SEC,
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
)


class ResemblyzerUnavailableError(InferencePipelineError):
    """Raised when Resemblyzer or its optional custom weights are unavailable."""


@dataclass
class ResemblyzerSpeakerEmbeddingAdapter(SpeakerEmbeddingBase):
    """Resemblyzer VoiceEncoder adapter with its packaged pretrained weights."""

    params: Mapping[str, object] | None = None
    encoder: Any | None = None
    preprocess_fn: Any | None = None

    name = "resemblyzer"

    def __post_init__(self) -> None:
        self.params = dict(self.params or {})
        self.model_name = str(self.params.get("model_name") or "resemblyzer")
        self.weights_path = self.params.get("weights_path")
        self.sample_rate_hz = int(self.params.get("sample_rate_hz", 16000))
        self.configured_device = str(self.params.get("device") or "cpu")
        self.dtype = "float32"
        self._load_sec: float | None = None
        SpeakerEmbeddingBase.__init__(
            self,
            model_name=self.model_name,
            min_duration_sec=non_negative_float(
                self.params.get("min_duration_sec", DEFAULT_MIN_DURATION_SEC),
                "min_duration_sec",
            ),
            device=self.configured_device,
            dtype=self.dtype,
        )

    def embed(
        self,
        audio_segment: AudioSegment,
        context: SpeakerEmbeddingContext,
    ) -> SpeakerEmbedding:
        started_at = time.perf_counter()
        audio = load_segment_samples(audio_segment, target_sample_rate=self.sample_rate_hz)
        if self._is_too_short(audio.duration_sec):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=audio.duration_sec,
            )
        encoder, preprocess = self._encoder(context)
        try:
            prepared = preprocess(audio.samples, source_sr=audio.sample_rate)
            vector = encoder.embed_utterance(prepared)
        except Exception as exc:
            raise ResemblyzerUnavailableError(
                f"Resemblyzer embedding extraction failed: {exc}"
            ) from exc
        return successful_embedding(
            self,
            audio_segment,
            context,
            vector,
            started_at=started_at,
            duration_sec=audio.duration_sec,
            sample_rate=audio.sample_rate,
            device=self.configured_device,
            load_sec=self._load_sec,
            metadata={"adapter": self.name, "weights_path": self.weights_path},
        )

    def _encoder(self, context: SpeakerEmbeddingContext) -> tuple[Any, Any]:
        if self.encoder is not None and self.preprocess_fn is not None:
            return self.encoder, self.preprocess_fn
        if importlib.util.find_spec("resemblyzer") is None:
            raise ResemblyzerUnavailableError(
                "resemblyzer is not installed in the active environment."
            )
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav

            kwargs: dict[str, object] = {
                "device": self.configured_device,
                "verbose": False,
            }
            if self.weights_path is not None:
                kwargs["weights_fpath"] = str(
                    resolve_embedding_model_path(self.weights_path, context)
                )
            started_at = time.perf_counter()
            self.encoder = VoiceEncoder(**kwargs)
            self.preprocess_fn = preprocess_wav
            self._load_sec = time.perf_counter() - started_at
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise ResemblyzerUnavailableError(
                f"Resemblyzer VoiceEncoder load failed: {exc}"
            ) from exc
        return self.encoder, self.preprocess_fn
