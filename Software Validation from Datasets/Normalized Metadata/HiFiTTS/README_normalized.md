# Hi Fi TTS Normalized Metadata README

## Dataset
- **Name:** Hi Fi TTS
- **Dataset ID:** `hifitts`
- **Raw dataset root:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\Hi Fi TTS\hi_fi_tts_v0`

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
- total manifest files parsed: `31`
- total manifest rows parsed: `323978`
- total normalized recordings emitted: `323978`
- total warnings/issues logged: `197809`

## Interpretation of logged issues

The high issue count in `normalization_log.csv` does **not** indicate dataset corruption or failed normalization.

Normalization completed successfully for this dataset:
- total manifest files parsed: `31`
- total manifest rows parsed: `323978`
- total normalized recordings emitted: `323978`

This means the manifest coverage matched the audio coverage for the normalization target, and the dataset was successfully converted into normalized metadata tables.

Most logged entries are **informational metadata gaps**, not missing audio or malformed manifest rows. In particular, many repeated `book_bandwidth_missing` entries occur because bandwidth metadata is not available for every `(reader_id, book_id, audio_quality)` combination. These messages are currently logged at the utterance level, so the same metadata gap may appear many times for the same book.

### Practical interpretation
- `INFO` rows in this dataset should generally be treated as **context notes**, not failures.
- The normalized outputs are valid and usable as long as:
  - `total normalized recordings emitted` matches the expected manifest coverage
  - there are no widespread `ERROR` rows indicating parse failures or unreadable audio
- For future cleanup, repeated informational rows may be deduplicated to one row per unique missing metadata key rather than one row per utterance.

### Recommended policy for downstream tools
When using this normalized dataset in later evaluation tooling:
- treat `ERROR` rows as true normalization failures
- treat `WARNING` rows as potential data-mapping issues requiring review
- treat `INFO` rows, especially repeated bandwidth-metadata notes, as non-fatal metadata limitations

## Logged ssues
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12352 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11736 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=10547 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=10547 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=10547 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11780 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11780 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11780 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11780 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11780 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=12220 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11965 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11965 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11965 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11965 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=11965 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=14179 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=14179 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=14179 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=14179 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=14179 | details=No bandwidth metadata found for this reader/book/quality.
- [INFO] book_bandwidth_missing | reader=11614 | quality=other | split=dev | book=14179 | details=No bandwidth metadata found for this reader/book/quality.
- ... 197759 additional issue rows omitted from README
