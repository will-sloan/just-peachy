# VOiCES DevKit Normalized Schema

This document defines the normalized output files produced by `normalize_voices.py`.

## Design goals

- keep raw data untouched
- avoid duplicating audio
- preserve the official manifest structure from `train_index.csv` and `test_index.csv`
- make `query_name` the stable cross-file join key
- support grouped evaluation by room, distractor, microphone, device, position, angle, speaker, and quality metrics

## Expected raw structure

The dataset root should contain:

- `VOiCES_devkit/`
- `recording_data/`

Within `VOiCES_devkit/` the normalizer expects:
- `distant-16k/speech/`
- `source-16k/`
- `references/train_index.csv`
- `references/test_index.csv`
- `references/filename_transcripts`
- `references/time_values.csv`
- speaker metadata tables

Within `recording_data/` the normalizer expects:
- `distances.csv`
- `quality_metrics.csv`

## Output files

### 1. `recordings.parquet`

One row per manifest row / evaluation utterance.

Key columns include:
- `recording_id`
- `split`
- `query_name`
- `speaker_id`, `speaker_id_padded`
- `gender`
- `chapter_id`
- `segment_id`
- `room`
- `distractor`
- `mic`
- `device`
- `position`
- `degrees`
- `distant_audio_path`
- `source_audio_path`
- `distant_sample_rate_hz`
- `distant_duration_sec`
- `source_sample_rate_hz`
- `source_duration_sec`
- `manifest_noisy_time`
- `manifest_source_time`

### 2. `utterances.parquet`

One row per evaluation utterance transcript.

Key columns include:
- `recording_id`
- `split`
- `query_name`
- `speaker_id`
- `room`
- `distractor`
- `mic`
- `position`
- `degrees`
- `text_original`
- `text_norm`
- `distant_audio_path`
- `source_audio_path`

### 3. `conditions.parquet`

One row per `query_name` / recording with joined condition and quality metadata.

Includes:
- room / distractor / mic / device / position / degrees
- distances from `distances.csv`
- PESQ / STOI / SIIB / SRMR from `quality_metrics.csv`

### 4. `speakers.parquet`

Speaker-level metadata joined from the available speaker tables.

### 5. `source_map.parquet`

Optional alignment/timing metadata derived from `time_values.csv`.

### 6. `normalization_log.csv`

One row per warning or issue encountered during normalization.

Typical issue types:
- `missing_distant_audio`
- `missing_source_audio`
- `audio_read_error`
- `filename_parse_mismatch`
- `duplicate_query_name`
- `metadata_missing`

### 7. `README_normalized.md`

Human-readable record of:
- the raw dataset location
- normalization decisions
- manifest source precedence
- known issues and counts
- output files written

## Transcript normalization

The raw transcript text is preserved exactly in `text_original`.

A conservative normalized version is written to `text_norm` using:
- lowercasing
- repeated whitespace collapse
- trimming leading/trailing whitespace

## Evaluation interpretation

This dataset is normalized as a **whole-utterance single-speaker far-field robustness benchmark**.
It is appropriate for:
- transcription / WER
- room-condition grouping
- distractor-condition grouping
- file-level speaker labeling

It is **not** treated here as a turn-level diarization dataset.
