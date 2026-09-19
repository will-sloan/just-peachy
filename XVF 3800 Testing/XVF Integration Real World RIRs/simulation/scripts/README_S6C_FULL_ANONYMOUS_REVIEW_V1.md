# Full anonymous results and selected adverse cases

`s6c_full_anonymous_review_v1.py` independently reconciles the completed full8 anonymous analysis from exact bound scene tables. It uses only the three hash-bound existing pure aggregate functions; no scorer module, neural backend or native runner is imported. It checks all80 population rows and preserves16 complete-population aggregates, with203 scenes/6016 words/693 turns/292 returns per route. Separate incomplete populations retain26 scenes/84 turns/32 returns. Primary156/4560 and strict-empty11 remain explicit.

The prospective `prepare` writes an immutable selection plan before candidate-pair inspection. Within each of C117/118, C065/079, C119/120, C121/122 and each tap, choose the largest positive real-minus-off latest-revised scene cpWER on complete nonempty scenes. Integer numerator/shared denominator is compared exactly; ties use ascending case ID. This produces at most8 paired failures, never invented harm when all deltas are nonpositive. No global winner is selected.

Inputs: SHA-pinned `full_n01_anonymous_core_v3/ANALYSIS_RECEIPT.json`, its scene/coverage tables, full prediction index/reference bank, then only selected score/prediction/support bindings. Raw corpus audio, full native logs and models are not scanned. One first-coverage score was inspected before selection solely for schema discovery; its paired outcome was not used to select cases.

Outputs under `reports/S6C/20260910T123540Z/full_anonymous_component_review_v1`: `PLAN.json`, `RESULT.json`, readable `FAILURE_EXAMPLES.md`, and `PUBLICATION.json`. All are new/no-overwrite. Results are source-bound descriptive development evidence, not new accuracy scoring, a representative sample, confidence interval, timing qualification or enrolled-name test. Four pure fixtures verify exact deterministic tie order, input-order invariance, non-fabrication of harm and paired-population rejection.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_full_anonymous_review_v1.py" test
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_full_anonymous_review_v1.py" prepare
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6c_full_anonymous_review_v1.py" run
```

Anaconda Prompt / Windows CMD (existing interpreter; no installation):

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_full_anonymous_review_v1.py" test
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_full_anonymous_review_v1.py" prepare
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_full_anonymous_review_v1.py" run
```

The real report requires exact same native source and final ASR words in each selected pair, so label attribution effects cannot be confused with lexical changes. First-final/first-display cp, Unknown support, return states and modal mapping are shown separately. Anonymous track numbers may permute; a label-number change alone is not an identity error. Missing/incomplete/empty reference populations are never assigned an invented complete cp denominator. Model-free policy outputs reuse captured neural observations and do not create independent acoustic trials.
