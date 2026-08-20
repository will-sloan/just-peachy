# Common Voice speaker-breadth tooling

## Purpose

This package constructs, validates, plans, and collects the additive Common Voice English 60+ speaker-breadth confirmation study. It freezes one model-independent speaker/audio cohort and feeds it to the existing Stage 10 extraction, scoring, calibration, identification, Unknown-rejection, and bootstrap implementation.

It does not select models, run diarization, tune enrollment duration, or download data.

## Inputs

- `JP_DATA_ROOT` (optional): directory containing `Raw Datasets (Not formatted)`. When unset, the repository's `Software Validation from Datasets` folder is used.
- Local release: `Raw Datasets (Not formatted)/Common Voice/cv-corpus-26.0-2026-06-12`.
- Selection policy: `configs/automated_evaluation/speaker_breadth_commonvoice_60plus.v1.yaml`.
- Runtime `-Backends`: the 2–3 finalist IDs chosen after the six-model Stage 10 analysis.

The wrapper resolves backend environments from the existing Stage 10 policy and extension registry. It uses `.venv` for `core-cpu` and `.stage8-envs/<profile>` for isolated profiles.
When an explicit configuration path is outside the Evaluation Tool, provenance
records its absolute path; repository configurations remain portable relative
paths.

## Run from Anaconda Prompt or PowerShell

Open Anaconda Prompt or PowerShell, then:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy"

$Wrapper = "Software Validation from Datasets\Evaluation Tool\scripts\run_speaker_breadth_commonvoice.ps1"

& $Wrapper -Action Prepare

& $Wrapper -Action Validate

& $Wrapper -Action Plan -Backends @(
  "PLACEHOLDER_FINALIST_1"
  "PLACEHOLDER_FINALIST_2"
)
```

After finalist selection, replace the placeholders and use `-Action Run`. The wrapper processes backends sequentially, reuses valid evidence, preserves invalid partial results before retrying, and isolates each backend's output. Use `-Action Status` to inspect progress and `-Action Collect` to build the compact analysis package.

## Outputs

- Frozen protocol: `benchmarks/speaker_breadth/commonvoice_60plus_v1`.
- Runtime evidence by default: `%USERPROFILE%/JustPeachyResults/speaker_breadth/commonvoice_60plus_v1/<protocol_id>/<backend>`.
- Compact collection by default: `%USERPROFILE%/JustPeachyResearchSummaries/speaker_breadth_commonvoice_60plus_<protocol_id>`.

The frozen package contains Stage 10-compatible Parquet manifests plus source selection, speaker inventory, age/covariate coverage, duration, decoded-audio validation, leakage, provenance, and checksums. It contains no raw audio, raw Common Voice client IDs, or model assets.

## Tests

From the Evaluation Tool directory:

```powershell
..\..\.venv\Scripts\python.exe -m pytest `
  tests\automated_evaluation\test_speaker_breadth_commonvoice.py -q `
  --basetemp=.pytest-speaker-breadth
```
