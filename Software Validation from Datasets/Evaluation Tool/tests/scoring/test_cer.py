from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import pytest

from app.dataset_registry.registry import get_dataset
from app.scoring.scorer import score_run
from app.scoring.wer import compute_cer
from app.utils.json_utils import write_jsonl


def test_compute_cer_excludes_whitespace() -> None:
    result = compute_cer("hello world", "hello word")

    assert result.reference_chars == 10
    assert result.hypothesis_chars == 9
    assert result.errors == 1
    assert result.deletions == 1
    assert result.cer == pytest.approx(0.1)


def test_score_run_writes_cer_metrics(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    predictions_dir = run_dir / "predictions"
    predictions_dir.mkdir(parents=True)
    write_jsonl(
        predictions_dir / "utterances.jsonl",
        [
            {
                "recording_id": "rec-001",
                "utt_id": "utt-001",
                "start_sec": 0.0,
                "end_sec": 1.0,
                "speaker_label": "speaker-a",
                "text": "hello word",
            }
        ],
    )
    records = [
        {
            "recording_id": "rec-001",
            "utt_id": "utt-001",
            "start_sec": 0.0,
            "end_sec": 1.0,
            "speaker_label": "speaker-a",
            "reference_text": "hello world",
            "audio_exists": True,
        }
    ]

    result = score_run(run_dir, get_dataset("cmu_arctic"), records, logging.getLogger(__name__))
    per_recording = pd.read_csv(result.per_recording_metrics_path)

    assert result.aggregate_metrics["aggregate_wer"] == pytest.approx(0.5)
    assert result.aggregate_metrics["aggregate_cer"] == pytest.approx(0.1)
    assert per_recording.loc[0, "cer"] == pytest.approx(0.1)
    assert int(per_recording.loc[0, "char_errors"]) == 1
