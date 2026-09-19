# Native replay guard fixtures

Purpose: verify that timing-only changes are excluded from semantic comparison while changed labels/source availability fail it, and that six simulated failed rows remain visible through repeated resume. Uses an explicitly labeled derived failure fixture; the original successful smoke results are untouched. No neural models or audio outputs run.

Inputs: existing epoch1 smoke index, unchanged frozen epoch1 and native-replay v3 helper. Outputs: model-free fixture and six-check receipt under replay_guard_checks/v1, plus a clearly named PARTIAL fixture index under epoch1. The test namespace must be new.

PowerShell from repository root:

```powershell
& '.\.edge-speech-env\python.exe' '.\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_replay_guard_checks.py'
```

Anaconda Prompt / CMD:

```bat
".edge-speech-env\python.exe" "XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_replay_guard_checks.py"
```

Never include the synthetic failure fixture as empirical accuracy/native execution. It exists only to test coverage bookkeeping and resume handling.
