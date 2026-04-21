# CHiME-6 Evaluation Scaffolding

This package contains the first-stage normalization and documentation files for the **CHiME-6** dataset.

## Purpose

The goal is **not** to modify the raw dataset. The goal is to create a structured metadata layer that can later be used by an evaluation tool to:

1. index all session audio streams
2. parse the JSON reference transcripts and speaker segments
3. preserve session-, speaker-, location-, and device-level metadata
4. create normalized text fields for fair transcript comparison
5. prepare the dataset for later transcription / diarization evaluation

## What this package creates

Running `normalize_chime6.py` produces:

- `recordings.parquet`
- `utterances.parquet`
- `segments.parquet`
- `normalization_log.csv`
- `README_normalized.md`

These are written into a separate output folder and point back to the original raw audio paths.

## Important design choices

- **Raw data is not changed**
- **Audio is not duplicated**
- JSON transcripts are treated as the authoritative source for segment timing, speaker labels, and words
- Both **original transcript text** and **normalized transcript text** are stored
- Participant close-mic streams and far-field unit/channel streams are indexed separately
- Train JSON does not include `ref` or `location`, so those fields remain empty there
- Overlap is preserved; segments are not flattened into a single-speaker timeline
- `text_original` preserves bracketed events such as `[laughs]`, `[noise]`, and `[inaudible ...]`
- `text_norm` removes bracketed events, lowercases text, removes punctuation, and collapses whitespace

## Suggested usage

```bash
python normalize_chime6.py ^
  --dataset-root "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CHiME 6" ^
  --output-dir "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Normalized Metadata\CHiME_6"
```
