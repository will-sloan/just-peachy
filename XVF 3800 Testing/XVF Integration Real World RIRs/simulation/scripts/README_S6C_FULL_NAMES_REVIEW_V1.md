# Independent actual full naming/common-duration review

Purpose: check completed full-bank naming numbers, source/roster partitions, observed/censored naming sets and common-roster duration comparisons. This reviews new actual full results, not old panel checks or the scorer source implementation. It keeps the six original naming conditions and six common-duration conditions separate.

Inputs are exact SHA-pinned NAME_ANALYSIS_RECEIPT files under `full_n01_naming_names_v3` and `full_n01_common_duration_names_v3`, their bound TURNS/PROFILE_NAME_RESULTS/RETAINED_ROWS/COVERAGE CSVs, scorer-only Q/roster/bank metadata, and `full_common_duration_results_v2/DURATION_RESULTS_RECEIPT.json`, its six compact comparison CSVs and bound interpretation. No raw corpus, audio, embeddings, native events, prediction or per-scene score JSON is reopened; score bindings are carried as drill-down references only. All CSV/JSON parsing uses the bytes whose hashes were verified.

Outputs under a fresh `full_naming_component_review_v2`: PLAN.json, RESULT.json, OBSERVED_NAME_SETS.json, COUNTEREXAMPLES.json and REVIEW.md. The plan fixes the input scope and deterministic adverse example rule before this helper processes results. Up to10 examples select maximum wrong-known source samples per original candidate and maximum positive30-minus5-second wrong-known turn delta per common rotation/tap, with explicit key tie order. These are selected adverse examples, not typical performance or new independent trials. Existing outputs are never overwritten.

Checks require777 unique Q occurrences per route; exact source identities, roster membership and sample partition; all observed/missing wait counts and independent linear quantiles; stable criterion attainment0.5seconds after retrospective onset; common14-person roster equality across tiers; exact paired-source denominators; all pooled/person/corpus changes, conditional delay partitions and retained-row exposure. Original names' partial-availability rosters are distinct from the common14-person subset. Complete versus incomplete known-source turns remain693/84 per route. No censored wait becomes zero, and live speech samples are not transcript row-seconds.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_full_names_review_v1.py"
```

Anaconda Prompt / CMD, using the existing environment without installation:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_full_names_review_v1.py"
```

The review performs no new metric integration, cp/MIMO rescoring, model/hardware run or family selection. It verifies descriptive arithmetic against completed scorer tables and retains their dependency/holdout/domain limitations. A failure preserves the initial plan/namespace; any repair must use a separately recorded source revision rather than silently relabeling a failed audit successful.

The first audit guard incorrectly required full-reference status on all777 turns and stopped before a final result. The correct84 incomplete-reference known-target turns are explicitly LIMITED_KNOWN_TARGET_SUPPORT, while693 complete-reference turns are SCORED_KNOWN_SOURCE_SUPPORT. The repaired guard checks each against the canonical bank's reference completeness. Original source/README/plan are preserved under `staging/s6c/20260910T123540Z/full_names_review/before_known_target_status_guard_v1`; the V1 report plan remains in place. Final V2 records this reviewer-only correction; no scoring or native source was changed.
