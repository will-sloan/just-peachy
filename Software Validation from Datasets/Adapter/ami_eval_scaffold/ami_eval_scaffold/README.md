# AMI Meeting Corpus Evaluation Scaffolding

This package contains the first-stage normalization and documentation files for the **AMI Meeting Corpus**.

## Purpose

The goal is **not** to modify the raw dataset. The goal is to create a structured metadata layer that can later be used by an evaluation tool to:

1. find close-talk and far-field audio streams
2. find the matching manual word and segment annotations
3. attach meeting and participant metadata
4. build normalized utterance, word, and segment tables
5. hand standardized reference data to a later evaluator

## What this package creates

Running `normalize_ami.py` produces:

- `recordings.parquet`
- `utterances.parquet`
- `words.parquet`
- `segments.parquet`
- `meetings.parquet`
- `participants.parquet`
- `normalization_log.csv`
- `README_normalized.md`

These are written into a separate output folder and point back to the original raw audio paths.

## Important design choices

- **Raw data is not changed**
- **Audio is not duplicated**
- `ami_manual_1.6.1` is used as the default annotation root
- `meetings.xml` is treated as the source of truth for agent-to-channel mapping
- `participants.xml` is used to attach participant metadata where available
- segment XML is used as the primary utterance/spurt layer
- word XML is used as the primary token/time layer
- both close-talk headset streams and far-field `Array1-*` streams are represented

## Suggested usage

```bash
python normalize_ami.py ^
  --dataset-root "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Raw Datasets (Not formatted)\AMI Meeting Corpus" ^
  --output-dir "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Normalized Metadata\AMI" ^
  --annotation-root-name "ami_manual_1.6.1"
```

## Files in this scaffold

- `normalize_ami.py` — dataset normalizer
- `text_normalization.py` — conservative transcript normalization helpers
- `schema_defs.py` — column definitions and helpers
- `README_normalized_template.md` — template used to generate dataset-level README
- `normalized_schema.md` — reference schema for the produced tables
- `output_contract_notes.md` — early notes for the later model-output contract
- `requirements.txt` — minimal Python dependencies
