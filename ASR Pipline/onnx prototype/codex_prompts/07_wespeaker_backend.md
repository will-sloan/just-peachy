# Prompt 07 — implement the WeSpeaker CAM++ ONNX speaker embedding backend

You are working in the existing Evaluation Tool repository.

## Goal
Add a real ONNX speaker embedding backend for enrollment and matching.

## Implement
In:
- `app/onnx_pipeline/speaker/backends/wespeaker_campplus_onnx.py`

Create a backend class that:
- loads a WeSpeaker CAM++ ONNX model with ONNX Runtime
- validates input/output signatures defensively
- exposes `embed(audio: np.ndarray, sample_rate: int) -> np.ndarray`

## Requirements
- keep model loading separate from matching logic
- isolate preprocessing assumptions
- document any expected sample rate or feature frontend assumptions
- raise clear errors if the ONNX model shape does not match expectations

## Also update
- `app/onnx_pipeline/factory.py`
- tests for configuration / failure behavior

## Constraints
- do not implement enrollment storage here
- do not hard-code thresholds here
- do not couple this backend to Evaluation Tool record dicts

## Acceptance criteria
- backend can be instantiated independently
- backend exposes a clear embedding method
- pipeline can be constructed with the backend, even if the enrollment store is still empty
