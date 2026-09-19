# S6C cadence scorer admission through unchanged V3

Purpose: verify that the existing explicit append-only V3 scorer contract admits the four C191–C194 cadence definitions, their registered parents and exact effective floor settings. No scorer or metric is changed. The test preserves every earlier 234 definition, admits 238 labels with 384 new-stage routes, exercises rejection guards and runs the existing 24 core fixtures. It does not score predictions or call models/hardware.

Inputs are the three exact SHA-pinned amendments in the script, original declaration chain, V6 effective registry and current frozen V3 scoring dependencies. Output is the immutable `independent_review/CADENCE_SCORER_ADMISSION_V1.json`, containing source bindings and the exact future registry arguments. Do not overwrite an existing receipt.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py "$sim\scripts\test_s6c_cadence_scorer_admission.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" "%SIM%\scripts\test_s6c_cadence_scorer_admission.py"
```

For a later completed cadence prediction index, use `s6c_analysis_v3.py` with its existing `--index`, fresh `--output-subdir` and `--require-complete` arguments. Append these exact registry arguments in either shell:

```text
--registry-extension design/COMMON_ROSTER_DURATION_AMENDMENT_V1.json b8d25fc00366242bd38bb1e56f16cd30dd1aa78262b8a1eda9e2a2fe4068671d --registry-extension design/FRESH_EVIDENCE_FOLLOWUP_AMENDMENT_V1.json b899191bccf897689b5ea543b05367f2b62d60fb481e7e2f3255246a7afe2b75 --registry-extension design/CADENCE_FLOOR_NEIGHBORHOOD_V1.json 69046b327908410cc7d291c23b7d77205f7cdacd7ca19ac03caf52307ed5d9d5 --expected-candidates 238
```

The final index path is supplied only when root publishes its completion. Existing 234-label score outputs remain bound to their original inputs; the added declaration creates a different future cache identity. All four new configurations have no gallery, so no dedicated name scoring or gallery-map change is necessary.
