# S6C native six-case family gate collector

Purpose: report actual retained decision-lineage activation and lifecycle counts for the completed 192-cell native family gate, then compare those same candidate/tap/case cells with the earlier completed cached-policy screen. This is integration and reachability evidence, not 192 additional independent accuracy trials or a global family rejection test. No model, raw audio, vector array, native event-log scan or rescoring is performed.

Inputs: complete source-bound `family_gate6_native_core_v3` and `fresh_family_rescue_core_v2` core receipts and their exact SCENE_RESULTS/TRACK_LIFECYCLE_RESULTS CSV buffers. Parsed bytes are the verified bytes. The exact 16 declared conditions × six cases × two taps and each paired reference/support denominator are required. Outputs in a fresh `family_gate6_native_results_v1` directory are per-family/tap activation summaries, all 192 compact paired cells and FAMILY_NATIVE_REVIEW_RECEIPT.json. All earlier artifacts remain unchanged.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py "$sim\scripts\s6c_family_native_results.py" --test
& $py "$sim\scripts\s6c_family_native_results.py" --output-subdir family_gate6_native_results_v1
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" "%SIM%\scripts\s6c_family_native_results.py" --test
"%PY%" "%SIM%\scripts\s6c_family_native_results.py" --output-subdir family_gate6_native_results_v1
```

Run after both source analyses complete. Existing output directories are rejected; choose a fresh name for a separately bound repeat. The four fixtures check signed metric deltas, missing cp preservation and rejection of substituted case/population/support. Counts refer to retained decision lineages, not successful identity repairs. A held/pending branch without release or promotion is exercised only on that path. Whole native/source parity receipts remain separate evidence. Source-paced acceptance and full-bank confirmation are not established by this collector.
