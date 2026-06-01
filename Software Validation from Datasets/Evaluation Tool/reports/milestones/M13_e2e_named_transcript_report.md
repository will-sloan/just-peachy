# M13 - End-to-End Named Transcript Pipeline

## High-Level Summary

M13 wires the Evaluation Tool external runner to the modular inference pipeline:
audio loading, VAD, segmentation, ASR, speaker embedding, speaker matching, and
transcript assembly now run behind `ExternalStubRunner` and still emit the
required `predictions/utterances.jsonl` contract.

The default M13 config is offline-safe. It uses real audio loading, energy VAD,
VAD chunking, no-op ASR text, no-op speaker embedding, and no-op speaker
matching. This proves the product pipeline and evaluator contract without
requiring unavailable model assets or downloads.

## Files Changed

- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/transcript/__init__.py`
- `app/inference_pipeline/transcript/assembler.py`
- `app/inference_pipeline/runtime/stats.py`
- `app/inference_pipeline/contracts.py`
- `app/model_runner/external_stub.py`
- `configs/inference/e2e_named_transcript.yaml`
- `tests/inference_pipeline/test_pipeline_e2e.py`
- `tests/model_runner/test_external_stub_bridge.py`
- `reports/milestones/M13_e2e_named_transcript_report.md`

## What Changed

- Added `PipelineRunner.predict(record, config) -> PipelineOutput`.
- Kept `PipelineRunner.run_one(...)` as the compatibility wrapper used by
  existing bridge tests.
- Added transcript assembly that sorts segment outputs chronologically and
  removes duplicate boundary text when chunks overlap or repeat.
- Added per-record diagnostics in `predictions/diagnostics.jsonl`.
- Added runtime diagnostics with total runtime, real-time factor, and per-stage
  timing for audio load, VAD, ASR, speaker, and postprocess.
- Updated `ExternalStubRunner` to lazily build the M13 pipeline from
  `configs/inference/e2e_named_transcript.yaml` when no test pipeline is
  injected.
- Extended `PipelineOutput` with optional diagnostics while preserving
  `to_utterance_prediction_row()` exactly.

## Runner Contract

The evaluator contract remains unchanged:

- The runner receives one selected metadata row at a time.
- The pipeline reads `record["inference_audio_path"]` after runtime
  materialization.
- `recording_id` and `utt_id` are preserved exactly.
- `start_sec` and `end_sec` are preserved when present.
- The evaluator-compatible file remains `predictions/utterances.jsonl`.

Diagnostics are written separately to `predictions/diagnostics.jsonl`, so the
scorer continues to consume only the required prediction rows.

## Diagnostics Written

Each diagnostics row includes:

- segment list
- segment ASR predictions
- speaker decisions
- raw ASR text
- normalized ASR text
- assembled text
- chronological ordering violation count
- segment overlap violation count
- total pipeline runtime
- pipeline real-time factor
- per-stage runtime breakdown

## Tests Run

```bash
cd /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets/Evaluation\ Tool
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_pipeline_e2e.py
```

Result: `2 passed`.

```bash
cd /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets/Evaluation\ Tool
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_pipeline_e2e.py tests/model_runner/test_external_stub_bridge.py tests/inference_pipeline/test_asr_interface.py tests/inference_pipeline/test_vad.py tests/inference_pipeline/test_segmentation.py
```

Result: `46 passed, 1 warning`.

```bash
cd /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets/Evaluation\ Tool
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py tests/inference_pipeline/test_contracts.py
```

Result: `21 passed`.

## Smoke Run

```bash
cd /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets/Evaluation\ Tool
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --project-root "/Users/billy/Documents/just-peachy/Software Validation from Datasets" --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name m13_e2e_smoke
```

Result:

- Run folder: `runs/20260601_131900_cmu_arctic_full_m13_e2e_smoke`
- Predictions: `1`
- Failed: `0`
- Missing predictions: `0`
- Aggregate WER: `1.0`
- Speaker label accuracy: `0.0`
- Unknown rate: `1.0`
- False known-speaker assignment rate: `0.0`
- Pipeline RTF from diagnostics: approximately `0.0011`
- Per-stage timing was written under
  `predictions/diagnostics.jsonl`.

The smoke command emitted sandbox/environment warnings from Arrow CPU probing
and Matplotlib cache setup, but the full run completed scoring and reporting.

## Remaining Incomplete Work

- The M13 default config intentionally uses no-op ASR and no-op speaker
  matching because local production model assets are not assumed available and
  downloads remain disabled.
- CER is available in inference pipeline metric helpers, but the existing full
  run scorer currently reports WER, not CER. The scorer was not changed because
  this milestone is scoped to the inference runner contract.
- Real named-speaker assignment requires an enabled speaker embedding model and
  an enrollment database with matching model IDs.
- Hardware optimization for Raspberry Pi, ExecuTorch, or custom accelerators is
  left for later milestones; the code path is kept modular and PyTorch-native.
