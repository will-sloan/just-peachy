# Paired component analysis

`s6a_probe_report.py` reads the completed v2 native scores and completed baseline scores. It writes `probe_results/PAIRED_SCENE_DELTAS.csv`, pooled population comparisons, evidence/lineage counts, source short-turn coverage, source-region flag coverage and exact B0/P0 lexical comparisons. These are fixed-panel screening diagnostics; ambient and strict-empty controls retain separate denominators. No audio or model is loaded. Run after the commands in README_S6A_PROBES.md finish.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' .\s6a_probe_report.py --test
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' .\s6a_probe_report.py
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6a_probe_report.py --test
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6a_probe_report.py
```

`--test` checks pooled counts on adversarial unequal denominators, reference-population separation, empty-reference rate semantics and retained short-turn unknown/missing support. The final command requires all720 probe scores and corresponding baseline scores. Pairwise deltas are candidate minus parent; negative lexical error deltas favor the candidate. Paired controls change only their declared route or component bundle. Source windows labelled contained are inside a known file envelope, not guaranteed acoustically pure; incomplete environmental speech stays unknown. Recorded tracker revisions do not imply corrected transcript or GUI revisions. Existing generated tables can be rebuilt exactly from their bound metrics; native outputs are never edited.

The short-turn table includes actual tracking coverage as well as contained embedding counts. `identity_source_turns` retains all input turns; mapped, unavailable and zero-sole-speech turns are explicit. Known/unknown modal-label counts and known/unknown sole-speech samples are separate from embedding availability. A known modal label is not proof of correct identity. Population labels and `identity_reference_complete` keep incomplete ambient diagnostics separate. The panel contains only two subsecond utterances, so read those exact counts rather than infer broad short-reply validation.
