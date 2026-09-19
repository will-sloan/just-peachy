# Frozen S6C native execution

`s6c_execution.py` freezes an exact application/code epoch and executes explicit
job manifests through the actual `PipelineEngine.start_paired_files` v3 route.
It uses the existing fixed assets and one resident model bundle per worker,
with fresh decoder/tracker/name/session state per scene. Actual paired journals,
model observations, gallery loading, transcript events and native completion
receipts must exist. Failed jobs are preserved and never silently replaced by
scorer labels or empty transcripts.

## Inputs and outputs

Freeze inputs: the reviewed live application, S6C helper source, validated
effective registry, metadata-only panel, S6B bound input index, original bank
and exact existing model assets. Freeze output is a versioned copy beneath
`simulation/staging/s6c/20260910T123540Z/<epoch>` and an immutable
`<EPOCH>_EXECUTION_MANIFEST.json` in the S6C report root. Do not freeze while
source is being edited; a changed source requires a new epoch.

Run input: an explicit immutable JSON object containing `jobs` and `stage`.
Every job binds its full profile, source pair/PCM hashes, capture origin,
telemetry, actual isolated gallery if required, and execution digest. The
job-builder entry documents supported stage selection. Bulk outputs go to
`G:\Just_Peachy_S6C\20260910T123540Z\<epoch>`; compact status/resource/ownership
receipts go to the report root. Readme output paths are examples; execute the
exact generated job-manifest path for the stage being resumed.

## Freeze (after review)

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_execution.py freeze --epoch epoch1
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_execution.py freeze --epoch epoch1
```

## Execute or resume an admitted manifest

PowerShell:

```powershell
$env:JP_S6C_SIM='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cFrozen=Join-Path $env:JP_S6C_SIM 'staging\s6c\20260910T123540Z\epoch1\scripts\s6c_execution.py'
$s6cJobs=Join-Path $env:JP_S6C_SIM 'reports\S6C\20260910T123540Z\jobs\epoch1\smoke_v1.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' $s6cFrozen run --epoch epoch1 --jobs $s6cJobs --workers 1
```

Anaconda Prompt / CMD:

```bat
set "JP_S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_S6C_SIM%\staging\s6c\20260910T123540Z\epoch1\scripts\s6c_execution.py" run --epoch epoch1 --jobs "%JP_S6C_SIM%\reports\S6C\20260910T123540Z\jobs\epoch1\smoke_v1.json" --workers 1
```

One worker is mandatory for paced runs; accelerated batch inference permits up
to four. Do not run heavy inference concurrently with paced/HIL acceptance.
The same command resumes only exactly matching successful receipts. A prior
failure/incomplete attempt stops admission until diagnosed and given an
explicit named retry location. Original failure bytes remain evidence.

## Monitoring and closure

The coordinator owns a one-byte Windows file lock and a creation-time-bound
ProcessPool. `HEARTBEAT.json` updates every 20 seconds with jobs, reuse/new
counts, active IDs, resource state and a measured ETA range. Optional observer
read faults are logged separately; native receipts stay authoritative and
strict. Durable per-invocation `rows.json`, completion and closure are written.
Only the coordinator's own workers are joined; unrelated apps are untouched.

`STOP_REQUEST.json` stops admission of new jobs. Active bounded jobs close and
write receipts. Resource floors/cap and the invocation closure reserve are in
README_S6C.md. A partial invocation is not a completed S6C study. Paired file
inference is silent host processing, not physical-board replay or CM5 proof.

Epoch2 repair: initial attempt/status writes are inside the native job failure handler. The common atomic writer has a bounded two-second PermissionError retry for transient Windows destination locks. Epoch1's failed recipe invocation and all actual receipts are preserved; the unchanged APP/model pipeline is frozen again before retry.

Use optional --registry with the absolute validated registry path when freezing C-only calibrated alternatives; default remains V1. A reused epoch must match that exact registry binding. Epoch2 also freezes native-replay v2, policy-matrix and calibrated-profile orchestration sources.

Epoch3 freezes the policy-matrix v2 compatible-source guard and the explicitly outcome-informed24-row rescue registration. Use --registry with EFFECTIVE_PROFILE_REGISTRY_V3.json. Application/model bytes remain separately compared to prior epochs; changing the registry alone does not authorize a neural cache with different frontend dependencies.
