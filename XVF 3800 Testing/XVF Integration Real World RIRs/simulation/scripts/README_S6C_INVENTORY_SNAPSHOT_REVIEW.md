# Review the preserved execution inventory snapshot

`test_s6c_execution_inventory_snapshot_v2.py` verifies and reproduces the saved
snapshot_v2 accounting using its exact metadata copies. It never follows a
receipt binding back to a current mutable source. It checks physical attempt
merging, session/job distinctions, event sums, per-worker cumulative-load maxima,
missing numeric values, native index reference gaps and prediction materialization
counts. It retains saved owner-state observations, not a new process census.

Inputs: SHA-pinned snapshot_v2, source snapshots, physical rows and the preserved
metadata resolver/copies. It also reruns34 pure source fixtures in temporary
metadata files. No audio, vectors, models, compressed predictions or event logs
are opened. Output: one fresh independent review JSON. This does not create a
new execution inventory or certify that the active study has finished.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$s6cSimulation\scripts\test_s6c_execution_inventory_snapshot_v2.py" --output "$s6cSimulation\reports\S6C\20260910T123540Z\independent_review\EXECUTION_INVENTORY_COMPONENT_REVIEW_V2.json"
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIMULATION=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set PYTHONDONTWRITEBYTECODE=1
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%S6C_SIMULATION%\scripts\test_s6c_execution_inventory_snapshot_v2.py" --output "%S6C_SIMULATION%\reports\S6C\20260910T123540Z\independent_review\EXECUTION_INVENTORY_COMPONENT_REVIEW_V2.json"
```

Use a new review filename rather than overwrite an existing receipt. Saved
metadata reads add I/O; avoid executing during a quiet paced/HIL interval.
