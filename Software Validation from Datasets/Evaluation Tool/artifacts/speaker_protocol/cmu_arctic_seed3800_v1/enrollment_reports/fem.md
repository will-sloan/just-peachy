# Enrollment DB Component Report

## Milestone

M10 - Enrollment Store and Enrollment CLI

- Run id: `speaker_protocol_enroll_fem`
- Schema version: `m10.enrollment_db.v1`
- Speakers: `7`
- Exemplars: `35`
- Model ids: `speechbrain_ecapa`

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

- `python scripts/enroll_speaker.py --display-name 'fem' --model-id speechbrain_ecapa --backend speechbrain --audio C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_fem_arctic\wav\arctic_a0316.wav C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_fem_arctic\wav\arctic_a0078.wav C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_fem_arctic\wav\arctic_a0476.wav C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_fem_arctic\wav\arctic_a0408.wav C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_fem_arctic\wav\arctic_a0491.wav --db artifacts\speaker_protocol\cmu_arctic_seed3800_v1\enrollment_db_speechbrain_ecapa.json --run-id speaker_protocol_enroll_fem --report artifacts\speaker_protocol\cmu_arctic_seed3800_v1\enrollment_reports\fem.md --prompt-id cmu_arctic_seed3800_v1`

## Validation

- Validation ok: `True`
- Minimum exemplars per speaker: `1`
- Minimum duration coverage per speaker: `0.750s`

## Speaker Summaries

- `aew`: exemplars=5, valid=5, duration_sec=15.610, model_ids=['speechbrain_ecapa'], complete=True
- `ahw`: exemplars=5, valid=5, duration_sec=21.715, model_ids=['speechbrain_ecapa'], complete=True
- `aup`: exemplars=5, valid=5, duration_sec=16.660, model_ids=['speechbrain_ecapa'], complete=True
- `axb`: exemplars=5, valid=5, duration_sec=16.425, model_ids=['speechbrain_ecapa'], complete=True
- `clb`: exemplars=5, valid=5, duration_sec=18.405, model_ids=['speechbrain_ecapa'], complete=True
- `eey`: exemplars=5, valid=5, duration_sec=15.635, model_ids=['speechbrain_ecapa'], complete=True
- `fem`: exemplars=5, valid=5, duration_sec=19.025, model_ids=['speechbrain_ecapa'], complete=True

## Warnings

- None.

## Errors

- None.

## Blockers

- None known.

## Incomplete

- None known.
