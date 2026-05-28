# M11 Speaker Matching Report

## Milestone

M11 - Speaker Matching, Unknown Fallback, and Threshold Calibration

## Summary

M11 adds a scoped speaker matching component for assigning enrolled speaker
names from segment embeddings. The implementation matches query embeddings
against the M10 enrollment database with PyTorch cosine similarity, configurable
thresholds, configurable score margins, model-id consistency checks, and
conservative `Unknown` fallback.

The matcher is independent of the Evaluation Tool runner. No changes were made
to `app/model_runner/external_stub.py`, dataset selection, scoring, plotting,
report generation, GUI, or the required `predictions/utterances.jsonl` schema.

## Files Changed

- `app/inference_pipeline/registry.py`
- `app/inference_pipeline/speaker_matching/__init__.py`
- `app/inference_pipeline/speaker_matching/base.py`
- `app/inference_pipeline/speaker_matching/cosine_matcher.py`
- `app/inference_pipeline/speaker_matching/thresholds.py`
- `configs/inference/components/speaker_matching/cosine_threshold.yaml`
- `tests/run_all_tests.py`
- `tests/run_smoke_tests.py`
- `tests/inference_pipeline/test_speaker_matching.py`
- `reports/component_reports/speaker_matching/threshold_calibration_m11_speaker_matching.md`
- `reports/milestones/M11_speaker_matching_report.md`

## Behavior Added

- `SpeakerMatcherBase.match(embedding, enrollment_db) -> SpeakerDecision`
- `CosineThresholdSpeakerMatcher` with centroid and exemplar scoring modes
- Structured decisions with best label, confidence, margin, threshold,
  accepted flag, matched reference, per-speaker scores, and final label
- `Unknown` fallback for below-threshold, ambiguous, no-enrollment,
  invalid-embedding, dimension-mismatch, and model-mismatch cases
- Threshold calibration helpers and CLI entry point
- YAML config for the `cosine_threshold` speaker matching component
- M11 registration in the all-test runner summary
- M11 synthetic calibration smoke check in the smoke-test harness

## Runner Contract Preservation

The matcher consumes embeddings and the enrollment DB only. It does not change:

- `record["inference_audio_path"]`
- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `predictions/utterances.jsonl`

## Validation Commands

Run from `/Users/billy/Documents/just-peachy`:

```bash
.venv/bin/python -m pytest "Software Validation from Datasets/Evaluation Tool/tests/inference_pipeline/test_speaker_matching.py"
```

Run from `/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool`:

```bash
../../.venv/bin/python -m pytest tests/inference_pipeline/test_enrollment_store.py
../../.venv/bin/python -m pytest tests/inference_pipeline/test_config_registry.py
../../.venv/bin/python -m pytest tests/model_runner/test_external_stub_bridge.py
../../.venv/bin/python -m compileall app/inference_pipeline/speaker_matching
../../.venv/bin/python -m app.inference_pipeline.speaker_matching.thresholds --enrollment-db /private/tmp/m11_speaker_matching_smoke/enrollment_db.json --samples-jsonl /private/tmp/m11_speaker_matching_smoke/samples.jsonl --report "reports/component_reports/speaker_matching/threshold_calibration_m11_speaker_matching.md" --run-id m11_speaker_matching --threshold-min 0.5 --threshold-max 0.95 --threshold-step 0.15 --min-margin 0.05 --runtime-model-id speaker-embedder@1
../../.venv/bin/python tests/run_smoke_tests.py --only m11-speaker-matching-calibration-direct
../../.venv/bin/python tests/run_smoke_tests.py --list
../../.venv/bin/python tests/run_all_tests.py --python ../../.venv/bin/python
```

## Test Results

- Speaker matching tests: `7 passed`
- Enrollment store tests: `7 passed`
- Config registry tests: `10 passed`
- External stub bridge tests: `4 passed`
- Compile check: passed
- Synthetic calibration smoke: passed; recommended threshold `0.9500`
- M11 smoke harness check: passed
- All-test harness: passed, including `tests/inference_pipeline/test_speaker_matching.py` labeled `M11`

## Required Component Report

The required calibration report is:

```text
reports/component_reports/speaker_matching/threshold_calibration_m11_speaker_matching.md
```

## Known Limitations

- Calibration used deterministic synthetic embeddings, not real speaker audio
  model outputs.
- The matcher is not wired into the end-to-end external runner yet.
- Product-quality thresholds still need calibration on real enrolled speakers
  and held-out unknown-speaker samples before deployment.

## Blockers

- None known for the scoped M11 component implementation.
