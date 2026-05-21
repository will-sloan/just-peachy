# M4 External Runner Smoke Bridge Report

## Milestone

M4 - External Runner Smoke Bridge with Dummy Pipeline

## Files Changed

- `app/model_runner/external_stub.py`
- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/dummy_components.py`
- `tests/model_runner/test_external_stub_bridge.py`
- `reports/milestones/M4_external_bridge_report.md`

## Summary

M4 wires `ExternalStubRunner.predict_one()` through a small modular
`PipelineRunner` that uses deterministic dummy components. The dummy pipeline
does not load models, run ASR, perform diarization, compute embeddings, export
to ExecuTorch, or apply hardware acceleration.

`PipelineRunner` accepts one selected metadata record, builds the existing
model-free `EvaluationRecord`, reads `record["inference_audio_path"]` through a
metadata-only dummy audio reader, creates a stable dummy transcript, returns no
speaker label, and maps the result back to the existing `UtterancePrediction`
schema expected by the evaluator.

## Runner Contract Preservation

- `ExternalStubRunner` keeps the existing `predict_one(record, run_config,
  logger)` public contract.
- The pipeline requires and uses `record["inference_audio_path"]`.
- `recording_id` and `utt_id` are preserved by the pipeline output and returned
  `UtterancePrediction`.
- `start_sec` and `end_sec` are preserved when present.
- `speaker_label=None` is emitted by the dummy speaker labeler, which is
  compatible with the existing `UtterancePrediction` schema.
- `ModelRunner.run_batch()` still owns JSONL writing to
  `predictions/utterances.jsonl`.
- No scorer, plot generation, report generator, CLI, GUI, dataset registry, or
  normalized metadata code was changed.

## Test Commands

Run from `Software Validation from Datasets/Evaluation Tool`:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py
```

Result:

```text
4 passed in 9.57s
```

## Smoke Command

Run from `Software Validation from Datasets/Evaluation Tool`:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --runner external-stub --run-name m4_external_bridge_smoke
```

Result:

```text
ERROR: Could not find project root. Run from inside the project, or pass --project-root.
```

## Smoke Artifacts

- `predictions/utterances.jsonl` created: No.
- JSONL validation result: Not applicable; the smoke command failed before a run
  folder or prediction file was created.
- Scoring completed: No.
- Reporting completed: No.

Focused tests did validate the bridge JSONL path by running
`ExternalStubRunner.run_batch()` against a temporary run folder, reading the
temporary `predictions/utterances.jsonl` through the existing
`read_utterance_predictions()` schema reader, and confirming identity/timing
preservation plus deterministic dummy text.

## Blockers

The local project root is missing the `Raw Datasets (Not formatted)` directory.
`app.utils.paths.find_project_root()` requires both `Normalized Metadata` and
`Raw Datasets (Not formatted)`, so the CLI smoke command fails before dataset
selection, inference, scoring, or reporting.

## Incomplete By Design

Real ASR, VAD, speaker diarization, speaker embeddings, model adapters, model
loading, Raspberry Pi optimization, ExecuTorch export, and hardware
acceleration are intentionally out of scope for M4.
