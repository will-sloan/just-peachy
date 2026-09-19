# Fixed-roster enrollment-duration results

This model-free descriptive collector checks completed V3 core/name receipts for the same six-profile,56-scene/two-tap panel. It verifies bound tables, all178 source occurrences per route, exact matched source support and roster membership across tiers. Outputs preserve pooled correct/wrong-known/Unknown samples, known/withheld populations, per-corpus and within-person deltas, paired observed/missing confirmed/stable-name waits and separately retained transcript row-seconds. It performs no model calls, new prediction scoring or inferential bootstrap. Original files remain unchanged.

Inputs: common_duration_panel_core_v3/ANALYSIS_RECEIPT.json and common_duration_panel_names_v3/NAME_ANALYSIS_RECEIPT.json. Outputs: common_duration_results_v1 with six compact CSVs and DURATION_RESULTS_RECEIPT.json. The output refuses overwrite. A matched source has the same case/segment/source/metadata identity; name correctness never uses Hungarian relabeling. Censored waits are not zero. Retained row-seconds are separate from live source samples.

Each A/B gallery has14 existing E30-eligible people (9CMU+5HiFi), identical competitors at5/15/30; Common Voice is still evaluated as withheld, not enrolled. This is exploratory panel evidence; do not claim all240 confirmation, independent people across corpora, matched device-domain enrollment or duration independent of changed speech content/centroid.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_common_duration_results.py --test
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_common_duration_results.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_common_duration_results.py --test
"C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_common_duration_results.py
```

Optional --core-subdir, --names-subdir and --output-subdir change explicit versioned inputs/output; the exact six-profile56-case grid guards remain. Use the pinned analysis interpreter; no dependency installation. All artifacts have source bindings; audio/vectors/journals are not copied.

