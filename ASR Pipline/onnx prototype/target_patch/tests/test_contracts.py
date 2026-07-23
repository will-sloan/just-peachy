from app.onnx_pipeline.contracts import InferenceRecord, UtterancePredictionData


def test_prediction_to_json_dict_has_expected_fields(tmp_path):
    pred = UtterancePredictionData(
        recording_id="rec-1",
        utt_id="utt-1",
        start_sec=0.0,
        end_sec=1.0,
        speaker_label=None,
        text="hello",
    )
    row = pred.to_json_dict()
    assert set(row.keys()) == {"recording_id", "utt_id", "start_sec", "end_sec", "speaker_label", "text"}
    assert row["recording_id"] == "rec-1"
    assert row["utt_id"] == "utt-1"


def test_inference_record_accepts_core_fields(tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"")
    rec = InferenceRecord(
        recording_id="r",
        utt_id="u",
        inference_audio_path=wav,
    )
    assert rec.recording_id == "r"
    assert rec.utt_id == "u"
