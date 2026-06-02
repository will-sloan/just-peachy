# Parallel Execution Runtime Report

## Milestone

M15 - Parallel Batch Execution and GPU Scheduling

## Scheduler Configuration

- Run id: `m15_fake_smoke`
- Serial fallback mode: `False`
- Max workers requested: `2`
- Effective max workers: `2`
- Timeout sec: `5.0000`
- Retry count: `0`
- GPU ids: `['0', '1']`
- Wall duration sec: `0.0807`

## Jobs Launched

| job | status | cuda device | duration sec | attempts | run folder | failure |
| --- | --- | --- | ---: | ---: | --- | --- |
| `fake_job_1` | succeeded | `0` | 0.0788 | 1 | `jobs/fake_job_1_2` |  |
| `fake_job_2` | succeeded | `1` | 0.0776 | 1 | `jobs/fake_job_2_2` |  |

## GPU Assignments And Memory

| job | GPU name | VRAM MB | peak MB | avg utilization | memory headroom | telemetry |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `fake_job_1` | unavailable | n/a | n/a | n/a | n/a | False |
| `fake_job_2` | unavailable | n/a | n/a | n/a | n/a | False |

## Validation Metrics

- Throughput audio hours per wall-clock hour: `743.4035`
- Failure rate under parallel load: `0.0000`
- GPU memory headroom percent: `n/a`
- Speedup vs serial baseline: `n/a`
- Speedup note: serial baseline was not measured for this run.

## Recommended Concurrency

- NVIDIA GeForce RTX 3080: recommended concurrency `1`.
  Use one large ASR or speaker embedding model process per RTX 3080 by default. Increase only for deterministic smoke jobs or small CPU-bound models after confirming at least 20 percent VRAM headroom.

- NVIDIA GeForce RTX 3090: recommended concurrency `2`.
  Use up to two moderate ASR or speaker embedding model processes on RTX 3090 when telemetry confirms at least 20 percent VRAM headroom. Keep one worker for very large models or high beam sizes.


## Commands

- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_job_scheduler.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests/inference_pipeline/test_job_scheduler.py tests/inference_pipeline/test_reporting_framework.py tests/inference_pipeline/test_asr_benchmark.py tests/model_runner/test_external_stub_bridge.py`
- `/Users/billy/Documents/just-peachy/.venv/bin/python -m pytest tests`
- `/Users/billy/Documents/just-peachy/.venv/bin/python scripts/run_parallel_sweep.py --run-id m15_fake_smoke --dry-run-fake-jobs --fake-job-count 2 --gpu-ids 0,1 --max-workers 2 --timeout-sec 5 --telemetry-poll-interval-sec 0.01`

Test results:

- Focused scheduler tests: `6 passed`.
- Adjacent scheduler/reporting/ASR/runner tests: `21 passed`.
- Full Evaluation Tool suite: `136 passed, 1 warning`.

## Reproducibility

- Each job received an isolated run folder and `parallel_job_config.yaml` snapshot.
- Each subprocess received explicit `CUDA_VISIBLE_DEVICES` when a GPU id was assigned.
- The scheduler did not modify `app/model_runner/external_stub.py` or `predictions/utterances.jsonl`.

## Blockers

- Real GPU telemetry was unavailable in this environment; dry/fake jobs can still validate scheduler isolation.

## Incomplete

- Smoke check used fake subprocess jobs, not production ASR or speaker embedding models.
