# Prompt 01 — scaffold ONNX pipeline package

You are working in the existing Evaluation Tool repository.

## Goal
Create a new package for the ONNX-first inference pipeline without changing the current scoring/reporting logic.

## Create this structure
- `app/onnx_pipeline/__init__.py`
- `app/onnx_pipeline/contracts.py`
- `app/onnx_pipeline/config.py`
- `app/onnx_pipeline/interfaces.py`
- `app/onnx_pipeline/audio.py`
- `app/onnx_pipeline/matching.py`
- `app/onnx_pipeline/pipeline.py`
- `app/onnx_pipeline/factory.py`
- `app/onnx_pipeline/adapters/__init__.py`
- `app/onnx_pipeline/adapters/evaluation_tool.py`
- `app/onnx_pipeline/asr/__init__.py`
- `app/onnx_pipeline/asr/backends/__init__.py`
- `app/onnx_pipeline/asr/backends/sherpa_whisper.py`
- `app/onnx_pipeline/asr/backends/sherpa_moonshine.py`
- `app/onnx_pipeline/speaker/__init__.py`
- `app/onnx_pipeline/speaker/store.py`
- `app/onnx_pipeline/speaker/backends/__init__.py`
- `app/onnx_pipeline/speaker/backends/wespeaker_campplus_onnx.py`
- `app/onnx_pipeline/vad/__init__.py`
- `app/onnx_pipeline/vad/silero_onnx.py`
- `app/onnx_pipeline/text/__init__.py`
- `app/onnx_pipeline/text/sherpa_punctuation.py`
- `configs/onnx_pipeline.desktop.example.yaml`
- `configs/onnx_pipeline.pi.example.yaml`
- `tests/test_contracts.py`
- `tests/test_matching.py`
- `tests/test_evaluation_adapter.py`

## Requirements
- Add module docstrings explaining the intended role of each file.
- Backend files may contain TODO placeholders, but the interfaces and imports must be coherent.
- Use type hints everywhere reasonable.
- Keep imports lightweight.

## Constraints
- Do not wire into `external_stub.py` yet.
- Do not add real model-loading code yet unless it is trivial.
- Do not modify scoring / report code.

## Acceptance criteria
- `pytest -q tests/test_contracts.py tests/test_matching.py tests/test_evaluation_adapter.py` passes
- importing `app.onnx_pipeline` does not raise errors
- the example YAML configs exist
