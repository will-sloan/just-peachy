# CMU ARCTIC Normalized Schema

This document defines the normalized output files produced by `normalize_cmu_arctic.py`.

## Design goals

- keep raw data untouched
- avoid duplicating audio
- store both original and normalized transcript text
- preserve speaker metadata such as gender and accent
- make later evaluation tooling simple and consistent

## Output files

### 1. `recordings.parquet`

One row per utterance audio file.

| Column | Meaning |
|---|---|
| `recording_id` | Stable unique recording key |
| `dataset` | Human-readable dataset name |
| `dataset_id` | Stable short dataset identifier |
| `speaker_id` | Full speaker folder name |
| `speaker_code` | Short code, e.g. `aew` |
| `gender` | Speaker gender from YAML metadata |
| `accent` | Human-readable accent label |
| `accent_group` | Grouping such as `native_us`, `other_english`, `non_native_or_accented` |
| `speaker_variant_group` | Grouping such as `core`, `other_accents`, `additional` |
| `utterance_id` | Prompt/audio ID |
| `audio_path` | Absolute path to the original raw WAV |
| `sample_rate_hz` | Audio sample rate |
| `duration_sec` | Audio duration in seconds |
| `num_channels` | Number of audio channels |
| `text_source` | Transcript source used for this row |
| `raw_transcript_path` | Path to the per-speaker `txt.done.data` used |
| `normalization_status` | `ok`, `audio_missing`, `transcript_only`, etc. |

### 2. `utterances.parquet`

One row per utterance-level reference transcript.

| Column | Meaning |
|---|---|
| `recording_id` | Stable unique key |
| `dataset` | Dataset name |
| `dataset_id` | Short dataset identifier |
| `speaker_id` | Full speaker folder name |
| `speaker_code` | Short speaker code |
| `gender` | Speaker gender |
| `accent` | Accent label |
| `accent_group` | Accent grouping |
| `speaker_variant_group` | Variant grouping |
| `utterance_id` | Prompt/audio ID |
| `start_sec` | Start time, always `0.0` for this dataset |
| `end_sec` | End time, equal to utterance duration |
| `text_original` | Original transcript text from source file |
| `text_norm` | Normalized comparison text |
| `text_source` | Transcript source used |
| `audio_path` | Raw WAV path |

### 3. `normalization_log.csv`

One row per warning or issue encountered during normalization.

Typical issue types:
- `missing_audio_for_transcript`
- `missing_transcript_for_audio`
- `speaker_metadata_missing`
- `audio_read_error`

### 4. `README_normalized.md`

Human-readable record of:
- the raw dataset location
- normalization decisions
- transcript source precedence
- known issues and counts
- output files written

## Transcript normalization

The raw transcript text is preserved exactly in `text_original`.

A conservative normalized version is written to `text_norm` using:
- lowercasing
- punctuation removal
- repeated whitespace collapse
- trimming leading/trailing whitespace

This is intended to support fairer transcript comparison without destroying the original text.
