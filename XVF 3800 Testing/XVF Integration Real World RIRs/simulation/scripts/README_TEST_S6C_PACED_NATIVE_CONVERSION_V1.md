# Existing native control for the paced converter

This model-free check exercises the new converter's pure extraction, policy replay and event summaries using the already completed **accelerated** C105/S45_08_07/O0 native case. It requires the pinned native integration audit, original epoch2 code and actual source receipts. It compares every decision, transcript/name event and three final label views to the already accepted own-source prediction, then checks event and shared dispatch counts.

It does not run models or pacing, admit a paced cell, manufacture a paced native receipt, or publish the in-memory prediction. A clearly marked `TEST_ONLY_SOURCE_PROJECTION.json` retains the two metadata fields needed by the pure function and the actual original receipt binding. It is not accepted by the paced inventory. The test creates that immutable small projection under `REPORT/paced_analysis_checks/observed_accelerated_control_v1`, and prints its review result. `--output` additionally writes a receipt to a fresh path; existing results are not overwritten.

This check cannot establish actual paced process/trajectory/quiet-lease admission. Those require the later real closed cells. It does perform one bounded post-closure policy replay, which is counted separately from zero new neural/native runs.

## PowerShell

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& (Join-Path $s6cRepo '.edge-speech-env\python.exe') (Join-Path $s6cSim 'scripts\test_s6c_paced_native_conversion_v1.py')
```

## Anaconda Prompt or Windows CMD

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\test_s6c_paced_native_conversion_v1.py"
```

Use the existing exact native Python; no installation is needed. To retain a new review receipt, append `--output` and a fresh absolute JSON filename under the existing `independent_review` directory. The helper sets the task-specific `JP_S6C_SIM` import root before importing the exact frozen epoch modules.
