# Machine A CPU and CUDA readiness

## Verdict

**Machine A is technically ready for either supported mode. Separate CPU and CUDA clean clones both passed setup, real evaluator smoke, release binding, and complete assignment preflight. Global massive launch is not authorized.**

The CPU path uses `.venv`, PyTorch 2.11.0+cpu, `core-cpu`, `cpu`, and `float32`. The CUDA path uses `.stage8-envs/core-cuda`, PyTorch 2.11.0+cu128, `core-cuda`, `cuda:0`, and `float32`. Each campaign assigns Machine A 20 scenarios, 12,368 item executions, 2,750 unique source files, and 16.882998 repeated audio hours. The authoritative reports in each clean clone say `READY_TO_LAUNCH` with no blockers.

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

## Final clean-clone evidence

| Check | CPU clone | CUDA clone |
|---|---|---|
| Clone | `just-peachy-launch-a-cpu-final` | `just-peachy-launch-a-gpu` |
| Dependency check | No broken requirements | No broken requirements |
| Real evaluator smoke | 1 selected; 1 prediction; 0 missing; 0 failed; WER 0.25 | 1 selected; 1 prediction; 0 missing; 0 failed; WER 0.25 |
| Resolved execution | `core-cpu`; `cpu`; `float32` | `core-cuda`; `cuda:0`; `float32` |
| Runtime evidence | 2.03 s pipeline time; GPU fields unavailable | 2.35 s pipeline time; 418.89 MiB peak allocated; 426 MiB peak reserved |
| Prediction comparison | Same utterance ID and transcript | Same utterance ID and transcript |
| Release binding | Valid and bound to checked-out commit | Valid and bound to checked-out commit |
| Full Machine A preflight | `READY_TO_LAUNCH`; 20/20; 12,368 items | `READY_TO_LAUNCH`; 20/20; 12,368 items |

The one-item ordinary evaluator report does not emit CER, so no CER value is inferred for this smoke. The separate fixed five-item qualification reports WER 0.1463414634 and CER 0.1444444444 for CPU, CUDA float32, and CUDA float16 with identical transcripts.

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

These commands passed in the final validation clones. Rerun the matching command immediately before launch; proceed only if it returns zero and still reports `READY_TO_LAUNCH` with 20/20 scenarios and no blockers.
