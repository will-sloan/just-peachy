# S6B chained 35-cell admission

`s6b_paced_resume_v3.py` creates the exact completion-only v3→v4 continuation while verifying both earlier reuse ledgers. Its purpose is to preserve every prior result and interrupted attempt, reuse 35 valid logical cells, and leave 29 original native jobs for execution. It starts no model and changes no source artifact.

Inputs are the closed v3 source, original-driver prepared fresh v4 destination, v3 interruption inventory, and ordered prior v1/v2 resume ledgers. Outputs are 70 exact copied files (35 COMPLETE.json and PROCESS_SAMPLES.jsonl pairs) and one admission receipt with their hashes, all native artifact chains and current PID/creation closure. Original absolute artifact references are retained. The first two native artifacts resolve into v1, the next 22 into v2 and the newest 11 into v3, but only through explicit per-job membership in every intervening reuse ledger.

All declared source inventories, manifests and previous copy bindings verify before copying. Every completed worker must match the native job key, whole source duration/sample count and expected PCM body hash/length. Current copied trajectories must match the original binding inside the unchanged completion receipt. Source buffers are rehashed just before exclusive destination creation, flushed/fsynced, checked afterward, and all preserved source bindings rechecked. There is no overwrite or partial-admission resume: use a fresh namespace after any interrupted copy operation. No filesystem transaction isolation against a concurrent external writer is claimed.

The source snapshot was already created by the unchanged historical helper at `paced/PACED_V3_INTERRUPTION_SOURCE_INDEX.json`. That helper and all old source/receipt files remain preserved. This new helper requires exactly 35 completions; it is deliberately bounded to the reviewed continuation. Native launch still waits for independent admission/observer review and a renewed quiet interval.

## PowerShell

Run once after v4 is prepared with the original driver and identical 64-job profile/case/tap/repetition selection. Existing receipt or destination jobs cause rejection.

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$paced = "$sim\reports\S6B\20260909T230840Z\paced"
$payload = 'G:\Just_Peachy_S6B\20260909T230840Z'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_resume_v3.py" --source "$payload\paced_finalists_epoch2_v3" --destination "$payload\paced_finalists_epoch2_v4" --inventory "$paced\PACED_V3_INTERRUPTION_SOURCE_INDEX.json" --prior-ledgers "$paced\PACED_READ_RETRY_RESUME_V1.json" "$paced\PACED_LIVE_READER_RESUME_V2.json" --receipt "$paced\PACED_OPTIONAL_LIVE_RESUME_V3.json"
```

## Anaconda Prompt / Windows CMD

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PACED=%SIM%\reports\S6B\20260909T230840Z\paced"
set "PAYLOAD=G:\Just_Peachy_S6B\20260909T230840Z"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_resume_v3.py" --source "%PAYLOAD%\paced_finalists_epoch2_v3" --destination "%PAYLOAD%\paced_finalists_epoch2_v4" --inventory "%PACED%\PACED_V3_INTERRUPTION_SOURCE_INDEX.json" --prior-ledgers "%PACED%\PACED_READ_RETRY_RESUME_V1.json" "%PACED%\PACED_LIVE_READER_RESUME_V2.json" --receipt "%PACED%\PACED_OPTIONAL_LIVE_RESUME_V3.json"
```

Count copied references separately from physical inference. The prospective final accounting is 64 successful physical sessions plus three interrupted sessions, not 64+2+24+35 successes. Four observer versions and three gaps remain part of the resource interpretation. Optional missing LIVE samples are visible in trajectories and counters; no interpolation or favorable-repetition selection is permitted.
