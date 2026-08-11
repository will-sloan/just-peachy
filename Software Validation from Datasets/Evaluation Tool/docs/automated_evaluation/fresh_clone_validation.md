# Fresh CPU and CUDA clone validation

Use two new clones, for example `just-peachy-launch-a-cpu-final` and `just-peachy-launch-a-gpu`. Preserve the historical `just-peachy-launch-a`. Do not copy `.venv` or `.stage8-envs` between checkouts.

## Procedure

```powershell
# Create the CPU clone
git clone <repository-url-or-approved-local-source> C:\Users\amiri\Documents\GitHub\just-peachy-launch-a-cpu-final
Set-Location C:\Users\amiri\Documents\GitHub\just-peachy-launch-a-cpu-final
git switch handoff
git checkout <FINAL_LAUNCH_COMMIT>
git status --short
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cpu -InstallFFmpeg -DownloadModels
$Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'

# Create the CUDA clone in a separate shell
git clone <repository-url-or-approved-local-source> C:\Users\amiri\Documents\GitHub\just-peachy-launch-a-gpu
Set-Location C:\Users\amiri\Documents\GitHub\just-peachy-launch-a-gpu
git switch handoff
git checkout <FINAL_LAUNCH_COMMIT>
git status --short
powershell -ExecutionPolicy Bypass -File scripts\prepare_execution_mode.ps1 -Mode cuda -InstallFFmpeg -DownloadModels
$Python = Join-Path (Get-Location) '.stage8-envs\core-cuda\Scripts\python.exe'

& $Python -m pip check
```

Make licensed datasets and the MIT RIR directory available through approved local directory junctions or equivalent read-only links. Never copy raw audio into Git or campaign output folders. Verify `ffmpeg -version` in the same shell.

```powershell
$Repo = (Get-Location).Path
$Eval = Join-Path $Repo 'Software Validation from Datasets\Evaluation Tool'
& $Python "$Eval\scripts\materialize_launch_campaign.py" --launch-package "$Eval\configs\automated_evaluation\<SELECTED_LAUNCH_PACKAGE>" --automated-runs-root "$Eval\automated_runs" --bind-current-commit
Get-Content "$Eval\automated_runs\<SELECTED_CAMPAIGN>\worker_assignments\release_binding.json"
```

The binding must name the checked-out final commit. Run one real CMU Arctic smoke through the normal evaluator, then execute the complete Machine A profile and assignment preflight from `machine_a_readiness.md`.

## Acceptance evidence

- Git worktree clean before runtime outputs; generated environments, caches, and runs remain ignored.
- CPU clone: Python 3.12, CPU-only PyTorch, device `cpu`, dtype `float32`, and `pip check` passes.
- CUDA clone: Python 3.12 and `torch==2.11.0+cu128`; CUDA runtime 12.8; `pip check` passes.
- CUDA clone: RTX 3080 selected as `cuda:0`; real evaluator allocator VRAM is nonzero. CPU clone never requires NVIDIA tooling.
- Whisper Base exact size/hash present; no inference-time download.
- Campaign validates at 41 scenarios and assignments are non-overlapping.
- Runtime assignment and release-binding identities bind to the final commit.
- Both matching Machine A wrappers, each in its own clone, say `READY_TO_LAUNCH` for 20/20 scenarios with `-PreflightOnly` and do not start inference.

This establishes Machine A technical readiness only. It does not pass Machine B or the scientific gates and does not authorize the massive run.
