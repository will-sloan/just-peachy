# Compare completed S6C core scores

`s6c_compare.py` combines explicitly selected candidate subsets from completed,
hash-bound core analysis receipts. It calls the unchanged
`s6b_analysis.paired_comparisons` on saved per-scene scores. It never runs a
predictor, reopens audio, or rescores predictions. V1 and V2 core scores are
allowed only with current exact scientific code bindings and exact AST parity
of their scientific adapter functions. Registry/schema/admission differences
remain documented in the receipts.

Inputs are a JSON selection specification, completed V1/V2 core receipts and
their exact COVERAGE/score/index bindings, the canonical bank/support index,
and all 184 registered labels from the original, calibration and rescue design
files. The latter include outcome-informed amendments; this is not a new
holdout or pristine preregistration. Each source explicitly names the candidates
to use. Unselected scores are not loaded. A candidate/ASR tap must retain one
identity tap across the selected union.

Create an immutable specification under the current S6C report. Supply actual
binding values from each completed receipt (do not use the placeholders below).
To resolve a duplicate, explicitly choose the desired candidate under just one
source. If selected twice, its entire scientific score must be exactly equal,
including costs and source bindings. Only schema/analysis-key/provenance fields
are excluded from equality. All source chains remain in the output; there is
no averaging or automatic preference for a later result.

```json
{
  "schema": "jp_s6c_compare_inputs.v1",
  "sources": [
    {"receipt": {"path": "C:/actual/old/ANALYSIS_RECEIPT.json", "bytes": 123, "sha256": "actual SHA256"}, "candidate_ids": ["C011", "C012", "C021", "C022"]},
    {"receipt": {"path": "C:/actual/rescue/ANALYSIS_RECEIPT.json", "bytes": 456, "sha256": "actual SHA256"}, "candidate_ids": ["C131", "C132", "C133", "C134", "C135", "C136", "C137", "C138"]}
  ]
}
```

PowerShell (use the preserved analysis interpreter; no installation):

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
Set-Location -LiteralPath $s6cScripts
$env:PYTHONDONTWRITEBYTECODE = '1'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_compare.py --test
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_compare.py --spec 'N00_RESCUE_COMPARISON_INPUTS_V1.json' --output-subdir 'n00_rescue_paired_v1'
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_compare.py --test
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_compare.py --spec "N00_RESCUE_COMPARISON_INPUTS_V1.json" --output-subdir "n00_rescue_paired_v1"
```

Relative specifications resolve under
`simulation/reports/S6C/20260910T123540Z`. The output must be a fresh child of that
report. All admission checks finish before creating it. Interrupted output is
preserved and requires a new output name. `--no-bootstrap` is an explicit
point-comparison-only run, with zero uncertainty comparisons.

Outputs are selected scene rows, paired point comparisons, conditional
uncertainty, full selected-score provenance, and COMPARISON_RECEIPT. Every
candidate/ASR/identity/case key is retained. Parent comparisons and same-profile
tap comparisons use actual matched case intersections. Missing selected parents
are listed; absence never becomes a perfect or empty result. Both-side reference
denominators must agree. All deltas are right minus left.

The inherited uncertainty function uses 2,000 conditional primary-word
resamples under the original dependency plan. This helper does not implement
cp-specific bootstrap; cp point deltas remain separate. Saved score identities
bind predictions and support transitively; those payloads are not reopened or
rescored. Measured comparison time is host analysis cost, never native or CM5
throughput. Numeric inner pools are one. Preserve this helper and every metric
dependency while a comparison runs.

## Explicit historical S6B table adapter

An optional `historical_sources` list in the same spec may select the exact
completed S6B `full_analysis_v1/ANALYSIS_RECEIPT.json`, SHA
`12ee9ccd91a2a924ba2f54b51f622c39c73ed15325073cac5439bad4298dda0f`.
Each entry contains `receipt`, `candidate_ids`, and an explicit `case_ids` list.
The outer receipt must occur in the SHA-pinned S6B LOCAL_ARTIFACT_INDEX. Its exact
53 MB scene table, complete 13,920-row index/grid, and unchanged inherited metric
code are verified before selecting rows. No per-scene historical score is
fabricated. The retained row's original same tap becomes its explicit identity
tap; historical policy/native timing and resource fields keep their old scope.
No v3 lifecycle or naming fields are invented.

For example, add `"historical_sources": [{"receipt": {"path": "C:/actual/S6B/full_analysis_v1/ANALYSIS_RECEIPT.json", "bytes": 123, "sha256": "12ee9ccd91a2a924ba2f54b51f622c39c73ed15325073cac5439bad4298dda0f"}, "candidate_ids": ["B00", "B01"], "case_ids": ["S45_01_06"]}]`
using the actual receipt length and desired matched cases. An empty `sources`
list is allowed for a purely historical comparison. The same scene key cannot
be selected through both adapters; choose one source explicitly. Metric numeric
cells alone are parsed; literal text such as `null` remains text. All comparisons
retain both identity taps in their output. Historical adapter provenance is
separate from full S6C per-score provenance.
