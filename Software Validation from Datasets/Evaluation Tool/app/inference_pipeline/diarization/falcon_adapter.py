"""Picovoice Falcon speaker diarization adapter."""

from __future__ import annotations

import importlib.util
import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from app.inference_pipeline.asr.audio_utils import resolve_model_path
from app.inference_pipeline.diarization.adapter_utils import (
    anonymous_speaker_label,
    mono_samples,
)
from app.inference_pipeline.diarization.base import (
    DiarizationBase,
    DiarizationParameters,
    DiarizationUnavailableError,
    SpeakerTurnRegion,
    mark_overlapping_turns,
)
from app.inference_pipeline.errors import ContractValidationError


class FalconDiarizationUnavailableError(DiarizationUnavailableError):
    """Raised when Falcon is unavailable or lacks a Picovoice AccessKey."""


@dataclass
class PicovoiceFalconDiarizer(DiarizationBase):
    """Falcon adapter using its raw mono PCM16 API."""

    params: DiarizationParameters | Mapping[str, object] | None = None
    engine: Any | None = None

    name = "picovoice_falcon"

    def __post_init__(self) -> None:
        raw = dict(self.params or {}) if isinstance(self.params, Mapping) else {}
        DiarizationBase.__init__(self, self.params)
        self.access_key_env = str(raw.get("access_key_env") or "PICOVOICE_ACCESS_KEY")
        self.model_path = raw.get("model_path")
        self.library_path = raw.get("library_path")
        self.device = str(raw.get("device") or "best")
        if not self.access_key_env.strip():
            raise ContractValidationError("Falcon access_key_env must be non-empty")
        if not self.device.strip():
            raise ContractValidationError("Falcon device must be non-empty")
        if self.params.min_speakers is not None or self.params.max_speakers is not None:
            raise ContractValidationError(
                "Picovoice Falcon does not expose speaker-count constraints"
            )
        self.last_runtime_sec: float | None = None
        self.last_turns: tuple[SpeakerTurnRegion, ...] = ()

    def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
        engine = self._engine()
        sample_rate = int(engine.sample_rate)
        samples = mono_samples(audio, target_sample_rate=sample_rate)
        pcm16 = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)
        started_at = time.perf_counter()
        try:
            segments = engine.process(pcm16.tolist())
            turns = [
                SpeakerTurnRegion(
                    start_sec=float(segment.start_sec),
                    end_sec=float(segment.end_sec),
                    speaker_turn_label=anonymous_speaker_label(segment.speaker_tag),
                    source=self.name,
                )
                for segment in segments
                if float(segment.end_sec) - float(segment.start_sec)
                >= self.params.min_turn_sec
            ]
        except Exception as exc:
            raise FalconDiarizationUnavailableError(
                f"Picovoice Falcon diarization failed: {exc}"
            ) from exc
        turns = mark_overlapping_turns(turns)
        self.last_runtime_sec = time.perf_counter() - started_at
        self.last_turns = tuple(turns)
        return turns

    def _engine(self) -> Any:
        if self.engine is not None:
            return self.engine
        if importlib.util.find_spec("pvfalcon") is None:
            raise FalconDiarizationUnavailableError(
                "pvfalcon is not installed in the active environment."
            )
        access_key = (os.environ.get(self.access_key_env) or "").strip()
        if not access_key:
            raise FalconDiarizationUnavailableError(
                f"Picovoice AccessKey is missing; set {self.access_key_env}."
            )
        try:
            import pvfalcon  # type: ignore[import-not-found]

            kwargs: dict[str, object] = {"access_key": access_key, "device": self.device}
            if self.model_path:
                kwargs["model_path"] = str(resolve_model_path(self.model_path))
            if self.library_path:
                kwargs["library_path"] = str(resolve_model_path(self.library_path))
            self.engine = pvfalcon.create(**kwargs)
        except Exception as exc:  # pragma: no cover - dependency boundary
            raise FalconDiarizationUnavailableError(
                f"Picovoice Falcon load failed: {exc}"
            ) from exc
        return self.engine

    def close(self) -> None:
        if self.engine is not None and hasattr(self.engine, "delete"):
            self.engine.delete()
        self.engine = None
