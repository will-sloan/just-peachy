# Two-machine launch runbook

Current status is `NOT_READY_TO_LAUNCH`. The commands below are the exact
handoff workflow, but the launch commands must wait for every blocker in
`launch_control_sheet.md` to clear.

## Before either machine starts — coordinator

From a reviewed clean clone at the final published launch commit:

```powershell
git status --short
git rev-parse HEAD
Set-Location 'Software Validation from Datasets/Evaluation Tool'
python scripts/materialize_launch_campaign.py --bind-current-commit
python run_evaluation.py campaign validate --campaign-root automated_runs/campaign_05_massive_release
python run_evaluation.py campaign validate-assignments `
  --campaign-root automated_runs/campaign_05_massive_release `
  --assignment automated_runs/campaign_05_massive_release/worker_assignments/machine_a.yaml `
  --assignment automated_runs/campaign_05_massive_release/worker_assignments/machine_b.yaml
python scripts/launch_readiness_probe.py credentials
```

Run the same materialization command on both clean clones. Confirm the generated
`worker_assignments/release_binding.json` files are byte-identical, then confirm
the campaign hash, 41 scenarios, A=20, B=21, no overlap, exact model and RIR
hashes, passed component canary/small/standard gates, and the bound final commit.
Credential output may show missing because gated backends are not included.

## Machine A — initial setup

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
Set-Location just-peachy
git checkout <final-launch-commit>
powershell -ExecutionPolicy Bypass -File install.ps1 -Profile dev -Device cpu -InstallFFmpeg
.\.venv\Scripts\python.exe scripts/bootstrap_models.py --whisper base
.\.venv\Scripts\python.exe scripts/verify_install.py `
  --profile dev --device cpu --cache-root models/cache --whisper base --require-models
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/materialize_launch_campaign.py --bind-current-commit
```

Make the licensed datasets locally available before preflight. Machine A must
repeat its real one-item smoke after the final clean clone.

## Machine B — initial setup

Run the same clone/install/materialize steps on B, then follow
`machine_b_setup.md`. Return `machine_b_profile.json` and the complete
`machine_b_assignment_preflight.json`. The coordinator must change
`NOT_YET_TESTED` to an evidence-backed status before launch.

## Machine A — run batch A1

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1
python run_evaluation.py campaign status --campaign-root automated_runs/campaign_05_massive_release
```

This owns assignment `assignment_5014479496c7` (20 scenarios). The wrapper
stops before inference if any full-assignment preflight check fails.

## Machine B — run batch B1

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1
python run_evaluation.py campaign status --campaign-root automated_runs/campaign_05_massive_release
```

This owns provisional assignment `assignment_53642fa92b2a` (21 scenarios).

## Status, controlled stop, and assignment-safe resume

Run on the affected worker's local clone:

```powershell
python run_evaluation.py campaign status --campaign-root automated_runs/campaign_05_massive_release
python run_evaluation.py campaign stop `
  --campaign-root automated_runs/campaign_05_massive_release `
  --reason "operator request"
```

Wait for the active process to stop and inspect status. Resume only that
worker's stopped IDs:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1 -ResumeStopped
# On B use launch_campaign_machine_b.ps1 -ResumeStopped
```

Do not edit a resolved scenario to recover from OOM or failure; any
result-affecting change needs a new scenario ID. Deterministic config/reference
failures are terminal. Retry only failures that the executor marks eligible.

## Export and transfer

After the worker has no missing/failed assignment scenario:

```powershell
# A
powershell -ExecutionPolicy Bypass -File scripts/export_machine_a_results.ps1 `
  -Destination C:/campaign_transfers/campaign_05_massive_release/machine_a

# B
powershell -ExecutionPolicy Bypass -File scripts/export_machine_b_results.ps1 `
  -Destination C:/campaign_transfers/campaign_05_massive_release/machine_b
```

The destination must not already exist. Each wrapper rejects partial export and
validates the transfer manifest/checksums. Transfer exactly the generated
`machine_a` or `machine_b` folder. Do not transfer
`database/campaign.sqlite`, raw datasets, model caches, secrets, or unrelated
runtime folders. An interrupted copy is invalid until repeated and validated.

## Coordinator — validate and merge

Copy both transfer folders to the coordinator, then:

```powershell
python run_evaluation.py campaign validate-transfer `
  --campaign-root automated_runs/campaign_05_massive_release `
  --transfer-root C:/campaign_transfers/campaign_05_massive_release/machine_a
python run_evaluation.py campaign validate-transfer `
  --campaign-root automated_runs/campaign_05_massive_release `
  --transfer-root C:/campaign_transfers/campaign_05_massive_release/machine_b

powershell -ExecutionPolicy Bypass -File scripts/merge_massive_campaign.ps1 `
  -MachineATransfer C:/campaign_transfers/campaign_05_massive_release/machine_a `
  -MachineBTransfer C:/campaign_transfers/campaign_05_massive_release/machine_b
```

The merge must report 41 global IDs, zero missing IDs, zero conflicting
duplicates, and accepted transfer checksums. Byte-identical duplicates are
reported but never silently overwritten.

## Final analysis

The standard campaign must already have a passed prerequisite artifact:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/analyze_massive_campaign.ps1 `
  -PrerequisiteEvidence automated_runs/campaign_04_standard_release/analysis/report/release_qualification.json
```

The wrapper performs index → validate → run → coverage → release-status.
Inspect:

```text
automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md
automated_runs/campaign_05_massive_release/analysis/report/coverage_report.md
automated_runs/campaign_05_massive_release/analysis/report/release_qualification.json
```

Running analysis without prerequisite evidence is allowed for diagnostics but
must leave the large release gate blocked.
