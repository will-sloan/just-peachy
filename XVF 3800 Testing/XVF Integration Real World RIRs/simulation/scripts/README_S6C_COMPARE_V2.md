# Explicit paired S6C comparisons V2

This model-free tool consumes completed, source-bound core V1/V2/V3 scores and the exact sealed S6B full-analysis table. It does not run models, regenerate words or rescore predictions. V1 remains unchanged. V3 registrations use explicit additive paths/SHA256 values and an expected label count.

Inputs: a JSON specification with schema `jp_s6c_compare_inputs.v2`; `sources` rows containing a completed receipt binding, candidate_ids and optional explicit case_ids; optional `historical_sources` with the exact sealed S6B full receipt, candidate_ids and required case_ids; `registry_extensions` as repeated [path, SHA256] pairs; `expected_candidates`; and a nonempty `comparisons` list. Each contrast has comparison_id, label, left/right objects {candidate_id, asr_tap, identity_tap}, and case_scope MATCHED_INTERSECTION or REQUIRE_IDENTICAL_SCENES. The maintained smoke specification below is an exact working example.

The collector verifies completed index/coverage/per-score bindings, scientific code/packages, all route identities, exact score cache identity and per-source registry provenance. Scientific duplicates retain every provenance once; conflicting duplicates reject. Historical scores retain their old timing/resource scope and never acquire invented v3 fields. Input audio/vector payloads are transitively bound, not reopened by this collector.

Each explicit contrast maps its two actual score routes onto the existing pure two-output comparison API through label-only O0=left/O1=right slots. Numeric scores are unchanged. Actual tap/identity routes are restored in results. The original paired numerator/denominator arithmetic and primary-word2000-resample conditional bootstrap run unchanged. cp metrics have paired point deltas only here; no cp bootstrap is claimed. Paired scenes, left/right-only cases, metric-valid denominators and retained bootstrap denominators remain distinct. Right-minus-left sign is always explicit.

Registered parent relationships are retained as historical lineage; only requested contrasts execute. A contrast label alone does not prove one-field causal isolation. Case-population/room/family and denominator mismatches reject. The selector is exploratory, not an untouched holdout. All240/both-tap confirmation is separate from this explicitly selected subset.

Outputs in a new contained report child: PAIRED_COMPARISONS.csv, SELECTED_SCENE_RESULTS.csv, PAIRED_UNCERTAINTY.json, SELECTED_SCORE_PROVENANCE.json, CONTRAST_ADMISSIONS.json and COMPARISON_RECEIPT.json. Existing output namespaces cannot be overwritten. No new code or models are written to previous epochs.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_compare_v2.py --test
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_compare_v2.py --spec design/compare_v2_smoke_inputs.json --output-subdir compare_v2_smoke_v1
```

Anaconda Prompt / CMD (use the pinned analysis interpreter, not the currently selected Conda environment):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_compare_v2.py --test
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_compare_v2.py --spec design/compare_v2_smoke_inputs.json --output-subdir compare_v2_smoke_v1
```

Run the smoke once; for another reviewed exact specification choose a new output namespace. `--no-bootstrap` omits uncertainty and never fabricates intervals. No new package installation is required. Scope limits: no name accuracy from anonymous cp, no phonetic latency, no production promotion, no CM5 qualification.

