# CMU ARCTIC Evaluation Scaffolding

This package contains the first-stage normalization and documentation files for the **CMU ARCTIC** dataset.

## Purpose

The goal is **not** to modify the raw dataset. The goal is to create a small, structured metadata layer that can later be used by an evaluation tool to:

1. find all audio files
2. find the matching reference transcripts
3. attach speaker metadata such as gender and accent
4. create normalized text fields for fair transcript comparison
5. hand standardized inputs to a later evaluator

## What this package creates

Running `normalize_cmu_arctic.py` produces:

- `recordings.parquet`
- `utterances.parquet`
- `normalization_log.csv`
- `README_normalized.md`

These are written into a separate output folder and point back to the original raw audio paths.

## Important design choices

- **Raw data is not changed**
- **Audio is not duplicated**
- **Per-speaker `etc/txt.done.data` is treated as the primary transcript source**
- The global `cmuarctic_data.txt` is treated as optional fallback only
- Both **original transcript text** and **normalized transcript text** are stored
- Speaker metadata such as gender and accent is injected from a maintained YAML file

## Suggested usage

```bash
python normalize_cmu_arctic.py ^
  --dataset-root "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\CMU Arctic" ^
  --output-dir "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Normalized Metadata\CMU_Arctic" ^
  --speaker-metadata "cmu_arctic_speaker_metadata.yaml"
```

## Files in this scaffold

- `normalize_cmu_arctic.py` — dataset normalizer
- `text_normalization.py` — conservative transcript normalization helpers
- `schema_defs.py` — column definitions and helpers
- `cmu_arctic_speaker_metadata.yaml` — speaker gender/accent metadata
- `README_normalized_template.md` — template used to generate dataset-level README
- `normalized_schema.md` — reference schema for the produced tables
- `output_contract_notes.md` — early notes for the later model-output contract
- `requirements.txt` — minimal Python dependencies
