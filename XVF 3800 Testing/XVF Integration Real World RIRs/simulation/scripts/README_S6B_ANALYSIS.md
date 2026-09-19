# S6B prediction scoring

`s6b_analysis.py` scores completed prediction records against the immutable scene bank and accepted source-support mappings. It runs text/metadata analysis only. It never imports APP tracking code, reads vectors/audio, calls models or changes runtime predictions.

## Inputs

The root-owned prediction index declares `profiles`, `case_ids` and rows containing `case_id`, `stream`, `profile_id`, `recipe_id`, `status` and `result:{path,sha256}`. Each completed result must include causal `decisions`, admitted `features`, `segmentation`, three final-transcript label views, flat transcript events, snapshot, recipe costs, policy wall time and measured duration. Exact hashes are verified before scoring. Reference support comes separately from `INPUT_INDEX.json`; reference metadata is used only in this scoring process.

The immutable scene bank and pure S6A text/support/statistics implementations are reused. Use the existing pinned MeetEval environment below; ordinary Anaconda Python may lack the required MeetEval0.4.3 package. No installation is needed.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $python "$sim\scripts\s6b_analysis.py" --test
& $python "$sim\scripts\s6b_analysis.py" --index CHALLENGE_PREDICTION_INDEX.json --output-subdir challenge_analysis_v1 --require-complete
& $python "$sim\scripts\s6b_analysis.py" --index PREDICTION_INDEX.json --output-subdir full_analysis_v1 --require-complete
```

For a bounded smoke screen while an index is being prepared, use a different output namespace:

```powershell
& $python "$sim\scripts\s6b_analysis.py" --index CHALLENGE_PREDICTION_INDEX.json --output-subdir smoke_v1 --limit 10 --no-bootstrap
```

A limited run preserves all unscored requested rows in coverage and cannot report complete.

## Anaconda Prompt or Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS_PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_analysis.py" --test
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_analysis.py" --index CHALLENGE_PREDICTION_INDEX.json --output-subdir challenge_analysis_v1 --require-complete
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_analysis.py" --index PREDICTION_INDEX.json --output-subdir full_analysis_v1 --require-complete
```

`--report` changes the S6B report directory. A relative `--index` is resolved beneath it. `--output-subdir` must be a child directory, never the report root. After any scorer/dependency correction, choose a new output version; mismatched existing score identities are rejected, not silently overwritten.

## Metrics and outputs

- `SCENE_RESULTS.csv`, `PROFILE_RESULTS.csv/.json`: pooled word/character S/D/I counts and actual denominators. Primary non-overlap, complete overlap MIMO, incomplete target-only and strict-empty populations remain separate. Empty WER is undefined; report insertions per decoded minute.
- Three cpWER views use identical final recognized words: first-final label, latest revised label, and first-readable-display label applied to final words. The last is a label-stability diagnostic, not word accuracy at the partial-output instant. Unknown is an emitted anonymous label and does not mean correct identity.
- `TURN_RESULTS.csv` and `SHORT_REPLY_RESULTS.csv/.json`: preserve every source occurrence, including repeated clips, unknown/tied labels and unavailable support. A fully contained embedding, a present label and a duration-Hungarian-mapped correct label are separate columns. Alternate globally optimal duration mappings stay ambiguous.
- `PAIRED_COMPARISONS.csv`: same-case/tap parent comparisons and paired O0/O1 counts, with room and equal-room deltas. `PAIRED_UNCERTAINTY.json` uses2,000 matched-block bootstrap repetitions within observed rooms and whole-block exclusions when any required member is absent. Speaker/clip/text/book/RIR/noise component deletion and leave-room-out results are descriptive sensitivities. Internal legacy O0/O1 keys mean left/right sides, explicitly stated in each record.
- `COVERAGE.csv`, `HEARTBEAT.json`, per-output `scores/`, and `ANALYSIS_RECEIPT.json`: exact attempted/scored/unavailable outputs and dependency bindings. COMPLETE_REQUESTED_INDEX means the requested index was scored; only separately listed480-output profiles have all240/two-tap confirmation.
- Recipe costs are retained by original names. Nested/full-dispatch totals may overlap model phases; do not add them indiscriminately or call concurrent phase sums wall time.
- `RECIPE_COST_RESULTS.csv` counts each declared recipe/case/tap once across tracker reusers. `STRATA_RESULTS.csv` reports whole-scene room, family, historical split, source corpus/quality/level, noise/SNR and receiver-condition memberships; overlapping memberships are not additive.
- `REGION_RESULTS.csv` intersects actual coarse segmentation/embedding spans with accepted source-support regions. Speech/overlap flags in quiet/noise support are diagnostics, not word-level false-insertion labels or phonetic VAD accuracy.

B37/B38 source-support controls explicitly assign a constant person/unknown over reference activity for the diagnostic identity score, independently of embedding coverage. Their text labels remain the actual scheduler control outputs. No source-support timing benefit is claimed for either control.

Timing uses saved approximate source support and measured warm upstream availability. Whole-file-support waits include missing/never-observed counts and do not establish phonetic onset, device latency, native paced latency or CM5 performance. Historical B00 missing availability remains missing. Deterministic policy replay cost is separate from upstream modeled availability.

## Validation

`--test` checks unique duration mapping, ambiguous global optima, missing wait counts and label-only lexical invariance. The initial real smoke used ten preserved historical B00 outputs: both taps on one primary, overlap, incomplete and empty case plus a short-reply case. All ten scored successfully with pinned MeetEval. This is scoring validation; it is not a new native model run or full-bank confirmation.
