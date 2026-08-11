# Persistent Campaign Executor (Stage 4)

## Purpose

This package turns frozen Stage 2 scenarios into a restart-safe execution queue without changing dataset loading, augmentation, inference, scoring, plotting, reporting, scenario hashes, or Stage 3 artifact contracts. It plans campaign folders, persists transactional state in SQLite, leases one scenario at a time, supervises the existing evaluator in a subprocess, validates final artifacts, and resumes safely after interruption or process restart.

Stage 5 adds an optional telemetry supervisor around this unchanged Stage 4 lifecycle. Campaign CLI runs enable it by default. Stage 6 can feed the executor an independently validated worker assignment, but does not add a network service or shared database. The executor still does not run multiple GPU-heavy scenarios concurrently or download models. The default remains one scenario subprocess at a time on each machine.

## Inputs

- a Stage 2 `resolved_scenarios.jsonl` catalog;
- the Parquet benchmark manifests referenced by those scenarios;
- an Evaluation Tool checkout containing the frozen component configurations and model assets;
- the existing normalized/raw datasets under `Software Validation from Datasets`;
- a short worker ID supplied by the operator;
- optional scenario IDs, an inclusive scenario-ID range, panel/tier filters, or exact `family=name` component filters.

The planner validates every scenario hash and benchmark checksum before creating state. Absolute paths, worker identity, hostname, retry number, and output location never change a global scenario ID.

## Outputs

The planner and executor use the Stage 3 layout:

```text
automated_runs/<campaign_id>/
  campaign_manifest.json
  campaign_manifest.sha256
  benchmark_manifests/
  database/campaign.sqlite
  scenarios/<scenario_id>/
    resolved_scenario.json
    run_config.yaml
    status.json
    predictions/
    metrics/
    resource_logs/
    logs/events.jsonl
    logs/runner.log
    logs/errors.jsonl
    report/
    checksums.json
  audit/
    work/<scenario_id>/attempt_<number>/
    partial_results/<scenario_id>/attempt_<number>/
    telemetry_raw/<scenario_id>/attempt_<number>/
  analysis/
```

`campaign.sqlite` uses `campaign-database.v1`. It stores campaign/scenario identity, deterministic ordinal, detailed state, worker and hostname, attempt count, start/end/heartbeat times, lease owner/expiry, exit code, exception category, concise error, expected artifacts, output completeness, retry eligibility, stop requests, attempts, and machine-readable events.

## State and retry rules

Detailed states are `pending`, `assigned`, `running`, `succeeded`, `succeeded_with_warnings`, `failed_retryable`, `failed_terminal`, `timeout`, `out_of_memory`, `interrupted`, `stopped`, and `invalid`. SQLite `BEGIN IMMEDIATE` transactions enforce lease ownership and state transitions.

- Valid completed artifacts are detected before work is claimed and are skipped.
- A success exit is accepted only after Stage 3 reports `complete`.
- Corrupt or incomplete success output becomes `invalid` and is not overwritten.
- Transient process/I/O failures may retry only while attempts remain.
- Schema, configuration, reference, and scenario-hash failures are terminal.
- OOM retries require an explicit unchanged `failure_policy.oom_retry.safe_retry_action` in the hashed scenario.
- Interrupted/stale work remains resumable even when the ordinary failure retry budget is exhausted.
- Before a retry, partial prediction/metric/report outputs move to `audit/partial_results`; they are never silently deleted.
- Campaign and scenario stop requests are polled while a subprocess runs.
- A deliberate `stopped` state remains terminal until the operator explicitly
  requeues it. Generic `campaign resume` can do this with its documented
  stopped-resume option; distributed operators should use assignment-scoped
  resume so they cannot requeue another worker's stopped work.

## Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"

python run_evaluation.py campaign plan --dry-run
python run_evaluation.py campaign plan --campaign-id campaign_example01 --scenario-id scenario_0123456789ab
python run_evaluation.py campaign validate --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign list --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_example01 --worker-id amir
python run_evaluation.py campaign resume --campaign-root automated_runs\campaign_example01 --worker-id amir
python run_evaluation.py campaign stop --campaign-root automated_runs\campaign_example01 --scenario-id scenario_0123456789ab --reason "operator request"
python run_evaluation.py campaign retry --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\campaign_example01
```

Telemetry is enabled by default for CLI `run` and `resume`. Set the interval or deliberately disable it as follows:

```bat
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_example01 --worker-id amir --telemetry --telemetry-interval-sec 1.0
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_example01 --worker-id amir --no-telemetry
```

Assignment-scoped status reports that worker's total, completed, remaining,
and per-state counts together with the persistent campaign stop flag and reason.
It does not include another worker's scenario counts.

See `app/resource_telemetry/README.md` for inputs, outputs, sensor availability, CUDA timing, privacy, and tests.

Stage 6 assignment-scoped execution uses the same executor and accepts no extra evaluator path:

```bat
python run_evaluation.py campaign run-assignment --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml --environment-profile core-cpu
python run_evaluation.py campaign run-assignment --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml --environment-profile core-cpu --resume-stopped
```

`--resume-stopped` requeues only stopped scenario IDs contained in that exact
validated assignment. It leaves every other worker's states untouched.

See `app/campaign_exchange/README.md` for deterministic selectors, the one-time independent campaign copy, transfer validation, merge behavior, and analysis handoff.

The example scenario ID must be replaced with an ID printed by `campaign plan --dry-run` or `campaign list`.

Select a non-overlapping range or exact component combination:

```bat
python run_evaluation.py campaign plan --campaign-id campaign_worker_a --scenario-range scenario_000000000000:scenario_7fffffffffff --component asr=whisper_base
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_worker_a --worker-id amir --scenario-range scenario_000000000000:scenario_7fffffffffff
```

## PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'

python run_evaluation.py campaign plan --dry-run
python run_evaluation.py campaign status --campaign-root automated_runs/campaign_example01
python run_evaluation.py campaign resume --campaign-root automated_runs/campaign_example01 --worker-id amir
```

## Testing

The Stage 4 suite uses deterministic synthetic subprocesses; it requires no GPU, model, API key, network access, or model download.

```bat
python -m pytest tests\automated_evaluation\test_stage4_campaign_executor.py -q --basetemp artifacts\pytest_stage4
python -m ruff check --no-cache app\campaign_executor app\cli\main.py tests\automated_evaluation\test_stage4_campaign_executor.py
```

The synthetic worker is a contract test utility only. Its output must never be reported as model accuracy, latency, or component qualification evidence.
