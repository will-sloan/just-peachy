# S6B revision and exposure diagnostics

`s6b_revision_analysis.py` is a separate, model-free supplement to `s6b_analysis.py`. It reads a prediction index, the corresponding completed per-output scores, and accepted source support. It never edits predictions or feeds reference labels to runtime code.

## Purpose and definitions

The supplement preserves first labels and distinguishes actual `ongoing_utterance_display` changes from `bounded_forward_reconciliation`. It reports per-scene and pooled first-final/latest cpWER and first-display-label(final words)/latest differences. A correction cannot erase an earlier first-label error.

Offline identity-harm diagnostics use the scorer's ambiguity-aware scene-global duration mapping. A transcript source span is identifiable only when complete-reference positive activity intersects exactly one known participant. Mixed-participant spans, incomplete references, missing alignment, unknown labels, display alias ambiguity and tied duration mappings stay explicit. This does not assign individual recognized words to source times.

Exposure integrates the saved label state of each retained transcript row from first readable display to the observed modeled session end. Known-wrong, unknown/unmapped and correct state seconds are separate. Never-correct rows are right-censored and retain their observed unresolved exposure. Multiple transcript rows coexist, so summed utterance-seconds can exceed wall duration. These are export-history/model-clock diagnostics, not measured GUI visibility or native paced/device latency.

B37's actual constant-person display maps explicitly to the constant-person source-support diagnostic. Historical B00 lacks the required full display-event availability and reports unavailable exposure, not zero harm or zero correction delay.

## Inputs

- A root prediction index, such as `CHALLENGE_PREDICTION_INDEX.json` or `PREDICTION_INDEX.json`.
- Its completed `s6b_analysis.py` output directory containing `scores/<profile>/<case>/<tap>.json`.
- Root `INPUT_INDEX.json` and hash-bound source-support files.

The supplement checks the prediction and source identities against each cached score. The score's three cp views must use equal reference denominators.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $python "$sim\scripts\s6b_revision_analysis.py" --test
& $python "$sim\scripts\s6b_revision_analysis.py" --index PILOT_VALIDATION_PREDICTION_INDEX.json --analysis-subdir pilot_analysis_v1 --output-subdir pilot_revision_analysis_v2 --require-complete
& $python "$sim\scripts\s6b_revision_analysis.py" --index CHALLENGE_PREDICTION_INDEX.json --analysis-subdir challenge_analysis_v1 --output-subdir challenge_revision_analysis_v1 --require-complete
```

For full confirmation, replace the index with `PREDICTION_INDEX.json` and use the matching full-analysis directory plus a new revision output directory.

## Anaconda Prompt or Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS_PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_revision_analysis.py" --test
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_revision_analysis.py" --index CHALLENGE_PREDICTION_INDEX.json --analysis-subdir challenge_analysis_v1 --output-subdir challenge_revision_analysis_v1 --require-complete
```

No new environment or package is needed. Optional `--report` changes the report root. Choose a new output version after any methodological change; earlier pilot/smoke results remain evidence of their original version.

## Outputs

- `REVISION_PROFILE_RESULTS.csv/.json`: scope counts, transitions, identifiable source-speaker counts, cp differences and censored exposure denominators.
- `REVISION_SCENE_RESULTS.csv`: per-scene first/latest metrics and revision/exposure state.
- `REVISION_EVENTS.csv`: every derived changed-label transition, actual revision scope and whether it occurs strictly after first finalization.
- `UTTERANCE_EXPOSURE.csv`: source-span identifiability, first preserved label, correction wait, known-wrong/unknown/correct time and never-correct censoring.
- `REVISION_ANALYSIS_RECEIPT.json`: exact prediction/score/support identities, tests, requested/scored/failure coverage and output bindings.

Source-speaker sets are offline identities of synthetic reference sources. Counting their union does not imply independent people, real-world generalization or enrolled naming.

The harmed source row and a different identity receiving a wrong attribution are distinct. `known_wrong_exposure_by_recipient_sec` groups identifiable wrong-state seconds by the other duration-mapped source identity; `distinct_wrong_attribution_recipient_count` preserves its unique denominator. Transition recipient sets separately record the wrong identity before and after a changed label. Unknown or ambiguous mappings never become an identifiable recipient. These remain retained-row diagnostics rather than word-level harm.

## Validation

Six focused fixtures verify wrong-to-correct exposure, the other participant receiving a wrong attribution, ambiguous duration mapping, mixed-participant exclusion, missing historical timing and the distinction between actual empty display and missing history. Actual epoch2 pilot metadata validates112 outputs across14 profiles, four scenes and both taps with no schema failures. R0 revision version2 adds explicit recipient accounting to the preserved version1 diagnostic. Neither pilot nor R0-only results establish all44 challenge or all240 confirmation performance.
