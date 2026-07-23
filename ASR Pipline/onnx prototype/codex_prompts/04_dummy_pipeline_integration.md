# Prompt 04 — wire a dummy ONNX pipeline into the external runner

You are working in the existing Evaluation Tool repository.

## Goal
Prove that the new ONNX pipeline package can be called through the existing external runner hook before real model code is added.

## Implement in `app/onnx_pipeline/pipeline.py`
Create an `OnnxSpeechPipeline` class that can be constructed with pluggable components:
- ASR engine
- optional VAD engine
- optional speaker embedder
- optional punctuator
- optional enrollment store

For now:
- allow the pipeline to operate with missing components
- if no ASR engine is provided, return placeholder text like `"TODO_ASR"`
- if no speaker embedder / store is provided, return `speaker_label=None`

## Implement in `app/onnx_pipeline/factory.py`
Add a placeholder `build_pipeline_from_config()` that returns a pipeline with no real model backends yet.

## Add example integration file
Create:
- `app/model_runner/external_stub_example.py`

This file should show:
- a cached singleton or `lru_cache` pattern for pipeline construction
- conversion from Evaluation Tool record dict -> `InferenceRecord`
- conversion from `UtterancePredictionData` -> existing prediction schema shape

## Optional
If the repo structure makes it easy, update `external_stub.py` behind a feature flag or clearly marked TODO branch. If not, leave `external_stub.py` unchanged and document the exact patch.

## Constraints
- Do not add real ASR yet
- Do not load any real model yet
- Do not change scoring/reporting

## Acceptance criteria
- a tiny run can execute through the dummy pipeline
- valid `predictions/utterances.jsonl` can still be produced
- the pipeline object is constructed once, not once per record
