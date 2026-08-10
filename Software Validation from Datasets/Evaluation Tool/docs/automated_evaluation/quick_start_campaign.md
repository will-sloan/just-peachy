# Campaign quick start

The current verdict is `NOT_READY_TO_LAUNCH`; clear the control-sheet blockers
before step 8. This is the shortest operator path after the final Stage 14
commit is published.

## 1–5. Clone, install, activate, verify, and materialize

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
Set-Location just-peachy
git checkout <frozen-commit-from-launch-control-sheet>
powershell -ExecutionPolicy Bypass -File install.ps1 -Profile dev -Device cpu -InstallFFmpeg
.\.venv\Scripts\python.exe scripts\bootstrap_models.py --whisper base
.\.venv\Scripts\python.exe scripts\verify_install.py `
  --profile dev --device cpu --cache-root models/cache --whisper base --require-models
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/materialize_launch_campaign.py --bind-current-commit
```

Run that materialization command independently on both clean clones and compare
the SHA-256 and contents of
`automated_runs/campaign_05_massive_release/worker_assignments/release_binding.json`.
Do not launch unless the two files are byte-identical and bind to the checked-out
final commit.

In Anaconda Prompt or cmd, use `.venv\Scripts\activate.bat` before changing
directory. Anaconda itself is not required.

## 6–7. Optional credentials and real smoke

```powershell
python scripts/launch_readiness_probe.py credentials
python run_evaluation.py full `
  --dataset cmu_arctic --max-recordings 1 --augmentation none `
  --runner configured `
  --inference-config configs/inference/live_mic_whisper_base.yaml `
  --run-name launch_smoke
```

Credentials may remain missing because the candidate excludes gated backends.
The smoke must have one prediction, no missing/failed item, and generated
metrics/plots/report.

## 8–10. Preflight and launch only the assigned worker

```powershell
# Machine A
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1

# Machine B, on the other clone
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1
```

Each wrapper validates the campaign, both assignments, machine capability, and
every assigned scenario before inference. Do not bypass a non-zero preflight.

## 11. Monitor, stop, and resume

```powershell
python run_evaluation.py campaign status --campaign-root automated_runs/campaign_05_massive_release
python run_evaluation.py campaign stop --campaign-root automated_runs/campaign_05_massive_release --reason "operator request"
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1 -ResumeStopped
# Use machine_b wrapper on B.
```

## 12–14. Export, merge, and analyze

```powershell
# On A / on B respectively
powershell -ExecutionPolicy Bypass -File scripts/export_machine_a_results.ps1
powershell -ExecutionPolicy Bypass -File scripts/export_machine_b_results.ps1

# On coordinator after copying both transfer folders
powershell -ExecutionPolicy Bypass -File scripts/merge_massive_campaign.ps1 `
  -MachineATransfer C:/campaign_transfers/campaign_05_massive_release/machine_a `
  -MachineBTransfer C:/campaign_transfers/campaign_05_massive_release/machine_b
powershell -ExecutionPolicy Bypass -File scripts/analyze_massive_campaign.ps1 `
  -PrerequisiteEvidence automated_runs/campaign_04_standard_release/analysis/report/release_qualification.json
```

Read [the launch control sheet](launch_control_sheet.md) on launch day and the
[two-machine runbook](two_machine_launch_runbook.md) for transfer/recovery detail.
