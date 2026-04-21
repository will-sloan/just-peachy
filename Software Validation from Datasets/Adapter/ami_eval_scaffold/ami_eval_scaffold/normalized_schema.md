# AMI Meeting Corpus Normalized Schema

This document defines the normalized output files produced by `normalize_ami.py`.

## Design goals

- keep raw data untouched
- avoid duplicating audio
- preserve close-talk and far-field stream identity
- preserve manual word and segment annotations
- attach meeting and participant metadata
- support later transcript, segmentation, and speaker-label evaluation

## Output files

### 1. `recordings.parquet`
One row per audio stream that is represented in normalization.

This includes:
- individual headset streams such as `Headset-0`
- far-field streams such as `Array1-01` through `Array1-08`

### 2. `segments.parquet`
One row per annotated segment projected onto a specific audio stream.

### 3. `utterances.parquet`
Initially identical in content to `segments.parquet`, kept as a clearer evaluation-facing table.

### 4. `words.parquet`
One row per XML token element of interest.

### 5. `meetings.parquet`
One row per meeting from `meetings.xml`.

### 6. `participants.parquet`
One row per participant from `participants.xml`, when available.

### 7. `normalization_log.csv`
Warnings/errors encountered during normalization.

### 8. `README_normalized.md`
Human-readable record of:
- dataset root
- annotation root used
- stream types used
- normalization decisions
- known issues and counts
- output files written

## Transcript normalization

The raw transcript text is preserved exactly in `text_original`.

A conservative normalized version is written to `text_norm` using:
- lowercasing
- repeated whitespace collapse
- trimming leading/trailing whitespace

No aggressive punctuation stripping is applied by default at this stage.
