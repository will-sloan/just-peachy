# S6C scorer-only identity and retained-name exposure

`s6c_name_analysis.py` adds name correctness to the separate anonymous/text core. It reads completed predictions; it never invokes a model, changes a gallery or supplies truth to a predictor. The source-owned `SCORER_GALLERY_MAP.json` maps native profile IDs and pseudonymous names to corpus-qualified metadata identities. These are research metadata identities, not independently verified human identity.

Inputs are an explicit S6C prediction index with case and ASR/identity routes, the completed enrollment map and plan, their exact Q occurrence manifest, the immutable S6B source-support index, and the canonical scene bank. Every named prediction must identify its actual gallery manifest, condition, tier and case; equivalent roster manifests do not erase setup-condition distinctions. Intended-but-unavailable templates, withheld/unselected people and no-gallery controls remain separate.

The scorer maps each Q occurrence to its exact source/support segment once, using the identity audio tap. Its live-name timeline uses the same .75-second evidence-end expiry as the inherited anonymous diagnostic. It integrates correct-name, wrong-known-name and unknown-name samples over sole-active source support. These numerators partition that denominator. Overlap exclusions, missing mappings, all occurrences and incomplete-reference limitations remain visible. An assigned name for a withheld or unselected source is a false known-name assignment, never an anonymous Hungarian remapping success.

First-name and first-correct-name waits are conditional source-support diagnostics. The prospective stable criterion is .5 contiguous seconds of correct **confirmed** name on sole-active support; silence and overlap interrupt that support. `first_stable_correct_name_wait_sec` reports when the full criterion is attained, .5 seconds after its interval begins. `retrospective_stable_interval_onset_wait_sec` separately reports that earlier interval onset and is never the time stability was established. This fixed descriptive criterion is independent of the runtime's confirmation thresholds. Missing successes retain right-censor status and observation duration; a subsecond turn may have a correct name but insufficient stable support. These times are based on modeled availability and estimated source alignment, not phonetic latency or Pi/CM5 runtime. Person rows combine each source identity chronologically within one scene, while turn rows retain every occurrence.

Retained transcript exposure is a separate row-seconds denominator. For each readable partial/final/revision, only the most recent **arrived ASR source span** identifies possible reference speakers. A later final span is never backfilled onto earlier partial display. Revisions retain the preceding arrived ASR span rather than using the new embedding's unrelated span. Multiple-person, incomplete and missing-reference spans remain unidentifiable. Each visible row persists to its next update and then to the saved observation horizon; no word timestamps or summed scene-duration interpretation is implied. Wrong-name episodes retain correction/retraction versus right-censored endings. Name revisions preserve their actual ongoing/bounded scope.

Query rows distinguish first query per lifetime tracker ID from cold name memory. Actual retained name-state retirement records make reentry cold again; if that history is truncated, unresolvable warm/cold cases remain unavailable. First query per source person is a separate offline chronological diagnostic. A short observation carrying a prior name is not a fresh query. Canonical source-empty controls preserve whole-capture assigned-name samples and retained assigned-name row-seconds in `EMPTY_CONTROL_RESULTS.csv`; these diagnose output without a deliberate reference speaker and do not establish the identity of every environmental sound.

Outputs under a fresh S6C report child include per-output score JSONs and compact `TURNS.csv`, `PEOPLE.csv`, `QUERIES.csv`, `RETAINED_ROWS.csv`, `NAME_REVISIONS.csv`, `PROFILE_NAME_RESULTS.csv`, `COVERAGE.csv` and `NAME_ANALYSIS_RECEIPT.json`. Exact source bindings and policy accompany the results. Completed core or naming coverage alone is not full S6C completion. Failed and missing outputs never become zero name error. This helper does not rank candidates.

PowerShell (existing analysis environment, no installation):

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_name_analysis.py --test
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s6c_name_analysis.py --index 'epoch1\ENROLLMENT_SMOKE_PREDICTION_INDEX.json' --output-subdir 'enrollment_smoke_names_v1' --require-complete
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_name_analysis.py --test
"..\staging\s5_text_metrics\analysis_env\Scripts\python.exe" s6c_name_analysis.py --index "epoch1\ENROLLMENT_SMOKE_PREDICTION_INDEX.json" --output-subdir "enrollment_smoke_names_v1" --require-complete
```

Use the actual completed index name; the example enrollment smoke index is not asserted to exist. Relative indexes resolve under `reports/S6C/20260910T123540Z`. A fresh output subdirectory is required. Keep the core/name helpers and dependencies unchanged while scoring. Native receipt provenance is transitive through verified predictions; this scorer reopens the actual gallery manifest but does not rehash every native model/audio payload. The completed enrollment source map is required even for no-gallery controls so denominators share one frozen identity authority.
