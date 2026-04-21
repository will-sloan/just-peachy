# External Runner Integration Prompt

Use this when handing the inference side to another developer.

The evaluator will call a model runner with one selected metadata row at a time.
The row includes:

- `recording_id`
- `utt_id`
- `audio_path_resolved`
- `inference_audio_path` (use this for model input; it points to source audio or a temporary augmented WAV)
- `audio_path_project_relative`
- `source_recording_id` for augmented runs
- `augmentation_condition_id`
- `augmentation_mode`
- `rir_label`
- `noise_type`
- `snr_db`
- `start_sec`
- `end_sec`
- `speaker_label`
- `reference_text` for simulation and scoring only

The runner must write `predictions/utterances.jsonl`. Each line must contain:

```json
{
  "recording_id": "string",
  "utt_id": "string",
  "start_sec": 0.0,
  "end_sec": 1.23,
  "speaker_label": "speaker-or-null",
  "text": "predicted transcript"
}
```

Optional future files:

- `predictions/words.jsonl`
- `predictions/segments.rttm`

To integrate a real ASR system, replace `ExternalStubRunner.predict_one()` in
`app/model_runner/external_stub.py` with a call to that system. Use
`record["inference_audio_path"]` as the audio input. During augmented runs this
path is a temporary WAV that exists for the duration of the call.
