# Bounded Prompt-8 final pipeline consolidation

This package implements the amended eight-day Prompt 8. It consumes completed, checksum-bound Prompt 4–7 evidence and creates the final desktop/software rankings, separate Raspberry Pi/Linux ARM64 deployment handoff, failure analysis, reproducibility manifest, XVF handoff, runbook, and compact upload ZIP.

It is an evidence-only finalizer. It does **not** launch inference, open a new scientific campaign, retune a held-out policy, fine-tune a model, implement XVF, or select different production candidates after Prompt 7. Its only valid completion marker is:

```text
COMPLETE_FULL_PIPELINE_PROGRAM_REDUCED_8DAY_V1
```

It never emits the reserved original marker `COMPLETE_FULL_PIPELINE_PROGRAM`.

## Inputs

The required entry point is the Prompt-7 universal `completion_marker.json`. The finalizer follows its exact SHA-256 predecessor links back through Prompt 6, Prompt 5, and Prompt 4. It validates:

- each stage's `full-pipeline-eight-day-stage-completion.v1` envelope;
- exact marker, scope, adapter identity, predecessor path, and predecessor hash;
- each universal artifact manifest and the three PASS gates;
- every direct artifact hash and every transitive `checksums.json` entry;
- all required development, held-out, extended, hardening, failure, and licensing files;
- all 18 held-out summary rows and all 18 frozen pipeline configs;
- frozen decision policy registry, extended set, matrix, runtime config, and program state;
- Prompt-6 and Prompt-7 licensing/provenance records;
- the exact execution-policy addendum and Prompt-8 adapter-registry binding;
- the exact Raspberry Pi/Linux ARM64 deployment-steering authority;
- `all18_deployment_evidence.json`, `extended_deployment_evidence.json`, and
  `raspberry_pi_candidate_shortlist.json`, including their predecessor hashes;
- the C:-only amendment and 35 GiB minimum free-space reserve.

The 192-hour program value and four-hour Prompt-8 value are advisory planning targets. They never terminate a healthy run and are not admission gates. Operator stop, the 35-GiB C: reserve, genuine stage failure, invalid prerequisite/scientific hashes, and worker-health timeouts remain effective.

The Prompt-7 catalog supplies PRIMARY, FALLBACK, and optional ALTERNATIVE roles. Prompt 8 verifies selected candidates are software-ready and does not reselect them.

Prompt 7 separately supplies the unordered 2–4 member Raspberry Pi candidate
shortlist. Prompt 8 consumes that exact membership as authority and enriches it
with checksum-bound Prompt-5 confidence intervals/paired effects and Prompt-6
serial desktop resource evidence. It never substitutes a different shortlist or
names a final Raspberry Pi winner.

## Outputs

The canonical report directory is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\full_pipeline\final\full_pipeline_program_reduced_8day_v1
```

It contains exactly the requested reports:

```text
FINAL_PIPELINE_REPORT.md
FINAL_PIPELINE_RANKING.csv
PIPELINE_PARETO_FRONTIER.csv
PIPELINE_FAILURE_ANALYSIS.md
FINE_TUNING_CANDIDATES.md
XVF3800_INTEGRATION_HANDOFF.md
RASPBERRY_PI_DEPLOYMENT_HANDOFF.json
REPRODUCIBILITY_MANIFEST.json
RESULT_FILE_INVENTORY.csv
FINAL_RUNBOOK.md
```

The compact package is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\JustPeachyResearchSummaries\full_pipeline\final\full_pipeline_program_reduced_8day_v1.zip
```

The ZIP uses a fixed ten-file allowlist and excludes raw datasets, model weights, credentials, large caches, raw prediction trees, and biometric vectors. The CLI prints the upload path and SHA-256 after `RunAll` or `ValidateCompletion` passes.

Native controller records are under:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_final_consolidation_reduced_8day_v1
```

They include `program_progress.json`, `input_binding.json`, gate records, `artifact_manifest.json`, `completion_marker.json`, stop/failure records when applicable, and the controller lock.

## Ranking and scientific interpretation

There is no weighted or hidden composite score.

- technical ranking uses the frozen safety-first priorities lexicographically;
- user-experience safety ranking separately orders wrong-known, stranger false-known, and text-stability latency;
- resource ranking separately orders standardized serial RTF, CPU, peak RAM, and model bytes, with missing/unsupported dimensions explicit;
- deployment/licensing ranking is separate and never claims legal or commercial clearance;
- Pareto analysis declares every dimension and explicitly marks missing, failed, or non-real-time rows ineligible.

All failed and missing source records remain referenced. The compact failure report copies only identifiers, classification, status, and source row location—not raw error text that might contain sensitive values.

A neural fine-tuning candidate is admitted only when a failed source row explicitly declares reproducible evidence, an allowed decision, a case/job and failure reason, and frozen regression tests. A single failed job is never enough. Separately, nonzero checksum-bound aggregate held-out wrong-known/stranger-false-known exposure may yield `POLICY_CHANGE_ONLY`; that is policy triage, not neural adaptation evidence. Otherwise the result is `NO_FINE_TUNING_CURRENTLY_JUSTIFIED`. No training occurs.

The desktop/software ranking and Raspberry Pi deployment handoff answer different
questions. The handoff preserves ordinary-accuracy tradeoffs while keeping
false-known/wrong-known safety distinctions explicit; reports H2 sharing only as
an unproven opportunity; retains H5's dual-speaker-model tradeoff, WeSpeaker
paths, and both ASR families where Prompt 7 retained them; and records unknown or
unsupported values instead of inventing ARM measurements. Its feasibility class
is one of the four steering-authorized 2-GiB classes, while evidence uncertainty
remains a separate status. Windows/x86 measurements do not establish Linux
ARM64 portability or Raspberry Pi performance. The handoff includes all 14
future target-hardware tests and all 7 future Linux ARM64 validations.

The XVF document defines future processed-audio, energy, AoA, confidence, direction-event, and synchronization contracts plus five frozen ablations. It does not implement XVF or claim real device performance.

## Run from PowerShell

Open PowerShell and run:

```powershell
$ToolRoot = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
$Prompt7 = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_production_candidate_hardening_reduced_8day_v1\completion_marker.json"
Set-Location $ToolRoot
& ".\scripts\run_full_pipeline_final_consolidation.ps1" -Action RunAll -Prompt7Marker $Prompt7
```

Status:

```powershell
& ".\scripts\run_full_pipeline_final_consolidation.ps1" -Action Status
```

Validate the completed package independently:

```powershell
& ".\scripts\run_full_pipeline_final_consolidation.ps1" -Action ValidateCompletion -Prompt7Marker $Prompt7
```

Request a graceful stop between phases:

```powershell
& ".\scripts\run_full_pipeline_final_consolidation.ps1" -Action Stop
```

`RunAll` is restart-safe. If the completion envelope already exists, it validates and reuses it. If a crash occurred after completion was written but before `PROGRAM_STATE.json` advanced, the next call completes only that state transition and revalidates the package.

## Run from Anaconda Prompt or Command Prompt

The wrapper deliberately uses the repository's locked Python environment. It can be invoked from Anaconda Prompt, Windows Terminal, or `cmd.exe` through PowerShell:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\run_full_pipeline_final_consolidation.ps1" -Action RunAll -Prompt7Marker "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\full_pipeline_production_candidate_hardening_reduced_8day_v1\completion_marker.json"
```

Direct Python, if troubleshooting the wrapper:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.full_pipeline_final_consolidation run-all --prompt7-marker "C:\absolute\C-only\prompt7\completion_marker.json"
```

Inputs must be absolute and resolve to drive C:. A junction or symlink that resolves to another drive is rejected.

## Automatic eight-day-controller adapter

Canonical handoff values:

```text
adapter_id: prompt8_final_consolidation_reduced_8day_v1
stage_workspace: ${TOOL_ROOT}\automated_runs\full_pipeline_final_consolidation_reduced_8day_v1
completion_record: ${STAGE_WORKSPACE}\completion_marker.json
progress_record: ${STAGE_WORKSPACE}\program_progress.json
controller_log: ${STAGE_WORKSPACE}\controller.log
restart_policy: RERUN_IDEMPOTENT
expected_duration_hours / advisory planning target: 4
elapsed_time_kill_switch_enabled: false
elapsed_time_admission_gate_enabled: false
```

Start argv (`shell=False`):

```text
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ${TOOL_ROOT}\scripts\run_full_pipeline_final_consolidation.ps1 -Action RunAll -WorkspaceRoot ${STAGE_WORKSPACE} -OutputRoot ${TOOL_ROOT}\JustPeachyResearchSummaries\full_pipeline\final\full_pipeline_program_reduced_8day_v1 -ZipPath ${TOOL_ROOT}\JustPeachyResearchSummaries\full_pipeline\final\full_pipeline_program_reduced_8day_v1.zip
```

Stop and validate use the same wrapper with `-Action Stop` and `-Action ValidateCompletion`. The orchestrator supplies these environment variables:

```text
JP8_ADAPTER_ID
JP8_ADAPTER_CONTRACT_SHA256
JP8_PREDECESSOR_COMPLETION_PATH
JP8_PREDECESSOR_COMPLETION_SHA256
JP8_COMPLETION_RECORD
JP8_PROGRESS_RECORD
```

The adapter's nine material classes must use narrow paths rather than declaring the whole tool root:

- inputs: the exact Prompt-4, Prompt-5, Prompt-6, and Prompt-7 `completion_marker.json` paths (each is separately included in Prompt 8's universal artifact manifest), `EIGHT_DAY_SCOPE_AMENDMENT.json`, `EIGHT_DAY_EXECUTION_POLICY_ADDENDUM.json`, `EIGHT_DAY_ADAPTERS.json`, `PROGRAM_STATE.json`, `full_pipeline_matrix.v1.yaml`, `full_pipeline_runtime.v1.yaml`, and `LICENSE_AND_ASSET_MANIFEST.md`;
- deployment authority input: the exact
  `runs\full_pipeline_program\RASPBERRY_PI_DEPLOYMENT_STEERING.json` path;
- workspaces: `${STAGE_WORKSPACE}`;
- caches: none;
- temporary: `${STAGE_WORKSPACE}\temp`;
- logs: `${STAGE_WORKSPACE}\controller.log`, `${STAGE_WORKSPACE}\program_progress.json`;
- results: none;
- reports: the canonical final report directory;
- packages: the canonical ZIP, `${STAGE_WORKSPACE}\completion_marker.json`, `${STAGE_WORKSPACE}\artifact_manifest.json`, `${STAGE_WORKSPACE}\input_binding.json`, `${STAGE_WORKSPACE}\program_state_before_prompt8.json`, and `${STAGE_WORKSPACE}\gate_records`;
- checkpoints: none.

Prompt 8 does not read model directories, shared neural caches, datasets, or inference outputs outside the exact checksum-linked Prompt 4–7 evidence chain. Its command working directory is an execution setting, not permission to inventory the full `${TOOL_ROOT}` as material input.

Terminal failures are reported with the exact public Prompt-8 statuses:
`BLOCKED_INCOMPLETE_EVIDENCE`, `BLOCKED_PRODUCTION_CANDIDATE`, or
`BLOCKED_OTHER`. A successful bounded run retains the amended completion marker
shown above; it does not emit an original full-scope marker.

The adapter may become READY only after Prompt 7 is READY and its exact predecessor contract is frozen. A missing Prompt-7 package remains NOT_READY; it is never converted into completion.

## Tests (no campaign)

These tests use synthetic files on drive C: and do not inspect unavailable outcomes or start inference:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_final_consolidation -q
& "..\..\.venv\Scripts\python.exe" -m ruff check app\full_pipeline_final_consolidation tests\full_pipeline_final_consolidation
& "..\..\.venv\Scripts\python.exe" -m compileall -q app\full_pipeline_final_consolidation
```
