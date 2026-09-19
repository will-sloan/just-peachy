# One current process snapshot for new QA restoration

Purpose: record current absence of the exact failed capture owner639888, bankV5 supervisor638164 and recorded telemetry host602832, including their creation times. Inputs are fixed QA identity metadata0785aaf3 and the unchanged accepted V5 process scanner af89c6df. The helper queries one complete process inventory and runs the existing strict marker/identity/readability decision, excluding only its own PID. Unknown or unreadable relevant processes block; no absence is inferred from a failed query.

Output: one fresh `--output` JSON below this S6D report root, including full inventory, decision, original identities and source bindings. This is read-only: no hardware lease, TCP query, getter, setter, recorder, audio, process termination or launch. It cannot itself authorize restoration. Actual V6 restoration repeats current process/TCP checks under the hardware lease. Run the file normally so a parent inline command containing control-tool names does not create a false control-marker match.

PowerShell / Anaconda PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_root_process_snapshot_v1.py" --output "$sim\reports\S6D\20260913T195357Z\capture_telemetry_recovery_v3\ROOT_PROCESS_SNAPSHOT.json"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_root_process_snapshot_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\capture_telemetry_recovery_v3\ROOT_PROCESS_SNAPSHOT.json"
```

Existing files are preserved; select a new output name for a separately justified observation. No repeated healthy polling is required. A successful scan remains time-specific evidence and does not explain historical telemetry or storage delays.
