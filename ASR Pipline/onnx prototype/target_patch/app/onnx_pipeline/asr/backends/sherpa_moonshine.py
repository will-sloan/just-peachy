from __future__ import annotations

import numpy as np


class SherpaMoonshineBackend:
    """Placeholder for a sherpa-onnx Moonshine backend.

    This should be implemented only after the first Whisper path works.
    """

    def __init__(self, model_dir: str, language: str | None = None, task: str | None = None) -> None:
        self.model_dir = model_dir
        self.language = language
        self.task = task
        raise NotImplementedError("Implement this backend in Codex Prompt 13.")

    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        raise NotImplementedError
