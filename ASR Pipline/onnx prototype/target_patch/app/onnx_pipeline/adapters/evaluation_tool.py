from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..contracts import InferenceRecord, UtterancePredictionData


def record_from_evaluation_dict(record: Mapping[str, Any]) -> InferenceRecord:
    return InferenceRecord(
        recording_id=str(record["recording_id"]),
        utt_id=str(record.get("utt_id") or record["recording_id"]),
        inference_audio_path=Path(record["inference_audio_path"]),
        start_sec=record.get("start_sec"),
        end_sec=record.get("end_sec"),
        source_recording_id=record.get("source_recording_id"),
        reference_text=record.get("reference_text"),
        reference_speaker_label=record.get("speaker_label"),
        metadata={k: v for k, v in record.items() if k not in {
            "recording_id",
            "utt_id",
            "inference_audio_path",
            "start_sec",
            "end_sec",
            "source_recording_id",
            "reference_text",
            "speaker_label",
        }},
    )


def prediction_to_evaluation_dict(prediction: UtterancePredictionData) -> dict[str, Any]:
    return prediction.to_json_dict()
