# Resource Telemetry and Component Timing (Stage 5)

## Purpose

This package adds opt-in measurement around the existing Stage 4 scenario subprocess and existing inference/scoring/reporting boundaries. It does not alter model inputs, model outputs, prediction normalization, scores, scenario hashes, retry identity, or component algorithms. Campaign CLI runs enable telemetry by default and still execute one scenario subprocess at a time.

CPU/process telemetry uses `psutil`. GPU telemetry uses optional NVIDIA NVML bindings from the inference profile. CPU collection remains functional when NVIDIA tooling is absent; unsupported fields are null and explained in `availability.json`. CUDA event timing runs only when the selected scenario uses CUDA and the active Torch build exposes CUDA.

## Inputs

- a Stage 4 planned campaign and frozen `resolved_scenario.json`;
- campaign, scenario, attempt, worker, host, and child PID identity;
- the scenario resource policy and selected CPU/CUDA device;
- an optional sampling interval, default `1.0` second;
- component boundaries emitted by the existing augmentation, pipeline, model-adapter, prediction, scoring, plotting, and reporting code.

Absolute audio/model/output paths, environment variables, API keys, and credential values are never written to shared telemetry artifacts.

## Outputs

Each successful telemetry-enabled attempt publishes these atomic, checksummed `artifact-registry.v2` files:

```text
scenarios/<scenario_id>/resource_logs/
  resource_usage.parquet
  component_spans.jsonl
  resource_summary.json
  availability.json
```

`resource_usage.parquet` contains typed timestamp, process tree, CPU, RAM, disk, free-space, GPU, VRAM, temperature, power, clock, throttle, active-component, and sampling-gap fields. `component_spans.jsonl` distinguishes cold initialization, warm inference, per-item work, scenario post-processing, and total scenario time. `resource_summary.json` contains counts, peaks, means, p50/p95/p99 values, phase/component summaries, and warnings. `availability.json` records source and reason for every unsupported sensor family.

Raw child span coordination files live under `automated_runs/<campaign_id>/audit/telemetry_raw/` and are not campaign exchange artifacts.

## Install or update the pinned environment

In Anaconda Prompt or Command Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
python -m pip install -r requirements\dev.txt
```

`requirements/core.txt` pins `psutil`; `requirements/inference.txt` pins `nvidia-ml-py`. The latter provides telemetry bindings only and does not install a CUDA-enabled Torch build.

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py campaign plan --campaign-id campaign_example01 --scenario-id <scenario_id>
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_example01 --worker-id amir --telemetry --telemetry-interval-sec 1.0
python run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\campaign_example01
```

Use `--no-telemetry` only for a deliberate uninstrumented comparison. It does not permit parallel GPU scenarios.

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python run_evaluation.py campaign run --campaign-root automated_runs/campaign_example01 --worker-id amir --telemetry --telemetry-interval-sec 1.0
```

## Tests and qualification

```bat
python -m pytest tests\automated_evaluation\test_stage5_resource_telemetry.py -q --basetemp artifacts\pytest_stage5
python -m pytest tests\automated_evaluation\test_stage3_artifact_contracts.py tests\automated_evaluation\test_stage4_campaign_executor.py -q --basetemp artifacts\pytest_stage5_regression
```

The Stage 5 suite includes fake CPU/GPU providers, missing-NVML behavior, process-tree sampling, gaps, peaks, nested/overlapping spans, atomic artifact publication, executor integration, prediction invariance, a real CPU smoke, and a CUDA-event smoke that skips unless CUDA is available to Torch.

The current development environment uses CPU-only Torch. Preserve it. Build and pin the separately approved CUDA environment before running the CUDA smoke; do not replace the CPU environment in place.
