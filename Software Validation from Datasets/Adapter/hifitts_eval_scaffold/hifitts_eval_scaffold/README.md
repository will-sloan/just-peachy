# Hi Fi TTS Evaluation Scaffolding

This package contains the first-stage normalization and documentation files for the **Hi Fi TTS** dataset.

## Purpose

The goal is **not** to modify the raw dataset. The goal is to create a small, structured metadata layer that can later be used by an evaluation tool to:

1. find all audio files
2. find the matching reference transcripts from the JSONL manifests
3. attach reader, split, quality, and book metadata
4. preserve all three transcript variants
5. create conservative normalized comparison text
6. hand standardized inputs to a later evaluator

## What this package creates

Running `normalize_hifitts.py` produces:

- `recordings.parquet`
- `utterances.parquet`
- `readers.parquet`
- `reader_books.parquet`
- `book_bandwidth.parquet`
- `normalization_log.csv`
- `README_normalized.md`

These are written into a separate output folder and point back to the original raw audio paths.

## Important design choices

- **Raw data is not changed**
- **Audio is not duplicated**
- The manifest JSONL rows are treated as the primary source of truth
- All three transcript fields are preserved:
  - `text`
  - `text_no_preprocessing`
  - `text_normalized`
- Reader name/gender/hours metadata is injected from a maintained YAML file
- Book and bandwidth metadata are joined from the provided text/tsv files

## Suggested usage

```bash
python normalize_hifitts.py ^
  --dataset-root "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\Hi Fi TTS\hi_fi_tts_v0" ^
  --output-dir "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Normalized Metadata\HiFiTTS" ^
  --reader-metadata ".\hifitts_reader_metadata.yaml"
```

## Files in this scaffold

- `normalize_hifitts.py` — dataset normalizer
- `text_normalization.py` — conservative transcript normalization helpers
- `schema_defs.py` — column definitions and helpers
- `hifitts_reader_metadata.yaml` — reader name/gender/hour metadata
- `README_normalized_template.md` — template used to generate dataset-level README
- `normalized_schema.md` — reference schema for the produced tables
- `output_contract_notes.md` — early notes for the later model-output contract
- `requirements.txt` — minimal Python dependencies
