# Prompt 03 — implement audio utilities and Evaluation Tool adapter

You are working in the existing Evaluation Tool repository.

## Goal
Implement the non-model plumbing that turns Evaluation Tool records into internal inference requests.

## Implement in `app/onnx_pipeline/audio.py`
Create utilities to:
- load mono audio from a file path
- preserve float32 output
- crop by `start_sec` / `end_sec`
- resample to a target sample rate
- optionally concatenate kept speech segments later

Implementation guidance:
- use `soundfile`
- use `scipy.signal.resample_poly`
- be explicit about shapes and dtypes
- handle stereo or multi-channel input by deterministic mono reduction

## Implement in `app/onnx_pipeline/adapters/evaluation_tool.py`
Add functions to:
- convert an Evaluation Tool record dict into `InferenceRecord`
- convert `UtterancePredictionData` into the dict / object shape needed by the existing runner layer

Requirements:
- preserve `recording_id`
- preserve `utt_id`
- keep `start_sec` / `end_sec`
- keep `speaker_label` nullable
- do not guess new IDs

## Tests
Add / update tests for:
- cropping behavior
- resampling behavior
- adapter conversion
- round-trip output formatting

## Constraints
- Do not touch `external_stub.py` yet
- Do not touch scoring / report code
- Do not load any model here

## Acceptance criteria
- tests pass
- adapter explicitly uses `inference_audio_path`
- adapter output can be serialized to the expected JSONL fields
