# S6B compact handoff table exporter

Purpose: copy the completed scientific results into compact, reviewable handoff tables, preserving populations and exact effective settings. This tool does not rerun models, calculate a weighted ranking, change predictions, or tune a profile.

Inputs: the complete challenge index (44 profiles, 44 scenes, both taps), the complete confirmation index (29 profiles, 240 scenes, both taps), completed score/summary directories, and `FINAL_SELECTION_DECISION.json`. That decision must name 3–5 fully confirmed profiles, a disposition and reason for every tried profile, companion IDs and explicitly selected diagnostic scene IDs. Diagnostic scenes are chosen after outcomes and are explanatory counterexamples, not an independent test population.

Outputs: a fresh `final_tables_v1` directory containing the final candidate registry, exact field differences, all-profile summaries, paired contrasts, short replies, selected strata and scene diagnostics, a scope note, and an extraction receipt with source hashes. Every CSV is verified against the completed upstream receipt before use. Exact profile/case/tap grids and unique population/short-result keys are checked. It asserts all 777 deliberate source turns per profile/tap, all 40 complete-reference subsecond turns, and the original population/word denominators. Large event, vector and audio artifacts remain local. It refuses to overwrite an existing export.

The decision has `status: FINAL_RESEARCH_SELECTION`. Each unique disposition requires `profile_id`, a nonempty `reason`, and one of these statuses: `SHORTLIST_CONDITIONAL_RESEARCH`, `FULL_CONFIRMED_NOT_SHORTLISTED`, `CHALLENGE_ONLY_REJECTED_AT_NOMINAL`, `DIAGNOSTIC_CONTROL`, or `CHALLENGE_ONLY_DIAGNOSTIC`. `shortlist_profile_ids`, `companion_profile_ids`, and `diagnostic_case_ids` must name actually confirmed profiles/cases; unknown names cannot silently disappear from an export.

PowerShell, after final scoring and the documented selection decision:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6b_handoff_tables.py" --index FULL_PREDICTION_INDEX.json --analysis-subdir full_analysis_v1 --component-subdir full_component_screen_v1 --output-subdir final_tables_v1
```

Anaconda Prompt or Command Prompt:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_handoff_tables.py" --index FULL_PREDICTION_INDEX.json --analysis-subdir full_analysis_v1 --component-subdir full_component_screen_v1 --output-subdir final_tables_v1
```

Use a new output directory for a reviewed correction and preserve the prior receipt. The exporter is separate from the frozen inference epoch. Final independent review and ZIP assembly remain explicit later steps; this receipt alone does not declare S6B complete.
