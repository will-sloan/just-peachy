# Enrollment DB Component Report

## Milestone

M10 - Enrollment Store and Enrollment CLI

- Run id: `m10_enrollment_store`
- Branch: `m10`
- Schema version: `m10.enrollment_db.v1`

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

## Summary

M10 adds a versioned enrollment database for associating speaker names with one
or more embedding exemplars. Each exemplar records `speaker_id`, `display_name`,
`prompt_id`, `audio_path`, `embedding`, `model_id`, `created_at`, `notes`,
duration metadata, and an embedding id. Speakers keep the exemplar list for
future exemplar-by-exemplar matching and expose a computed centroid embedding for
future centroid matching.

The standalone CLI at `scripts/enroll_speaker.py` enrolls one speaker from one
or more existing WAV files. It uses the existing M9 speaker embedding adapters:
`speechbrain` is the real default backend, and `fake` is explicit smoke-test
plumbing only.

The tracked DB artifact is an empty baseline at
`artifacts/enrollment/enrollment_db.json`; smoke checks wrote temporary DBs under
`/private/tmp/m10_enrollment_smoke`.

## Runner Contract Preservation

No changes were made to `app/model_runner/external_stub.py`, the Evaluation Tool
runner contract, dataset registry, scorer, GUI, existing CLI, plot generation,
or report generator. Enrollment is a separate artifact workflow and does not
change `record["inference_audio_path"]`, `predictions/utterances.jsonl`, or the
identity fields matched by scoring.

## Commands Run

- `git status --short --branch`
- `.venv/bin/python --version`
- `.venv/bin/python -m pytest --version`
- `../../.venv/bin/python -m pytest tests/inference_pipeline/test_enrollment_store.py`
- `../../.venv/bin/python -m pytest tests/inference_pipeline/test_contracts.py tests/model_runner/test_external_stub_bridge.py`
- `../../.venv/bin/python -m pytest tests/inference_pipeline/test_speaker_embedding_interface.py`
- `../../.venv/bin/python -m compileall app/inference_pipeline/enrollment scripts/enroll_speaker.py`
- `../../.venv/bin/python -m pip show speechbrain`
- `mkdir -p /private/tmp/m10_enrollment_smoke`
- `../../.venv/bin/python -c 'from pathlib import Path; import numpy as np, soundfile as sf; root=Path("/private/tmp/m10_enrollment_smoke"); sr=16000; t=np.arange(sr, dtype=np.float32)/sr; sf.write(root/"alice.wav", (0.1*np.sin(2*np.pi*220*t)).astype(np.float32), sr); sf.write(root/"bob.wav", (0.1*np.sin(2*np.pi*330*t)).astype(np.float32), sr)'`
- `../../.venv/bin/python scripts/enroll_speaker.py --display-name Alice --model-id fake_speaker_embedding@smoke --backend fake --audio /private/tmp/m10_enrollment_smoke/alice.wav --db /private/tmp/m10_enrollment_smoke/enrollment_db.json --report /private/tmp/m10_enrollment_smoke/alice_report.md --run-id m10_smoke_alice --min-duration-sec 0.1`
- `../../.venv/bin/python scripts/enroll_speaker.py --display-name Bob --model-id fake_speaker_embedding@smoke --backend fake --audio /private/tmp/m10_enrollment_smoke/bob.wav --db /private/tmp/m10_enrollment_smoke/enrollment_db.json --report /private/tmp/m10_enrollment_smoke/bob_report.md --run-id m10_smoke_bob --min-duration-sec 0.1`
- `../../.venv/bin/python -c 'from pathlib import Path; from app.inference_pipeline.enrollment import load_enrollment_db, validate_enrollment_database; db=load_enrollment_db(Path("/private/tmp/m10_enrollment_smoke/enrollment_db.json")); report=validate_enrollment_database(db, runtime_model_id="fake_speaker_embedding@smoke", min_exemplars_per_speaker=1, min_duration_sec_per_speaker=0.1); print(f"speakers={len(db.speakers)} exemplars={db.exemplar_count} ok={report.ok} models={db.embedding_model_ids}")'`
- `../../.venv/bin/python scripts/enroll_speaker.py --display-name Alice --model-id speechbrain_ecapa@1.1.0 --backend speechbrain --audio /private/tmp/m10_enrollment_smoke/alice.wav --db /private/tmp/m10_enrollment_smoke/speechbrain_enrollment_db.json --report /private/tmp/m10_enrollment_smoke/speechbrain_alice_report.md --run-id m10_speechbrain_alice --min-duration-sec 0.1`
- `../../.venv/bin/python scripts/enroll_speaker.py --display-name Bob --model-id speechbrain_ecapa@1.1.0 --backend speechbrain --audio /private/tmp/m10_enrollment_smoke/bob.wav --db /private/tmp/m10_enrollment_smoke/speechbrain_enrollment_db.json --report /private/tmp/m10_enrollment_smoke/speechbrain_bob_report.md --run-id m10_speechbrain_bob --min-duration-sec 0.1`
- `../../.venv/bin/python -c 'from pathlib import Path; from app.inference_pipeline.enrollment import load_enrollment_db, validate_enrollment_database; db=load_enrollment_db(Path("/private/tmp/m10_enrollment_smoke/speechbrain_enrollment_db.json")); report=validate_enrollment_database(db, runtime_model_id="speechbrain_ecapa@1.1.0", min_exemplars_per_speaker=1, min_duration_sec_per_speaker=0.1); print(f"speakers={len(db.speakers)} exemplars={db.exemplar_count} ok={report.ok} models={db.embedding_model_ids}")'`

## Results

- Enrollment store tests: `7 passed`
- Existing contract and external stub bridge tests: `15 passed`
- Speaker embedding boundary tests: `9 passed`
- Compile check: passed
- Fake CLI smoke DB load: `speakers=2 exemplars=2 ok=True models=('fake_speaker_embedding@smoke',)`
- SpeechBrain CLI smoke DB load: `speakers=2 exemplars=2 ok=True models=('speechbrain_ecapa@1.1.0',)`

## Validation Checks

- Save/load round-trip preserves speakers, exemplars, model ids, durations, and computed centroids.
- Duplicate display names are rejected both when adding a speaker and when loading an invalid DB.
- Missing audio files fail before enrollment.
- Model-version mismatches emit `UserWarning` and are included in validation reports.
- Completeness checks cover valid embedding count and duration coverage per speaker.
- The DB loads in a separate Python process from disk.

## Blockers

- None for the M10 store and CLI implementation in this environment. `speechbrain` is installed in `.venv`, and ECAPA assets are present in the local Evaluation Tool model cache.

## Incomplete

- Live microphone enrollment is intentionally deferred beyond M10.
- The real SpeechBrain smoke check used synthetic one-second WAV files to verify workflow and DB metadata, not a product-quality speaker-separation evaluation.
- No speaker matcher module exists yet, so this milestone exposes validated DB load/summary behavior for future matcher tests instead of inventing matcher architecture.
