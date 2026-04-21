# LibriSpeech Normalized Metadata README

## Dataset
- **Name:** LibriSpeech
- **Dataset ID:** `librispeech`
- **Raw dataset root:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\LibreSpeech`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- slicing by split, clean/other grouping, speaker, chapter, and book metadata

## Evaluation unit
- **Unit:** one utterance audio file
- **Key:** `(speaker_id, chapter_id, utterance_id)`

## Included splits
- `dev-clean`
- `dev-other`
- `test-clean`
- `test-other`
- `train-clean-100`
- `train-clean-360`
- `train-other-500`

## Excluded folders in first pass
- `intro-disclaimers`
- `original-books`
- `original-mp3`
- `raw-metadata`

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
- total included splits found: `7`
- total transcript rows parsed: `292367`
- total normalized recordings emitted: `292367`
- total warnings/issues logged: `0`

## Known issues
- none
