# S6B conditional cpWER uncertainty

`s6b_cp_uncertainty.py` adds paired uncertainty and dependency sensitivity to completed S6B scores. It reads metadata and scores only; it performs no neural inference, prediction edits, hardware access or reference-to-runtime feedback. It complements the core scorer's primary lexical WER uncertainty with all complete nonempty reference cpWER.

## Definitions and limitations

Each contrast pools actual reference-word denominators. The script reports output O0/O1 contrasts, declared candidate/parent contrasts when both profiles are present, and within-profile first-final/latest plus first-display-label(final words)/latest contrasts. Positive values mean the right-hand cpWER is worse. First-display-label(final words) measures label stability applied to final recognized words; it is not partial-word accuracy.

The default 2,000 replicates resample whole complete-reference matched blocks within the observed rooms. A matched block with an absent required complete-reference member is excluded in full. The point estimate on every paired scene and the bootstrap point/interval on the retained whole-block subset have separate denominators. A challenge-panel interval can therefore describe a smaller subset than the adjacent all-paired point; do not present it as the confidence interval for that larger point. Unselected panel cases and selected-but-unscored cases are listed separately. The full bank contains 203 complete nonempty scenes; incomplete ambient and strict-empty reference populations are not assigned cpWER.

Room summaries, equal-room deltas, leave-one-room-out results and shared speaker/source/prompt/book/RIR/noise component deletion ranges are descriptive sensitivities. Dependency closures are formed on all 240 scenes before complete-reference projection, retaining bridges through excluded reference populations and entire matched blocks. Each deletion removes an entire connected component from the bootstrap subset. If deleting a component leaves no references, its result is unavailable. No-op deletions outside the included subset are omitted.

Blocks share source material and other dependencies, and only five room configurations were measured. The conditional percentile interval may be optimistic and is not a new-room generalization, independent holdout, equivalence test, multiple-comparison-adjusted significance result or automatic ranking rule. Whole-bank source-component connectivity is reported explicitly.

## Inputs and outputs

Inputs are a prediction index, its completed core analysis directory, the frozen scene bank and effective profile registry. The script checks the core analysis/index identity, binds each score and requires score/prediction identity equality and valid cp S/D/I arithmetic. It uses the already verified core score chain; it does not reopen large native evidence. `--require-complete` rejects absent or failed requested score outputs.

Current score bytes are admitted and freshly hash-bound as immutable core scores. The core receipt does not contain individual score-byte hashes, so this supplement does not independently establish that a score was never edited before admission. Complete status also requires the upstream prediction index to declare COMPLETE.

Outputs in a new report child directory:

- `CP_PAIRED_UNCERTAINTY.csv/.json`: pooled points, bootstrap subset denominators, conditional intervals and detailed exclusions/sensitivities.
- `CP_DEPENDENCY_DELETIONS.csv`: every nonempty source-component deletion and its retained denominator.
- `DEPENDENCY_STRUCTURE.json`: frozen bank matched blocks and source closures.
- `CP_UNCERTAINTY_RECEIPT.json`: source/score/code identities, tests, completeness and output hashes.

Choose a new output version after a methodological or source change. R0-only and pilot outputs cannot establish performance of all 44 configurations or all 240 scenes.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $python "$sim\scripts\s6b_cp_uncertainty.py" --test
& $python "$sim\scripts\s6b_cp_uncertainty.py" --index R0_CHALLENGE_PREDICTION_INDEX.json --analysis-subdir r0_challenge_analysis_v1 --output-subdir r0_cp_uncertainty_v1 --require-complete
& $python "$sim\scripts\s6b_cp_uncertainty.py" --index CHALLENGE_PREDICTION_INDEX.json --analysis-subdir challenge_analysis_v1 --output-subdir challenge_cp_uncertainty_v1 --require-complete
```

For full confirmation use `PREDICTION_INDEX.json` with its corresponding full analysis directory and a new uncertainty directory.

## Anaconda Prompt or Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS_PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_cp_uncertainty.py" --test
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_cp_uncertainty.py" --index R0_CHALLENGE_PREDICTION_INDEX.json --analysis-subdir r0_challenge_analysis_v1 --output-subdir r0_cp_uncertainty_v1 --require-complete
```

No installation or environment activation is needed. Optional `--report` selects another report root. `--replicates` defaults to 2000 and must be at least 100.

## Validation

Five focused fixtures cover unequal reference denominators, whole-block exclusion with a separately preserved all-paired point, unselected versus failed members, the exact degenerate single-block interval, and source dependency bridges through a reference-ineligible scene.
