# Stage 7 Core Component Screening

## Purpose

This package qualifies and screens only the current core speech stack: full-record input, Energy VAD, Silero VAD, VADChunker, Whisper Tiny/Base/Small, SpeechBrain ECAPA extraction, and the cosine matcher's contract/composition. Whisper Base is the VAD/segmentation reference ASR. It does not implement Stage 10 speaker verification, identification, calibration, EER, FAR, FRR, or unknown-rejection scoring.

The package reuses the frozen Stage 2 manifest and scenario hash, the Stage 1 resolver/runner, Stage 4 executor, Stage 5 telemetry, and Stage 6 merged analysis index. It does not define a competing component format, alter source component YAML, download models, or create a full Cartesian product.

## Inputs

- `benchmarks/v1/small_source_manifest.parquet` and `manifest_summary.json`;
- existing component YAML and `configs/automated_evaluation/component_registry.v1.yaml`;
- `configs/automated_evaluation/core_screening.v1.yaml`;
- local Tiny, Base, Small, Silero, and ECAPA assets for real qualification;
- one real speech WAV for Stages A/E;
- a Stage 6 `analysis/analysis_input_index.json` for campaign analysis.

## Outputs

Planning writes `benchmarks/stage7/core_screening_plan.json`, its SHA-256 sidecar, `screening_scenarios.jsonl`, and a generated README. The initial catalog has only Stage B/C work. Stage D scenarios appear only after one or two segmentation candidates are explicitly shortlisted. Three-repeat final scenarios appear only after finalists are explicitly declared.

Qualification writes `runs/component_qualification/stage7_core_cpu.json`. Every component is recorded as `qualified`, `unavailable`, or `failed`, with catalog/model/config identity, repeated-smoke evidence, and an isolated reason. Missing assets are unavailable, never downloaded.

Analysis writes:

```text
automated_runs/<campaign_id>/analysis/core_screening/
  screening_analysis.json
  screening_analysis.md
```

Missing and failed outputs use an empty hypothesis for primary WER/CER while remaining explicit reliability counts. Metrics that lack required references or output contracts are listed as unsupported and are not emitted.

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py screening plan
python run_evaluation.py screening qualify --repetitions 2
```

After Stage C analysis selects one or two segmenters, create only the targeted Stage D catalog:

```bat
python run_evaluation.py screening plan --segmentation-shortlist energy_chunks --segmentation-shortlist silero_chunks
```

After Stage D selects finalists, request the three-repeat validation catalog:

```bat
python run_evaluation.py screening plan --segmentation-shortlist energy_chunks --finalist energy_chunks__whisper_base
```

Analyze independently merged results:

```bat
python run_evaluation.py screening analyze ^
  --plan benchmarks\stage7\core_screening_plan.json ^
  --analysis-index automated_runs\<campaign_id>\analysis\analysis_input_index.json ^
  --qualification runs\component_qualification\stage7_core_cpu.json
```

The default qualification audio is the already available CMU Arctic `arctic_b0476.wav`. Pass `--audio` to select another local speech WAV and `--degraded-audio` to add a valid clean/degraded ECAPA drift pair.
Whisper Base is read from the versioned protocol and is the default; a deliberate qualification-only cross-check can select another scoped model with `--reference-asr whisper_tiny` or `--reference-asr whisper_small`.

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'

python run_evaluation.py screening plan
python run_evaluation.py screening qualify --repetitions 2
```

## Run tests

```bat
python -m pytest tests\automated_evaluation\test_stage7_core_screening.py -q --basetemp artifacts\pytest_stage7
python -m ruff check app\core_screening tests\automated_evaluation\test_stage7_core_screening.py
```

The real qualification test skips only when its package or local model/audio assets are absent. It never requests network access.

## Scientific sequence

1. Stage A records availability, contract validity, model loading, device placement, one valid output, identities, and repeated execution.
2. Stage B compares Tiny/Base/Small with full-record input and no speaker processing on identical small controlled-clean items and conditions.
3. Stage C fixes Whisper Base and varies full record, Energy observation, Energy chunks, Silero observation, and Silero chunks.
4. Stage D crosses only one or two declared Stage C segmenters with qualified Whisper models.
5. Stage E qualifies ECAPA on identical segments; cosine matching is contract/composition only.
6. Declared finalists receive three repetitions. Advancement uses hard reliability gates, Pareto dominance, and a deterministic diverse cap; a slower candidate survives when it offers a non-dominated accuracy, reliability, or robustness tradeoff.
