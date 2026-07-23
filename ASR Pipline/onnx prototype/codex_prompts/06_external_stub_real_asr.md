# Prompt 06 — connect real ASR into `external_stub.py`

You are working in the existing Evaluation Tool repository.

## Goal
Replace the dummy path with real transcription through the ONNX pipeline.

## Task
Update:
- `app/model_runner/external_stub.py`

so that:
- it constructs or retrieves a cached ONNX pipeline instance
- converts the incoming record dict to `InferenceRecord`
- runs the pipeline
- returns the correct prediction object / dict for the existing runner flow

## Required behavior
- use `record["inference_audio_path"]`
- preserve `recording_id`
- preserve `utt_id`
- preserve `start_sec`
- preserve `end_sec`
- return `speaker_label=None` for now unless already implemented
- emit real transcript text

## Important
If `start_sec` / `end_sec` exist:
- crop correctly before transcription
- do not ignore them for segment-based datasets

## Constraints
- Do not touch scoring/reporting code
- Do not touch dataset registry logic
- Do not change JSONL schema fields

## Acceptance criteria
- a tiny `cmu_arctic` run with `external-stub` produces real ASR text
- scoring still works
- model is not loaded per record
- there is no ID drift
