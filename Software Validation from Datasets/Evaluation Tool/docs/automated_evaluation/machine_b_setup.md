# Machine B setup from a clean clone

Machine B is **`NOT_YET_TESTED`**. Complete these steps on the actual second
computer; do not reuse Machine A's profile.

The entire provisional B assignment has already passed a static cross-check on
Machine A: 21/21 scenario definitions, 13,430 item executions, 2,622 unique
source files, model/RIR identities, and pipeline resolution. This does not prove
that any of those inputs or capabilities exist on B.

## 1. Clone and install

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
Set-Location just-peachy
git rev-parse HEAD
powershell -ExecutionPolicy Bypass -File install.ps1 -Profile dev -Device cpu -InstallFFmpeg
.\.venv\Scripts\python.exe scripts\bootstrap_models.py --whisper base
.\.venv\Scripts\python.exe scripts\verify_install.py `
  --profile dev --device cpu --cache-root models/cache --whisper base --require-models
.\.venv\Scripts\python.exe -m pip check
```

The commit must equal the final launch commit selected by the coordinator.
The tracked launch package retains the earlier candidate evidence commit; the
materializer binds runtime assignments to the final checked-out HEAD. Anaconda
Prompt is optional. In cmd, activate with
`.venv\Scripts\activate.bat`; in PowerShell use process-policy bypass if local
activation is restricted.

## 2. Provide local data

Place or link the same licensed datasets under
`Software Validation from Datasets/Raw Datasets (Not formatted)`. Do not copy
audio into the campaign. Materialize the candidate campaign:

```powershell
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/materialize_launch_campaign.py --bind-current-commit
python run_evaluation.py campaign validate --campaign-root automated_runs/campaign_05_massive_release
```

Send the generated `worker_assignments/release_binding.json` hash to the
coordinator before preflight. It must be byte-identical to Machine A's binding.

## 3. Run one real smoke

```powershell
python run_evaluation.py full `
  --dataset cmu_arctic `
  --max-recordings 1 `
  --augmentation none `
  --runner configured `
  --inference-config configs/inference/live_mic_whisper_base.yaml `
  --run-name machine_b_base_smoke
```

Confirm one standardized prediction, zero missing/failed items, and generated
metrics, plots, and report. The WER value itself is not a readiness threshold.

## 4. Generate the actual profile and full assignment preflight

```powershell
python scripts/launch_readiness_probe.py machine `
  --machine-id machine_b `
  --repository-root ../.. `
  --project-root .. `
  --environment-profile core-cpu `
  --output-root automated_runs/campaign_05_massive_release `
  --output artifacts/launch_readiness/machine_b_profile.json

python scripts/launch_readiness_probe.py assignment `
  --machine-id machine_b `
  --repository-root ../.. `
  --project-root .. `
  --environment-profile core-cpu `
  --output-root automated_runs/campaign_05_massive_release `
  --campaign-root automated_runs/campaign_05_massive_release `
  --assignment automated_runs/campaign_05_massive_release/worker_assignments/machine_b.yaml `
  --machine-profile artifacts/launch_readiness/machine_b_profile.json `
  --output artifacts/launch_readiness/machine_b_assignment_preflight.json
```

Send the coordinator only these two JSON files, the smoke run's report summary,
and the verifier result. Do not send credentials, model caches, raw data, or the
campaign SQLite database. The coordinator must confirm 21/21 scenarios were
preflighted and the verdict is `READY_TO_LAUNCH` before the assignment becomes
hardware-verified.
