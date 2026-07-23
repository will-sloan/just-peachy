# target_patch

This folder mirrors the **intended placement** inside the existing Evaluation Tool repo.

## Intended destination

Copy these files into:

`Evaluation Tool/`

so that you end up with:

- `Evaluation Tool/app/onnx_pipeline/...`
- `Evaluation Tool/app/model_runner/external_stub_example.py`
- `Evaluation Tool/configs/...`
- `Evaluation Tool/scripts/...`
- `Evaluation Tool/tests/...`

## What is implemented here

### Real, reusable code
- config schema
- dataclasses / contracts
- audio loading / crop / resample
- speaker matching logic
- enrollment store
- Evaluation Tool record adapter
- pipeline orchestration skeleton
- ONNX model inspection / validation helper scripts
- tests for non-model pieces

### Deliberately left as backend wrappers / TODO
- sherpa-onnx Whisper runtime wrapper
- sherpa-onnx Moonshine runtime wrapper
- WeSpeaker CAM++ runtime wrapper
- Silero VAD runtime wrapper
- sherpa-onnx punctuation wrapper

Those pieces are where Codex should finish the implementation using the prompt set in `../codex_prompts/`.

## Why this split is intentional

The generic orchestration code is stable and should be owned by your repo.
The model-specific wrappers are the most likely to change based on:
- model family choice
- deployment target
- library API changes
- benchmark outcomes

## Required invariants

- `record["inference_audio_path"]` is the inference input
- `(recording_id, utt_id)` must not change
- `start_sec` / `end_sec` must be honored
- models must be loaded once per runner instance, not once per record
