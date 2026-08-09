# Automated Evaluation Quick Reference

Use these commands from `Software Validation from Datasets\Evaluation Tool` after activating the correct environment. Replace example campaign IDs, worker IDs, scenario IDs, and transfer paths. See [System guide](system_guide.md) for meaning, prerequisites, and limitations.

## Activate and verify core CPU

From the repository root:

```powershell
.\.venv\Scripts\Activate.ps1
python scripts\verify_install.py --profile dev --device cpu --cache-root models/cache --whisper tiny,base,small --require-models
python -m pip check
cd "Software Validation from Datasets\Evaluation Tool"
```

Anaconda Prompt or Command Prompt activation: `.venv\Scripts\activate.bat`.

## List runtime components

```powershell
python -c "from app.inference_pipeline.catalog import ComponentCatalog; c=ComponentCatalog.load(); print(f'{len(c.entries)} components'); [print(f'{e.family:18} {e.name:36} {e.qualification_status}') for e in c.entries]"
```

## Real one-item selected pipeline

```powershell
python run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --runner configured --inference-config configs\inference\live_mic_whisper_base.yaml --run-name base_one_item
```

## Component qualification smokes

```powershell
python run_evaluation.py screening qualify --reference-asr whisper_base
python run_evaluation.py extended-screening smoke
python run_evaluation.py speaker-protocol smoke
python run_evaluation.py diarization smoke
```

Each smoke runs only when its local prerequisites exist. A smoke proves a contract, not scientific superiority.

## Plan and validate a campaign

```powershell
python run_evaluation.py campaign plan --dry-run --tier small --panel controlled_clean --component asr=whisper_base
python run_evaluation.py campaign plan --campaign-id campaign_core01 --tier small --panel controlled_clean --component asr=whisper_base --default-max-retries 1
python run_evaluation.py campaign validate --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign list --campaign-root automated_runs\campaign_core01
```

The CLI filters an approved scenario catalog. Conditions, repetition, device, dtype, and scoring policy are already inside each catalog scenario; they are not ad hoc plan flags.

## Run, monitor, stop, resume, retry

```powershell
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_core01 --worker-id amir
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign stop --campaign-root automated_runs\campaign_core01 --reason "planned shutdown"
python run_evaluation.py campaign resume --campaign-root automated_runs\campaign_core01 --worker-id amir
python run_evaluation.py campaign retry --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\campaign_core01
```

Useful selectors:

```powershell
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_core01 --worker-id amir --scenario-id scenario_8cff9abad3fc
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_core01 --worker-id amir --scenario-range scenario_000000000000:scenario_7fffffffffff --max-scenarios 10
```

## Two-machine assignment

```powershell
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_core01 --worker-id amir --environment-profile core-cpu --partition-index 0 --partition-count 2
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_core01 --worker-id friend --environment-profile core-cpu --partition-index 1 --partition-count 2
python run_evaluation.py campaign validate-assignments --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_amir.yaml --assignment automated_runs\campaign_core01\worker_assignments\worker_friend.yaml
```

Explicit manual selections are also supported:

```powershell
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_core01 --worker-id amir --environment-profile core-cpu --scenario-id scenario_8cff9abad3fc --scenario-id scenario_985b27ddeab0
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_core01 --worker-id friend --environment-profile core-cpu --scenario-range scenario_800000000000:scenario_ffffffffffff --component asr=whisper_base --panel controlled_clean --maximum-scenario-count 25
```

## Prepare, run, and export one worker

```powershell
python run_evaluation.py campaign prepare-worker-copy --campaign-root automated_runs\campaign_core01 --assignment automated_runs\campaign_core01\worker_assignments\worker_amir.yaml --destination C:\worker_campaigns\amir_core01
python run_evaluation.py campaign run-assignment --campaign-root C:\worker_campaigns\amir_core01 --assignment C:\worker_campaigns\amir_core01\worker_assignments\worker_amir.yaml --environment-profile core-cpu
python run_evaluation.py campaign export-results --campaign-root C:\worker_campaigns\amir_core01 --assignment C:\worker_campaigns\amir_core01\worker_assignments\worker_amir.yaml --environment-profile core-cpu --destination C:\transfer\transfer_amir
```

## Validate and merge worker results

```powershell
python run_evaluation.py campaign validate-transfer --campaign-root automated_runs\campaign_core01 --transfer-root C:\transfer\transfer_amir
python run_evaluation.py campaign validate-transfer --campaign-root automated_runs\campaign_core01 --transfer-root C:\transfer\transfer_friend
python run_evaluation.py campaign merge-results --campaign-root automated_runs\campaign_core01 --transfer-root C:\transfer\transfer_amir --transfer-root C:\transfer\transfer_friend
python run_evaluation.py campaign validate-merged --campaign-root automated_runs\campaign_core01
```

## Analyze without rerunning inference

```powershell
python run_evaluation.py analysis index --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis validate --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis coverage --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis run --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis release-status --campaign-root automated_runs\campaign_core01
```

Optional declared paired comparison:

```powershell
python run_evaluation.py analysis run --campaign-root automated_runs\campaign_core01 --comparison scenario_baseline,scenario_candidate,micro_wer,wer
```

Final reports are under:

```text
automated_runs\campaign_core01\analysis\report\campaign_report.md
automated_runs\campaign_core01\analysis\report\coverage_report.md
automated_runs\campaign_core01\analysis\report\release_qualification.json
```

## Installation of isolated optional profiles

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile core-cuda
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile extended-local -DownloadModels
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile onnx -DownloadModels
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile wenet -DownloadModels
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile wespeaker -DownloadModels
```

No scenario may download a model implicitly. Never put credential values in command arguments, YAML, logs, assignments, or result transfers.

## Fast diagnostics

```powershell
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_core01
python run_evaluation.py campaign list --campaign-root automated_runs\campaign_core01 --state failed_retryable --state failed_terminal --state invalid
python run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\campaign_core01
python run_evaluation.py analysis coverage --campaign-root automated_runs\campaign_core01
```

Inspect `status.json`, `logs\events.jsonl`, `logs\errors.jsonl`, `logs\runner.log`, `metrics\failures.parquet`, `resource_logs\resource_summary.json`, `checksums.json`, and `analysis\plot_status.json`. Do not manually edit result artifacts.
