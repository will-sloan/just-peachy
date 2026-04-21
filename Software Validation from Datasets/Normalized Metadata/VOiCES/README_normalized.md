# VOiCES Normalized Metadata README

## Dataset
- **Name:** VOiCES DevKit
- **Dataset ID:** `voices`
- **Raw dataset root:** `C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\VOiCES`

## Purpose
This normalized metadata layer was created to support later evaluation of:
- utterance-level transcription
- WER-style comparison
- slicing by room, distractor, microphone, device, position, angle, speaker, and quality metrics

## Evaluation unit
- **Unit:** one manifest row = one distant/noisy WAV + one clean source WAV + one transcript
- **Key:** `query_name`


VOiCES metric cheat sheet
WER vs PESQ: lower PESQ usually means worse perceived audio quality, so WER often goes up as PESQ goes down.
WER vs STOI: lower STOI usually means speech is less understandable, so WER often goes up as STOI goes down.
WER vs SIIB: lower SIIB usually means less speech information is preserved, so WER often goes up as SIIB goes down.
WER vs SRMR: lower SRMR usually means more reverberation/echo, so WER often goes up as SRMR goes down.
Plain-language meanings
PESQ: “How good does the speech sound overall?”
STOI: “How understandable should the speech be?”
SIIB: “How much useful speech information is getting through?”
SRMR: “How badly is room echo/reverberation affecting the speech?”

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
- total manifest rows parsed: `19200`
- total normalized recordings emitted: `19200`
- total condition rows emitted: `19200`
- total warnings/issues logged: `0`

## Known issues
- none
