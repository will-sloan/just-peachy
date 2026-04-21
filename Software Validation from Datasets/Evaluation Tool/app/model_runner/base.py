"""Base wrapper interface for model inference runners."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

from app.augmentation.processor import RuntimeAugmentor
from app.prediction_io.schema import UtterancePrediction
from app.utils.json_utils import write_json


@dataclass(frozen=True)
class RunnerResult:
    """Summary of an inference run."""

    predictions_path: Path
    attempted_count: int
    written_count: int
    skipped_count: int
    failed_count: int
    run_duration_sec: float


class ModelRunner(ABC):
    """Clean interface between the evaluator and external inference code."""

    name = "base"

    def run_batch(
        self,
        records: Iterable[dict[str, object]],
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> RunnerResult:
        """Run inference and write standardized prediction outputs."""

        records_list = list(records)
        predictions_dir.mkdir(parents=True, exist_ok=True)
        self.before_run(records_list, predictions_dir, run_config, logger)

        predictions_path = predictions_dir / "utterances.jsonl"
        attempted_count = 0
        written_count = 0
        skipped_count = 0
        failed_count = 0
        condition_prediction_counts: dict[str, int] = {}
        condition_handles = {}
        started_at = time.perf_counter()
        augmentor = RuntimeAugmentor.from_run_config(run_config, logger)
        augmentor.prepare()

        try:
            with predictions_path.open("w", encoding="utf-8") as handle:
                progress = tqdm(records_list, desc="Inference", unit="utt")
                last_condition = None
                for record in progress:
                    condition = str(record.get("augmentation_condition_id") or "clean")
                    if condition != last_condition:
                        progress.set_postfix_str(f"condition={condition}")
                        logger.info("Inference condition: %s", condition)
                        last_condition = condition
                    attempted_count += 1
                    try:
                        with augmentor.materialized_record(record) as inference_record:
                            prediction = self.predict_one(inference_record, run_config, logger)
                    except Exception as exc:
                        failed_count += 1
                        logger.exception(
                            "Inference failed for %s: %s",
                            record.get("recording_id"),
                            exc,
                        )
                        continue
                    if prediction is None:
                        skipped_count += 1
                        continue
                    row = prediction.to_jsonable()
                    line = _json_line(row)
                    handle.write(line)
                    condition_handle = condition_handles.get(condition)
                    if condition_handle is None:
                        condition_dir = predictions_dir / _safe_condition_folder(condition)
                        condition_dir.mkdir(parents=True, exist_ok=True)
                        condition_handle = (condition_dir / "utterances.jsonl").open(
                            "w",
                            encoding="utf-8",
                        )
                        condition_handles[condition] = condition_handle
                    condition_handle.write(line)
                    condition_prediction_counts[condition] = (
                        condition_prediction_counts.get(condition, 0) + 1
                    )
                    written_count += 1
        finally:
            for condition_handle in condition_handles.values():
                condition_handle.close()
            augmentor.cleanup()
        run_duration_sec = time.perf_counter() - started_at

        result = RunnerResult(
            predictions_path=predictions_path,
            attempted_count=attempted_count,
            written_count=written_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            run_duration_sec=run_duration_sec,
        )
        self.after_run(result, predictions_dir, run_config, logger)
        write_json(
            predictions_dir / "runner_summary.json",
            {
                "runner": self.name,
                "attempted_count": attempted_count,
                "written_count": written_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
                "run_duration_sec": run_duration_sec,
                "predictions_path": predictions_path.name,
                "condition_prediction_counts": condition_prediction_counts,
            },
        )
        return result

    def before_run(
        self,
        records: list[dict[str, object]],
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        """Optional setup hook before predictions are written."""

    def after_run(
        self,
        result: RunnerResult,
        predictions_dir: Path,
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> None:
        """Optional cleanup hook after predictions are written."""

    @abstractmethod
    def predict_one(
        self,
        record: dict[str, object],
        run_config: dict[str, object],
        logger: logging.Logger,
    ) -> UtterancePrediction | None:
        """Return one standardized prediction or ``None`` if output is missing."""


def prediction_from_record(record: dict[str, object], text: str) -> UtterancePrediction:
    """Build a standardized utterance prediction from a selected metadata row."""

    return UtterancePrediction(
        recording_id=str(record["recording_id"]),
        utt_id=str(record.get("utt_id") or record.get("utterance_id") or record["recording_id"]),
        start_sec=_optional_float(record.get("start_sec")),
        end_sec=_optional_float(record.get("end_sec")),
        speaker_label=_optional_string(record.get("speaker_label")),
        text=text,
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _json_line(row: dict[str, object]) -> str:
    import json

    return json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"


def _safe_condition_folder(condition: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in condition)[:120]
