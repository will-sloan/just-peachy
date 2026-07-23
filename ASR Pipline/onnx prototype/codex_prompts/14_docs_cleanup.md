# Prompt 14 — documentation cleanup and handoff polish

You are working in the existing Evaluation Tool repository.

## Goal
Make the ONNX pipeline maintainable for the next engineer.

## Produce / update
- `docs/onnx_pipeline_overview.md`
- `docs/onnx_pipeline_model_inventory.md`
- `docs/onnx_pipeline_known_risks.md`

## Required content
### Overview
- architecture diagram in text form
- module boundaries
- config files
- integration point with `external_stub.py`

### Model inventory
- ASR model family in use
- VAD model in use
- speaker model in use
- punctuation model in use
- where each artifact lives on disk
- who owns updating them

### Known risks
- diarization is not solved
- Raspberry Pi model may differ from desktop model
- thresholds require calibration
- model licenses must be rechecked per artifact
- per-record model loads are forbidden

## Constraints
- do not rewrite previous docs unless necessary
- avoid fluff
- keep docs operational and specific

## Acceptance criteria
- docs exist
- a new engineer could resume the ONNX pipeline work with minimal oral context
