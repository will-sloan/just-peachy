# Stage 9 Extended Backend Screening

## Purpose

This package integrates only backends that produced real valid Stage 8 outputs. It builds immutable, environment-aware scenarios; preserves the same controlled-clean items used by Stage 7; provides ASR, VAD/segmentation, embedding-extraction, and composition-only diarization stages; analyzes missing and failed outputs in the denominator; and records separate model-quality, runtime, hardware, and environment comparisons.

It does not evaluate WeNet, pyannote, Falcon, or NeMo in their current blocked states. It does not calculate speaker verification/identification metrics (Stage 10), DER/JER (Stage 11), or a full Cartesian product.

## Inputs

- `runs/extended_backend_qualification/qualification_summary.json` and its source profile evidence;
- `configs/automated_evaluation/extended_qualification_registry.v1.yaml`;
- `configs/automated_evaluation/extended_screening.v1.yaml`;
- the existing component YAML and component catalog;
- `benchmarks/v1/small_source_manifest.parquet`;
- existing Stage 2 conditions and scenario hash contracts;
- an optional Stage 6 merged analysis index and embedding result JSONL.

## Outputs

Planning writes under `benchmarks/stage9/`:

```text
extended_screening_plan.json
extended_screening_plan.sha256
extended_screening_scenarios.jsonl
scenarios_core_cpu.jsonl
scenarios_extended_local.jsonl
scenarios_onnx.jsonl
scenarios_wespeaker.jsonl
scenario_catalogs_by_environment.json
extended_component_comparison_tables.{json,md}
advancement_and_exclusion_report.{json,md}
environment_compatibility_matrix.{json,md}
benchmark_coverage_report.{json,md}
shortlist_manifest.json
```

The real smoke gate writes `runs/extended_screening/real_smoke_matrix.json`, isolated profile evidence, and smoke-scoped handoff reports. Full analysis writes under `automated_runs/<campaign_id>/analysis/extended_screening/`. Vectors may be read from a temporary typed embedding-analysis input but are not copied into the comparison tables or shortlist.

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py extended-screening plan
python run_evaluation.py extended-screening smoke --rerun
```

Create one campaign per compatible environment. These catalogs retain the same global scenario IDs:

```bat
python run_evaluation.py campaign plan --catalog benchmarks\stage9\scenarios_core_cpu.jsonl --campaign-id campaign_stage9_core
python run_evaluation.py campaign plan --catalog benchmarks\stage9\scenarios_extended_local.jsonl --campaign-id campaign_stage9_local
python run_evaluation.py campaign plan --catalog benchmarks\stage9\scenarios_onnx.jsonl --campaign-id campaign_stage9_onnx
python run_evaluation.py campaign plan --catalog benchmarks\stage9\scenarios_wespeaker.jsonl --campaign-id campaign_stage9_wespeaker
```

Run each campaign with its matching interpreter:

```bat
..\..\.venv\Scripts\python.exe run_evaluation.py campaign run --campaign-root automated_runs\campaign_stage9_core --worker-id amir --telemetry
..\..\.stage8-envs\extended-local\Scripts\python.exe run_evaluation.py campaign run --campaign-root automated_runs\campaign_stage9_local --worker-id amir --telemetry
..\..\.stage8-envs\onnx\Scripts\python.exe run_evaluation.py campaign run --campaign-root automated_runs\campaign_stage9_onnx --worker-id amir --telemetry
..\..\.stage8-envs\wespeaker\Scripts\python.exe run_evaluation.py campaign run --campaign-root automated_runs\campaign_stage9_wespeaker --worker-id amir --telemetry
```

After validated transfer/merge creates a Stage 6 analysis index:

```bat
python run_evaluation.py extended-screening analyze ^
  --plan benchmarks\stage9\extended_screening_plan.json ^
  --analysis-index automated_runs\<campaign_id>\analysis\analysis_input_index.json ^
  --embedding-results automated_runs\<campaign_id>\analysis\embedding_extractions.jsonl
```

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool'
& ../../.venv/Scripts/python.exe run_evaluation.py extended-screening plan
& ../../.venv/Scripts/python.exe run_evaluation.py extended-screening smoke --rerun
```

## Targeted interactions

No interaction scenarios are created initially. After one-family screens identify candidates, explicitly name only justified shortlists:

```bat
python run_evaluation.py extended-screening plan ^
  --asr-shortlist faster_whisper ^
  --vad-shortlist webrtc_chunks ^
  --embedding-shortlist resemblyzer
```

The resolver rejects a requested interaction when its active extended components require different isolated profiles. Finalists are repeated only when passed through repeatable `--finalist` arguments.

## Tests

```bat
python -m pytest tests\automated_evaluation\test_stage9_extended_screening.py -q --basetemp artifacts\pytest_stage9
python -m ruff check app\extended_screening tests\automated_evaluation\test_stage9_extended_screening.py
```

The test suite covers catalog alignment, incompatible environments, deterministic scenarios, identical items, missing denominators, Pareto decisions, exclusions, output contracts, and all nine real Stage 8-qualified backends. `--rerun` is the explicit real model gate and never permits implicit model downloads.
