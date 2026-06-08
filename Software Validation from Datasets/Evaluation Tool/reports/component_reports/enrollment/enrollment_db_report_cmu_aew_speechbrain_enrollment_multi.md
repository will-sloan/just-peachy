# Enrollment DB Component Report

## Milestone

M10 - Enrollment Store and Enrollment CLI

- Run id: `cmu_aew_speechbrain_enrollment_multi`
- Schema version: `m10.enrollment_db.v1`
- Speakers: `1`
- Exemplars: `15`
- Model ids: `speechbrain_ecapa, speechbrain_ecapa_voxceleb`

## Files Changed

- `app/inference_pipeline/enrollment/__init__.py`
- `app/inference_pipeline/enrollment/store.py`
- `app/inference_pipeline/enrollment/schema.py`
- `app/inference_pipeline/enrollment/prompts.py`
- `scripts/enroll_speaker.py`

## Summary

M10 adds a versioned enrollment database, store helpers, validation checks,
and a standalone CLI for enrolling one speaker from existing WAV files.
The store keeps per-exemplar vectors for future exemplar-by-exemplar matching
and computes per-speaker centroid embeddings for future centroid matching.

## Schema

Each exemplar records `speaker_id`, `display_name`, `prompt_id`, `audio_path`,
`embedding`, `model_id`, `created_at`, and `notes`; the DB also records
schema version and top-level model-id metadata.

## CLI

`scripts/enroll_speaker.py` enrolls from existing WAV files. The default
`speechbrain` backend uses the existing lazy SpeechBrain ECAPA adapter and
fails clearly when dependencies or local model assets are unavailable. The
`fake` backend is explicit smoke/test plumbing only.

## Runner Contract Preservation

Enrollment is a standalone artifact workflow. It does not change app/model_runner/external_stub.py, record['inference_audio_path'], predictions/utterances.jsonl, or scoring identity fields.

## Commands

- `python scripts/enroll_speaker.py --display-name 'Alice' --model-id speechbrain_ecapa --backend speechbrain --audio ../RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0535.wav ../RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0536.wav ../RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0537.wav ../RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0538.wav ../RawDatasets/CMU Arctic/cmu_us_aew_arctic/wav/arctic_b0539.wav --db /Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool/artifacts/enrollment/enrollment_db.json --run-id cmu_aew_speechbrain_enrollment_multi`

## Validation

- Validation ok: `True`
- Minimum exemplars per speaker: `1`
- Minimum duration coverage per speaker: `0.750s`

## Speaker Summaries

- `Alice`: exemplars=15, valid=15, duration_sec=38.865, model_ids=['speechbrain_ecapa', 'speechbrain_ecapa_voxceleb'], complete=True

## Warnings

- Alice has mixed enrollment model_ids: speechbrain_ecapa, speechbrain_ecapa_voxceleb
- model_id mismatch for Alice: stored 'speechbrain_ecapa_voxceleb' != runtime 'speechbrain_ecapa'

## Errors

- None.

## Blockers

- None known.

## Incomplete

- Live microphone enrollment is intentionally deferred beyond M10.
