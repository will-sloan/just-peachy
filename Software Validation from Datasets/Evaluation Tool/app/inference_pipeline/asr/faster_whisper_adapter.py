"""Lazy faster-whisper adapter boundary."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Mapping

from app.inference_pipeline.asr.base import ASRBase, ASRContext
from app.inference_pipeline.contracts import ASRTranscript, AudioSegment
from app.inference_pipeline.errors import InferencePipelineError


class FasterWhisperASRUnavailableError(InferencePipelineError):
    """Raised when faster-whisper is selected without local support."""


@dataclass
class FasterWhisperASR(ASRBase):
    """Boundary for future faster-whisper comparison runs."""

    params: Mapping[str, object] | None = None

    name = "faster_whisper"

    def __post_init__(self) -> None:
        ASRBase.__init__(self)
        self.params = dict(self.params or {})

    def transcribe(self, audio_segment: AudioSegment, context: ASRContext) -> ASRTranscript:
        _ = (audio_segment, context)
        if importlib.util.find_spec("faster_whisper") is None:
            raise FasterWhisperASRUnavailableError(
                "faster-whisper is not installed in the active environment."
            )
        raise FasterWhisperASRUnavailableError(
            "faster-whisper execution is not wired in M7; use whisper_tiny when local assets are available."
        )
