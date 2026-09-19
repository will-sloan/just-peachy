# Four-namespace paced closure and observation coverage

`s6b_paced_closure_v2.py` is a separate report-only helper for the final four-namespace paced study. It preserves `s6b_paced_closure.py`, pins that historical source hash, and retains its summary-grid, worker/PCM/tail, trajectory-copy, artifact, native-launch and owned-process closure checks. It does not run models, change predictions, stop processes or modify the original evidence. Run final aggregation only after the final coordinator and every owned worker have closed. Use a fresh output directory.

The expected scope is exactly 64 logical cells: B00/B36/B10/B17 × four admitted whole cases × O0/O1 × repetitions 1 and 2. Across `paced_finalists_epoch2_v1` through `v4`, the fresh-complete counts are 2/22/11/29, interrupted counts 1/1/1/0, and copied completion-reference counts 0/2/24/35. This means 64 successful physical native sessions plus three preserved interrupted sessions, or 67 physical attempts. Copied receipts do not count as new inference. A changed count, duplicate successful job, foreign worker CLI/manifest, failed final summary, live owned process, or changed artifact fails closure.

Inputs are the final v4 `MANIFEST.json` and complete `SUMMARY.json`, all four preserved namespaces, and the three ordered repaired-observer directories: `read_retry_overlay_v1_run1`, `live_reader_overlay_v2_run1`, and `optional_live_overlay_v3_run1`. The original unwrapped coordinator is the fourth observer version. Repaired-observer statuses must be FAILED/FAILED/COMPLETE. The final optional observer must retain every malformed snapshot before mapping an admitted LIVE JSON parse failure to a missing observation. The helper verifies event order, full raw snapshot bindings, the terminal identical pair, exact pathwise read/missing counts and retained-byte totals. It does not parse a valid prefix, interpolate, or reuse a previous LIVE value. Non-LIVE authoritative files remain strict.

Outputs are fresh `PACED_CLOSURE.json`, `PACED_CLOSURE.md` and `PACED_OBSERVATION_COVERAGE.csv`. The JSON retains source bindings, 67 attempt identities, namespace counts, exact native repetition comparisons, successful-cell resource ranges, separate interrupted partial trajectories, current RAM/C:/G: status, and per-job/profile/tap observation coverage. The CSV is a compact successful-cell coverage export. Empty numerical CSV cells mean unavailable, not zero.

## Observation and resource meanings

Every stored process sample remains in the denominator. These are separate quantities:

- Null LIVE rows, which may include the time before a status file exists.
- Observed LIVE objects without telemetry, including model-loading phases. Per-phase sample counts are retained.
- Actual source/cursor observations eligible for ASR or speaker backlog calculations.
- Explicit `optional_live_json_missing` read events. Per-path counters are available only for the final optional observer; earlier missing-read counters are unavailable, not zero. Reader-call counts remain separate from stored-row counts.

Observed-sample backlog peaks remain useful, but they are never described as proven continuous-time maxima. This limit applies even when all stored sample points contain telemetry. Missing intervals further reduce coverage. `whole_time_max_sec` is always unavailable; `complete_stored_grid_max_sec` is also unavailable when the stored grid has missing values. No imputation is performed. Actual consecutive process-sample gaps and gaps above 0.75 seconds are counted. Native display-event emission timestamps remain independent of LIVE observations and retain their original interpretation.

Native-worker process-tree observations marked complete by the stored sampler are separated from partial/missing observations, with availability counts for each memory metric. This is a sampler-flag scope: the frozen `sample_tree` can fall back to the root process when descendant enumeration fails without clearing `tree_complete`. The helper therefore cannot independently guarantee exhaustive OS descendant enumeration. It preserves that limitation rather than changing native sampling. USS is private resident memory, RSS is a sum upper bound that can duplicate shared pages, private commit is virtual commitment, and unavailable PSS remains null. The coordinator's RSS is separately sampled; it is not called native-worker tree memory or silently added to it. Inherited summary ranges remain the original driver's observations, while sampler-complete-only ranges are separately available per job. Sampled process-tree CPU remains a lower bound. Interrupted partial attempts are preserved separately and are not substituted into successful-cell resource ranges.

Four observer versions, three interruption gaps and unrelated host activity limit resource comparability. All repetitions remain; no favorable repetition is selected. Fresh-process, finite-scene cells do not establish a continuous multi-scene leak, desktop-to-CM5 speed factor, CM5 ARM64 throughput, 2 GB fit or thermal qualification. The immutable pre-paced 3,936-native-job checkpoint remains separate from this paced accounting.

## Model-free checks

`--check-root` creates only tiny synthetic fixture files in a fresh directory. It checks the inherited grid/worker/trajectory rejection conditions, four-namespace accounting, exact native argument form, full factorial membership, malformed-read retention and counter mismatches, null/loading/telemetry denominators, sample gaps, missing values, sampler-complete-tree/coordinator separation and compact CSV semantics. An additional fixture preserves a raw snapshot whose after-read metadata check failed before optional hash fields were assigned; its authoritative raw binding is still checked, and the final malformed identical pair must retain complete identity fields. No active measurement artifact or source audio is read by this mode. A successful fixture receipt proves these bounded checks; it is not a claim that the final study has completed.

PowerShell, safe while native measurements run:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_closure_v2.py" --check-root "$sim\staging\s6b\20260909T230840Z\paced_closure_v2_checks_NEW"
```

Anaconda Prompt or Windows CMD, using the existing project interpreter without installing anything:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_closure_v2.py" --check-root "%SIM%\staging\s6b\20260909T230840Z\paced_closure_v2_checks_NEW"
```

## Final aggregation after every worker closes

Use these commands only when the v4 complete summary and final observer completion are durable. The helper refuses a still-live observer and validates namespace process closure before accepting native evidence. It hashes the explicit paced artifacts and retained malformed snapshots at this final stage. It performs no broad historical re-audit or inference. The output directory must be new and outside all source/observer namespaces.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = "$repo\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
$paced = "$sim\reports\S6B\20260909T230840Z\paced"
$payload = 'G:\Just_Peachy_S6B\20260909T230840Z'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\s6b_paced_closure_v2.py" --final "$payload\paced_finalists_epoch2_v4" --namespaces "$payload\paced_finalists_epoch2_v1" "$payload\paced_finalists_epoch2_v2" "$payload\paced_finalists_epoch2_v3" "$payload\paced_finalists_epoch2_v4" --observer-roots "$paced\read_retry_overlay_v1_run1" "$paced\live_reader_overlay_v2_run1" "$paced\optional_live_overlay_v3_run1" --output "$paced\final_closure_v2"
```

Anaconda Prompt / Windows CMD:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PACED=%SIM%\reports\S6B\20260909T230840Z\paced"
set "PAYLOAD=G:\Just_Peachy_S6B\20260909T230840Z"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6b_paced_closure_v2.py" --final "%PAYLOAD%\paced_finalists_epoch2_v4" --namespaces "%PAYLOAD%\paced_finalists_epoch2_v1" "%PAYLOAD%\paced_finalists_epoch2_v2" "%PAYLOAD%\paced_finalists_epoch2_v3" "%PAYLOAD%\paced_finalists_epoch2_v4" --observer-roots "%PACED%\read_retry_overlay_v1_run1" "%PACED%\live_reader_overlay_v2_run1" "%PACED%\optional_live_overlay_v3_run1" --output "%PACED%\final_closure_v2"
```

If a later authoritative interruption or scope change occurs, preserve this helper and its receipts. Do not weaken its expected counts to label partial evidence complete; use a separately reviewed report version.
