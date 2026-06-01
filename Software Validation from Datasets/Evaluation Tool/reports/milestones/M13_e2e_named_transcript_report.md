# M13 End-to-End Named Transcript Pipeline Report

## Milestone

M13 - End-to-End Named Transcript Pipeline

## Summary

M13 wires the existing modular inference components into one Evaluation Tool
pipeline path. `ExternalStubRunner` now invokes `PipelineRunner.predict()` and
returns only the evaluator-compatible utterance fields while writing separate
pipeline diagnostics for debugging.

The smoke-safe default config uses real audio loading, energy VAD, VAD chunking,
no-op ASR text, no-op speaker embedding, and conservative `Unknown` speaker
matching. This avoids model downloads while proving the product path: audio in,
segmented transcript out, valid `predictions/utterances.jsonl` written.

## Files Changed

- `app/inference_pipeline/pipeline.py`
- `app/inference_pipeline/transcript/__init__.py`
- `app/inference_pipeline/transcript/assembler.py`
- `app/inference_pipeline/runtime/stats.py`
- `app/model_runner/external_stub.py`
- `configs/inference/e2e_named_transcript.yaml`
- `tests/inference_pipeline/test_pipeline_e2e.py`
- `tests/model_runner/test_external_stub_bridge.py`
- `reports/milestones/M13_e2e_named_transcript_report.md`

## Behavior Added

- `PipelineRunner.predict(record, config) -> PipelineOutput`
- Config-backed pipeline construction from `e2e_named_transcript.yaml`
- Audio loading from `record["inference_audio_path"]`
- VAD, segmentation, segment ASR, speaker embedding, speaker matching, and
  transcript assembly in one call
- Chronological segment ordering before utterance assembly
- Duplicate token overlap removal when chunk transcripts are merged
- Per-stage runtime tracking and pipeline realtime factor diagnostics
- `pipeline_diagnostics.jsonl` and `pipeline_diagnostics_summary.json`

## Runner Contract Preservation

The evaluator-facing prediction file remains:

```text
predictions/utterances.jsonl
```

Rows still contain only:

```text
recording_id, utt_id, start_sec, end_sec, speaker_label, text
```

`recording_id` and `utt_id` are preserved exactly from the selected record, and
`start_sec` / `end_sec` are copied through when present. Segment lists, raw ASR
text, normalized text, speaker decisions, and runtime stats are written only to
diagnostic files beside the prediction contract.

## Validation Commands

Run from `Software Validation from Datasets/Evaluation Tool`:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_pipeline_e2e.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py -q
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests -q -k "inference_pipeline or external_stub or e2e"
/Users/billy/Documents/just-peachy/.venv/bin/python -m compileall app/inference_pipeline/pipeline.py app/inference_pipeline/transcript app/inference_pipeline/runtime app/model_runner/external_stub.py
```

## Test Results

- M13 focused tests: `3 passed`
- External stub bridge tests: `4 passed`
- Requested broader selection: `120 passed, 8 deselected`
- Compile check: passed
- `git diff --check`: passed

## Smoke Run

Command:

```bash
/Users/billy/Documents/just-peachy/.venv/bin/python run_evaluation.py full --project-root /Users/billy/Documents/just-peachy/Software\ Validation\ from\ Datasets --dataset cmu_arctic --max-recordings 1 --runner external-stub --augmentation none --run-name m13_e2e_named_transcript_smoke
```

Result:

- Run folder: `runs/20260531_133140_cmu_arctic_full_m13_e2e_named_transcript_smoke`
- Predictions: `1`
- Failed predictions: `0`
- Missing predictions: `0`
- Aggregate WER: `1.0000`
- Speaker label accuracy: `0.0`
- Unknown rate: `1.0`
- False known-speaker assignment rate: `0.0`
- Chronological ordering violations: `0`
- Mean pipeline RTF: `0.0010271956925634387`

The smoke run completed scoring, plots, and report generation. The run emitted
expected environment warnings from PyArrow CPU probing and Matplotlib cache
fallback, but the command exited successfully.

## Known Limitations

- The default M13 config intentionally uses no-op ASR and no-op speaker
  embedding/matching so the smoke run does not require downloads or model
  assets.
- Real ASR text quality, real speaker embeddings, and real named-speaker
  assignment still require local Whisper/SpeechBrain assets and an enrolled
  speaker database.
- The existing evaluator reports WER and speaker-label metrics; CER is not
  currently emitted by `score_run`.

## Blockers

- None for the scoped M13 implementation.
