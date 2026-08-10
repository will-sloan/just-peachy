# Launch Readiness Preflight

## Purpose

This package provides the final machine and complete-assignment checks required before a frozen campaign is launched. It verifies every assigned scenario, not a sample. It does not run inference, download models, install packages, or expose credential values.

The checks cover campaign and assignment identity, Git commit and dirty state, environment profile, component qualification and compatibility, package versions, credential presence, model asset sizes and hashes, every selected source-audio file and segment bound, exact RIR files and hashes, output writability, RAM, and estimated disk capacity. A report says `READY_TO_LAUNCH` only when all assigned scenarios pass.

## Inputs and outputs

Inputs are a complete repository clone, project data directory, frozen campaign, worker assignment YAML, environment-profile label, machine ID, and local output directory. Outputs are a privacy-safe machine profile JSON and an assignment-preflight JSON. Credential names and presence may be recorded; values are never recorded.

## Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate

python "Software Validation from Datasets\Evaluation Tool\scripts\launch_readiness_probe.py" machine ^
  --machine-id machine_a ^
  --repository-root . ^
  --project-root "Software Validation from Datasets" ^
  --environment-profile core-cpu ^
  --output-root "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_05_massive_release" ^
  --output "Software Validation from Datasets\Evaluation Tool\artifacts\launch_readiness\machine_a_profile.json"

python "Software Validation from Datasets\Evaluation Tool\scripts\launch_readiness_probe.py" assignment ^
  --machine-id machine_a ^
  --repository-root . ^
  --project-root "Software Validation from Datasets" ^
  --environment-profile core-cpu ^
  --output-root "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_05_massive_release" ^
  --campaign-root "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_05_massive_release" ^
  --assignment "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_05_massive_release\worker_assignments\machine_a.yaml" ^
  --machine-profile "Software Validation from Datasets\Evaluation Tool\artifacts\launch_readiness\machine_a_profile.json" ^
  --output "Software Validation from Datasets\Evaluation Tool\artifacts\launch_readiness\machine_a_assignment_preflight.json"
```

An exit code of `0` means ready, `2` means the complete report was generated but launch is blocked, and `3` means the preflight could not safely produce evidence. Do not use `--existence-only` for final launch approval because that option intentionally skips audio-header and segment-bound validation.

Check credential-gated backends without printing credential values:

```bat
python "Software Validation from Datasets\Evaluation Tool\scripts\launch_readiness_probe.py" credentials
```

This reports only `READY` or `MISSING`. Those optional credentials are not
required by the frozen Whisper Base massive-campaign candidate.

## PowerShell

The same commands work in PowerShell using backticks instead of carets for line continuation. Use the exact commands generated in `docs/automated_evaluation/launch_control_sheet.md` for the frozen release campaign.

## Frozen campaign materialization and assignment-safe resume

From the Evaluation Tool directory, reproduce and hash-check the candidate
massive campaign and both non-overlapping assignments with:

```bat
python scripts\materialize_launch_campaign.py
```

The launch wrappers run a full assignment preflight before inference. A normal
run does not requeue a deliberate stop. To resume only the stopped scenarios
owned by one worker, use that worker's wrapper with `-ResumeStopped`; it does
not alter stopped scenarios in the other assignment.

## Tests

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python -m pytest tests\automated_evaluation\test_stage14_launch_readiness.py -q
python -m ruff check --no-cache app\launch_readiness scripts\launch_readiness_probe.py tests\automated_evaluation\test_stage14_launch_readiness.py
```
