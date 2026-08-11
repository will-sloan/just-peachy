# Two-machine CPU/CUDA launch runbook

## Gate zero

First select one campaign mode for both assignments: CPU or CUDA. Do not mix profiles under one campaign. Do not start until both complete preflights return `READY_TO_LAUNCH`, both checkouts use the same final commit/release binding, and canary/small/standard approval exists.

## Shared frozen work

| Machine | Scenarios | Items | Repeated audio | CPU candidate | CUDA candidate |
|---|---:|---:|---:|---|---|
| A | 20 | 12,368 | 16.883 h | `assignment_5014479496c7` | `assignment_01f0cf86b339` |
| B | 21 | 13,430 | 16.837 h | `assignment_53642fa92b2a` | `assignment_ea9976889bd2` |

Candidate IDs document the coverage split. After `--bind-current-commit`, use the exact runtime IDs/hashes in each clone's `release_binding.json`. The global scenario IDs remain unchanged and assignments must have zero overlap.

## Setup on both machines — CPU

```powershell
Set-Location <CLONE_ROOT>
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels
$Repo = (Get-Location).Path
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
```

## Setup on both machines — CUDA (use instead)

```powershell
Set-Location <CLONE_ROOT>
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
$Repo = (Get-Location).Path
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
$Python = Join-Path $Repo '.stage8-envs\core-cuda\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.gpu.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
```

Set `$Python` and the launch package to the selected mode. Make the same licensed source paths and exact Dining/Restaurant RIR files available locally. Run each matching wrapper with `-PreflightOnly`. Compare both `release_binding.json` files before launch.

## Launch — CPU

After both CPU preflights pass:

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1"
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_b.ps1"
```

## Launch — CUDA (use instead)

After both CUDA preflights pass:

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1"
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_b_gpu.ps1"
```

## Status, controlled stop, and assignment-scoped resume

```powershell
# CPU selection:
$Campaign = Join-Path $Eval 'automated_runs\campaign_05_massive_release'
# For CUDA, replace the previous line with:
# $Campaign = Join-Path $Eval 'automated_runs\campaign_06_massive_release_cuda'
& $Python "$Eval\run_evaluation.py" campaign status --campaign-root $Campaign
& $Python "$Eval\run_evaluation.py" campaign stop --campaign-root $Campaign --reason 'operator request'
```

Resume on A or B with its own wrapper and `-ResumeStopped`. Completed checksum-valid scenarios are skipped; partial artifacts are preserved; the other worker's assignment is not claimed.

## Export and transfer

CPU:

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_a_results.ps1" -Destination C:\campaign_transfers\campaign_05_massive_release\machine_a
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_b_results.ps1" -Destination C:\campaign_transfers\campaign_05_massive_release\machine_b
```

CUDA (use instead):

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_a_gpu_results.ps1" -Destination C:\campaign_transfers\campaign_06_massive_release_cuda\machine_a
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_b_gpu_results.ps1" -Destination C:\campaign_transfers\campaign_06_massive_release_cuda\machine_b
```

Transfer those two folders intact. Do not move the live campaign database or share SQLite over a network drive.

## Coordinator merge and analysis

CPU:

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\merge_massive_campaign.ps1" -MachineATransfer C:\campaign_transfers\campaign_05_massive_release\machine_a -MachineBTransfer C:\campaign_transfers\campaign_05_massive_release\machine_b
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\analyze_massive_campaign.ps1" -PrerequisiteEvidence C:\approved\standard_gate.json
```

CUDA (use instead):

```powershell
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\merge_gpu_campaign.ps1" -MachineATransfer C:\campaign_transfers\campaign_06_massive_release_cuda\machine_a -MachineBTransfer C:\campaign_transfers\campaign_06_massive_release_cuda\machine_b
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\analyze_gpu_campaign.ps1" -PrerequisiteEvidence C:\approved\standard_gate.json
```

Merge must report 41 checksum-valid, globally unique scenarios and no conflicting duplicate. The final report is under the selected campaign's `analysis/report/campaign_report.md`.
