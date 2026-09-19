# Native176 descriptive retention report

Purpose: read four exact frozen JSON summaries from `native176_results_analysis_v1` and render the full result interpretation, paired adverse/repeat evidence and a root-review-only retention/cache proposal. The helper does not read audio/journals, import scoring backends, rerun models/scoring, inspect live processes/devices, accept credits or create execution approval. It preserves all176 jobs, all176 comparisons and all repeats. It recommends research retention only; root owns actual candidate and cache decisions.

Inputs: pinned SUMMARY.json, ALL176.json, PAIR176.json and CREDIT68_METADATA_PROPOSAL.json. Output must be a fresh directory. Outputs: ANALYSIS.md, DESCRIPTIVE_COMPARISONS.json (all pair/never-correct/repeat records), RETENTION_CACHE_PROPOSAL.json (zero accepted credits), and exact-bound RECEIPT.json. The preexisting five aggregation adversaries are recorded in the upstream summary receipt; this report adds exact population, ID and paired-occurrence equality guards. No broad scientific retesting occurs.

PowerShell:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_native176_retention_report_v1.py' --output 'G:\Just_Peachy_S6D\20260913T195357Z\application\native176_retention_report_v1'
```

Anaconda Prompt or Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_native176_retention_report_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\application\native176_retention_report_v1"
```

Do not overwrite a completed report. Use a fresh reviewed suffix if regeneration is justified by a new source epoch. Source/reference metrics and earlier failed scorer/recovery receipts remain immutable. The report does not query whether future allocation gates are currently satisfied.
