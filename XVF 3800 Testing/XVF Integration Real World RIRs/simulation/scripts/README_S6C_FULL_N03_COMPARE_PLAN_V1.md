# Full N03 comparison request binding

This metadata-only helper binds the nine full N03 comparisons requested before its scoring: N01 C065 to N03 C067 on each tap, historical B00/B01/B36 to C067 on each tap, and C067 O0 to O1. All 240 cases remain requested. Selection follows earlier panel results; this is exploratory confirmation, not an untouched holdout. Historical controls compare generations, not isolated settings.

Inputs are the exact pre-scoring `FULL_N03_COMPARISON_SCOPE_V1.json`, the preserved full-anonymous comparison specification, completed N03 and N01 core receipts, the historical sealed score receipt and two explicitly bound registry amendments. The helper hashes the same bytes it parses. It does not open predictions or run models/scorers. The subsequent unchanged comparison tool independently admits each underlying score and table, with right-minus-left arithmetic. cp deltas are point estimates; the separate inherited primary-word bootstrap is conditional on its recorded dependency blocks.

Outputs are new `design/full_n03_compare_v2_inputs_V1.json` and `design/FULL_N03_COMPARISON_BINDING_V1.json`. Existing files are never overwritten. Run the binding once after full N03 core closes successfully. Do not rerun an occupied namespace.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s6c_full_n03_compare_plan_v1.py
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_compare_v2.py --spec design/full_n03_compare_v2_inputs_V1.json --output-subdir full_n03_comparisons_v1
```

Anaconda Prompt / CMD (the explicit interpreters override the active environment):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s6c_full_n03_compare_plan_v1.py
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_compare_v2.py --spec design/full_n03_compare_v2_inputs_V1.json --output-subdir full_n03_comparisons_v1
```

No neural jobs or inference are launched. Comparison collection is a single analysis worker; keep it outside paced quiet intervals. Full N03 native closure and shared parity are separate evidence, not implied by this metadata helper.
