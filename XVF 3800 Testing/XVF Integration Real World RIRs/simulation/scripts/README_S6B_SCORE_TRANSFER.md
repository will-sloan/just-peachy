# Transfer verified S6B scores into a combined analysis

`s6b_score_transfer.py` avoids recalculating already completed per-output metrics when a later combined prediction index contains those exact outputs. It performs no inference or replay and never copies aggregate tables or prior completion receipts. The normal frozen core scorer must still run on the combined index and freshly rebuild all paired/strata/coverage summaries.

## Admission rules

The source analysis must be complete. Its receipt binds COVERAGE.csv, and COVERAGE.csv binds each score file. The helper verifies that chain, the source index, every current prediction, reference-support file, score identity, current metric code/package/schema/bank identity and analysis key. Source keys must occur exactly in the complete destination index with identical prediction bindings. Source scores stay unchanged.

All checks finish before copying starts. Missing/failed/changed inputs are rejected; they never become reusable success. Score destinations must remain within the named target analysis directory. Existing byte-identical copies allow transfer resumption; a differing destination is never overwritten. A target containing a core-analysis heartbeat or completion receipt is rejected because its scoring has already started. Do not run a transfer concurrently with target scoring.

The exact in-memory source bytes are length/hash-verified before copying. A new destination is published from a unique same-directory temporary file after flush/fsync, using an atomic hard-link creation that refuses replacement, then removing the temporary name. This requires hard-link support, as available on this run's NTFS destination. An interrupted pre-publication write cannot become a partial valid score name; a hard termination may leave an unreferenced temporary file. A later core run independently reopens predictions/support and checks each copied analysis key before using it. Admission does not lock files against arbitrary later mutation; the run's normal immutable-file discipline still applies.

## Inputs and outputs

Inputs are the completed source analysis directory, complete later prediction index, root INPUT_INDEX.json, frozen scene bank, current metric-code bindings and the existing pinned metric environment.

Only `scores/<profile>/<case>/<tap>.json` is copied to the target directory. A separate `SCORE_TRANSFER_RECEIPT.json` records source/coverage/index/code identities, every planned score, copied/existing counts and test results. `--verify-only` performs the preflight and writes a no-copy receipt. It does not authorize the combined analysis to be declared complete.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$python = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $python "$sim\scripts\s6b_score_transfer.py" --test
& $python "$sim\scripts\s6b_score_transfer.py" --source-analysis-subdir r0_full_analysis_v1 --target-index FULL_PREDICTION_INDEX.json --target-analysis-subdir full_analysis_v1 --receipt-subdir score_transfer_v1
& $python "$sim\scripts\s6b_analysis.py" --index FULL_PREDICTION_INDEX.json --output-subdir full_analysis_v1 --require-complete
```

The final combined index for this run is FULL_PREDICTION_INDEX.json; pass it explicitly as shown. The helper's generic default is not this run's final index name. Run only after the source analysis and combined prediction index are complete. Append `--verify-only` to the transfer command for a read-only admission check; use a distinct receipt subdirectory to preserve both check and execution evidence.

## Anaconda Prompt or Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "ANALYSIS_PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_score_transfer.py" --test
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_score_transfer.py" --source-analysis-subdir r0_full_analysis_v1 --target-index FULL_PREDICTION_INDEX.json --target-analysis-subdir full_analysis_v1 --receipt-subdir score_transfer_v1
"%ANALYSIS_PY%" "%SIM%\scripts\s6b_analysis.py" --index FULL_PREDICTION_INDEX.json --output-subdir full_analysis_v1 --require-complete
```

No new environment is needed. Optional `--report` selects the report root. Keep source and target directories distinct, and choose a new target after scoring dependency changes.

## Validation

Ten isolated checks use the actual preflight/copy path with temporary synthetic score metadata: exact atomic copy, exact resume, changed package identity, changed prediction bytes, changed source score, conflicting target score, modified bound coverage table, an already-started target, changed source bytes after admission, and interrupted pre-publication all have their expected outcomes. The fixtures contain no speech audio, models or real user data. Full-run transfer has a separate receipt and is not claimed by the fixtures.

