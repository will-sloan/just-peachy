# S6C work and state reporting V1

`s6c_work_state_report_v1.py` reports existing prototype-comparison work and state-count observations from 31 explicitly bound S6C lifecycle CSV authorities, plus byte estimates from two already closed chronological snapshots. It uses the Python standard library. It does not load models, read predictions/audio/native events, rescore, replay a policy, search for pending sessions or change source files.

## Fixed inputs and scope

The sole catalog is `reports/S6C/20260910T123540Z/requirement_gap_review_v2/STRATA_AND_STATE_SOURCE_INDEX.json`, SHA256 `bae3ec7011eec5b53ab782c1813ca6107e456db7674fc2f709ca370e045038e5`. Its 31 `comparison_work_tables` declarations resolve completed core V1/V2/V3 authorities and exact `TRACK_LIFECYCLE_RESULTS.csv` pointers. These are the 29 S6C core authorities from the original working export plus completed full N03 and N08/N10. Historical S6B tables are outside this specific lifecycle schema. Different panel/full/native/cached-policy authorities remain separate; their actual analysis `scope`, declared cases and actual ASR/identity routes are retained in `SOURCE_ADMISSION.json`.

The two snapshot declarations are the prior-reviewed `long_session/v1/chronological/C001/O0_O0/SNAPSHOT.json` and C002 counterpart. They are model-free chronological policy diagnostics over genuine native cached evidence. The N00 reconstructed clean-support path rejects much of the legacy evidence. They are not recognition validation, actual native endurance, paced cold-start measurements or finalist resource measurements.

Every JSON/CSV is parsed from the exact buffer verified against its original byte count and SHA256. The helper validates completed status, table pointer, declared route/case product, exact actual route labels, unique rows and scored/unscored counts. All 31 source authorities and the catalog are checked again at closure. Source rows do not become physical-session/inference counts. This helper refuses an active shared paced/continuous quiet lease before execution and each authority; it does not run a competing observer or reserve a new lease.

## Outputs

Use a fresh immediate child of `REPORT/work_state_reporting`. The report leaves partial files visible after failure and never overwrites a prior result.

- `<source_id>/SOURCE_CELLS.csv`: every original lifecycle CSV column and decoded cell text, in original column/row order, with five appended `__work_` provenance columns. These include exact authority/table hashes, original logical row number and SHA256 of the original cell dictionary serialized with the helper's canonical JSON function. CSV quoting may change but original cell text does not. Original whole-file hashes remain bound. No activation/lineage cell is discarded or reinterpreted.
- `GROUP_METRICS.csv`: one row per authority, candidate, actual ASR/identity route and metric. It retains declared/observed/missing source-row counts, field presence and value-observed/value-missing counts. Min/median/max use observed values only; all tied maximum case IDs appear in sorted order. Absent fields and blank source cells never become zero. Blank output aggregates mean unavailable or not additive, distinguished by the explicit counts and `sum_scope`.
- `CHRONOLOGICAL_STATE_ONLY.json`: exact projected counts/work/byte estimates from the two admitted snapshots, with original bindings and explicit model-free scope. Per-track measured heap and native process RSS are null.
- `SOURCE_ADMISSION.json`: exact source paths/hashes, authority table pointers, headers, routes/cases and original authority scope. Original sources remain the authority for these observations.
- `RESULT.json`: completed explicit report status, source/group/metric counts, output hashes, source/README bindings and limitations. This is not final S6C acceptance.

The metrics are `decisions`, `track_count`, `peak_live`, `peak_archive`, `blocked_unique_evidence_sec`, `prototype_comparisons`, `max_live_prototype_comparisons_per_observation`, and final/peak-observed variants of active, dormant, provisional, live, archive, cumulative retirements, lifetime external IDs and prototypes.

Only decisions, prototype comparisons and source blocked-evidence seconds receive within-group sums. The sum is over the selected source's observed rows, not independent replications or a pooled total across experiments. Missing rows/values remain explicit. No global sum or winner is produced. State stocks and byte estimates are never summed. A cumulative-retirement maximum is a maximum of per-scene counters, not a lifetime total across fresh scenes.

`peak_live`/`peak_archive` preserve tracker-maintained fields. `peak_observed_*` describe sampled decision-count observations and can miss unobserved states. `final_*` maxima are across final scene states, not within-session peaks. `prototype_comparisons` can include archive work beyond the maximum live comparisons per observation; these fields must not be treated as equivalent. None of them is a measured CPU-time or neural-call count.

Array payload and shallow object bytes exclude recursive Python heap, models, queues and process RSS. Per-track heap is unavailable; dividing global array totals by live tracks would invent a measurement. Actual future paced RSS and continuous/native final state remain separate report scopes.

## Future closed-native adapter boundary

The pure `project_tracker_snapshot(snapshot, pointer)` function can project an explicitly named tracker object. It does not admit a native session. This command-line version accepts only the two pinned chronological declarations. A separately reviewed future adapter must first use the held inventory/long diagnostics admission to verify completed closure, original epoch/profile/gallery/source, owner/released lease and exact artifact binding; it must then declare the actual final tracker JSON pointer and native execution kind. Missing final state fields stay unavailable. This prospective interface is not a claim that any pending native snapshot has been inspected or admitted.

## PowerShell

The existing EDGE Python has all required standard-library dependencies. No install or environment modification is needed.

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = Join-Path $s6cSim 'reports\S6C\20260910T123540Z'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_work_state_report_v1.py'
& $s6cPython -B $s6cScript checks --output (Join-Path $s6cReport 'work_state_reporting\SOURCE_CHECKS_V1.json')
& $s6cPython -B $s6cScript run --output (Join-Path $s6cReport 'work_state_reporting\working_v1')
```

## Anaconda Prompt or Windows CMD

The explicit Python executable selects the existing environment, so `conda activate` is unnecessary.

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%S6C_SIM%\reports\S6C\20260910T123540Z"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_work_state_report_v1.py"
"%S6C_PYTHON%" -B "%S6C_SCRIPT%" checks --output "%S6C_REPORT%\work_state_reporting\SOURCE_CHECKS_V1.json"
"%S6C_PYTHON%" -B "%S6C_SCRIPT%" run --output "%S6C_REPORT%\work_state_reporting\working_v1"
```

Once these paths exist, reproduction needs fresh suffixes; do not delete or overwrite the completed reports. Tests are 12 small synthetic checks covering grouping, zero/missing/absent fields, missing source rows, route/key faults, nonfinite/bool counts, tied maxima, source-cell quoting, exact-buffer binding and byte-scope projection. They read no actual score table and are not empirical measurements. Actual report execution, if completed, is separately bound by `RESULT.json`.
