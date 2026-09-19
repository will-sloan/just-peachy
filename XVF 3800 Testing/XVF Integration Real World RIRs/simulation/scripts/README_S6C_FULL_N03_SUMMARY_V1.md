# Full N03 compact results

This helper validates and summarizes the completed C067 full-bank core score against C065 and the nine requested matched comparisons. It reads exact hash-bound CSV/JSON buffers once, reproduces headline integer aggregates from per-scene rows, checks the 480 case/tap grid and unchanged raw final words, and keeps short, return, lifecycle, conditional uncertainty and native source-cost denominators separate. No metric implementation, predictor or old result is changed.

Inputs: `full_n03_native_core_v3`, `full_n01_anonymous_core_v3` and `full_n03_comparisons_v1` completion receipts and their declared compact tables. These are pinned completed sources. Native model receipts, PCM and prediction payloads are transitively bound and are not reopened. Outputs: a fresh `reports/S6C/20260910T123540Z/full_n03_results_v1/RESULT.json` with exact source bindings, checks, four complete-population rows, short-turn and lifecycle summaries, nested costs, nine pair summaries and eight deterministic extreme examples. The examples are chosen after comparison by fraction delta then case ID, two largest harms and two benefits per tap; they are descriptive extremes, not representative sampling.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s6c_full_n03_summary_v1.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" s6c_full_n03_summary_v1.py
```

Run once after both core and comparison completion. Existing output is rejected. This is one compact analysis worker and must remain outside paced quiet intervals. Actual schema/grid/hash/nonnegative/denominator and recomputed aggregate checks fail before publishing. No neural model, policy replay, scoring, plotting or hardware is run. Model/API/full-dispatch costs overlap and cannot be added into whole-pipeline wall time; missing component costs remain explicit. Source clocks are not paced display or CM5 latency.

The first summary attempt stopped before output because comparison receipts use an `artifacts` list rather than core `tables`. Exact prior source/README are preserved in `staging/s6c/20260910T123540Z/full_n03_summary/before_comparison_schema_fix_v1`; the corrected collector verifies and binds that lineage. Original score/comparison sources were unchanged.
