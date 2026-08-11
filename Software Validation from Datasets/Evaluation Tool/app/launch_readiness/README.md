# Launch Readiness Preflight

## Purpose

This package provides the final machine, release-binding, and
complete-assignment checks required before a frozen campaign is launched. It
verifies every assigned scenario, not a sample. It does not run inference,
download models, install packages, or expose credential values.

The checks cover campaign and assignment identity, Git commit and dirty state, environment profile, component qualification and compatibility, package versions, credential presence, model asset sizes and hashes, every selected source-audio file and segment bound, exact RIR files and hashes, output writability, RAM, and estimated disk capacity. A report says `READY_TO_LAUNCH` only when all assigned scenarios pass.

## Inputs and outputs

Inputs are a complete repository clone, project data directory, frozen
campaign, worker assignment YAML, release binding/checksum, launch package,
environment-profile label, machine ID, and local output directory. Outputs are
a privacy-safe machine profile JSON, release-binding validation JSON, and an
assignment-preflight JSON. Credential values are never recorded; the supported
production campaign requires no credentials.

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

The normal operator does not run these low-level probes manually. From the
repository root use:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda -PreflightOnly
```

The launch wrapper first validates `release_binding.json` and its SHA-256
sidecar against Git HEAD, the frozen launch package, both assignments, and the
global campaign. The same commands accept `cpu` explicitly.

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
python -m ruff check --no-cache app\launch_readiness scripts\launch_readiness_probe.py scripts\validate_release_binding.py tests\automated_evaluation\test_stage14_launch_readiness.py
```
