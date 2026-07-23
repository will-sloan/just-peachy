# Prompt 05 — implement the sherpa-onnx Whisper backend

You are working in the existing Evaluation Tool repository.

## Goal
Add the first real ASR backend using sherpa-onnx and a Whisper ONNX model family.

## Implement
In:
- `app/onnx_pipeline/asr/backends/sherpa_whisper.py`

Create a backend class that:
- reads its config from `AsrConfig`
- validates required model paths
- constructs the sherpa-onnx recognizer once
- exposes `transcribe(audio: np.ndarray, sample_rate: int) -> str`

## Requirements
- handle the model session / recognizer lifecycle once
- keep the backend isolated from Evaluation Tool details
- make configuration explicit for model paths and decoding options
- include clear errors when model files are missing

## Also update
- `app/onnx_pipeline/factory.py` to build this backend when configured
- `tests/` with at least one non-heavy unit test that validates configuration / failure behavior

## Constraints
- Do not implement alternative ASR backends yet
- Do not change the prediction contract
- Do not add model download logic inside production code

## Acceptance criteria
- pipeline can be constructed with `SherpaWhisperBackend`
- missing-model error messages are clear
- backend is reusable across multiple records
- code is ready for the next prompt to wire into `external_stub.py`
