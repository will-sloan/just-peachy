# M14 Real Pipeline Completion Report

## Milestone

M14 - Real Pipeline Completion

## Summary

M14 keeps the M13 Evaluation Tool contract intact while making the end-to-end
pipeline practically runnable with local real model assets. The external-stub
runner can now select an inference config from the CLI, the new real-local
profile uses Whisper tiny and SpeechBrain ECAPA with downloads disabled, and
scoring now emits CER alongside existing WER metrics.

The default `e2e_named_transcript.yaml` remains smoke-safe. Real-model execution
is opt-in through `configs/inference/e2e_real_local.yaml`.

## Files Changed

- `app/cli/main.py`
- `app/inference_pipeline/asr/whisper_adapter.py`
- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/speaker_embedding/speechbrain_adapter.py`
- `app/model_runner/external_stub.py`
- `app/scoring/wer.py`
- `app/scoring/scorer.py`
- `configs/inference/e2e_real_local.yaml`
- `tests/inference_pipeline/test_pipeline_e2e.py`
- `tests/model_runner/test_external_stub_bridge.py`
- `tests/scoring/test_cer.py`
- `reports/milestones/M14_real_pipeline_completion_report.md`

## Behavior Implemented

- Added `--inference-config` for external-stub runs.
- Added real local inference profile using:
  - energy VAD
  - VAD chunking
  - local Whisper tiny ASR
  - local SpeechBrain ECAPA speaker embeddings
  - cosine threshold speaker matching
- Resolved component-reference YAML files when pipeline configs are loaded at
  runtime.
- Preserved evaluator predictions as `predictions/utterances.jsonl` with only:
  `recording_id`, `utt_id`, `start_sec`, `end_sec`, `speaker_label`, `text`.
- Preserved exact `recording_id`, `utt_id`, `start_sec`, and `end_sec`.
- Kept diagnostics separate in `pipeline_diagnostics.jsonl` and
  `pipeline_diagnostics_summary.json`.
- Added diagnostics summary fields for speaker label accuracy, unknown rate,
  false known-speaker assignment rate, thresholds, margins, RTF, and per-stage
  runtime.
- Added CER counts and aggregate CER to scoring outputs.

## Local Assets

Found:

- Whisper package in `.venv`
- Whisper tiny asset: `/Users/billy/Documents/just-peachy/models/cache/whisper/tiny.pt`
- SpeechBrain package in `.venv`
- SpeechBrain ECAPA assets:
  `Evaluation Tool/models/cache/speechbrain/spkrec-ecapa-voxceleb/`

Missing or incomplete:

- Default enrollment DB exists but is empty:
  `artifacts/enrollment/enrollment_db.json`
- Real known-speaker assignment is blocked until enrollment samples are added.

Enrollment command path:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/enroll_speaker.py \
  --display-name Alice \
  --model-id speechbrain_ecapa@1.1.0 \
  --backend speechbrain \
  --audio /path/to/alice.wav \
  --db artifacts/enrollment/enrollment_db.json \
  --min-duration-sec 0.75
```

## Run Command

Real local pipeline:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full \
  --project-root "/Users/billy/Documents/just-peachy/Software Validation from Datasets" \
  --dataset cmu_arctic \
  --max-recordings 1 \
  --runner external-stub \
  --augmentation none \
  --inference-config configs/inference/e2e_real_local.yaml \
  --run-name m14_real_pipeline_config_smoke_v2
```

Smoke-safe default:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full \
  --project-root "/Users/billy/Documents/just-peachy/Software Validation from Datasets" \
  --dataset cmu_arctic \
  --max-recordings 1 \
  --runner external-stub \
  --augmentation none \
  --run-name m14_real_pipeline_smoke
```

## Test Results

Commands run from `Software Validation from Datasets/Evaluation Tool`:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_pipeline_e2e.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/scoring/test_cer.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests -q -k "inference_pipeline or external_stub or scoring or e2e"
/Users/billy/Documents/just-peachy/.venv/bin/python -m compileall app/inference_pipeline app/model_runner app/scoring scripts
git diff --check
```

Results:

- Pipeline focused tests: `8 passed`
- External stub bridge tests: `5 passed`
- CER tests: `2 passed`
- Inference pipeline suite: `121 passed, 1 warning`
- Selected cross-suite tests: `128 passed, 8 deselected, 1 warning`
- Compileall: passed
- `git diff --check`: passed

## Smoke Results

Smoke-safe default run:

- Run folder: `runs/20260531_134950_cmu_arctic_full_m14_real_pipeline_smoke`
- Predictions: `1`
- Failed: `0`
- Missing: `0`
- Aggregate WER: `1.0000`
- Aggregate CER: `0.7297`
- Unknown rate: `1.0`
- Mean pipeline RTF: `0.0011519895448427735`

Real local config run:

- Run folder: `runs/20260531_135407_cmu_arctic_full_m14_real_pipeline_config_smoke_v2`
- Predictions: `1`
- Failed: `0`
- Missing: `0`
- Aggregate WER: `0.5000`
- Aggregate CER: `0.3243`
- Speaker label accuracy: `0.0`
- Unknown rate: `1.0`
- False known-speaker assignment rate: `0.0`
- Chronological ordering violations: `0`
- Pipeline RTF: `0.22537198493990465`
- Stage runtime seconds:
  - audio_load: `0.0009139999892795458`
  - vad: `0.003696540996315889`
  - segmentation: `0.0000738340022508055`
  - asr: `0.607175583994831`
  - speaker_embedding: `0.26188879199617077`
  - speaker_matching: `0.00022537499899044633`
  - postprocess: `0.0000752909982111305`
- Speaker matching threshold: `0.82`
- Speaker matching min margin: `0.05`

The smoke commands emitted PyArrow CPU-probing warnings and Matplotlib cache
fallback warnings in the sandbox, but both exited successfully and produced
scoring plus reports.

## Calibration

No real enrolled speaker samples were available in the default DB, so M14 ran a
synthetic calibration smoke through the existing calibration module:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m app.inference_pipeline.speaker_matching.thresholds \
  --enrollment-db /private/tmp/m14_speaker_matching_calibration/enrollment_db.json \
  --samples-jsonl /private/tmp/m14_speaker_matching_calibration/samples.jsonl \
  --report /private/tmp/m14_speaker_matching_calibration/threshold_calibration_m14_synthetic.md \
  --threshold-min 0.5 \
  --threshold-max 0.95 \
  --threshold-step 0.15 \
  --min-margin 0.05 \
  --scoring-mode centroid \
  --unknown-label Unknown \
  --max-false-known-rate 0.0 \
  --run-id m14_synthetic_calibration \
  --runtime-model-id m14_synthetic_speaker_embedder@1
```

Result:

- Recommended threshold: `0.95`
- Report: `/private/tmp/m14_speaker_matching_calibration/threshold_calibration_m14_synthetic.md`

## Remaining Work

- Build a real enrollment DB with local WAV samples before expecting named
  known-speaker assignment.
- Calibrate the production threshold against real enrollment/query embeddings.
- Consider setting `MPLCONFIGDIR` to a writable project temp folder to suppress
  Matplotlib cache warnings during smoke runs.
