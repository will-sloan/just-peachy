# Prompt 10 — add conservative VAD trimming

You are working in the existing Evaluation Tool repository.

## Goal
Use VAD to trim silence and optionally define subsegments, but without destabilizing record-level evaluation.

## Implement
In:
- `app/onnx_pipeline/vad/silero_onnx.py`

Create a VAD backend wrapper that:
- loads the configured Silero model / runtime path
- returns speech timestamps or a trimmed audio region
- can operate conservatively for record-level processing

## Update
- `app/onnx_pipeline/pipeline.py`

Recommended v1 behavior:
- trim leading / trailing silence
- do not aggressively fragment utterance-level input unless explicitly configured

## Constraints
- VAD is optional by config
- do not turn VAD into generic diarization
- do not break existing record-level processing assumptions

## Acceptance criteria
- VAD can be enabled / disabled
- pipeline still works with VAD off
- with VAD on, silence trimming is applied before ASR
