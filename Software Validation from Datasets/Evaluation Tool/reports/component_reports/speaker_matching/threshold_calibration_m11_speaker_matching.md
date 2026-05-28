# Speaker Matching Threshold Calibration Report

## Milestone

M11 - Speaker Matching, Unknown Fallback, and Threshold Calibration

- Run id: `m11_speaker_matching`
- Scoring mode: `centroid`
- Minimum margin: `0.0500`
- Unknown label: `Unknown`
- Conservative max false-known rate: `0.0000`

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

## Summary

M11 adds cosine speaker matching against the M10 enrollment database,
including configurable thresholds, score margins, model-id checks,
and conservative `Unknown` fallback for unsafe decisions.

## Runner Contract Preservation

Threshold calibration reads enrollment DB and query embedding artifacts only. It does not modify app/model_runner/external_stub.py, record['inference_audio_path'], predictions/utterances.jsonl, or scoring identity fields.

## Commands

- `python -m app.inference_pipeline.speaker_matching.thresholds --enrollment-db /private/tmp/m11_speaker_matching_smoke/enrollment_db.json --samples-jsonl /private/tmp/m11_speaker_matching_smoke/samples.jsonl --report reports/component_reports/speaker_matching/threshold_calibration_m11_speaker_matching.md --threshold-min 0.5 --threshold-max 0.95 --threshold-step 0.15 --min-margin 0.05 --scoring-mode centroid --unknown-label Unknown --max-false-known-rate 0.0 --run-id m11_speaker_matching --runtime-model-id speaker-embedder@1`

## Recommended Threshold

- Recommended threshold: `0.9500`
- Known-speaker accuracy: `1.0000`
- False-known rate: `0.0000`
- Unknown rate: `0.3333`
- Unknown rejection rate: `1.0000`
- Accepted / Unknown: `2` / `1`

## Threshold Sweep

| threshold | known accuracy | false-known rate | unknown rate | unknown rejection | accepted | unknown | margin mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5000 | 1.0000 | 0.3333 | 0.0000 | 0.0000 | 3 | 0 | 0.7266 |
| 0.6500 | 1.0000 | 0.3333 | 0.0000 | 0.0000 | 3 | 0 | 0.7266 |
| 0.8000 | 1.0000 | 0.3333 | 0.0000 | 0.0000 | 3 | 0 | 0.7266 |
| 0.9500 | 1.0000 | 0.0000 | 0.3333 | 1.0000 | 2 | 1 | 0.7266 |

## Verification-Style Metrics

- Positive pairs: `2`
- Negative pairs: `4`
- Equal error rate: `0.0000`
- Equal error threshold: `0.9999`
- TAR at fixed FAR:
  - FAR `0.0100`: TAR `1.0000`
  - FAR `0.0500`: TAR `1.0000`
  - FAR `0.1000`: TAR `1.0000`

## Score Margin Distribution

- Margin mean: `0.7266`
- Margin min/max: `0.2000` / `0.9898`

## Blockers

- None known.

## Incomplete

- None known.
