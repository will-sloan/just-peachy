# LibriSpeech Evaluation Scaffolding

This package contains the first-stage normalization and documentation files for the **LibriSpeech** dataset.

## Purpose

The goal is **not** to modify the raw dataset. The goal is to create a small, structured metadata layer that can later be used by an evaluation tool to:

1. find all audio files
2. find the matching reference transcripts
3. attach speaker, chapter, and book metadata
4. create normalized text fields for fair transcript comparison
5. hand standardized inputs to a later evaluator

## What this package creates

Running `normalize_librispeech.py` produces:

- `recordings.parquet`
- `utterances.parquet`
- `speakers.parquet`
- `chapters.parquet`
- `books.parquet`
- `normalization_log.csv`
- `README_normalized.md`

These are written into a separate output folder and point back to the original raw audio paths.

## Important design choices

- **Raw data is not changed**
- **Audio is not duplicated**
- Only the seven standard ASR splits are included by default
- Auxiliary/source folders are excluded from the first normalization pass
- Both **original transcript text** and **normalized transcript text** are stored
- Speaker/chapter/book metadata is joined from `SPEAKERS.TXT`, `CHAPTERS.TXT`, and `BOOKS.TXT`

## Suggested usage

```bash
python normalize_librispeech.py ^
  --dataset-root "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\LibreSpeech" ^
  --output-dir "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Normalized Metadata\LibriSpeech"
```

## Files in this scaffold

- `normalize_librispeech.py` — dataset normalizer
- `text_normalization.py` — conservative transcript normalization helpers
- `schema_defs.py` — column definitions and helpers
- `README_normalized_template.md` — template used to generate dataset-level README
- `normalized_schema.md` — reference schema for the produced tables
- `output_contract_notes.md` — early notes for the later model-output contract
- `requirements.txt` — minimal Python dependencies
