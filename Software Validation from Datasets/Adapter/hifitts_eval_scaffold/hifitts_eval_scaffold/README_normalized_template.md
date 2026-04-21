# Hi Fi TTS Normalized Metadata README

## Dataset
- **Name:** Hi Fi TTS
- **Dataset ID:** `hifitts`
- **Raw dataset root:** `{dataset_root}`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- slicing by reader, quality, split, book, and bandwidth metadata

## Evaluation unit
- **Unit:** one utterance audio file
- **Key:** `(reader_id, audio_quality, split, book_id, audio_filepath_relative)`

## Manifest source of truth
Each JSONL manifest row is treated as authoritative for:
- `audio_filepath`
- `text`
- `duration`
- `text_no_preprocessing`
- `text_normalized`

## Transcript field policy
- `text` is the preferred evaluation reference for basic transcription comparison
- `text_normalized` is preserved for alternate comparison policies
- `text_no_preprocessing` is preserved for provenance, even if some rows contain encoding artifacts

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `readers.parquet`
- `reader_books.parquet`
- `book_bandwidth.parquet`
- `normalization_log.csv`

## Summary statistics
- total manifest files parsed: `{num_manifest_files}`
- total manifest rows parsed: `{num_manifest_rows}`
- total normalized recordings emitted: `{num_recordings}`
- total warnings/issues logged: `{num_log_rows}`

## Known issues
{issues_block}
