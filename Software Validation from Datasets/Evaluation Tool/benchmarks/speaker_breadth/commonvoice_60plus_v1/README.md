# Common Voice 60+ speaker breadth v1

This is a frozen, model-independent source protocol for breadth confirmation of Stage 10 speaker-recognition finalists. It changes the source population and audio only; Stage 10 enrollment, cosine scoring, backend-specific calibration, identification, Unknown rejection, and bootstrap methodology remain unchanged.

## Inputs

- Logical data root: `Raw Datasets (Not formatted)/Common Voice/cv-corpus-26.0-2026-06-12` under `JP_DATA_ROOT`.
- Canonical metadata: `prepared/en/metadata/original/validated.tsv`.
- Locale: `en`.
- Included self-reported age categories: `sixties`, `seventies`, `eighties`, `nineties`.
- Selection seed: `3800`.

## Frozen design

- Known speakers: 272 (5 enrollment, 10 calibration, 15 evaluation clips each).
- Calibration Unknown speakers: 48 (25 clips each).
- Evaluation Unknown speakers: 93 (25 clips each).
- Enrollment clips: 1360.
- Calibration probes: 3920.
- Evaluation probes: 6405.
- Total clips: 11685.

All selected source clips and within-speaker transcripts are unique. Raw Common Voice client IDs are never published. `source_selection.tsv` joins every Stage 10 `item_id` to age and optional metadata diagnostics.

## Run from Anaconda Prompt or PowerShell

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_breadth_commonvoice.ps1" -Action Plan -Backends @("PLACEHOLDER_FINALIST_1")
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_breadth_commonvoice.ps1" -Action Validate
```

Run only after Stage 10 finalist selection. Pass the chosen backends at runtime; the wrapper selects each backend's qualified environment and runs them sequentially. Use `-Action Collect` afterward for the compact analysis package.

## Outputs

The Parquet files are consumed unchanged by `speaker-protocol extract`, `evaluate`, and `validate`. TSV/JSON files contain selection, speaker inventory, age/covariate coverage, durations, source provenance, decoded-audio validation, and leakage evidence. Raw audio and model assets are not included.

This package is frozen. Do not regenerate it in place; use a new protocol version for a result-affecting change.
