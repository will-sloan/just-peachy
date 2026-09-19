# Independent final endpoint scorer admission

Purpose: reproduce the held 240-label endpoint scorer admission through the unchanged V3 append-only registry API. Only the final original receipt publication is intercepted; all actual metadata checks and 24 core fixtures execute. It checks exact result fields and source hashes before/after, without scoring predictions or creating a model.

Inputs: exact `independent_review/ENDPOINT_SCORER_ADMISSION_V1.json`, its source bindings and four explicit amendments. Output: new immutable `ENDPOINT_SCORER_COMPONENT_REVIEW_V1.json` beside the original, with reproduced fields, source/README bindings and limits. The original receipt and all scoring dependencies remain unchanged. An existing review output intentionally prevents duplicate publication.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "$sim\scripts\test_s6c_endpoint_scorer_component_review_v1.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%SIM%\scripts\test_s6c_endpoint_scorer_component_review_v1.py"
```

Use the existing analysis environment, with no package changes. This is metadata/API admission evidence, not an independent numerical review of future endpoint scores or a new native run.
