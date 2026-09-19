# S6D all240 focus presentation replay

Purpose: apply the actual `PresentationState` T0/T1/T2 controller to original frozen C088/A15 and C091/B15 transcript events, all240 scenes and both taps, while preserving complete unfiltered text. This is a cheap policy replay of original predictions, not repaired-native, GUI-timing, hardware, beam or CM5 evidence.

Inputs: `--output` is a fresh directory. The helper follows the completed S6C NAME_ANALYSIS_RECEIPT bindings to the full prediction index, actual original15 galleries, scorer-only E/C/Q identity map, source-support/scene metadata and Q transcripts. Selection is declared in PLAN.json before reading predictions or truth: first1, first3 and all15 sorted opaque profile IDs, fixed across scenes/taps. Each selection has a matched unfiltered T0 and filtered T1/T2 view. No currently active person/seat is used to select a target and no identity thresholds change.

Outputs: PLAN.json, RESULT.json, AGGREGATES.csv, PER_CASE.csv and VISIBILITY_DELAYS.csv,5760 policy cells over960 predictions. Whole acoustic/reference clocks and incomplete ambient references stay separate. Reference tokens retained are conservative LCS matches for visible rows with one unambiguous reference person; mixed/incomplete visible tokens remain unclassified rather than treated as harmless. Missed/unresolved words combine ASR errors, mapping ambiguity and filtering. Estimated active-time coverage is a source-span metric, not proof those words were recognized. First visible overlapping-row delay is saved modeled availability with never-visible counts, not phonetic/GUI latency. Target-absent rows have zero target denominator and do not establish perfect recall. Full unfiltered raw words must remain identical.

PowerShell:

```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_application_focus_replay.py" --output "$s6dSim\reports\S6D\20260913T195357Z\application\focus_replay_v1"
```

Anaconda Prompt / Windows CMD (no activation/install):

```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_application_focus_replay.py" --output "%S6D_SIM%\reports\S6D\20260913T195357Z\application\focus_replay_v1"
```

Use a new output suffix to repeat; historical/current evidence is never overwritten. No neural calls, playback or device access occurs. Full local tables may be large; compact handoff should retain aggregates, denominator/selection definitions and adverse examples with exact table hashes. Independent review and native/GUI confirmation remain separate gates.
