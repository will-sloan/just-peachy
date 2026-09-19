# S6C fixed strata and adverse-condition synthesis V1

`s6c_strata_adverse_v1.py` prepares and later runs a finite descriptive comparison of existing completed score tables. It closes the strata narrative/reporting task, not a new model experiment or final operating selection. It uses only Python's standard library. No model, audio, vector, prediction, native event log, token aligner, scorer or policy is invoked. Existing source and earlier report files remain unchanged.

## Registered routes and contrasts

The fixed route set has 28 entries: C065, C067, C079, C117, C118, C121, C122, C088, C091, C076, B00, B01 and B36 on both original same-tap routes; C085 on O0 ASR/O1 identity; C086 on O1 ASR/O0 identity. C088/C091 are included as their existing core-score conditions; this report does not infer actual known-name accuracy from anonymous core scores.

The 30 fixed comparisons are these 14 pairs on both same taps: C065 to C067/C076/C079/C121; C121 to C122; C079 to C122; C117 to C118/C065/C121; C118 to C079/C122; B36 to C065/C067/C076. The other two compare C065 on the same ASR tap with each registered cross route. Direction is always right minus left. No extra C085/C086 route, alias propagation or scene-dependent roster is fabricated. B00/B01 and the naming routes remain in the full original-strata output even when they are not members of these explicit paired contrasts.

The original four populations stay separate: 156 primary nonoverlap scenes, 47 complete-overlap, 26 incomplete-reference and 11 strict-empty scenes per route. There is no combined complete-word headline here: primary words inherit serialized WER, while complete-overlap words inherit MIMO edit counts. All ten dimensions are retained: room, family, historical split, corpus, source quality, source level, noise category, SNR, receiver orientation and obstruction. Multi-corpus/quality/level/noise membership overlaps, so the rows cannot be summed into disjoint totals. A family or returning speaker is not automatically an independently verified physical relocation.

## Inputs and exact authority admission

The fixed source catalog is `REPORT/requirement_gap_review_v2/STRATA_AND_STATE_SOURCE_INDEX.json`, SHA256 `bae3ec7011eec5b53ab782c1813ca6107e456db7674fc2f709ca370e045038e5`, where REPORT is `simulation/reports/S6C/20260910T123540Z`.

- `anonymous`: exact full_n01_anonymous_core_v3 authority for C065/C079/C117/C118/C121/C122.
- `naming`: exact full_n01_naming_core_v3 authority for C088/C091.
- `n03`: exact full_n03_native_core_v3 authority for C067.
- `historical`: the catalog's exact S6B full_analysis_v1 authority, SHA256 `12ee9ccd91a2a924ba2f54b51f622c39c73ed15325073cac5439bad4298dda0f`, for B00/B01/B36. Its path is resolved from that existing authority, not guessed. Its original scene/strata tables lack identity-tap columns; the explicit original same-tap interpretation is recorded and cannot admit cross routes.
- `n12`: explicit null until the completed full C076 core authority exists and is supplied by its owner.
- `cross`: explicit null until the completed full C085/C086 core authority exists and is supplied by its owner.

The `full_n12_native_core_v3` and `full_cross_native_core_v3` labels are intended descriptions only while unresolved. They are not fabricated paths or source hashes. The helper does not discover pending files. Completed N08/N10 RESULT and V2 interpretation bindings are cited separately; no N08/N10 routes are added to this grid.

Admission requires original `SCENE_RESULTS.csv` and `STRATA_RESULTS.csv` pointers in COMPLETE core receipts, canonical input declaration, full240 actual-route coverage and exact inherited metric/reference/normalizer source hashes. Known source slots are immutable. Resolution can fill only the two null slots, and all their case sets must match the fixed full-bank authority. Helper/README bytes are bound in the draft and rechecked by later commands. Merely sharing a schema string or equal scene counts cannot substitute for this admission.

Draft and resolve read receipts/catalog/prose metadata only. Actual table reading happens only in `run`, after root reviews the fully resolved specification. Each CSV is parsed from the same bounded buffer whose size/hash is verified. The largest allowed input buffer is 80 MiB; the exact historical scene table is about 53 MiB. The helper does not decompress archives or follow prediction/log/model pointers. It refuses an active shared paced/continuous quiet lease before each source-table pair.

## Exact membership and aggregate verification

For each selected route, the helper requires all240 exact cases and the original four population counts. It reconstructs memberships from the seven arrays in each scene's `strata` JSON, plus the separate `room`, `family_id` and `historical_split` columns. Unique nonempty memberships are mandatory. It requires a one-to-one match between every reconstructed dimension/value/population group and the original selected STRATA rows. Source row numbers and full original scene-cell hashes bind the exact member list.

Before any paired metric, source scene count, duration and requested integer edit/support/return totals are reconciled to that original STRATA row. This is arithmetic admission of existing scored counts, not rescoring or a fresh WER calculation. The original aggregate's cells are retained verbatim as strings. Source-duration sums use a 1e-7-second absolute floating-point comparison; integer counts and exact member sets use exact equality.

Pairs require identical stratum case IDs, not merely equal counts. Complete lexical/cp reference-word denominators must agree both per scene and in the aggregate. Each metric also records its own eligible case IDs, observed/ineligible scene counts and both denominators. Differing eligible case sets make the paired rate and count delta unavailable; original source observations remain present.

The six metric views are:

| Metric | Numerator | Denominator / scope |
| --- | --- | --- |
| word | Original inherited word errors | Reference words; primary serialized WER or separate complete-overlap MIMO scope |
| cp_first_display_label_final_words | Original first-display-label final-word cp errors | Full reference words; not partial-transcript WER |
| cp_latest_revised | Original latest-label final-word cp errors | Full reference words; not pure tracking when words differ |
| unknown_support | Original Unknown samples | Sole-active source-support samples; not named-person correctness |
| inconsistent_returns | Original inconsistent return turns | Consistent + inconsistent + Unknown return turns, with eligibility shown |
| empty_insertions | Original strict-empty insertion count | Actual source seconds, displayed per source minute |

Full word and cp views are explicitly unavailable on incomplete and strict-empty populations, even if an inherited source contains a target-only diagnostic. Their original source cells are still retained. Empty-insertion views are unavailable outside strict-empty cases. Zero or unavailable exposure yields no rate. A source numeric zero stays zero; missing full-reference metrics never become zero. Unknown/return counts follow their original source-support scope and do not establish identity naming accuracy.

## Predeclared adverse-example selection

All paired rows remain in the output, including improvements, zeros and unavailable metrics. The examples choose the largest **strictly positive** harmful difference for each contrast, metric, original population and basis (rate and raw count separately). Exact rational deltas determine order; ties use dimension and value lexically, with every tied maximum retained as a reference. Zero is not called harm. No positive group produces an explicit `NO_POSITIVE_HARM` record, not an invented favorable score.

Tiny-support flags are descriptive and never filter a group: fewer than five eligible scenes; fewer than20 reference words for word/cp; fewer than16,000 sole-support samples; fewer than five return turns; or less than60 seconds of empty-source exposure. These thresholds do not change any metric or declare statistical significance. Rate and count extremes can select different groups.

The concise narrative retains a per-contrast count of positive metric/population maxima and shows one largest positive rate example per metric and original population across the retained per-contrast maxima, breaking ties by contrast ID/dimension/value. It never compares one metric's numerical scale with another, and it never combines original populations. Full per-contrast examples, raw counts, both denominators, member cases and flags remain in the companion outputs. Descriptive high rates in tiny groups are not a global winner/loser ranking or an independent holdout result. No CI, bootstrap, new WER or timing/reset causality is produced.

## Outputs

Every action uses a fresh child namespace under `REPORT/strata_adverse_v1` and refuses overwrite.

- `checks`: `CHECKS.json`, with 13 model-free guards and exact source/README bindings. It reads no actual CSVs.
- `draft`: `SPEC.json`, status `DRAFT_UNRESOLVED_NO_ANALYSIS`; two null authority slots remain explicit.
- `resolve`: a new `SPEC.json`, status `RESOLVED_COMPLETE_SOURCES_PENDING_ROOT_RUN_REVIEW`, with both owner-supplied completed receipt bindings and lineage to the unchanged draft. This command still reads no score-table bodies.
- `run`: `ORIGINAL_STRATA_AND_MEMBERSHIPS.json` retains all selected original strata cells plus exact member/source-row bindings; `PAIRED_STRATA_METRICS.csv` retains every paired view and denominator; `DESCRIPTIVE_HARM_EXAMPLES.json` retains both rate/count extrema and ties; `NARRATIVE.md` gives the bounded synthesis; `RESULT.json` binds all artifacts, sources and scopes. Raw scene tables and scored texts are not rewritten or re-exported.

No actual analysis run is authorized before root reviews a fully resolved plan. This helper intentionally has no placeholder-cell execution or partial-grid inference. If a future authority is missing, resolution fails without starting table analysis. Partial output from any actual error remains intact and a corrected attempt requires a new namespace.

## PowerShell: currently available preparation

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = Join-Path $s6cSim 'reports\S6C\20260910T123540Z'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_strata_adverse_v1.py'
& $s6cPython -B $s6cScript checks --name source_checks_v1
& $s6cPython -B $s6cScript draft --name draft_v1
```

## Anaconda Prompt or Windows CMD: currently available preparation

The explicit executable supplies the existing environment. No installation or `conda activate` is needed.

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%S6C_SIM%\reports\S6C\20260910T123540Z"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_strata_adverse_v1.py"
"%S6C_PYTHON%" -B "%S6C_SCRIPT%" checks --name source_checks_v1
"%S6C_PYTHON%" -B "%S6C_SCRIPT%" draft --name draft_v1
```

Once those namespaces exist, reproduction uses fresh suffixes; do not delete the held artifacts.

## Later resolution and run, after completed authorities and root review

The values in angle brackets below must come from the completed owners' receipts/reviews. They are deliberately not guessed current authority bindings. Both pending slots must be supplied together. A freshly calculated hash alone is not proof of an approved source or scope.

```powershell
$s6cDraft = Join-Path $s6cReport 'strata_adverse_v1\draft_v1\SPEC.json'
& $s6cPython -B $s6cScript resolve --name resolved_v1 --spec $s6cDraft --spec-sha256 '<held-draft-SHA256>' --authority n12 '<actual-completed-N12-receipt-path>' '<owner-supplied-N12-SHA256>' --authority cross '<actual-completed-cross-receipt-path>' '<owner-supplied-cross-SHA256>'
# Only after root reviews the returned resolved SPEC:
& $s6cPython -B $s6cScript run --name actual_v1 --spec (Join-Path $s6cReport 'strata_adverse_v1\resolved_v1\SPEC.json') --spec-sha256 '<root-reviewed-resolved-SHA256>'
```

```bat
"%S6C_PYTHON%" -B "%S6C_SCRIPT%" resolve --name resolved_v1 --spec "%S6C_REPORT%\strata_adverse_v1\draft_v1\SPEC.json" --spec-sha256 "<held-draft-SHA256>" --authority n12 "<actual-completed-N12-receipt-path>" "<owner-supplied-N12-SHA256>" --authority cross "<actual-completed-cross-receipt-path>" "<owner-supplied-cross-SHA256>"
REM Only after root reviews the returned resolved SPEC:
"%S6C_PYTHON%" -B "%S6C_SCRIPT%" run --name actual_v1 --spec "%S6C_REPORT%\strata_adverse_v1\resolved_v1\SPEC.json" --spec-sha256 "<root-reviewed-resolved-SHA256>"
```

The guards cover exact28/30 scope, seven-plus-three membership, duplicate memberships, equal-count/different-case rejection, metric eligibility, full-reference denominator mismatch, incomplete full-word nulls, explicit historical same-tap absence, invalid cross routes, positive-only rational tie order, retained tiny support, changed exact buffers and nonfinite metrics. They are synthetic schema/analysis guards, not empirical results.
