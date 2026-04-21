# Hi Fi TTS Normalized Schema

This document defines the normalized output files produced by `normalize_hifitts.py`.

## Design goals

- keep raw data untouched
- avoid duplicating audio
- treat manifest JSONL rows as the source of truth
- preserve all transcript variants
- attach reader/book/bandwidth metadata where available
- support later transcription evaluation with simple joins

## Output files

### 1. `recordings.parquet`

One row per FLAC utterance file.

Key columns include:
- `recording_id`
- `reader_id`
- `reader_name`
- `gender`
- `audio_quality`
- `split`
- `book_id`
- `audio_path`
- `audio_filepath_relative`
- `sample_rate_hz`
- `duration_sec_audio`
- `duration_sec_manifest`
- `book_bandwidth`
- `book_bandwidth_comment`
- `raw_manifest_path`
- `normalization_status`

### 2. `utterances.parquet`

One row per reference utterance.

Key columns include:
- `recording_id`
- `reader_id`
- `audio_quality`
- `split`
- `book_id`
- `start_sec`
- `end_sec`
- `text`
- `text_no_preprocessing`
- `text_normalized`
- `text_norm_eval`
- `audio_path`
- `audio_filepath_relative`

### 3. `readers.parquet`

One row per reader, built from the maintained YAML metadata file.

### 4. `reader_books.parquet`

One row per reader-book pairing, built from:
- `readers_books_clean.txt`
- `readers_books_other.txt`

### 5. `book_bandwidth.parquet`

One row per `(reader_id, book_id, audio_quality)` from `books_bandwidth.tsv`.

### 6. `normalization_log.csv`

One row per warning or issue encountered during normalization.

Typical issue types:
- `missing_audio_for_manifest_row`
- `audio_read_error`
- `reader_metadata_missing`
- `book_bandwidth_missing`
- `reader_books_mapping_missing`

### 7. `README_normalized.md`

Human-readable record of:
- the raw dataset location
- manifest structure
- normalization decisions
- transcript field policy
- known issues and counts
- output files written

## Transcript policy

The raw manifest already contains three text fields:
- `text`
- `text_no_preprocessing`
- `text_normalized`

All three are preserved.

A fourth field, `text_norm_eval`, is created as a conservative evaluation-friendly text.
Recommended default comparison target for transcription evaluation is:
- `text` for ASR/WER-style comparison

`text_no_preprocessing` is retained for reference, but may contain mojibake artifacts in some rows.
