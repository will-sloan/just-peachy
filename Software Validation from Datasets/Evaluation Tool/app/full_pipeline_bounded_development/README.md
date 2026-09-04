# Eight-Day Bounded Prompt-4 Development Controller

## Purpose and scientific boundary

This additive package runs the user-authorized, C:-only reduced realization of
Prompt 4. It preserves all 18 pipelines and the frozen v5 challenger policies
and qualification evidence while replacing the original 807-case development
campaign with a deterministic 180-case panel. It never edits the stopped v5
workspace and never merges its partial result rows into the bounded result set.

The successful amended marker is:

```text
COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1
```

It must not be interpreted as `COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE`; the
original full scope remains incomplete. The package has no held-out command.

## Selection

Selection seed is fixed at `5107` and uses metadata/reference hashes only:

- Controlled-v1: choose two unique audio sources by seeded SHA-256 within each
  of 12 `scenario_id` strata, then keep all three truth overlays. This is 24
  unique recordings and 72 cases.
- Product-v2: retain all 36 unique recordings and choose exactly one
  `ALL_KNOWN`, one `MIXED_KNOWN_UNKNOWN`, and one `ALL_UNKNOWN` variant per
  recording. Every recording contributes one full-gallery variant; the other
  gallery sizes are globally balanced with seeded hash tie-breaking. This is
  108 cases.

The realized Product-v2 selection contains exactly 36 full-gallery cases and
12 cases at each of gallery sizes 1, 2, 5, 10, 20, and 50. Across both sources,
each truth overlay has exactly 60 cases. The manifest records all 180 selected
and all 627 excluded cases, selected physical audio IDs, speaker coverage,
strata, seed, case-manifest SHA-256, and reference SHA-256.

## Inputs

- The prepared `full_speech_pipeline_v1` development protocol.
- The locked 18-row matrix and runtime configuration.
- The user-authorized scope amendment at
  `runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json`.
- The cleanly stopped v5 Prompt-4 workspace, specifically its frozen decision
  policy registry, complete qualification bundle/evidence, anchor runtime
  qualification, and stopped partial-run inventory.
- Existing shared component cache at
  `JustPeachyResults/full_pipeline/_shared_cache`.

Every material path, including Windows temporary storage, must resolve to C:.
Every stage checks that at least 35 GiB remains free on C: before it starts.
During either inference action a 30-second reserve monitor requests the existing
controller's graceful stop and writes `storage_reserve_pause.json` before the
reserve can be knowingly crossed; it never deletes or relocates evidence.

## Outputs

The bounded workspace contains:

```text
bounded_selection.json
input_binding.json
orchestration_plan.json
decision_policy_registry.json
development_accuracy/
resource_spots/
combined_evidence/
frozen_pipeline_configs/       # exactly 18 YAML files + checksums.json
gates/                         # hash, firewall, prerequisite gates
artifact_manifest.json
completion_marker.json
```

The report root contains a scope-labelled `development_summary.csv`,
`extended_set.yaml`, `development_report.md`, checksums, the compact ZIP, and a
checksum-validated standard scientific report below `scientific_report/`.
`completion_marker.json` is written last and provides absolute C:-only paths
and hashes for Prompt 5. Its universal stage envelope uses `status: COMPLETE`,
`prompt_index: 4`, the amended completion marker, three PASS gates, and the
artifact manifest. Failed, stopped, or incomplete runs cannot emit it.

After that envelope validates, `Collect` atomically advances the canonical
`runs\full_pipeline_program\PROGRAM_STATE.json` to Prompt 4 and binds the
completion-record path and SHA-256. The update is idempotent for the same
record and fails closed if another stage has already advanced the program;
this is the automatic admission gate used by bounded Prompt 5.

No raw dataset, model weight, enrollment biometric vector, or cache payload is
placed in the compact report ZIP.

## Complete PowerShell sequence

Open PowerShell in the repository root:

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Plan
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Prepare
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Run
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action PrepareResources
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action RunResources
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Analyze
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Freeze
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Collect
```

The automatic eight-day orchestrator uses the single restart-safe `Execute`
action. It performs the same sequence and stops immediately if any stage does
not return PASS/COMPLETE:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Execute
```

`Plan`, `Prepare`, `PrepareResources`, `Analyze`, `Freeze`, and `Collect` are
model-free or postprocessing operations. `Run` and `RunResources` are the only
actions that execute inference. Accuracy concurrency is exactly two; resource
measurement concurrency is exactly one with an isolated attempt cache.

## Monitor and graceful stop

Run this complete command in a second PowerShell window:

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Status
```

Request a restart-safe stop without deleting results or caches:

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Stop
```

Rerun the interrupted `Run` or `RunResources` action to resume.

## Orchestrator adapter commands and paths

The Prompt-4 stage working directory is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
```

The stage workspace is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_development_prompt4_reduced_8day_v1
```

Use these four complete argv-equivalent commands from the stage working
directory. `Execute` is idempotent and is both start and resume:

```powershell
# Start
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run_full_pipeline_bounded_development.ps1" -Action Execute

# Resume after interruption
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run_full_pipeline_bounded_development.ps1" -Action Execute

# Graceful stop
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run_full_pipeline_bounded_development.ps1" -Action Stop

# Fail-closed completion validation
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run_full_pipeline_bounded_development.ps1" -Action Validate
```

The eight-day orchestrator sets `JP8_ADAPTER_ID` and
`JP8_ADAPTER_CONTRACT_SHA256` for Execute and Validate so the completion
envelope binds the registered adapter. A manual run may omit both and receives
the checksum-bound native adapter identity.

Key controller files are:

```text
completion:  <workspace>\completion_marker.json
selection:   <workspace>\bounded_selection.json
stage plan:  <workspace>\orchestration_plan.json
accuracy:    <workspace>\development_accuracy\campaign_progress.json
resources:   <workspace>\resource_spots\campaign_progress.json
acc. state:  <workspace>\development_accuracy\controller_state.json
res. state:  <workspace>\resource_spots\controller_state.json
acc. logs:   <workspace>\development_accuracy\attempts\
res. logs:   <workspace>\resource_spots\attempts\
```

Restart policy: never delete or recreate the workspace. Request `Stop`, wait
for both controller states to become `STOPPED`, and run `Execute` again. The
state databases retain complete jobs; partial attempts are not published as
reusable evidence, while checksum-valid shared component cache entries remain
reusable.

The C:-only material-path inventory used by the adapter is:

1. Inputs/protocol/configs: the Evaluation Tool root and v5 source-evidence
   root.
2. Frozen policy/qualification evidence: the v5 `frozen\` and
   `qualification\` trees.
3. Model/checkpoint assets: paths resolved by the locked matrix beneath C:.
4. Shared inference cache: `JustPeachyResults\full_pipeline\_shared_cache`.
5. Temporary/staging files: `%LOCALAPPDATA%\Temp` and attempt-local resource
   caches, both on C:.
6. Restart state/logs: the bounded workspace, SQLite databases, progress,
   controller state, and `attempts\` trees.
7. Scientific result trees: `JustPeachyResults\full_pipeline\full_speech_pipeline_v1`.
8. Reports/summaries: the bounded `JustPeachyResearchSummaries` report root
   plus the common full-pipeline summary root.
9. Packages/manifests/gates: the bounded compact ZIP, artifact manifest,
   completion marker, and three gate files, all under the two C:-only roots
   above.

## Anaconda Prompt / cmd.exe

No Conda activation is required because the wrapper calls the repository
virtual environment explicitly. From Anaconda Prompt or cmd.exe:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_bounded_development.ps1" -Action Status
```

To use Python directly after activating the repository environment:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_bounded_development.cli status
```

## Tests

From the Evaluation Tool root:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests\full_pipeline_bounded_development -q
..\..\.venv\Scripts\python.exe -m ruff check app\full_pipeline_bounded_development tests\full_pipeline_bounded_development
```
