"""Read and write standardized prediction JSONL files."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.prediction_io.schema import (
    UTTERANCE_REQUIRED_FIELDS,
    WORD_REQUIRED_FIELDS,
    UtterancePrediction,
    WordPrediction,
)
from app.utils.json_utils import read_jsonl, write_jsonl


def write_utterance_predictions(
    path: Path,
    predictions: Iterable[UtterancePrediction | dict[str, object]],
) -> int:
    """Write ``utterances.jsonl`` predictions."""

    rows: list[dict[str, object]] = []
    for prediction in predictions:
        if isinstance(prediction, UtterancePrediction):
            row = prediction.to_jsonable()
        else:
            row = dict(prediction)
        rows.append(row)
    return write_jsonl(path, rows)


def read_utterance_predictions(path: Path) -> list[dict[str, object]]:
    """Read and lightly validate ``utterances.jsonl`` predictions."""

    rows = list(read_jsonl(path))
    missing_messages: list[str] = []
    for index, row in enumerate(rows, start=1):
        missing = [field for field in UTTERANCE_REQUIRED_FIELDS if field not in row]
        if missing:
            missing_messages.append(f"line {index}: missing {', '.join(missing)}")
    if missing_messages:
        joined = "; ".join(missing_messages[:10])
        raise ValueError(f"Invalid utterances.jsonl: {joined}")
    return rows


def write_word_predictions(
    path: Path,
    predictions: Iterable[WordPrediction | dict[str, object]],
) -> int:
    """Write optional ``words.jsonl`` predictions."""

    rows: list[dict[str, object]] = []
    for prediction in predictions:
        if isinstance(prediction, WordPrediction):
            row = prediction.to_jsonable()
        else:
            row = dict(prediction)
        rows.append(row)
    return write_jsonl(path, rows)


def read_word_predictions(path: Path) -> list[dict[str, object]]:
    """Read and lightly validate optional ``words.jsonl`` predictions."""

    if not path.exists():
        return []
    rows = list(read_jsonl(path))
    missing_messages: list[str] = []
    for index, row in enumerate(rows, start=1):
        missing = [field for field in WORD_REQUIRED_FIELDS if field not in row]
        if missing:
            missing_messages.append(f"line {index}: missing {', '.join(missing)}")
    if missing_messages:
        joined = "; ".join(missing_messages[:10])
        raise ValueError(f"Invalid words.jsonl: {joined}")
    return rows


def prediction_files_present(predictions_dir: Path) -> dict[str, bool]:
    """Report which standard prediction contract files are present."""

    return {
        "utterances.jsonl": (predictions_dir / "utterances.jsonl").exists(),
        "words.jsonl": (predictions_dir / "words.jsonl").exists(),
        "segments.rttm": (predictions_dir / "segments.rttm").exists(),
    }
