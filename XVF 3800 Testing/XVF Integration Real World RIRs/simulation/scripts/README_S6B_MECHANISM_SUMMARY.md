# Compact the completed full R0 mechanism audit

Purpose: `s6b_mechanism_summary.py` makes a compact, source-bound JSON and Markdown derivative of the completed full R0 audit. It does not execute a tracker or neural model, read reference speakers or geometry, access hardware, select a winning method, or change campaign evidence. It uses only Python's standard library.

Inputs: a passing full `s6b_mechanism_audit.py` report, its exact bound prediction index and frozen epoch manifest, the manifest's canonical input index, and explicit expected profile/scene/native-job counts. The full R0 population is 23 profiles × 240 scenes × O0/O1 = 11,040 predictions sharing 480 native jobs. Original B00 is included but lacks S6B tracker instrumentation; unavailable internal activity is not reported as a measured zero.

Outputs: a new JSON with exact cell-grid checks, per-profile and per-tap mechanism/capacity/cue/revision counts, deduplicated native counts and source hashes; plus a small Markdown table. It checks the independently aggregated counters against the original audit, rejects duplicate or missing cells, and refuses existing output names. The full audit remains local and unchanged. It verifies the full audit and its upstream index/source bindings, while the full audit itself is the evidence for the expensive native/prediction byte rehash.

Activity is distinct from benefit. Unknown fractions here use decision counts; the scientific scorer uses different explicit support/turn/word denominators. Positive cue credit and nonzero spatial scores do not establish a changed final label. Dormant reactivation is an operation, not a reference-scored correct return. The export keeps tracker forward revisions separate from transcript revision scopes. Current missing-cue comparisons may retain earlier cue state. No parameter fitting occurs.

## PowerShell

Use the verified interpreter; no environment or package installation is required. First run the full model-free audit if it has not already completed, then export its compact derivative.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$report = Join-Path $sim 'reports\S6B\20260909T230840Z'
& $py "$sim\scripts\s6b_mechanism_audit.py" predictions --epoch epoch2 --index "$report\R0_FULL_PREDICTION_INDEX.json" --output-name R0_FULL_MECHANISM_AUDIT_FINAL.json
& $py "$sim\scripts\s6b_mechanism_summary.py" --audit "$report\mechanisms\R0_FULL_MECHANISM_AUDIT_FINAL.json" --output "$report\mechanisms\R0_FULL_MECHANISM_SUMMARY.json" --expect-profiles 23 --expect-scenes 240 --expect-native-jobs 480
```

## Anaconda Prompt or Command Prompt

No `conda activate` is needed because the interpreter is explicit.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "REPORT=%SIM%\reports\S6B\20260909T230840Z"
"%PY%" "%SIM%\scripts\s6b_mechanism_audit.py" predictions --epoch epoch2 --index "%REPORT%\R0_FULL_PREDICTION_INDEX.json" --output-name R0_FULL_MECHANISM_AUDIT_FINAL.json
"%PY%" "%SIM%\scripts\s6b_mechanism_summary.py" --audit "%REPORT%\mechanisms\R0_FULL_MECHANISM_AUDIT_FINAL.json" --output "%REPORT%\mechanisms\R0_FULL_MECHANISM_SUMMARY.json" --expect-profiles 23 --expect-scenes 240 --expect-native-jobs 480
```

Skip the first command when the accepted full audit already exists. For a later repeat, choose new audit and summary filenames and update both arguments. Do not overwrite historical audit receipts. These commands do not launch new inference or play audio.
