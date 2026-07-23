from __future__ import annotations

import numpy as np

from ..contracts import SpeechSegment


class SileroOnnxBackend:
    """Placeholder for a Silero ONNX VAD backend.

    Fill this file in Prompt 10.
    Expected behavior:
    - load Silero or sherpa-onnx VAD once
    - return speech segments in seconds
    - be conservative by default
    """

    def __init__(self, model_path: str, sample_rate: int = 16000, trim_only: bool = True) -> None:
        self.model_path = model_path
        self.sample_rate = sample_rate
        self.trim_only = trim_only
        raise NotImplementedError("Implement this backend in Codex Prompt 10.")

    def segment(self, audio: np.ndarray, sample_rate: int) -> list[SpeechSegment]:
        raise NotImplementedError
