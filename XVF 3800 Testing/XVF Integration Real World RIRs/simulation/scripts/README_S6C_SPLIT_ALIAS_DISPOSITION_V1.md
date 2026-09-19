# S6C split-route alias disposition V1

Purpose: preserve the unexecuted224-job split preparation while making a new112-job manifest containing only C085 O0-ASR/O1-ID and C086 O1-ASR/O0-ID. Every selected original job object, job key and output folder stays exact. C083 O0/O0 and C084 O1/O1 are documented aliases of actual completed C065 same-tap cells after removing only executable profile_id; input audio/PCM declarations, durations and conditions must also match per case.

Inputs: exact old jobs/epoch2/split_v1.json and split_scan_v1/ADMISSION.json, reviewed route_coverage_v1/ROUTE_COVERAGE.json, original recipes_v1 C065 jobs and their112 COMPLETE metadata receipts. It rejects any execution artifact in the old coordinator namespace or any existing native split output folder. No waveform, model, vectors, prediction/score bodies or journals are read. Outputs: jobs/epoch2/split_cross_only_v2.json and design/SPLIT_ALIAS_DISPOSITION_V1.json, both immutable. Old files are preserved. There are no model or hardware calls and no coordinator launch.

PowerShell preparation:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py "$sim\scripts\s6c_split_alias_disposition_v1.py"
& $py "$sim\scripts\s6c_orchestrator_scan_v2.py" prepare --jobs "$sim\reports\S6C\20260910T123540Z\jobs\epoch2\split_cross_only_v2.json" --workers 4 --name split_cross_only_scan_v2
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
"%PY%" "%SIM%\scripts\s6c_split_alias_disposition_v1.py"
"%PY%" "%SIM%\scripts\s6c_orchestrator_scan_v2.py" prepare --jobs "%SIM%\reports\S6C\20260910T123540Z\jobs\epoch2\split_cross_only_v2.json" --workers 4 --name split_cross_only_scan_v2
```

The second command creates only a V2 coordinator admission and revalidates its frozen dependencies. Root controls the later run queue. After independent admission review and prior worker closure, the existing V2 run syntax is `s6c_orchestrator_scan_v2.py run --admission <REPORT\orchestration\split_cross_only_scan_v2\ADMISSION.json>`; do not run it as part of this preparation. Alias disposition does not fabricate candidate-ID predictions, new scores or physical attempts.
