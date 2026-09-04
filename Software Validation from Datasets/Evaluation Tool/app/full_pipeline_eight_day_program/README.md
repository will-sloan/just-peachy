# Eight-Day Full-Pipeline Program Controller

## Purpose

This package is the additive program-level controller for the user-authorized,
bounded Prompt 4–8 campaign. It does not implement speech inference, change a
frozen scientific policy, or reinterpret the original full-scope prompts. It
loads one command adapter per prompt, applies the authoritative eight-day
amendment as the bounded scientific scope and planning target, and starts the next prompt only after the previous prompt's exact
reduced-scope completion evidence has been independently validated.

The fixed scope identity is:

```text
scope_id: full_pipeline_prompts_4_8_eight_day_c_only.v1
scope_class: BOUNDED_REDUCED
original_full_scope_complete: false
```

The controller enforces:

- Prompt 4–8 nominal planning targets of 48, 60, 30, 12, and 4 hours, within
  the amendment's 192-hour target and 38-hour contingency. These elapsed-time
  values are advisory ETA targets only: a healthy run is never stopped, blocked,
  or denied admission because a stage or the total program takes longer;
- C:-only resolved input/output/cache/temp/checkpoint/log/report/package paths,
  including existing ancestor/junction resolution;
- a 35 GiB free-space reserve on C: before admission and during execution;
- exactly one controller process, stale-lock recovery, persisted child PID, and
  restart-safe adapter semantics;
- a graceful stop command with no implicit forced termination;
- durable, fsync-backed JSONL milestone notifications before every automatic
  transition;
- an exact predecessor completion path and SHA-256 chain;
- exact amended completion markers; original unqualified markers are rejected;
- rehashed artifact manifests and rehashed PASS records for hash, firewall, and
  prerequisite validation;
- console percentage, ETA, stage state, and C: free-space monitoring.

The durable execution policy is `ADVISORY_ONLY_NO_AUTOMATIC_STOP`. Automatic
continuation can stop only for a genuine stage failure, an invalid scientific or
hash gate, an explicit operator stop, or the C: safety reserve. Worker-level
timeouts remain in place to detect a failed/hung model operation; they are not
wall-clock campaign limits.

The included adapter template deliberately marks Prompts 4–8 `NOT_READY`.
In particular, an absent Prompt 6, 7, or 8 implementation can never become
complete merely because a file with a completion-looking name exists. A later
bounded-stage package must provide a complete READY adapter before transition.
The configuration is reloaded at each stage boundary, so a later prompt may be
installed while an earlier long-running prompt is active. Admitted/completed
adapter contracts are immutable; only not-yet-admitted entries may change.

## Files

- `adapter_config.template.json` — safe all-NOT_READY example;
- `contracts.py` — amendment, adapter, C:-only, completion, hash, and gate checks;
- `controller.py` — single-controller/restart/stop/transition state machine;
- `storage.py` — atomic state, append-only milestones, hashing, path checks, lock;
- `monitor.py` — read-only percentage/ETA console view;
- `cli.py` / `__main__.py` — commands;
- `scripts/run_full_pipeline_eight_day_program.ps1` — PowerShell wrapper;
- `tests/full_pipeline_eight_day_program/` — model-free synthetic tests only.

## Authoritative inputs

The controller reads:

1. `docs/full_pipeline/EIGHT_DAY_SCOPE_AMENDMENT.md` for the human-readable
   interpretation;
2. `runs/full_pipeline_program/EIGHT_DAY_SCOPE_AMENDMENT.json` as machine
   authority for the bounded scientific scope;
3. a C:-only adapter configuration supplied with `--adapter-config`;
4. stage-native inputs declared by each READY adapter;
5. the previous stage's validated completion record when Prompt 5–8 starts.

The final reproducibility package also retains
`runs/full_pipeline_program/EIGHT_DAY_EXECUTION_POLICY_ADDENDUM.json`, the
durable user-authorized record explaining why the same 192-hour scope target is
now advisory-only. The live controller records the matching policy ID in state,
status, and milestones.

No held-out prediction, dataset, model, or scientific result is opened by the
controller itself. Those remain the responsibility of the bounded stage package
and its validator.

## Adapter configuration

Create the initial all-NOT_READY configuration once:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action WriteTemplate
```

The command refuses to overwrite an existing configuration. The default output
is:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json
```

Each prompt entry is either:

```json
{
  "adapter_id": "prompt_6_adapter_pending",
  "readiness": "NOT_READY",
  "not_ready_reason": "bounded_stage_adapter_not_installed",
  "expected_duration_hours": 30
}
```

or a READY command adapter with all of these fields:

```json
{
  "adapter_id": "immutable_unique_adapter_id",
  "readiness": "READY",
  "expected_duration_hours": 30,
  "stage_workspace": "${PROGRAM_WORKSPACE}\\prompt_6",
  "cwd": "${STAGE_WORKSPACE}",
  "completion_record": "${STAGE_WORKSPACE}\\completion.json",
  "progress_record": "${STAGE_WORKSPACE}\\progress.json",
  "controller_log": "${STAGE_WORKSPACE}\\controller.log",
  "start_command": ["C:\\...\\python.exe", "-m", "app.bounded_prompt_6", "run"],
  "resume_command": ["C:\\...\\python.exe", "-m", "app.bounded_prompt_6", "resume"],
  "stop_command": ["C:\\...\\python.exe", "-m", "app.bounded_prompt_6", "stop"],
  "validate_command": ["C:\\...\\python.exe", "-m", "app.bounded_prompt_6", "validate-and-finalize"],
  "restart_policy": "RESUME_COMMAND",
  "stop_grace_seconds": 300,
  "environment": {},
  "material_paths": {
    "inputs": [],
    "workspaces": [],
    "caches": [],
    "temporary": [],
    "logs": [],
    "results": [],
    "reports": [],
    "packages": [],
    "checkpoints": []
  }
}
```

All nine material-path classes must be declared, even when a class is empty.
The stage workspace, cwd, completion record, progress record, and controller log
must also occur explicitly in that inventory. Input paths must exist at stage
admission. Every declared path and every absolute command token is resolved and
must remain on C:. Commands are argv arrays executed with `shell=False`.

Supported path tokens are `${TOOL_ROOT}`, `${PROGRAM_WORKSPACE}`,
`${AMENDMENT_PATH}`, `${PROMPT_INDEX}`, `${STAGE_WORKSPACE}`, and
`${ADAPTER_CONTRACT_SHA256}`. Commands may additionally use the runtime-only
`${PREDECESSOR_COMPLETION_PATH}`, `${PREDECESSOR_COMPLETION_SHA256}`, and
`${PREDECESSOR_COMPLETION_MARKER}` tokens. Those are expanded only after the
previous stage is revalidated; using them for Prompt 4 is an error. Unresolved
tokens fail validation.

The adapter subprocess also receives:

```text
JP8_SCOPE_ID
JP8_SCOPE_CLASS
JP8_ORIGINAL_FULL_SCOPE_COMPLETE
JP8_PROMPT_INDEX
JP8_COMPLETION_MARKER
JP8_ADAPTER_ID
JP8_ADAPTER_CONTRACT_SHA256
JP8_PROGRAM_WORKSPACE
JP8_STAGE_WORKSPACE
JP8_COMPLETION_RECORD
JP8_PROGRESS_RECORD
JP8_PREDECESSOR_PROMPT_INDEX
JP8_PREDECESSOR_COMPLETION_MARKER
JP8_PREDECESSOR_COMPLETION_PATH
JP8_PREDECESSOR_COMPLETION_SHA256
```

`TEMP`, `TMP`, and `TMPDIR` are forced to the adapter's declared C:-only
temporary directory.

The controller automatically adds its adapter configuration, authoritative
amendment, and (for Prompt 5–8) the revalidated predecessor completion record
to every admission preflight, including SHA-256. The stage adapter may also list
the fixed predecessor path under `inputs`, but it does not need a dynamic path
placeholder to make that dependency auditable.

## Universal completion contract

The stage's finalizer writes `JP8_COMPLETION_RECORD` only after its native
scientific validator passes. The record must use:

```json
{
  "schema_version": "full-pipeline-eight-day-stage-completion.v1",
  "scope_id": "full_pipeline_prompts_4_8_eight_day_c_only.v1",
  "scope_class": "BOUNDED_REDUCED",
  "original_full_scope_complete": false,
  "prompt_index": 5,
  "status": "COMPLETE",
  "completion_marker": "COMPLETE_ALL18_CORE_EVALUATION_REDUCED_8DAY_V1",
  "adapter_id": "...",
  "adapter_contract_sha256": "...",
  "predecessor": {
    "prompt_index": 4,
    "completion_marker": "COMPLETE_ALL18_DEVELOPMENT_AND_FREEZE_REDUCED_8DAY_V1",
    "completion_record_path": "C:\\...\\completion.json",
    "completion_record_sha256": "..."
  },
  "artifact_manifest": {"path": "C:\\...\\manifest.json", "sha256": "..."},
  "gate_records": {
    "hash_validation": {"path": "C:\\...\\hash_gate.json", "sha256": "..."},
    "firewall_validation": {"path": "C:\\...\\firewall_gate.json", "sha256": "..."},
    "prerequisite_validation": {"path": "C:\\...\\prerequisite_gate.json", "sha256": "..."}
  }
}
```

Prompt 4 uses `"predecessor": null`. Each gate file has schema
`full-pipeline-eight-day-gate.v1`, its exact gate name, `status: PASS`, the
prompt index, and the exact scope ID. The manifest has schema
`full-pipeline-eight-day-artifact-manifest.v1`, all bounded scope labels, the
prompt index, and a nonempty `artifacts` array. Each artifact entry has an
absolute C: path, SHA-256, and `required: true`. The manifest must include all
three gate files. The controller recalculates every referenced hash.

The adapter contract hash and predecessor values are supplied by the controller,
so a stage finalizer does not need to predict them before launch and no circular
self-hash is required.

## Outputs

The program workspace contains:

- `program_state.json` — atomic restart state and per-stage hash bindings;
- `controller.lock` — live single-controller lock (removed on clean exit);
- `controller.lock.stale.*` — retained stale-lock audit records;
- `milestones.jsonl` — append-only durable notifications;
- `stop_request.json` — last durable graceful-stop request;
- `preflights/*.json` — resolved C:-only path and free-space admissions;
- one adapter-owned stage workspace for each configured prompt.

No data is moved to D:, G:, a junction, or a network/mapped spill path. The
controller never deletes evidence or staging data.

## PowerShell commands

Validate configuration only (no campaign starts):

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Validate -Json
```

Start or restart the automatic controller after all required adapters are READY:

```powershell
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Run
```

One status snapshot:

```powershell
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Status
```

Continuous percentage/ETA monitor:

```powershell
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Monitor -Follow -IntervalSeconds 30
```

Request a graceful stop without killing the adapter:

```powershell
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action Stop -StopReason "maintenance_requested"
```

Revalidate all completed-stage hashes and the predecessor chain:

```powershell
.\scripts\run_full_pipeline_eight_day_program.ps1 -Action ValidateCompletions -Json
```

The checked-in `EIGHT_DAY_ADAPTERS.json` now declares Prompts 4–8 `READY` and
the controller advances between them automatically after each checksum and
prerequisite gate passes. The all-`NOT_READY` template remains the safe starting
point for a new program. Do not start duplicate stage wrappers beside the active
controller.

The pending Prompt 5–8 adapters also bind
`runs/full_pipeline_program/RASPBERRY_PI_DEPLOYMENT_STEERING.json`. That
authority adds Windows/x86-64 versus Linux ARM64 portability and approximate
2-GB Raspberry Pi deployment evidence without modifying Prompt 4, frozen
desktop science, evaluation membership, thresholds, splits, or ranking rules.

## Anaconda Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_eight_day_program validate-config --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json" --json
python -m app.full_pipeline_eight_day_program status --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json"
python -m app.full_pipeline_eight_day_program monitor --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json" --follow --interval-seconds 30
python -m app.full_pipeline_eight_day_program run --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json"
```

The repository `.venv` remains the validated control environment even when the
commands are entered from Anaconda Prompt.

## Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
..\..\.venv\Scripts\python.exe -m app.full_pipeline_eight_day_program validate-config --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json" --json
..\..\.venv\Scripts\python.exe -m app.full_pipeline_eight_day_program status --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json"
..\..\.venv\Scripts\python.exe -m app.full_pipeline_eight_day_program monitor --adapter-config "runs\full_pipeline_program\EIGHT_DAY_ADAPTERS.json" --follow --interval-seconds 30
```

## Tests

The focused test suite uses temporary C:-only directories and a synthetic
model-free subprocess. It does not inspect held-out predictions, load models,
or start any scientific campaign:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_eight_day_program -q
```

Expected result: `20 passed` or more as the package grows.
