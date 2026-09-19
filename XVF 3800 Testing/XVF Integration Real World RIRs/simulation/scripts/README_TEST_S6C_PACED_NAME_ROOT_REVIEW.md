# Independent paced name-emission review

Purpose: review the held pure name-emission API with an independent integer-time oracle and synthetic whole-API cases. It tests stable-name attainment, repeated occurrences, arrived-span causality, empty-text clearing, overlapping empty-control row exposure, clock reversal, and admission/closure failures. It performs no native run, model call, policy replay, actual paced scoring or original-source edits.

Inputs are the exact held helper digest in the test and its unchanged scorer dependencies; all event/support/gallery fixtures are generated in memory. Output is one fresh JSON review receipt with source hashes, checks and explicit zero empirical execution counts. Existing output files are refused. A future intentionally changed helper needs a separately reviewed digest; do not repoint the test merely to hide a failure.

PowerShell:

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& (Join-Path $s6cRepo '.edge-speech-env\python.exe') (Join-Path $s6cSim 'scripts\test_s6c_paced_name_root_review.py') --output (Join-Path $s6cSim 'reports\S6C\20260910T123540Z\independent_review\PACED_NAME_EMISSION_ROOT_REVIEW_V1.json')
```

Anaconda Prompt or Windows CMD (use the exact existing Python even inside another active environment):

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\test_s6c_paced_name_root_review.py" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\independent_review\PACED_NAME_EMISSION_ROOT_REVIEW_V1.json"
```

No environment install or physical audio device is involved. The collector still must independently verify actual paced source, owner closure, original events, gallery and Q/support bytes before using the API on observations.

