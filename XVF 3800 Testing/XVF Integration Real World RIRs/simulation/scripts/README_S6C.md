# S6C integrated enrollment and spatial study

This directory adds versioned S6C orchestration around the existing application,
canonical 240 physically processed scene pairs and disjoint permitted local
speech. S6C preserves S0–S6B, all RIRs/model weights, source rights/exclusions and
the GUI default. It does not start S6D, training, a new download or human recording.

## Current entry points and inputs/outputs

`s6c_common.py` supplies exact path/hash bindings, atomic JSON, resource admission
and current resource inspection. It reads the local filesystem and writes no
files when invoked directly. It prints RAM, C/G free space and the bytes under
the three new S6C roots. C retains 50 GiB, G 75 GiB; new output cap is 120 GiB.
Actual execution starts with at most four workers and one inner model thread.

`s6c_design.py` reads the previous effective profile registry, source support
receipts, canonical bank and metadata panel. It registers hypotheses before
new S6C inference/results, writes the design/panel, coverage CSV and checkpoint
under `simulation/reports/S6C/20260910T123540Z`. A completed design is immutable;
rerunning returns it, never rewrites it from newer outcomes. Effective runnable
profiles and cache identity are admitted separately after component validation.

Source inventory and independent foundation commands have their own maintained
`README_S6C_SOURCES.md` and `README_S6C_FOUNDATION_AUDIT.md`. New neural execution,
native/replay acceptance, paced endurance and packaging commands will be added
as those entry points are implemented and reviewed. A registered plan alone is
not a completed experiment or an executable simulation campaign.

## PowerShell

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_common.py
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' .\s6c_design.py
```

## Anaconda Prompt or CMD

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_common.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_design.py
```

Use the existing interpreter directly; no package reinstall is required.

## Checkpoint, stop and bounds

The invocation started 2026-09-10 12:35:40 UTC with 72 hours allowed. New work
stops by 2026-09-13 11:35:40 UTC, preserving one hour for safe closure and
packaging. `S6C_CHECKPOINT.json` records progress. Actual coordinators maintain a
10–30 second heartbeat and creation-time-bound process ownership; only their
own workers are closed. Never stop unrelated applications to meet a benchmark.

To request cooperative stop, create `STOP_REQUEST.json` in the S6C report root
with an object such as `{"reason":"operator requested pause"}`. Admission
then fails before another unit begins. A stop does not complete remaining
scope, and existing successful receipts are preserved for exact resume.

Optional digital board playback remains gated on this session's analog-output
setup fact plus one-owner/exact-endpoint/settings/bit-transparency checks.
Offline file inference produces no sound through PC or XVF outputs. Optional
hardware absence never substitutes fabricated device enrollment for real
processing and does not block mandatory offline enrollment.

## Rollback

The pre-S6C exact app snapshot and original hashes are recorded by
`reports/S6C/20260910T123540Z/INTAKE_AND_SNAPSHOT.json`; original S6B evidence
remains immutable. No Git reset, cleanup or broad file replacement is part of
rollback. Run without a v3 profile to use the preserved ordinary application
branch. Do not mutate the source of an active or frozen execution epoch.

Epoch2 orchestration repair: atomic JSON replacement retries only Windows PermissionError for at most two seconds; persistent errors remain fatal with the temporary file preserved. Epoch1 source and failed-attempt evidence remain unchanged.
