# VOiCES DevKit Evaluation Scaffolding

This package contains the first-stage normalization and documentation files for the **VOiCES DevKit** dataset.

## Purpose

The goal is **not** to modify the raw dataset. The goal is to create a small, structured metadata layer that can later be used by an evaluation tool to:

1. find all distant/noisy evaluation WAVs
2. find the matching clean source WAVs
3. find the matching reference transcript
4. attach room / distractor / microphone / angle / speaker metadata
5. join condition and quality metadata for grouped evaluation
6. hand standardized inputs to a later evaluator

## What this package creates

Running `normalize_voices.py` produces:

- `recordings.parquet`
- `utterances.parquet`
- `conditions.parquet`
- `speakers.parquet`
- `source_map.parquet`
- `normalization_log.csv`
- `README_normalized.md`

These are written into a separate output folder and point back to the original raw audio paths.

## Important design choices

- **Raw data is not changed**
- **Audio is not duplicated**
- `references/train_index.csv` and `references/test_index.csv` are treated as the primary manifest
- `query_name` is treated as the stable key for joins
- `filename_transcripts` is treated as optional fallback / consistency check, not the primary manifest
- `distances.csv` and `quality_metrics.csv` are joined as condition metadata
- `time_values.csv` is joined cautiously because it contains a duplicate `index,index` header
- Speaker IDs are normalized to zero-padded 4-digit strings for reliable joins

## Suggested usage

```bash
python normalize_voices.py ^
  --dataset-root "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\VOiCES" ^
  --output-dir "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Normalized Metadata\VOiCES"
```

## Files in this scaffold

- `normalize_voices.py` — dataset normalizer
- `schema_defs.py` — column definitions and helpers
- `text_normalization.py` — conservative transcript normalization helpers
- `normalized_schema.md` — reference schema for the produced tables
- `README_normalized_template.md` — template used to generate dataset-level README
- `output_contract_notes.md` — early notes for the later model-output contract
- `requirements.txt` — minimal Python dependencies
