from pathlib import Path

from app.onnx_pipeline.adapters.evaluation_tool import (
    prediction_to_evaluation_dict,
    record_from_evaluation_dict,
)
from app.onnx_pipeline.contracts import UtterancePredictionData


def test_record_adapter_uses_inference_audio_path(tmp_path):
    wav = tmp_path / "audio.wav"
    wav.write_bytes(b"")
    record = {
        "recording_id": "rec-1",
        "utt_id": "utt-1",
        "inference_audio_path": str(wav),
        "start_sec": 1.5,
        "end_sec": 3.0,
        "reference_text": "hello",
        "speaker_label": "spkA",
    }
    adapted = record_from_evaluation_dict(record)
    assert adapted.inference_audio_path == Path(wav)
    assert adapted.start_sec == 1.5
    assert adapted.end_sec == 3.0


def test_prediction_adapter_roundtrip():
    pred = UtterancePredictionData(
        recording_id="rec-1",
        utt_id="utt-1",
        text="hello world",
        speaker_label=None,
        start_sec=0.0,
        end_sec=1.0,
    )
    row = prediction_to_evaluation_dict(pred)
    assert row["recording_id"] == "rec-1"
    assert row["utt_id"] == "utt-1"
    assert row["text"] == "hello world"
