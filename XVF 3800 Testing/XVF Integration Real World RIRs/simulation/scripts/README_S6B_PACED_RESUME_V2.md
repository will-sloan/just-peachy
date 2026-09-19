# S6B exact completion resume admission

`s6b_paced_resume_v2.py` records a scoped closed-source file inventory, then copies only exact completed receipt/trajectory pairs into a fresh original-driver prepared namespace. Its inputs are the source, destination, source inventory and previous immutable resume ledger. It outputs a JSON preservation/admission receipt and, in admit mode, copied COMPLETE.json and PROCESS_SAMPLES.jsonl files. It starts no model or child process and performs no deletion or move.

Snapshot mode inventories every file in the explicitly supplied paced namespace and rejects any still-live PID/creation identity found in launch, completion, failure or coordinator records. Admission verifies that inventory, the earlier resume ledger's entire original source closure and copied bytes, all job objects/keys, and each native artifact binding. Only current job artifacts or explicitly earlier-admitted original job paths are accepted. The first two of the current 24 completions legitimately point into the original v1 namespace. Their absolute paths are preserved; no receipt is rewritten.

The destination must have a prepared original manifest with all job objects identical and no jobs directory. All preflight checks precede copying. Each source buffer is rehashed immediately before exclusive destination creation, flushed/fsynced and rehashed afterward. There is no overwrite/resume of a partially copied admission: preserve any interrupted destination and use a fresh namespace. A final source recheck detects intervening changes; it does not provide filesystem transaction isolation. Snapshot and receipt destinations must be outside the source namespace.

Use the exact project interpreter. The commands below are the intended one-time v2→v3 admission; existing receipts/destinations deliberately block repetition. The original frozen driver already prepared v3 with B00,B36,B10,B17, both O0/O1 taps and two repetitions. Native execution remains separately gated by independent review and a reserved quiet period; see README_S6B_PACED_LIVE_READER_V2.md.

## PowerShell

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$paced = "$sim\reports\S6B\20260909T230840Z\paced"
$source = 'G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v2'
$dest = 'G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v3'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_resume_v2.py" --mode snapshot --source $source --receipt "$paced\PACED_V2_INTERRUPTION_SOURCE_INDEX.json"
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_resume_v2.py" --mode admit --source $source --destination $dest --inventory "$paced\PACED_V2_INTERRUPTION_SOURCE_INDEX.json" --prior-ledger "$paced\PACED_READ_RETRY_RESUME_V1.json" --receipt "$paced\PACED_LIVE_READER_RESUME_V2.json"
```

## Anaconda Prompt / Windows CMD

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PACED=%SIM%\reports\S6B\20260909T230840Z\paced"
set "SOURCE=G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v2"
set "DEST=G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v3"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_resume_v2.py" --mode snapshot --source "%SOURCE%" --receipt "%PACED%\PACED_V2_INTERRUPTION_SOURCE_INDEX.json"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_resume_v2.py" --mode admit --source "%SOURCE%" --destination "%DEST%" --inventory "%PACED%\PACED_V2_INTERRUPTION_SOURCE_INDEX.json" --prior-ledger "%PACED%\PACED_READ_RETRY_RESUME_V1.json" --receipt "%PACED%\PACED_LIVE_READER_RESUME_V2.json"
```

The retained logical count includes copied successes only once. Physical interrupted attempts remain separate evidence. Do not add the two earlier copied references to the physical inference count. Three observer versions and interruption gaps limit resource comparisons; native source order and algorithms remain frozen.
