# M10 Enrollment Store Report

## Milestone

M10 - Enrollment Store and Enrollment CLI

## Summary

M10 adds a versioned, UI-independent enrollment database for associating one
speaker display name with one or more embedding exemplars. The implementation is
scoped to enrollment storage, validation, and a standalone file-based CLI.

Each exemplar records:

- `speaker_id`
- `display_name`
- `prompt_id`
- `audio_path`
- `embedding`
- `model_id`
- `created_at`
- `notes`

The store preserves per-exemplar embeddings for future exemplar-by-exemplar
matching and computes per-speaker centroid embeddings for future centroid
matching.

## Files Changed

- `app/inference_pipeline/enrollment/__init__.py`
- `app/inference_pipeline/enrollment/store.py`
- `app/inference_pipeline/enrollment/schema.py`
- `app/inference_pipeline/enrollment/prompts.py`
- `scripts/enroll_speaker.py`
- `artifacts/enrollment/enrollment_db.json`
- `artifacts/enrollment/samples/.gitkeep`
- `tests/inference_pipeline/test_enrollment_store.py`
- `reports/component_reports/enrollment/enrollment_db_report_m10_enrollment_store.md`
- `reports/milestones/M10_enrollment_store_report.md`

## CLI

`scripts/enroll_speaker.py` enrolls one speaker from one or more existing WAV
files. It accepts speaker display name, prompt id, model/version metadata,
notes, backend selection, and DB/report output paths.

The default backend is `speechbrain`, using the existing lazy SpeechBrain ECAPA
adapter. The `fake` backend is explicit smoke-test plumbing only.

## Runner Contract Preservation

No changes were made to `app/model_runner/external_stub.py`, `PipelineRunner`,
the dataset registry, scorer, GUI, existing CLI, plot generation, or report
generator.

Enrollment is a separate artifact workflow and does not change:

- `record["inference_audio_path"]`
- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `predictions/utterances.jsonl`

## Validation Commands

Run from `Software Validation from Datasets/Evaluation Tool`:

```bash
../../.venv/bin/python -m pytest tests/inference_pipeline/test_enrollment_store.py
../../.venv/bin/python -m pytest tests/inference_pipeline/test_contracts.py tests/model_runner/test_external_stub_bridge.py
../../.venv/bin/python -m pytest tests/inference_pipeline/test_speaker_embedding_interface.py
../../.venv/bin/python -m compileall app/inference_pipeline/enrollment scripts/enroll_speaker.py
```

Smoke checks used temporary artifacts under `/private/tmp/m10_enrollment_smoke`:

```bash
../../.venv/bin/python scripts/enroll_speaker.py --display-name Alice --model-id fake_speaker_embedding@smoke --backend fake --audio /private/tmp/m10_enrollment_smoke/alice.wav --db /private/tmp/m10_enrollment_smoke/enrollment_db.json --report /private/tmp/m10_enrollment_smoke/alice_report.md --run-id m10_smoke_alice --min-duration-sec 0.1
../../.venv/bin/python scripts/enroll_speaker.py --display-name Bob --model-id fake_speaker_embedding@smoke --backend fake --audio /private/tmp/m10_enrollment_smoke/bob.wav --db /private/tmp/m10_enrollment_smoke/enrollment_db.json --report /private/tmp/m10_enrollment_smoke/bob_report.md --run-id m10_smoke_bob --min-duration-sec 0.1
../../.venv/bin/python scripts/enroll_speaker.py --display-name Alice --model-id speechbrain_ecapa@1.1.0 --backend speechbrain --audio /private/tmp/m10_enrollment_smoke/alice.wav --db /private/tmp/m10_enrollment_smoke/speechbrain_enrollment_db.json --report /private/tmp/m10_enrollment_smoke/speechbrain_alice_report.md --run-id m10_speechbrain_alice --min-duration-sec 0.1
../../.venv/bin/python scripts/enroll_speaker.py --display-name Bob --model-id speechbrain_ecapa@1.1.0 --backend speechbrain --audio /private/tmp/m10_enrollment_smoke/bob.wav --db /private/tmp/m10_enrollment_smoke/speechbrain_enrollment_db.json --report /private/tmp/m10_enrollment_smoke/speechbrain_bob_report.md --run-id m10_speechbrain_bob --min-duration-sec 0.1
```

## Test Results

- `tests/inference_pipeline/test_enrollment_store.py`: `7 passed`
- `tests/inference_pipeline/test_contracts.py` plus `tests/model_runner/test_external_stub_bridge.py`: `15 passed`
- `tests/inference_pipeline/test_speaker_embedding_interface.py`: `9 passed`
- Compile check: passed
- Fake CLI smoke DB: `speakers=2 exemplars=2 ok=True`
- SpeechBrain CLI smoke DB: `speakers=2 exemplars=2 ok=True`

## Validation Coverage

- Save/load round-trip.
- Duplicate speaker display names.
- Missing audio files.
- Model-version mismatch warnings.
- Multiple exemplars per speaker.
- Enrollment completeness by exemplar count.
- Duration coverage per speaker.
- Separate-process DB load.

## Required Component Report

The component-level report is:

```text
reports/component_reports/enrollment/enrollment_db_report_m10_enrollment_store.md
```

## Known Limitations

- Live microphone enrollment is intentionally deferred beyond M10.
- The real SpeechBrain smoke check used synthetic one-second WAV files to verify
  workflow and metadata persistence, not product-quality speaker separation.
- No speaker matcher module exists yet, so M10 exposes validated DB behavior for
  future matcher tests without adding matcher architecture.

## Open Issues

None known for the M10 enrollment store and CLI implementation.
