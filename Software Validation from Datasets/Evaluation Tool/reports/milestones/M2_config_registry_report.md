# M2 Configuration and Registry Report

## Summary

M2 added a YAML-backed configuration system and lightweight component registry
for the future inference pipeline. It did not implement VAD, ASR, segmentation,
speaker embedding, speaker matching, model loading, GPU execution, Raspberry Pi
optimization, ExecuTorch export, or hardware integration.

Changed files:

- `app/inference_pipeline/config.py`
- `app/inference_pipeline/registry.py`
- `app/inference_pipeline/__init__.py`
- `configs/inference/base.yaml`
- `configs/inference/cpu_smoke.yaml`
- `configs/inference/desktop_gpu.yaml`
- `configs/inference/raspberry_pi_future.yaml`
- `configs/inference/components/vad/silero.yaml`
- `configs/inference/components/asr/whisper_tiny.yaml`
- `configs/inference/components/speaker_embedding/speechbrain_ecapa.yaml`
- `tests/inference_pipeline/test_config_registry.py`
- `docs/inference_pipeline/MILESTONE_LEDGER.md`
- `reports/milestones/M2_config_registry_report.md`

## Config Loading

`PipelineConfig.from_yaml_path(...)` loads a top-level YAML file using
`yaml.safe_load`. Component choices can be written inline or referenced by
relative YAML path. Relative component references are resolved first from the
top-level config file directory, then from the Evaluation Tool root.

The config object includes:

- component choices for VAD, segmentation, ASR, speaker embedding, and speaker
  matching
- runtime options such as device, sample rate, batch size, thread count,
  precision, dry-run mode, download policy, and cache directory
- metadata such as config name, profile, notes, and future-profile marker

## Registry Lookup

`registry.py` maps component names to lightweight adapter placeholder classes.
Registry lookup returns adapter classes only; it does not instantiate adapters
or load model weights.

Registered names include:

- `no_op_vad`
- `silero_vad`
- `no_op_segmentation`
- `no_op_asr`
- `whisper_tiny`
- `no_op_speaker_embedding`
- `speechbrain_ecapa`
- `no_op_speaker_matching`

Unknown enabled component names fail with `UnknownComponentError`. Disabled
components are represented with `DisabledComponentAdapter` in dry-run output.

## Dry-Run Validation

`dry_run_config(config)` returns JSON-safe selected component details,
including slot, name, enabled state, adapter class name, requested adapter, and
params. It also includes runtime options. It does not import torch, numpy,
transformers, SpeechBrain, Whisper, Silero, datasets, or model assets.

## Validation Commands

Run from `Software Validation from Datasets\Evaluation Tool`:

```powershell
& '..\..\myenv\Scripts\python.exe' -m pytest tests\inference_pipeline\test_config_registry.py
& '..\..\myenv\Scripts\python.exe' -m pytest tests\inference_pipeline\test_contracts.py
& '..\..\myenv\Scripts\python.exe' -m pytest tests\test_m0_docs.py
```

## Test Results

- `tests\inference_pipeline\test_config_registry.py`: 10 passed.
- `tests\inference_pipeline\test_contracts.py`: 11 passed.
- `tests\test_m0_docs.py`: 5 passed.

## Protected-Path Safety Confirmation

Based on file-scope inspection and the target file list, M2 edits were limited
to `app/inference_pipeline/config.py`, `app/inference_pipeline/registry.py`,
`app/inference_pipeline/__init__.py`, `configs/inference/**`,
`tests/inference_pipeline/test_config_registry.py`,
`docs/inference_pipeline/MILESTONE_LEDGER.md`, and this report.

No M2 edits were made to:

- `app/model_runner/`
- `app/prediction_io/`
- `app/scoring/`
- `app/dataset_registry/`
- `app/gui/`
- `app/cli/`
- `app/plotting/`
- `app/reporting/`
- normalized metadata loaders

## Open Issues

None known.
