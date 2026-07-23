from __future__ import annotations

import numpy as np


class SherpaWhisperBackend:
    """Placeholder for a sherpa-onnx Whisper backend.

    Fill this file in Prompt 05.
    Expected behavior:
    - load a sherpa-onnx non-streaming Whisper recognizer once
    - expose transcribe(audio, sample_rate) -> str
    - validate model_dir layout and fail clearly if files are missing
    """

    def __init__(self, model_dir: str, language: str | None = None, task: str | None = None) -> None:
        self.model_dir = model_dir
        self.language = language
        self.task = task
        raise NotImplementedError("Implement this backend in Codex Prompt 05.")

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        raise NotImplementedError
