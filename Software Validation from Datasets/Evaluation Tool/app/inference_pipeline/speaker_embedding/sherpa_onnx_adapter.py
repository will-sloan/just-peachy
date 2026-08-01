"""Sherpa-ONNX speaker-embedding adapter."""

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
    positive_int,
    resolve_embedding_model_path,
    successful_embedding,
)
from app.inference_pipeline.speaker_embedding.base import (
    DEFAULT_MIN_DURATION_SEC,
    SpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
)


class SherpaOnnxSpeakerEmbeddingUnavailableError(InferencePipelineError):
    """Raised when Sherpa-ONNX speaker embedding cannot run locally."""


@dataclass
class SherpaOnnxSpeakerEmbeddingAdapter(SpeakerEmbeddingBase):
    """Embedding extraction through Sherpa-ONNX's speaker stream API."""

    params: Mapping[str, object] | None = None
    extractor: Any | None = None

    name = "sherpa_onnx_speaker_embedding"

    def __post_init__(self) -> None:
        self.params = dict(self.params or {})
        self.model_path = self.params.get("model_path") or self.params.get("model")
        self.model_name = str(
            self.params.get("model_name") or "sherpa_onnx_3dspeaker"
        )
        self.sample_rate_hz = positive_int(
            self.params.get("sample_rate_hz", 16000), "sample_rate_hz"
        )
        self.num_threads = positive_int(self.params.get("num_threads", 1), "num_threads")
        self.provider = str(self.params.get("provider") or "cpu")
        self.dtype = "float32"
        self._load_sec: float | None = None
        SpeakerEmbeddingBase.__init__(
            self,
            model_name=self.model_name,
            min_duration_sec=non_negative_float(
                self.params.get("min_duration_sec", DEFAULT_MIN_DURATION_SEC),
                "min_duration_sec",
            ),
            device="cuda" if self.provider.lower().startswith("cuda") else "cpu",
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
        extractor = self._extractor(context)
        try:
            stream = extractor.create_stream()
            stream.accept_waveform(audio.sample_rate, audio.samples)
            stream.input_finished()
            if not extractor.is_ready(stream):
                raise SherpaOnnxSpeakerEmbeddingUnavailableError(
                    "Sherpa-ONNX requires more speech for embedding extraction."
                )
            vector = extractor.compute(stream)
        except SherpaOnnxSpeakerEmbeddingUnavailableError:
            raise
        except Exception as exc:
            raise SherpaOnnxSpeakerEmbeddingUnavailableError(
                f"Sherpa-ONNX embedding extraction failed: {exc}"
            ) from exc
        return successful_embedding(
            self,
            audio_segment,
            context,
            vector,
            started_at=started_at,
            duration_sec=audio.duration_sec,
            sample_rate=audio.sample_rate,
            device=self.device,
            load_sec=self._load_sec,
            metadata={"adapter": self.name, "model_path": str(self.model_path)},
        )

    def _extractor(self, context: SpeakerEmbeddingContext) -> Any:
        if self.extractor is not None:
            return self.extractor
        if importlib.util.find_spec("sherpa_onnx") is None:
            raise SherpaOnnxSpeakerEmbeddingUnavailableError(
                "sherpa-onnx is not installed in the active environment."
            )
        try:
            model_path = resolve_embedding_model_path(self.model_path, context)
            import sherpa_onnx  # type: ignore[import-not-found]

            started_at = time.perf_counter()
            config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(model_path),
                num_threads=self.num_threads,
                provider=self.provider,
            )
            self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)
            self._load_sec = time.perf_counter() - started_at
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SherpaOnnxSpeakerEmbeddingUnavailableError(
                f"Sherpa-ONNX speaker embedding model load failed: {exc}"
            ) from exc
        return self.extractor
