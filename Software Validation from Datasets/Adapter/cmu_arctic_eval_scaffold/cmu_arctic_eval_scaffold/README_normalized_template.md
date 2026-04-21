# CMU ARCTIC Normalized Metadata README

## Dataset
- **Name:** CMU Arctic
- **Dataset ID:** `cmu_arctic`
- **Raw dataset root:** `{dataset_root}`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- speaker-group slicing by gender and accent

## Evaluation unit
- **Unit:** one utterance audio file
- **Key:** `(speaker_id, utterance_id)`

## Transcript source precedence
1. per-speaker `etc/txt.done.data`
2. optional fallback to global `cmuarctic_data.txt` if explicitly enabled

## Raw structure assumptions
Each speaker folder is expected to contain:
- `wav/`
- `etc/txt.done.data`

## Normalization decisions
- raw WAV files were not changed
- raw transcript files were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- speaker gender/accent metadata comes from `cmu_arctic_speaker_metadata.yaml`

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `normalization_log.csv`

## Summary statistics
- total speaker folders found: `{num_speakers}`
- total transcript rows parsed: `{num_transcript_rows}`
- total normalized recordings emitted: `{num_recordings}`
- total warnings/issues logged: `{num_log_rows}`

## Known issues
{issues_block}
