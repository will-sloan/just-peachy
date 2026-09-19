# Closed native176 result summary

`s6d_native176_results_summary_v1.py` reads the exact accepted scoring specification, 176 immutable SCORE files/INDEX, prior composite VALIDATION, saved RESULT metadata, original manifest metadata and conditional serial892 declarations. It aggregates existing counts, preserves unavailable/censored opportunities and changed-output pairs, and joins the fixed 68 repaired r1 credit proposals to exact accepted closure evidence. It does not rerun the scorer, inference, policy, audio, journals, processes, hardware, or GUI. It creates no retention, cache, or execution approval.

Inputs are pinned paths and hashes in `PINS`. Output must be a fresh directory; use a new reviewed suffix if the documented one already exists. Outputs are SUMMARY.json, ALL176.json, PAIR176.json, CREDIT68_METADATA_PROPOSAL.json, AGGREGATION_CHECKS.json and RECEIPT.json. All176 retains per-job opportunities, adverse rows and exact score/closure bindings. The credit artifact accepts zero credits; root must assess retention and source/allocation compatibility separately. Resource fields are saved result durations/cursors, not a new CPU/memory census. No actual audio or event journal is read.

Quantiles use linear interpolation among observed values. Censor and unavailable status counts remain explicit. Pooled error rates divide summed existing errors by summed reference words; cpWER remains an aggregation of independently assigned per-job scores. Overlapping retained name intervals are row-seconds, never wall duration. Repeats are observations, not new independent cases. Native headless publication/consumption does not establish actual Tk rendering or scanout timing.

PowerShell:

```powershell
$s = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' "$s\s6d_native176_results_summary_v1.py" --self-test
& 'C:\Users\amiri\anaconda3\python.exe' "$s\s6d_native176_results_summary_v1.py" --output 'G:\Just_Peachy_S6D\20260913T195357Z\application\native176_results_analysis_v1'
```

Anaconda Prompt or Command Prompt:

```bat
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_native176_results_summary_v1.py" --self-test
"C:\Users\amiri\anaconda3\python.exe" "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6d_native176_results_summary_v1.py" --output "G:\Just_Peachy_S6D\20260913T195357Z\application\native176_results_analysis_v1"
```

The five small adversarial aggregation checks cover censored/unavailable denominator retention, unequal word denominators, empty/interpolated quantiles, nonfinite refusal, and exclusion of changed-output timing. They do not import any scientific backend or run production scoring. Do not rerun the scorer because this summarizer reports a join failure; diagnose metadata first and preserve partial summary attempts.
