# S6B completed prediction admission guard

Purpose: verify already-created replay outputs against previously completed indexes before another replay invocation reuses them. The frozen native cache already validates source/config/artifact bytes; this adds a separate prediction-file byte boundary to its existing prediction-key check. It never edits predictions or performs inference.

Inputs: one or more completed prediction indexes. An optional existing prediction directory must contain only files covered by those indexes. Outputs: a new guard receipt listing exact indexes and unique output bindings. A same-size/same-mtime byte edit with an unchanged prediction key is rejected; incomplete unindexed outputs require diagnosis before reuse.

PowerShell, before extending the challenge replay:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py "$sim\scripts\s6b_prediction_guard.py" --test
& $py "$sim\scripts\s6b_prediction_guard.py" --indexes B00_FULL_PREDICTION_INDEX.json R0_CHALLENGE_PREDICTION_INDEX.json --existing-folder "$sim\reports\S6B\20260909T230840Z\epoch2\predictions" --receipt CHALLENGE_REPLAY_INPUT_GUARD.json
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6B_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6B_PY%" "%SIM%\scripts\s6b_prediction_guard.py" --test
"%S6B_PY%" "%SIM%\scripts\s6b_prediction_guard.py" --indexes B00_FULL_PREDICTION_INDEX.json R0_CHALLENGE_PREDICTION_INDEX.json --existing-folder "%SIM%\reports\S6B\20260909T230840Z\epoch2\predictions" --receipt CHALLENGE_REPLAY_INPUT_GUARD.json
```

Add the completed challenge/full-bank index to the list for later invocations and use a fresh receipt filename. Do not launch dependent replay if the guard fails. Complete indexes are retained as admission evidence; no hash manifest includes itself. This tool is independent of frozen prediction code and does not invalidate completed neural work.
