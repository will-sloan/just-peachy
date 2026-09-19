# Compact token and strata result review

Purpose: independently reconcile the completed full-token and strata exports without repeating original score, reference, native, model or storage scans. Standard-library Python only; no production imports. This is a compact arithmetic review, not fresh metric computation.

Inputs: fixed SHA-bound RESULT.json files under full_token_boundaries_v1/results_v1 and strata_adverse_v1/actual_v1; their exact compact exported artifacts and small plans/helper bindings. Original scored CSV tables are not opened. A live PACED_QUIET_OWNER.json blocks execution. Run only after root confirms a quiet analysis window.

Outputs: a fresh independent_review/token_strata_design_v1/REVIEW_RECEIPT.json and REVIEW.md. The receipt binds same-read buffers, reviewer source and this README, records each check count, keeps the 72 token population summaries and explicitly states inherited admission limits. Existing outputs are refused and all source artifacts remain unchanged.

Checks: token18-route/4320-cell population grid; alignment-internal counts and boundary flags; all72 population aggregates and3840 paired deltas; strata28-route/2912-stratum exact membership representations; all18720 numerator/denominator/rational-delta and tiny-flag rows; all1440 positive-maximum/no-positive statuses and ties; narrative30-row count table. It does not rerun alignment or verify raw per-scene truth/eligibility independently.

PowerShell:
```powershell
$sim = 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation'
& "$sim/staging/s5_text_metrics/analysis_env/Scripts/python.exe" -B "$sim/scripts/s6c_token_strata_review_v1.py"
```

Anaconda Prompt or CMD (uses the campaign's held analysis interpreter, no activation or installation):
```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/staging/s5_text_metrics/analysis_env/Scripts/python.exe" -B "C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/scripts/s6c_token_strata_review_v1.py"
```

No workbook, formulas or original CSV is edited. No model/policy/scorer/native process or scanner is invoked. Floating presentations are checked at1e-12 tolerance; exact integer/rational denominators and identifiers are compared exactly. Reproduction must use a separately authorized fresh review namespace rather than deleting the preserved receipt.

