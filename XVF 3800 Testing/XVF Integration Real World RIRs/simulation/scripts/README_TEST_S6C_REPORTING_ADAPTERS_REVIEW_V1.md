# Independent common-duration and cadence reporting admission review

`test_s6c_reporting_adapters_review_v1.py` reviews the separate full-bank common-duration collector V2 and four-candidate cadence scorer admission. Inputs are held source/README bytes, the exact existing cadence admission receipt and its declared registries. It compares six inherited duration functions by AST, executes five inherited and four exact-buffer duration fixtures, and reruns the actual238-label admission routine while intercepting only its final receipt publication. It checks that the captured admission matches the original and all original source/receipt bytes remain unchanged.

No full result collection, prediction scoring, audio reading, model or hardware call occurs. Outputs are a new immutable `reports/S6C/20260910T123540Z/independent_review/REPORTING_ADAPTERS_COMPONENT_REVIEW_V1.json`. An existing receipt is rejected. The review does not establish numerical correctness of not-yet-collected full common-duration results.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "$sim\scripts\test_s6c_reporting_adapters_review_v1.py"
```

Anaconda Prompt / Windows CMD (use the existing interpreter, no install):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%SIM%\scripts\test_s6c_reporting_adapters_review_v1.py"
```

Exact source/support/roster paired denominators, censored waits, source sample versus retained-row exposure, and append-only declaration cache semantics are reviewed separately. Model-free fixtures cannot validate native accuracy, causal policy quality or prospective experiment completion.
