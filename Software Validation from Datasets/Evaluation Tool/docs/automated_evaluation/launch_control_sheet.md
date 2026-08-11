# Launch control sheet — CPU and CUDA campaigns

> Overall verdict: **`NOT_READY_TO_LAUNCH`**. CPU and CUDA are supported execution modes, and Machine A passed separate clean-clone setup, real evaluator smoke, release binding, and complete 20-scenario preflight for both. Machine B and the canary/small/standard scientific gates remain mandatory.

## Frozen identities

| Field | Value |
|---|---|
| Branch | `handoff` |
| CPU campaign | `campaign_05_massive_release`; SHA `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4` |
| CPU catalog | SHA `24AD135F8F2F2450EED78D910727FC63B585958602D28429B3B46B5A1060367E` |
| CUDA campaign | `campaign_06_massive_release_cuda`; SHA `A101D43DD3784EEFD1F8738594A13556DD4F9908C55B96F983FBF6B8F628753D` |
| CUDA catalog | SHA `1FCDEB638470AE55FC0F4EB88DBB77BF7AB8D5B06704DD1CCFCD5D6C3102B511` |
| Large manifest | `BC207E61B82052F06CCB9FFFE038B6DFE7B1C65C21843D08905946114238DE88` |
| Speaker manifest | `A9B0B28F5C7FDEF51215069521215BB78598DB9497E40BDA6C893181F71288D4` |
| CPU runtime | `core-cpu`; `cpu`; `float32`; `.venv` |
| CUDA runtime | `core-cuda`; `cuda:0`; `float32`; `.stage8-envs/core-cuda` |
| Model | Whisper Base; 145,262,807 bytes; SHA-256 `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E` |
| Credentials | None |

Both campaigns are supported. They preserve the same scientific coverage but have distinct scenario IDs because device is result-affecting. Never run one campaign with the other profile.

## Capacity and assignment plan

| Worker | Candidate assignment | Scenarios | Items | Audio | Measured estimate | State |
|---|---|---:|---:|---:|---:|---|
| Machine A | `assignment_01f0cf86b339` | 20 | 12,368 | 16.883 h | 3.40 h; 2.81–5.18 h | CPU and CUDA clean-clone preflights passed 20/20 |
| Machine B | `assignment_ea9976889bd2` | 21 | 13,430 | 16.837 h | 3.40 h; 2.81–5.17 h provisional | Not tested |
| Total | non-overlapping | 41 | 25,798 | 33.720 h | about 3.4 h parallel after both machines qualify | Not authorized |

Estimated result storage is 2.15 GiB for A and 2.30 GiB for B. Keep at least 7.2 GiB free on each worker and at least 15 GiB on the merge machine. Runtime assignment IDs/hashes and the release-binding hash must be read from the materialized `release_binding.json`; they intentionally bind to the exact checked-out commit.

CPU candidate assignments are `assignment_5014479496c7` (A) and `assignment_53642fa92b2a` (B). CUDA candidate assignments are shown in the table. Candidate IDs freeze coverage; final runtime assignment IDs bind to the exact launch commit.

## Choose and prepare one mode

Run from the repository root in PowerShell:

```powershell
$Repo = (Get-Location).Path
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
$Python = Join-Path $Repo '.stage8-envs\core-cuda\Scripts\python.exe'

# CPU
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1" -PreflightOnly

# CUDA
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
$Python = Join-Path $Repo '.stage8-envs\core-cuda\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.gpu.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1" -PreflightOnly
```

Inspect the selected campaign's exact runtime binding, then launch only after `-PreflightOnly` passes:

```powershell
Get-Content "$Eval\automated_runs\<SELECTED_CAMPAIGN>\worker_assignments\release_binding.json"
# CPU
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1"
# CUDA
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1"
```

Machine B uses `launch_campaign_machine_b.ps1` for CPU or `launch_campaign_machine_b_gpu.ps1` for CUDA, only after its own complete preflight passes.

## Control and transfer

CPU:

```powershell
$Python = Join-Path $Repo '.venv\Scripts\python.exe'
$Campaign = Join-Path $Eval 'automated_runs\campaign_05_massive_release'
& $Python "$Eval\run_evaluation.py" campaign status --campaign-root $Campaign
& $Python "$Eval\run_evaluation.py" campaign stop --campaign-root $Campaign --reason 'operator request'
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1" -ResumeStopped
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_a_results.ps1" -Destination C:\campaign_transfers\campaign_05_massive_release\machine_a
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_b_results.ps1" -Destination C:\campaign_transfers\campaign_05_massive_release\machine_b
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\merge_massive_campaign.ps1" -MachineATransfer C:\campaign_transfers\campaign_05_massive_release\machine_a -MachineBTransfer C:\campaign_transfers\campaign_05_massive_release\machine_b
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\analyze_massive_campaign.ps1" -PrerequisiteEvidence C:\approved\standard_gate.json
```

CUDA:

```powershell
& $Python "$Eval\run_evaluation.py" campaign status --campaign-root "$Eval\automated_runs\campaign_06_massive_release_cuda"
& $Python "$Eval\run_evaluation.py" campaign stop --campaign-root "$Eval\automated_runs\campaign_06_massive_release_cuda" --reason 'operator request'
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1" -ResumeStopped
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_a_gpu_results.ps1" -Destination C:\campaign_transfers\campaign_06_massive_release_cuda\machine_a
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\export_machine_b_gpu_results.ps1" -Destination C:\campaign_transfers\campaign_06_massive_release_cuda\machine_b
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\merge_gpu_campaign.ps1" -MachineATransfer C:\campaign_transfers\campaign_06_massive_release_cuda\machine_a -MachineBTransfer C:\campaign_transfers\campaign_06_massive_release_cuda\machine_b
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\analyze_gpu_campaign.ps1" -PrerequisiteEvidence C:\approved\standard_gate.json
```

Expected final count: 41 checksum-valid merged scenarios. Expected report is `automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md` for CPU or `automated_runs/campaign_06_massive_release_cuda/analysis/report/campaign_report.md` for CUDA.

## Manual blockers

1. Install, profile, run a real smoke, and fully preflight Machine B; do not copy Machine A evidence.
2. Confirm both workers materialize the same selected CPU or CUDA campaign at the same approved final commit and retain zero-overlap assignments.
3. Pass and approve the component canary, small, and standard gates for the selected execution mode.
4. Keep Bedroom unresolved and excluded; never substitute ParkingLot or Kitchen.
