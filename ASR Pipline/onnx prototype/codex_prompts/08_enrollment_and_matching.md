# Prompt 08 — implement enrollment storage and speaker matching

You are working in the existing Evaluation Tool repository.

## Goal
Make the pipeline capable of known-speaker assignment with Unknown fallback.

## Implement in `app/onnx_pipeline/speaker/store.py`
Create an enrollment store that can:
- add one embedding for a speaker
- add multiple embeddings for a speaker
- persist to disk
- load from disk
- return a gallery of speaker -> embeddings

Use a simple, transparent format. Favor clarity over cleverness.

## Implement in `app/onnx_pipeline/matching.py`
Add:
- cosine similarity
- best-match selection
- second-best score tracking
- threshold + margin-based acceptance logic
- Unknown fallback logic

## Update `app/onnx_pipeline/pipeline.py`
When a speaker backend and enrollment store are configured:
- compute the embedding for the current record
- match it against enrolled speakers
- set `speaker_label` to the accepted speaker
- otherwise set `speaker_label` to the configured Unknown label

## Constraints
- wrong known-speaker label is worse than Unknown
- keep the threshold config-driven
- do not add diarization here

## Acceptance criteria
- tests cover:
  - exact match
  - below-threshold rejection
  - close-second-best rejection
- pipeline can emit known speaker labels and Unknown
