# Machine A CPU and CUDA readiness

## Verdict

**Both implementations are qualified; separate final clean-clone preflights are required. Global massive launch is not authorized.**

The preserved CPU path uses `.venv`, PyTorch 2.11.0+cpu, `core-cpu`, `cpu`, and `float32`. The CUDA path uses an isolated environment and the evidence below. Each campaign assigns Machine A 20 scenarios, 12,368 item executions, 2,750 unique source files, and 16.882998 repeated audio hours. The authoritative launch verdict for each mode must come from its post-commit clean clone.

## Hardware and runtime evidence

| Field | Value |
|---|---|
| OS | Windows 11 (`10.0.26200`) |
| CPU | 8 physical / 16 logical cores |
| RAM | about 64 GiB |
| GPU | NVIDIA GeForce RTX 3080 |
| VRAM | 10,240 MiB |
| Driver | 610.62 |
| Python | 3.12.7 |
| PyTorch | 2.11.0+cu128 |
| CUDA runtime / cuDNN | 12.8 / 91900 |
| Profile | `core-cuda` |
| Device / dtype | `cuda:0` / `float32` |
| Whisper peak allocator VRAM | 418.89 MiB allocated; 426 MiB reserved |
| Credentials | None |

CPU has no CUDA prerequisite and must report GPU measurements as unavailable rather than fabricating zeros. CUDA requires the exact GPU profile and fails on CPU-only PyTorch.

`torch.cuda.is_available()` was true, the selected device opened successfully, the model parameter device was CUDA, and real evaluator diagnostics showed nonzero allocated and reserved VRAM. See `gpu_qualification_report.md`.

## Capacity

Measured CUDA pipeline RTF gives a 3.40-hour point estimate and 2.81–5.18-hour range for Machine A, including 20 seconds of initialization allowance per scenario. Keep at least 7.2 GiB free. This is a bounded estimate, not a guarantee; desktop GPU activity contaminated device-wide utilization samples. Measure a separate bounded estimate before selecting the CPU campaign.

## CPU clean-clone preflight-only

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels
$Eval = Join-Path (Get-Location) 'Software Validation from Datasets\Evaluation Tool'
$Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a.ps1" -PreflightOnly
```

## CUDA clean-clone preflight-only

From the clean clone root after licensed-data linking:

```powershell
$Repo = (Get-Location).Path
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
$Python = Join-Path $Repo '.stage8-envs\core-cuda\Scripts\python.exe'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.gpu.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_a_gpu.ps1" -PreflightOnly
```

Launch only if the final command returns zero and the report says `READY_TO_LAUNCH` with 20/20 scenarios and no blockers.
