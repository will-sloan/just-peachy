# Independent compact native-family results review

Purpose: reconcile the completed 192-cell native six-case family collector with its exact completed scorer tables, preserving native versus cached prediction scope. It checks each unique candidate/tap/case key, reference/support denominator, retained scalar delta and 32 lineage/lifecycle summary rows. Four original model-free guards are reproduced. This is descriptive table arithmetic, not rescoring or a native inference run.

Inputs: the exact `family_gate6_native_results_v1/FAMILY_NATIVE_REVIEW_RECEIPT.json`, native/cached core authorities and three bound scorer CSVs, plus the collector's two compact output CSVs. Only these explicit metadata/table buffers are read. Output: new immutable `independent_review/FAMILY_RESULTS_COMPONENT_REVIEW_V1.json`, with source bindings, field counts and interpretation limits. Existing files remain unchanged; duplicate publication fails.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "$sim\scripts\test_s6c_family_results_component_review_v1.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%SIM%\scripts\test_s6c_family_results_component_review_v1.py"
```

No package installation is required. No native event, PCM, model, vector, gallery or prediction payload is read. Pending/retained lineage counts are not proof of successful identity repair; absent release/promotion remains unobserved. Exact native clock/vector parity and paced/full-bank acceptance are established by their separate evidence, not this table review.
