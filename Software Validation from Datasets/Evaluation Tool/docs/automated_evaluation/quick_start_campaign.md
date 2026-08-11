# CPU or CUDA campaign quick start

Choose CPU (`campaign_05_massive_release`) or CUDA (`campaign_06_massive_release_cuda`). Both use Whisper Base and explicit float32 through the same evaluator. Do not launch either massive campaign until Machine B and canary/small/standard gates are approved.

## Common shell variables

Run from the selected clean clone root:

```powershell
$Repo = (Get-Location).Path
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
```

## CPU path

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
$Campaign = Join-Path $Eval 'automated_runs\campaign_05_massive_release'
& $Python "$Eval\run_evaluation.py" campaign validate --campaign-root $Campaign
Get-Content "$Campaign\worker_assignments\release_binding.json"
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1" -PreflightOnly
```

Launch only after preflight says `READY_TO_LAUNCH`:

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1"
```

## CUDA path

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
$Python = Join-Path $Repo '.stage8-envs\core-cuda\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.gpu.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
$Campaign = Join-Path $Eval 'automated_runs\campaign_06_massive_release_cuda'
& $Python "$Eval\run_evaluation.py" campaign validate --campaign-root $Campaign
Get-Content "$Campaign\worker_assignments\release_binding.json"
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1" -PreflightOnly
```

Launch only after preflight says `READY_TO_LAUNCH` and the smoke recorded nonzero VRAM:

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1"
```

## Status, stop, resume, and export

Use the `$Python` and `$Campaign` selected above.

```powershell
& $Python "$Eval\run_evaluation.py" campaign status --campaign-root $Campaign
& $Python "$Eval\run_evaluation.py" campaign stop --campaign-root $Campaign --reason 'operator request'

# CPU resume/export
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1" -ResumeStopped
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_a_results.ps1" -Destination C:\campaign_transfers\campaign_05_massive_release\machine_a

# CUDA resume/export
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1" -ResumeStopped
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_a_gpu_results.ps1" -Destination C:\campaign_transfers\campaign_06_massive_release_cuda\machine_a
```

The wrappers repeat repository, campaign, assignment, profile, model, dataset, RIR, device/dtype, and disk checks. CPU does not require CUDA. CUDA never falls back to CPU.
