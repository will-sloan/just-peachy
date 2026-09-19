# Independent V5 restoration source review

`s6d_restoration_review_checks_v5.py` verifies exact V5 source freeze764893d4, copied source files, unchanged dependencies and original saved failure. It independently compares top-level AST definitions for the owner/bridge changes and runs eight additional pure policy checks. It imports only the pure policy and never calls the owner execution function, hardware libraries, getter/setter, models or UI.

Inputs: `--source-root` is the independent copy of the six frozen files; `--freeze` is SOURCE_FREEZE.json; `--baseline` is the original saved batch folder; `--author-receipt` is the independently rerun unchanged58-fixture receipt; `--output` is fresh G. Output: compact `INDEPENDENT_REVIEW.json` with source/authority/input hashes, tests, exact AST scope and explicit limits. The checks cover exact restoration when AGC is disabled, strict numeric-vs-boolean static/ancillary values, forged derived fields, missing USB proof and policy purity. No original receipt is overwritten and no old failure becomes PASS.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$g = 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\dynamic_gain_restoration_independent_v5'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$g\source\s6d_capture_checks_v5.py" --source-root "$g\source" --baseline-batch "$r\hardware_batches\bank_v1_P_MAIN6_B1_pre_QA" --output "$g\unchanged58"
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_restoration_review_checks_v5.py" --source-root "$g\source" --freeze "$r\runner\dynamic_gain_restoration_v5\SOURCE_FREEZE.json" --baseline "$r\hardware_batches\bank_v1_P_MAIN6_B1_pre_QA" --author-receipt "$g\unchanged58\RECEIPT.json" --output "$g\additional8"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "GREV=G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\dynamic_gain_restoration_independent_v5"
"C:\Users\amiri\anaconda3\python.exe" -B "%GREV%\source\s6d_capture_checks_v5.py" --source-root "%GREV%\source" --baseline-batch "%R%\hardware_batches\bank_v1_P_MAIN6_B1_pre_QA" --output "%GREV%\unchanged58"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_restoration_review_checks_v5.py" --source-root "%GREV%\source" --freeze "%R%\runner\dynamic_gain_restoration_v5\SOURCE_FREEZE.json" --baseline "%R%\hardware_batches\bank_v1_P_MAIN6_B1_pre_QA" --author-receipt "%GREV%\unchanged58\RECEIPT.json" --output "%GREV%\additional8"
```

First verify every `source_copies[].copy` SHA256/byte count against the freeze and copy those files into a fresh G source directory. Both fixture commands require fresh output suffixes. The current frozen hardware owner intentionally retains maintained-path resolution: copied files are for pure metadata tests only, never physical execution. Source acceptance does not authorize recovery, new QA or capture launches; those remain root-owned separate gates.
