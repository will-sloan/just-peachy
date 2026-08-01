"""Lazy WeSpeaker speaker-embedding adapter."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import torch

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


class WeSpeakerUnavailableError(InferencePipelineError):
    """Raised when WeSpeaker or its configured model cannot run locally."""


@dataclass
class WeSpeakerEmbeddingAdapter(SpeakerEmbeddingBase):
    """WeSpeaker embedding extraction using its in-memory PCM API."""

    params: Mapping[str, object] | None = None
    model: Any | None = None

    name = "wespeaker"

    def __post_init__(self) -> None:
        self.params = dict(self.params or {})
        self.model_source = str(self.params.get("model_source") or "english")
        self.model_path = self.params.get("model_path")
        self.model_name = str(self.params.get("model_name") or "wespeaker_english")
        self.sample_rate_hz = int(self.params.get("sample_rate_hz", 16000))
        self.configured_device = str(self.params.get("device") or "cpu")
        self.dtype = str(self.params.get("dtype") or "float32")
        self.allow_model_downloads = bool(self.params.get("allow_model_downloads", False))
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
        requested_duration = self._segment_duration(audio_segment)
        if self._is_too_short(requested_duration):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=requested_duration,
            )
        audio = load_segment_samples(
            audio_segment,
            target_sample_rate=self.sample_rate_hz,
        )
        if self._is_too_short(audio.duration_sec):
            return self._short_embedding(
                audio_segment,
                context,
                started_at=started_at,
                duration_sec=audio.duration_sec,
            )
        model = self._model(context)
        try:
            pcm = torch.from_numpy(audio.samples).unsqueeze(0)
            vector = model.extract_embedding_from_pcm(pcm, audio.sample_rate)
        except Exception as exc:
            raise WeSpeakerUnavailableError(
                f"WeSpeaker embedding extraction failed: {exc}"
            ) from exc
        if vector is None:
            raise WeSpeakerUnavailableError("WeSpeaker returned no embedding.")
        return successful_embedding(
            self,
            audio_segment,
            context,
            torch.as_tensor(vector).detach().cpu().reshape(-1),
            started_at=started_at,
            duration_sec=audio.duration_sec,
            sample_rate=audio.sample_rate,
            device=self.configured_device,
            load_sec=self._load_sec,
            metadata={"adapter": self.name, "model_source": self.model_source},
        )

    def _model(self, context: SpeakerEmbeddingContext) -> Any:
        if self.model is not None:
            return self.model
        if importlib.util.find_spec("wespeaker") is None:
            raise WeSpeakerUnavailableError(
                "wespeaker is not installed in the active environment."
            )
        reference = self.model_source
        if self.model_path is not None:
            try:
                reference = str(resolve_embedding_model_path(self.model_path, context))
            except Exception as exc:
                if not self.allow_model_downloads:
                    raise WeSpeakerUnavailableError(
                        f"WeSpeaker local model is unavailable: {exc}"
                    ) from exc
        elif not self.allow_model_downloads:
            raise WeSpeakerUnavailableError(
                "WeSpeaker downloads are disabled and model_path is not configured."
            )
        try:
            import torchaudio

            if not hasattr(torchaudio, "set_audio_backend"):
                torchaudio.set_audio_backend = lambda *_args, **_kwargs: None
            import wespeaker  # type: ignore[import-not-found]

            started_at = time.perf_counter()
            if Path(reference).exists() and hasattr(wespeaker, "load_model_local"):
                self.model = wespeaker.load_model_local(reference)
            else:
                self.model = wespeaker.load_model(reference)
            if hasattr(self.model, "set_device"):
                self.model.set_device(self.configured_device)
            if hasattr(self.model, "set_resample_rate"):
                self.model.set_resample_rate(self.sample_rate_hz)
            self._load_sec = time.perf_counter() - started_at
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise WeSpeakerUnavailableError(f"WeSpeaker model load failed: {exc}") from exc
        return self.model
