from __future__ import annotations

from typing import Protocol

import numpy as np

from .contracts import SpeechSegment


class VadEngine(Protocol):
    def segment(self, audio: np.ndarray, sample_rate: int) -> list[SpeechSegment]:
        ...


class AsrEngine(Protocol):
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        ...


class SpeakerEmbedder(Protocol):
    def embed(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        ...


class Punctuator(Protocol):
    def punctuate(self, text: str) -> str:
        ...
