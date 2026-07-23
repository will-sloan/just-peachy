# Prompt 02 — implement contracts and config

You are working in the existing Evaluation Tool repository.

## Goal
Implement the stable internal data contracts and YAML config loading for the ONNX pipeline.

## Implement in `app/onnx_pipeline/contracts.py`
Define typed dataclasses for:
- `InferenceRecord`
- `SpeechSegment`
- `SpeakerMatch`
- `UtterancePredictionData`

Requirements:
- `InferenceRecord` must be able to represent:
  - `recording_id`
  - `utt_id`
  - `inference_audio_path`
  - `start_sec`
  - `end_sec`
  - optional reference text / speaker label
  - free-form metadata
- `UtterancePredictionData` must map cleanly to the Evaluation Tool JSONL contract
- include small helper methods if useful, but keep it simple

## Implement in `app/onnx_pipeline/config.py`
Define dataclasses for:
- runtime config
- VAD config
- ASR config
- speaker config
- punctuation config
- enrollment config
- thresholds
- root pipeline config

Add:
- `load_pipeline_config(path: str | Path) -> PipelineConfig`

## Update tests
Add tests that:
- instantiate config objects
- load example YAML
- serialize / validate prediction contract fields

## Constraints
- No model code yet
- No hard-coded Windows-only paths
- Keep the config schema explicit and readable

## Acceptance criteria
- tests pass
- the YAML example files round-trip through `load_pipeline_config`
- prediction dataclass contains exactly the fields needed to emit `utterances.jsonl`
