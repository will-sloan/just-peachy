from __future__ import annotations

import numpy as np


class WeSpeakerCampPlusOnnxBackend:
    """Placeholder for a WeSpeaker CAM++ ONNX embedding backend.

    Fill this file in Prompt 07.
    Expected behavior:
    - load ONNX Runtime session once
    - validate model I/O
    - expose embed(audio, sample_rate) -> np.ndarray
    """

    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        raise NotImplementedError("Implement this backend in Codex Prompt 07.")

    def embed(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        raise NotImplementedError
