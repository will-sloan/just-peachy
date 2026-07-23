from __future__ import annotations


class SherpaPunctuationBackend:
    """Placeholder for a sherpa-onnx punctuation backend.

    Fill this file in Prompt 09.
    """

    def __init__(self, model_dir: str) -> None:
        self.model_dir = model_dir
        raise NotImplementedError("Implement this backend in Codex Prompt 09.")

    def punctuate(self, text: str) -> str:
        raise NotImplementedError
