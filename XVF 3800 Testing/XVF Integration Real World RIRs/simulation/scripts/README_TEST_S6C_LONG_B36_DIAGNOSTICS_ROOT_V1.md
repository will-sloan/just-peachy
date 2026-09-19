# Independent review of original B36 continuous diagnostics

This helper reviews the pinned B36 continuous reporting source before any completed continuous session is available. It runs the 41 owner fixtures, checks unchanged historical observation functions, and independently exercises actual-summary schema, observer denominator, quiet-lease, clock and process-accounting cases. It does not launch a model, replay policy, read native session logs or access PCM.

Inputs are the held diagnostic helper and its source dependencies, plus synthetic data created in an automatically managed temporary directory. The output is one immutable JSON review receipt with source hashes and the exact check list. This review is not evidence that an actual session completed. Reporting preparation/execution still requires later native closure.

PowerShell:

    $s6cSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
    Set-Location -LiteralPath $s6cSim
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B 'scripts\test_s6c_long_b36_diagnostics_root_v1.py' 'reports\S6C\20260910T123540Z\independent_review\LONG_B36_DIAGNOSTICS_ROOT_REVIEW_V1.json'

Anaconda Prompt or Windows Command Prompt (no conda activation or installation required):

    cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B scripts\test_s6c_long_b36_diagnostics_root_v1.py reports\S6C\20260910T123540Z\independent_review\LONG_B36_DIAGNOSTICS_ROOT_REVIEW_V1.json

Choose a fresh receipt filename for a later run; existing output is preserved. A failed check raises an exception before publishing a PASS receipt.

The first review invocation stopped at a malformed opening docstring before any code executed. The source and README are preserved under staging/s6c/20260910T123540Z/b36_diagnostics_root_review/before_docstring_fix_v1. The held production diagnostic source was unchanged.
