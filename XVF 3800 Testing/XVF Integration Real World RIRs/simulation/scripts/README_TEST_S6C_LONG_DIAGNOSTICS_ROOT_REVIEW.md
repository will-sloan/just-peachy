# Independent continuous diagnostics source review

Purpose: reproduce the held helper's 39 small checks and add independent streaming, source/emission order, closure-event, quiet-gate, source-frame and process-missingness fixtures. It checks the six reused pure function selections against their pinned original source. This test creates no native session, policy replay, model or PCM read and does not read an actual long-session event log.

Inputs are the exact held local helper and its pinned source dependencies. The expected production helper SHA is recorded in the test. Outputs are a fresh JSON review receipt, with exact helper/README/test bindings, check names and scope. Temporary synthetic files are removed by Python's temporary-directory manager; existing sources and receipts remain unchanged. Passing this test does not establish actual session completion.

Use the existing EDGE executable in either shell. No installation or environment activation is needed.

PowerShell:

```powershell
$simTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pythonTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $pythonTask -B "$simTask\scripts\test_s6c_long_diagnostics_root_review.py" --output "$simTask\reports\S6C\20260910T123540Z\independent_review\LONG_DIAGNOSTICS_ROOT_REVIEW_V1.json"
```

Anaconda Prompt or Windows CMD:

```bat
set "S6C_REVIEW_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REVIEW_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_REVIEW_PY%" -B "%S6C_REVIEW_SIM%\scripts\test_s6c_long_diagnostics_root_review.py" --output "%S6C_REVIEW_SIM%\reports\S6C\20260910T123540Z\independent_review\LONG_DIAGNOSTICS_ROOT_REVIEW_V1_CMD.json"
```

The output must not exist. Use a new filename for a reproduction; preserve failed or previous results. Actual continuous analysis uses README_S6C_LONG_DIAGNOSTICS_V1.md only after native closure and outside paced measurement intervals.

