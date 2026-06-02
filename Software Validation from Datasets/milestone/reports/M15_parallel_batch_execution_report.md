# M15 - Parallel Batch Execution and GPU Scheduling

## High-Level Summary

M15 adds a small subprocess-based scheduler for isolated parallel evaluation
jobs. Each job runs in its own process, receives its own run folder, writes a
`parallel_job_config.yaml` snapshot, and gets an explicit
`CUDA_VISIBLE_DEVICES` assignment when a GPU id is configured.

The implementation keeps the existing Evaluation Tool runner contract intact.
No changes were made to `app/model_runner/external_stub.py` or to the required
`predictions/utterances.jsonl` schema.

## Files Added Or Updated

- `Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/runtime/gpu.py`
- `Software Validation from Datasets/Evaluation Tool/app/inference_pipeline/runtime/job_scheduler.py`
- `Software Validation from Datasets/Evaluation Tool/scripts/run_parallel_sweep.py`
- `Software Validation from Datasets/Evaluation Tool/configs/runtime/rtx3080.yaml`
- `Software Validation from Datasets/Evaluation Tool/configs/runtime/rtx3090.yaml`
- `Software Validation from Datasets/Evaluation Tool/configs/sweeps/parallel_asr_eval.yaml`
- `Software Validation from Datasets/Evaluation Tool/tests/inference_pipeline/test_job_scheduler.py`
- `Software Validation from Datasets/Evaluation Tool/reports/runtime/parallel_execution_m15_fake_smoke.md`
- `Software Validation from Datasets/milestone/reports/M15_parallel_batch_execution_report.md`

## What Changed

- Added best-effort `nvidia-smi` GPU discovery and telemetry helpers.
- Added injectable fake telemetry support for tests.
- Added a scheduler with one subprocess per job, unique run folders, explicit
  CUDA assignment, configurable max workers, timeout, retry count, and serial
  fallback mode.
- Added per-job stdout/stderr logs, job config snapshots, JSON scheduler
  results, CSV job summaries, and Markdown runtime reporting.
- Added RTX 3080 and RTX 3090 runtime profiles with conservative recommended
  concurrency.
- Added a parallel ASR sweep scaffold over the same CMU Arctic subset.
- Added a dry fake-job smoke path for environments without CUDA or model
  assets.

## Runtime Report

Required runtime report:

`Software Validation from Datasets/Evaluation Tool/reports/runtime/parallel_execution_m15_fake_smoke.md`

The report includes scheduler configuration, job folders, GPU assignments,
durations, failures/retries, throughput, failure rate, memory headroom, speedup
status, and recommended RTX 3080/RTX 3090 concurrency.

## Tests And Smoke Checks

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_job_scheduler.py
```

Result: `6 passed`.

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_job_scheduler.py tests/inference_pipeline/test_reporting_framework.py tests/inference_pipeline/test_asr_benchmark.py tests/model_runner/test_external_stub_bridge.py
```

Result: `21 passed`.

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests
```

Result: `136 passed, 1 warning`. The warning is the existing Torch JIT
deprecation warning under Python 3.14.

```bash
cd "/Users/billy/Documents/just-peachy/Software Validation from Datasets/Evaluation Tool"
/Users/billy/Documents/just-peachy/.venv/bin/python scripts/run_parallel_sweep.py --run-id m15_fake_smoke --dry-run-fake-jobs --fake-job-count 2 --gpu-ids 0,1 --max-workers 2 --timeout-sec 5 --telemetry-poll-interval-sec 0.01
```

Result:

- Scheduler result:
  `runs/parallel_sweeps/m15_fake_smoke/parallel_scheduler_result.json`
- Runtime report:
  `reports/runtime/parallel_execution_m15_fake_smoke.md`
- Failure rate: `0.0000`

## Validation Metrics From Smoke Check

- Two small jobs ran independently in isolated folders.
- Both jobs received explicit CUDA assignments: `0` and `1`.
- Failure rate: `0.0000`.
- Throughput was computed from fake job audio duration and wall-clock time.
- GPU memory headroom was unavailable because real GPU telemetry was not
  available in this environment.
- Speedup vs serial baseline was not measured for the fake-job smoke check.

## Recommended Concurrency

- RTX 3080: recommended concurrency `1` for large ASR or speaker embedding
  jobs, increasing only after confirming at least 20 percent VRAM headroom.
- RTX 3090: recommended concurrency `2` for moderate jobs when telemetry shows
  sufficient headroom; keep `1` for very large models or high beam sizes.

## Remaining Incomplete Or Blocked

- Real RTX 3080/RTX 3090 execution was not validated in this environment.
- `nvidia-smi` telemetry was unavailable locally, so GPU name, VRAM, utilization,
  and memory headroom are reported as unavailable in the smoke report.
- The smoke check used fake subprocess jobs rather than production ASR or
  speaker embedding models to avoid requiring model downloads or CUDA hardware.
