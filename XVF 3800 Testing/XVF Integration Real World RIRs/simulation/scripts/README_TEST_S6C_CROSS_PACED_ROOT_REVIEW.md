# Independent cross-route coordinator review

This source-only review reproduces 21 local and 72 inherited checks, verifies the exact registered C085 O0-ASR/O1-ID and C086 O1-ASR/O0-ID routes and 16+4 panel metadata, and checks the worker AST against the original with only the separate result schema and quiet-lease kind changed.

An isolated copy of the adapted coordinator is exercised with a synthetic successful Popen handle followed by an injected creation-time query failure. No real process is launched. Temporary files prove the spawn record precedes the query, only the owned fake handle is closed, unknown creation stays unknown and the quiet lease remains retained instead of claiming successful closure. The test never prepares PCM, loads models or chooses a finalist.

Inputs are the pinned local source files and original epoch/panel metadata. Output is a fresh JSON review receipt with source bindings and the synthetic failure projection. Temporary fixture paths in that projection are test-only and expire; they are not real native evidence. Use a fresh receipt filename for each run. No installation is required.

PowerShell:

```powershell
$simTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pythonTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $pythonTask -B "$simTask\scripts\test_s6c_cross_paced_root_review.py" --output "$simTask\reports\S6C\20260910T123540Z\independent_review\CROSS_PACED_ROOT_REVIEW_V1.json"
```

Anaconda Prompt / Windows CMD:

```bat
set "S6C_CROSS_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_CROSS_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_CROSS_PY%" -B "%S6C_CROSS_SIM%\scripts\test_s6c_cross_paced_root_review.py" --output "%S6C_CROSS_SIM%\reports\S6C\20260910T123540Z\independent_review\CROSS_PACED_ROOT_REVIEW_CMD_V1.json"
```

Actual prepare/run commands belong to README_S6C_PACED_CROSS_ROUTES_V1.md and require the separately reviewed inventory/analysis adapter and exclusive quiet interval. A source review is not completed runtime acceptance.


The initial AST fixture omitted the documented quiet-lease-kind literal; it was corrected before the isolated coordinator fault test. Prior fixture/README bytes and the reason are preserved under cross_paced_root_review/before_metadata_projection_fix_v1. The production coordinator and original native function were unchanged.

The first isolated coordinator attempt also exposed a missing STDOUT constant in the synthetic subprocess stub before its fake Popen ran. The corrected stub includes that ordinary constant; its prior source is preserved as before_stub_stdout_fix_v2.py. No production process or source changed.
