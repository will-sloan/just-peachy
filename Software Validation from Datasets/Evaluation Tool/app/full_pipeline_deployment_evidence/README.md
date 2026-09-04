# Full-pipeline deployment-evidence contracts

## Purpose

This isolated package validates the checksum-bound Raspberry Pi steering and
provides common structured evidence, 2-GiB feasibility, and Linux ARM64
portability contracts for Prompts 5--8. It is an additive reporting layer: it
does not run models, change scientific metrics, filter pipeline membership, or
turn Windows/x86 desktop measurements into Raspberry Pi measurements.

It intentionally lives outside `app/full_pipeline`. The active Prompt-4 freeze
hashes that runtime package, so this deployment-only helper must remain
separate.

## Inputs and outputs

Input is the C:-local authority
`runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json`, plus stage
resource/config evidence. The helper requires exact steering identities,
deployment attributes, four 2-GiB classes, four Linux ARM64 portability classes,
26 candidate fields, 14 future hardware tests, and 7 future Linux ARM64 tests.

Outputs are ordinary Python dictionaries for stage-specific JSON reports. Every
attribute is a structured evidence cell with an explicit `MEASURED`, `DERIVED`,
`UNKNOWN`, or `UNSUPPORTED` status. A `LINUX_ARM64_READY` or
`LIKELY_2GB_FEASIBLE` conclusion cannot be manufactured from desktop evidence.
Source provenance uses flat `source_path`, `source_sha256`, and `source_field`
keys so downstream Prompt-8 consolidation can consume it without translation.

## Model-free validation

From PowerShell at the Evaluation Tool root:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "..\..\.venv\Scripts\python.exe" -m pytest `
  ".\tests\full_pipeline_deployment_evidence" -q
```

From Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_deployment_evidence -q
```

These tests parse JSON and validate dictionaries only. They do not load audio,
models, embeddings, or held-out predictions.
