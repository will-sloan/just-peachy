# AMI Normalized Metadata README

## Dataset
- **Name:** AMI Meeting Corpus
- **Dataset ID:** `ami`
- **Raw dataset root:** `{dataset_root}`
- **Annotation root used:** `{annotation_root}`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- speaker-attributed transcription
- WER-style comparison
- segmentation / utterance-level comparison
- close-talk vs far-field comparison
- meeting-level and stream-level analysis

## Evaluation units
- **Words:** XML word tokens from `words/*.words.xml`
- **Utterances/segments:** XML segments from `segments/*.segments.xml`
- **Recordings:** headset streams and `Array1-*` meeting-level streams

## Streams included
- individual headset channels
- `Array1-01` through `Array1-08` where present

## Normalization decisions
- raw WAV files were not changed
- raw XML annotations were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- `meetings.xml` is used for agent-to-channel mapping
- `participants.xml` is used for speaker metadata where available
- segment text is reconstructed from inclusive word-ID ranges in the corresponding words XML

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `words.parquet`
- `segments.parquet`
- `meetings.parquet`
- `participants.parquet`
- `normalization_log.csv`

## Summary statistics
- total meetings parsed: `{num_meetings}`
- total recording streams emitted: `{num_recordings}`
- total segment/utterance rows emitted: `{num_segments}`
- total word rows emitted: `{num_words}`
- total warnings/issues logged: `{num_log_rows}`

## Known issues
{issues_block}
