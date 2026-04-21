# LibriSpeech Normalized Metadata README

## Dataset
- **Name:** LibriSpeech
- **Dataset ID:** `librispeech`
- **Raw dataset root:** `{dataset_root}`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- slicing by split, clean/other grouping, speaker, chapter, and book metadata

## Evaluation unit
- **Unit:** one utterance audio file
- **Key:** `(speaker_id, chapter_id, utterance_id)`

## Included splits
{included_splits_block}

## Excluded folders in first pass
{excluded_folders_block}

## Transcript source precedence
1. chapter-level `*.trans.txt` files in standard ASR splits

## Raw structure assumptions
Each included split is expected to contain:
- `<split>/LibriSpeech/<split>/<speaker_id>/<chapter_id>/`
- one `<speaker_id>-<chapter_id>.trans.txt`
- many `<speaker_id>-<chapter_id>-<utt>.flac`

## Normalization decisions
- raw FLAC files were not changed
- raw transcript files were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- speaker/chapter/book metadata comes from `SPEAKERS.TXT`, `CHAPTERS.TXT`, and `BOOKS.TXT`

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `speakers.parquet`
- `chapters.parquet`
- `books.parquet`
- `normalization_log.csv`

## Summary statistics
- total included splits found: `{num_splits}`
- total transcript rows parsed: `{num_transcript_rows}`
- total normalized recordings emitted: `{num_recordings}`
- total warnings/issues logged: `{num_log_rows}`

## Known issues
{issues_block}
