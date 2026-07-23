# Prompt 09 — add optional punctuation post-processing

You are working in the existing Evaluation Tool repository.

## Goal
Improve transcript readability without changing the prediction contract.

## Implement
In:
- `app/onnx_pipeline/text/sherpa_punctuation.py`

Create a punctuation backend wrapper that:
- can be enabled / disabled by config
- accepts raw ASR text
- returns punctuated text

## Update
- `app/onnx_pipeline/factory.py`
- `app/onnx_pipeline/pipeline.py`

Pipeline behavior:
- ASR text first
- punctuation only if enabled
- if punctuation backend fails, fail clearly or optionally allow a strict config switch to bypass it

## Constraints
- do not block the whole architecture on punctuation
- do not change JSONL fields
- do not alter speaker logic here

## Acceptance criteria
- punctuation can be toggled by config
- pipeline still works with punctuation disabled
- text is punctuated only after ASR
