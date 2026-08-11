# Machine B CPU or CUDA setup

Machine B is **not yet qualified**. It may select CPU or CUDA, but its assignment and the other worker must use the matching frozen campaign. Do not copy Machine A's profile or infer readiness from the 24 GB VRAM specification.

## Required sequence

1. Clone the repository and check out the exact final launch commit on branch `handoff`.
2. Make the licensed dataset and approved RIR paths available using the same local junction/link layout; do not commit raw data.
3. From the clone root, choose one setup command:

```powershell
# CPU
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels
$Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'

# CUDA
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
$Python = Join-Path (Get-Location) '.stage8-envs\core-cuda\Scripts\python.exe'

& $Python -m pip check
nvidia-smi
```

4. For CPU, confirm PyTorch `+cpu`, device `cpu`, dtype `float32`, and no CUDA requirement. For CUDA, confirm CUDA-enabled PyTorch, `torch.cuda.is_available() == True`, the actual NVIDIA GPU/UUID and VRAM. In both modes verify the exact Whisper Base checksum.
5. Materialize exactly one matching committed campaign (`launch_package.v1.yaml` for CPU or `launch_package.gpu.v1.yaml` for CUDA):

```powershell
$Repo = (Get-Location).Path
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
# CPU
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit

# CUDA (use instead of the CPU command)
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\launch_package.gpu.v1.yaml" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
```

6. Run a one-item real evaluator smoke. CPU must record `cpu`; CUDA must record `cuda:0` and nonzero allocator VRAM.
7. Generate the Machine B profile and run the complete assignment preflight using the same commands as `machine_a_readiness.md`, replacing `machine_a` with `machine_b` and selecting `machine_b.yaml`.
8. Verify 21/21 scenarios, 13,430 items, and no blockers.
9. First exercise `-PreflightOnly`, then launch the matching wrapper:

```powershell
# CPU
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_b.ps1" -PreflightOnly
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_b.ps1"
# CUDA
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_b_gpu.ps1" -PreflightOnly
powershell -ExecutionPolicy Bypass -File "$Eval\scripts\launch_campaign_machine_b_gpu.ps1"
```

## Compatibility rule

For the CPU campaign, Machine B must use `core-cpu`, `cpu`, and `float32`. For the CUDA campaign, the second GPU may be a different model and may have 24 GB VRAM; its hardware identity is recorded as environment metadata, while execution remains `core-cuda`, `cuda:0`, `float32`, Whisper Base with the exact hash, one scenario at a time. Float16, different model assets, or changed runtime settings require new scenario and assignment identities. Mixed CPU/GPU execution under one campaign is prohibited.

## Estimated load

Machine B has 21 scenarios, 13,430 item executions, and 16.837 repeated audio hours in either coverage-equivalent campaign. The CUDA provisional estimate based on Machine A is 3.40 hours, range 2.81–5.17 hours. Measure a CPU estimate when selecting CPU, and replace either provisional estimate with Machine B's own bounded benchmark before launch. Reserve at least 7.3 GiB free disk.
