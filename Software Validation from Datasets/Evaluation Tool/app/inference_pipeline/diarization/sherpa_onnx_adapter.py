"""Sherpa-ONNX offline speaker diarization adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from typing import Any, Mapping

from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.inference_pipeline.diarization.adapter_utils import (
    anonymous_speaker_label,
    mono_samples,
    sorted_segments,
)
from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationParameters,
    DiarizationUnavailableError,
    SpeakerTurnRegion,
    mark_overlapping_turns,
)
from app.inference_pipeline.errors import ContractValidationError


class SherpaOnnxDiarizationUnavailableError(DiarizationUnavailableError):
    """Raised when Sherpa-ONNX diarization models cannot run locally."""


@dataclass
class SherpaOnnxDiarizer(DiarizationBase):
    """Offline segmentation + embedding + clustering through Sherpa-ONNX."""

    params: DiarizationParameters | Mapping[str, object] | None = None
    diarizer: Any | None = None

    name = "sherpa_onnx_diarization"

    def __post_init__(self) -> None:
        raw = dict(self.params or {}) if isinstance(self.params, Mapping) else {}
        DiarizationBase.__init__(self, self.params)
        self.segmentation_model = raw.get("segmentation_model_path") or raw.get(
            "segmentation_model"
        )
        self.embedding_model = raw.get("embedding_model_path") or raw.get(
            "embedding_model"
        )
        self.num_threads = int(raw.get("num_threads", 2))
        self.provider = str(raw.get("provider") or "cpu")
        configured_clusters = raw.get("num_clusters", raw.get("num_speakers", -1))
        self.num_clusters = -1 if configured_clusters is None else int(configured_clusters)
        if (
            self.params.min_speakers is not None
            or self.params.max_speakers is not None
        ) and not (
            self.params.min_speakers is not None
            and self.params.min_speakers == self.params.max_speakers
        ):
            raise ContractValidationError(
                "Sherpa adapter supports speaker-count constraints only as an exact "
                "min_speakers == max_speakers value"
            )
        exact_speaker_count = (
            self.params.min_speakers
            if self.params.min_speakers is not None
            and self.params.min_speakers == self.params.max_speakers
            else None
        )
        if exact_speaker_count is not None:
            if self.num_clusters not in {-1, exact_speaker_count}:
                raise ContractValidationError(
                    "Sherpa num_clusters conflicts with equal min_speakers/max_speakers"
                )
            self.num_clusters = exact_speaker_count
        self.clustering_threshold = float(raw.get("clustering_threshold", 0.5))
        self.min_duration_on = float(raw.get("min_duration_on", 0.3))
        self.min_duration_off = float(raw.get("min_duration_off", 0.5))
        if self.num_threads < 1:
            raise ContractValidationError("Sherpa diarization num_threads must be >= 1")
        if self.num_clusters == 0 or self.num_clusters < -1:
            raise ContractValidationError("Sherpa diarization num_clusters must be -1 or >= 1")
        if not 0.0 <= self.clustering_threshold <= 1.0:
            raise ContractValidationError(
                "Sherpa diarization clustering_threshold must be in [0, 1]"
            )
        if self.min_duration_on < 0 or self.min_duration_off < 0:
            raise ContractValidationError(
                "Sherpa diarization minimum durations must be >= 0"
            )
        if not self.provider.strip():
            raise ContractValidationError("Sherpa diarization provider must be non-empty")
        self.last_runtime_sec: float | None = None
        self.last_turns: tuple[SpeakerTurnRegion, ...] = ()

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        diarizer = self._diarizer()
        sample_rate = int(getattr(diarizer, "sample_rate", 16000))
        samples = mono_samples(audio, target_sample_rate=sample_rate)
        started_at = time.perf_counter()
        try:
            raw_result = diarizer.process(samples)
            turns = [
                SpeakerTurnRegion(
                    start_sec=float(segment.start),
                    end_sec=float(segment.end),
                    speaker_turn_label=anonymous_speaker_label(segment.speaker),
                    source=self.name,
                )
                for segment in sorted_segments(raw_result)
                if float(segment.end) - float(segment.start) >= self.params.min_turn_sec
            ]
        except Exception as exc:
            raise SherpaOnnxDiarizationUnavailableError(
                f"Sherpa-ONNX diarization failed: {exc}"
            ) from exc
        turns = mark_overlapping_turns(turns)
        self.last_runtime_sec = time.perf_counter() - started_at
        self.last_turns = tuple(turns)
        return turns

    def _diarizer(self) -> Any:
        if self.diarizer is not None:
            return self.diarizer
        if importlib.util.find_spec("sherpa_onnx") is None:
            raise SherpaOnnxDiarizationUnavailableError(
                "sherpa-onnx is not installed in the active environment."
            )
        try:
            segmentation_path = resolve_model_path(self.segmentation_model)
            embedding_path = resolve_model_path(self.embedding_model)
            import sherpa_onnx  # type: ignore[import-not-found]

            segmentation = sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
                pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(
                    model=str(segmentation_path)
                ),
                num_threads=self.num_threads,
                provider=self.provider,
            )
            embedding = sherpa_onnx.SpeakerEmbeddingExtractorConfig(
                model=str(embedding_path),
                num_threads=self.num_threads,
                provider=self.provider,
            )
            clustering = sherpa_onnx.FastClusteringConfig(
                num_clusters=self.num_clusters,
                threshold=self.clustering_threshold,
            )
            config = sherpa_onnx.OfflineSpeakerDiarizationConfig(
                segmentation=segmentation,
                embedding=embedding,
                clustering=clustering,
                min_duration_on=self.min_duration_on,
                min_duration_off=self.min_duration_off,
            )
            self.diarizer = sherpa_onnx.OfflineSpeakerDiarization(config)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise SherpaOnnxDiarizationUnavailableError(
                f"Sherpa-ONNX diarization model load failed: {exc}"
            ) from exc
        return self.diarizer
