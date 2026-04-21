"""Built-in fake model runner for pipeline self-tests."""

from __future__ import annotations

import logging

from app.model_runner.base import ModelRunner, prediction_from_record
from app.prediction_io.schema import UtterancePrediction


class FakeModelRunner(ModelRunner):
    """Generate fake predictions in the same format as a real runner."""

    name = "simulation"

    def __init__(self, simulation_mode: str) -> None:
        allowed = {"perfect", "noisy", "drop_some"}
        if simulation_mode not in allowed:
            raise ValueError(f"Unknown simulation mode {simulation_mode!r}; choose one of {sorted(allowed)}")
        self.simulation_mode = simulation_mode

    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction | None:
        reference = str(record.get("reference_text") or "")
        index = int(record.get("_selection_index") or 0)

        if self.simulation_mode == "drop_some" and index % 20 == 19:
            logger.info("Simulation skipped prediction for %s", record.get("recording_id"))
            return None

        if self.simulation_mode == "perfect" or self.simulation_mode == "drop_some":
            text = reference
        else:
            text = _lightly_corrupt(reference, index)
        return prediction_from_record(record, text)


def _lightly_corrupt(text: str, index: int) -> str:
    """Make deterministic small transcript changes so WER is non-zero."""

    words = text.split()
    if not words:
        return "noise"
    mode = index % 3
    if mode == 0 and len(words) > 1:
        drop_at = min(len(words) - 1, max(0, len(words) // 2))
        return " ".join(words[:drop_at] + words[drop_at + 1 :])
    if mode == 1:
        replace_at = min(len(words) - 1, max(0, len(words) // 2))
        words[replace_at] = "noise"
        return " ".join(words)
    return " ".join(words + ["extra"])

