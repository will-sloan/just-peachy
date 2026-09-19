# S6C N00 independent admission and contrast review

`s6c_n00_review_v2.py` reads completed, immutable N00 core tables and eight
predeclared profile traces across all 56 panel scenes and both taps. It counts
native-admitted vectors rejected by the v3 clean-support guard, commitment and
lifecycle events, and outcome-selected explanatory cases. It does not run models,
retune profiles, change old evidence, or interpret opportunities as person errors.

Inputs are `reports/S6C/20260910T123540Z/n00_challenge_core_v1` and its bound
`epoch1/CHALLENGE_N00_PREDICTION_INDEX.json`. Every consumed compressed prediction
is verified against the exact completed index before decoding. The complete
core receipt, compact source tables, registry and helper bytes are bound anew.
This script does not independently recompute word/cpWER or reopen native neural
receipts; those remain the completed scorer's transitive evidence.

Outputs in a fresh `independent_review/n00_screen_v2` directory are profile and
paired-contrast CSVs, 896 trace-cell admission counts, explanatory trace excerpts
without vectors/audio, and `REVIEW_RECEIPT.json`. Additional trace reads are
outcome-selected explanatory examples, listed separately from the fixed 896-cell
incidence denominator. The 56 scenes contain 34 primary, 6 complete overlap,
5 incomplete-reference and all 11 empty controls. Complete cp/return summaries
pool the first two populations only. Source clean seconds summed across observed
windows overlap; they are never described as unique admitted duration.

Run one model-free process. A new output directory is required for another run:

```powershell
$s6cScripts = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
Set-Location -LiteralPath $s6cScripts
& 'C:\Users\amiri\anaconda3\python.exe' s6c_n00_review_v2.py --output-subdir independent_review/n00_screen_v2
```

Equivalent Anaconda Prompt or CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6c_n00_review_v2.py --output-subdir independent_review/n00_screen_v2
```

No external packages are required. Equal scene metrics across capacity settings
are descriptive under this observed sparse-support regime, not evidence that
capacity is irrelevant. V3 old-voice-gate controls retain new support/commitment
semantics and are not aliases of accepted S6B baselines. Lower-support thresholds
or fresh N01 dual evidence are separately registered, outcome-informed studies.


V2 preserves the exact V1 helper and outputs and corrects only the profile table all-population counters: the inherited ALL_COMPLETE_NONEMPTY aggregate is excluded from those sums. Its primary/overlap members are counted once. The independently computed896-trace counts, complete cp/return/short values, capacity equality and explanatory cases are unchanged. The new receipt binds the earlier receipt explicitly.
