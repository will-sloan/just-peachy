# Independent scorer V3 admission review

`test_s6c_scorer_v3_review.py` verifies the six held scorer sources/documentation
against the author's pinned source-only admission receipt, compares actual
metric/support function ASTs, and reproduces the explicit additive registration
and evaluator map admission. It executes pure fixtures and supplementary SHA,
duplicate-input and count failures. It does not score predictions, run models,
edit source inputs or publish an execution epoch.

Inputs: pinned V3 admission receipt, original and extension design/maps,
completed gallery material bindings, canonical case metadata, held scorer code.
Outputs: one fresh source-bound independent JSON review. The 234 labels include
historical controls and aliases; the 2175 map rows include original assignments.

PowerShell:

```powershell
$s6cSimulation = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$s6cSimulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "$s6cSimulation\scripts\test_s6c_scorer_v3_review.py" --output "$s6cSimulation\reports\S6C\20260910T123540Z\independent_review\SCORER_V3_COMPONENT_REVIEW_V1.json"
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIMULATION=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_SIMULATION%\staging\s5_text_metrics\analysis_env\Scripts\python.exe" "%S6C_SIMULATION%\scripts\test_s6c_scorer_v3_review.py" --output "%S6C_SIMULATION%\reports\S6C\20260910T123540Z\independent_review\SCORER_V3_COMPONENT_REVIEW_V1.json"
```

Use a new receipt filename for a later review. If a held source binding changes,
stop and request the new source admission; do not rewrite the old authority.
