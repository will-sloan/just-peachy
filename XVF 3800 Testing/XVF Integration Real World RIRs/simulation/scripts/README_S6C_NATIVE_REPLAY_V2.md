# Native observation replay and parity

Purpose: verify that completed S6C native sessions reproduce every logical speaker decision and shared transcript/name event through the exact frozen v3 scheduler. Writes hash-bound compressed predictions for analysis and a detailed parity receipt. A mismatch stops immediately with retained differences. This runs no new neural models and performs no audio playback.

Inputs: an immutable S6C epoch, one or more COMPLETE native result indices, and a new simple output label. Source receipts bind actual vectors, raw observations, events and PCM journals. Equal candidate/case/routes cannot be pooled; use separate labels for repeated runs. Naming jobs load their exact isolated manifest.

Outputs: `reports/S6C/20260910T123540Z/<epoch>/<label>_NATIVE_REPLAY_PARITY.json`, a corresponding prediction index, and gzip predictions on G:. Native clocks and costs remain in the source receipts; replay costs and release-watermark mechanics are deliberately excluded from logical parity, never substituted for native latency. Resume validates all sources and reruns parity before accepting an existing prediction.

PowerShell, from the repository root:

```powershell
$sim = Join-Path (Get-Location) 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& '.\.edge-speech-env\python.exe' "$sim\scripts\s6c_native_replay_v2.py" --epoch epoch1 --results "$sim\reports\S6C\20260910T123540Z\jobs\epoch1\smoke_v1_RESULTS.json" --label smoke_v2
```

Anaconda Prompt / CMD, from the repository root (the explicit verified environment is used):

```bat
set "SIM=%CD%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
".edge-speech-env\python.exe" "%SIM%\scripts\s6c_native_replay_v2.py" --epoch epoch1 --results "%SIM%\reports\S6C\20260910T123540Z\jobs\epoch1\smoke_v1_RESULTS.json" --label smoke_v2
```

Do not edit an epoch or existing outputs. Diagnose a mismatch and preserve its receipt before making a separately named source revision. The helper itself is bound into every new prediction.

V2 preserves requested counts and failed/missing source rows; incomplete source grids cannot become COMPLETE. Resume compares every semantic payload field against a freshly recomputed exact replay, including when interruption prevented a final index. The v1 helper and valid six-cell smoke outputs remain unchanged.
