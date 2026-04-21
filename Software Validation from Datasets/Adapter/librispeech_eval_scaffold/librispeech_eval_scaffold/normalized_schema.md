# LibriSpeech Normalized Schema

This document defines the normalized output files produced by `normalize_librispeech.py`.

## Design goals

- keep raw data untouched
- avoid duplicating audio
- preserve official LibriSpeech concepts such as `speaker_id`, `chapter_id`, and split
- store both original and normalized transcript text
- support later evaluation tooling with simple joins

## Included splits

Only these seven standard ASR splits are included by default:

- `dev-clean`
- `dev-other`
- `test-clean`
- `test-other`
- `train-clean-100`
- `train-clean-360`
- `train-other-500`

## Output files

### 1. `recordings.parquet`

One row per utterance audio file.

Key columns include:
- `recording_id`
- `split`
- `subset_group`
- `speaker_id`
- `chapter_id`
- `utterance_id`
- `audio_path`
- `sample_rate_hz`
- `duration_sec`
- `speaker_sex`
- `speaker_name`
- `chapter_title`
- `project_title`
- `book_id`
- `book_title`
- `book_authors`
- `text_source`
- `raw_transcript_path`
- `normalization_status`

### 2. `utterances.parquet`

One row per utterance-level reference transcript.

Key columns include:
- `recording_id`
- `split`
- `subset_group`
- `speaker_id`
- `chapter_id`
- `utterance_id`
- `start_sec`
- `end_sec`
- `text_original`
- `text_norm`
- `audio_path`

### 3. `speakers.parquet`

One row per speaker from `SPEAKERS.TXT`.

### 4. `chapters.parquet`

One row per chapter from `CHAPTERS.TXT`.

### 5. `books.parquet`

One row per book from `BOOKS.TXT`.

### 6. `normalization_log.csv`

One row per warning or issue encountered during normalization.

### 7. `README_normalized.md`

Human-readable record of:
- the raw dataset location
- included and excluded folders
- normalization decisions
- transcript source precedence
- known issues and counts
- output files written

## Transcript normalization

The raw transcript text is preserved exactly in `text_original`.

A conservative normalized version is written to `text_norm` using:
- lowercasing
- repeated whitespace collapse
- trimming leading/trailing whitespace

This is intentionally light because LibriSpeech transcript text is already ASR-normalized.
