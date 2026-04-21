# VOiCES Normalized Metadata README

## Dataset
- **Name:** VOiCES DevKit
- **Dataset ID:** `voices`
- **Raw dataset root:** `{dataset_root}`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- slicing by room, distractor, microphone, device, position, angle, speaker, and quality metrics

## Evaluation unit
- **Unit:** one manifest row = one distant/noisy WAV + one clean source WAV + one transcript
- **Key:** `query_name`

## Manifest source precedence
1. `references/train_index.csv`
2. `references/test_index.csv`
3. optional fallback/consistency check from `references/filename_transcripts`

## Raw structure assumptions
The dataset root is expected to contain:
- `VOiCES_devkit/`
- `recording_data/`

## Normalization decisions
- raw WAV files were not changed
- raw transcript/manifests were not changed
- original transcript text is preserved
- normalized transcript text is stored separately
- `query_name` is used as the stable join key
- speaker IDs are normalized to zero-padded 4-digit strings for metadata joins
- `distances.csv` and `quality_metrics.csv` are joined as condition metadata
- `time_values.csv` is joined cautiously because of its duplicate `index,index` header

## Output files
- `recordings.parquet`
- `utterances.parquet`
- `conditions.parquet`
- `speakers.parquet`
- `source_map.parquet`
- `normalization_log.csv`

## Summary statistics
- total manifest rows parsed: `{num_manifest_rows}`
- total normalized recordings emitted: `{num_recordings}`
- total condition rows emitted: `{num_condition_rows}`
- total warnings/issues logged: `{num_log_rows}`

## Known issues
{issues_block}
