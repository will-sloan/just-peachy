# Stage 14 launch helpers

## Purpose

These scripts are thin launch-day wrappers around the existing Evaluation Tool
CLI. They materialize the frozen campaign candidate, inspect every assigned
scenario, run exactly one worker assignment, export checksummed results, merge
independent transfers, and invoke the existing analysis workflow. They do not
implement a second executor, store secrets, download models, or enable parallel
GPU jobs.

## Inputs and outputs

Inputs are `configs/automated_evaluation/launch_package.v1.yaml`, a complete
repository clone at its expected commit, local datasets, the exact Whisper Base
asset, and one generated worker assignment. Runtime outputs are written to
`automated_runs/campaign_05_massive_release`, machine-local preflight JSON is
written to `artifacts/launch_readiness`, and transfer packages default to the
repository-level `transfer_packages` folder.

## PowerShell

Run from `Software Validation from Datasets/Evaluation Tool`:

```powershell
python scripts/materialize_launch_campaign.py --bind-current-commit
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1
```

After a deliberate stop, resume only the current worker's assignment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1 -ResumeStopped
powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1 -ResumeStopped
```

After every assigned scenario succeeds:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/export_machine_a_results.ps1
powershell -ExecutionPolicy Bypass -File scripts/export_machine_b_results.ps1
powershell -ExecutionPolicy Bypass -File scripts/merge_massive_campaign.ps1
powershell -ExecutionPolicy Bypass -File scripts/analyze_massive_campaign.ps1 `
  -PrerequisiteEvidence automated_runs/campaign_04_standard_release/analysis/report/release_qualification.json
```

Each launch wrapper first validates the global campaign, both assignments, the
local machine profile, and every scenario in its assignment. A preflight
blocker returns non-zero before inference starts. Export refuses to overwrite a
destination and refuses to call a partial transfer complete.

`--bind-current-commit` is the clean post-commit release path. It avoids an
impossible self-referential commit hash in a tracked file by deterministically
binding both ignored runtime assignments to the checkout's actual HEAD. Both
machines must compare
`automated_runs/campaign_05_massive_release/worker_assignments/release_binding.json`;
the files must be byte-identical before launch. Omit the flag only to reproduce
the pre-commit candidate identities recorded in the versioned package.

## Anaconda Prompt or Command Prompt

Anaconda is optional. Ordinary Command Prompt works with the repository virtual
environment:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\materialize_launch_campaign.py --bind-current-commit
powershell -ExecutionPolicy Bypass -File scripts\launch_campaign_machine_a.ps1
```

The command without the flag is retained only to reproduce the candidate
evidence at commit `4e1c1e7...`.

Use the Machine B wrapper on the second clone. Do not run both wrappers against
one shared campaign database on a network drive.

## Verification

```bat
python -m pytest tests\automated_evaluation\test_stage14_launch_readiness.py tests\automated_evaluation\test_stage6_campaign_exchange.py -q --basetemp artifacts\pytest_stage14
python -m ruff check --no-cache app\launch_readiness scripts\launch_readiness_probe.py scripts\materialize_launch_campaign.py tests\automated_evaluation\test_stage14_launch_readiness.py
```

The launch-day source of truth is
`docs/automated_evaluation/launch_control_sheet.md`.
