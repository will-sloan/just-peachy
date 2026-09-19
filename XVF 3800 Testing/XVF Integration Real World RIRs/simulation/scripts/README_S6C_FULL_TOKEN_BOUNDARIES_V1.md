# Full-bank scored-text token-boundary supplement

`s6c_full_token_boundaries_v1.py` prepares and, only after explicit complete authority admission, computes a separate token-position diagnostic from original core `SCENE_RESULTS.csv` fields. It does not import a model, run a policy, read predictions or native events, access audio/vectors, or replace the authoritative core metrics. No native/log verification is inferred from a scored-text table.

The finite selection contains 18 routes and 4,320 scene rows: C065, C067, C072, C074, C076, historical B00/B01/B36 on both same-tap routes, plus C085 O0-ASR/O1-identity and C086 O1-ASR/O0-identity. Each route retains all 240 scenes. The explicit comparisons use C065 with the same ASR tap as the left side for each other route, producing 16 comparisons across 240 scenes (3,840 paired rows). Both taps remain dependent views of captures; these are not independent trials or candidate-selection rules.

## Inputs and admission

- Original completed S6C V3 core receipts, exact SHA-256 and byte-bound original `SCENE_RESULTS.csv`, including `normalized_final_text` (omitted from the compact working export). Every full source CSV is parsed from its exact verified buffer once during `run`; every original row participates in row-count and duplicate-key checks. Only the registered selected routes enter diagnostics. CSV record ordinals, not physical line numbers, identify quoted multiline records.
- Historical paths are resolved through the exact existing `design/full_n01_anonymous_compare_v2_inputs_V3.json`; the original S6B receipt must also match its sealed `LOCAL_ARTIFACT_INDEX.json` entry. No historical output is relabeled as S6C native execution. The historical source table is approximately 53 MB, while individual S6C authorities vary (the eight-family anonymous table is approximately 13 MB). The 100 MiB per-file bound is explicit; memory includes one decoded whole table, selected rows and the final compact diagnostic objects.
- The SHA-pinned canonical scene bank and the original `s4_h2_analysis.normalize` and `s6a_text_metrics.reference_layout` functions. Only those exact function ASTs execute, without importing their modules/scorer dependencies.
- The SHA-pinned `positional_edits` function from held `s6c_endpoint_audit_v1.py`, compiled unchanged as a pure function. Its unit edit costs and backtrace priority are **equal, substitution, deletion, insertion**. A repeated word can have another equally optimal alignment; this helper deliberately preserves the original deterministic choice. A scene alignment is limited to 2,000,000 DP cells.
- Future N08/N10, N12 and cross authorities remain null in the finite draft. Intended directory names are descriptive labels only, without invented paths/hashes. `prepare` requires the owner's exact completed receipt path and SHA for each pending slot. It does not read score CSVs. `run` requires a separately bound complete plan and rereads its source receipts. An active shared paced quiet lease refuses preparation or streaming; no lease/process is changed.

Known C065/C067 and historical authorities are fixed in the draft. Alternative completed authorities, aliases, panel subsets, duplicate routes, missing scenes and partial core receipts are not silently substituted. Source code and maintained README are bound into the specification; changing them requires a fresh specification rather than reuse of an earlier plan.

## Populations and field interpretation

Per route the canonical bank contains 156 `PRIMARY_NONOVERLAP`, 47 `COMPLETE_OVERLAP`, 11 `STRICT_EMPTY_REFERENCE` and 26 `INCOMPLETE_REFERENCE` scenes. The 203 nonempty complete scenes contain 6,016 reference words. All 240 rows and actual scored source durations remain present, including the four longer captures. Original scene duration is neither rounded to 45 seconds nor inferred from nominal scheduling.

- `token_alignment` is null for all 26 incomplete scenes; so are full-reference edit deltas and first/last loss indicators. The available partial reference word count is labeled `available_reference_words`, never treated as a complete all-speaker denominator.
- Complete overlap is serialized in the unchanged canonical source-start utterance order. Its resulting edit count is a **separate serialized diagnostic**, not MIMO WER, cpWER, speaker attribution, time-constrained loss or overlap recall. It is aggregated separately from primary scenes.
- Strict-empty scenes are retained with their observed hypothesis. Their reference boundaries are unavailable/null, while insertions are counted. An empty observed hypothesis is the exact empty string; missing CSV fields are rejected.
- First/last reference token operations retain `equal`, `substitution` or `deletion` distinctly. `first_reference_token_deleted` / `last_reference_token_deleted` refer only to deletions, not substitutions or acoustic clipping. A one-token reference can contribute to both boundaries. Only nonempty complete scenes enter `boundary_eligible_scenes`; empty or incomplete populations have null boundary deletion totals, not zero.
- Cell records retain the complete alignment position arrays, explicit tie rule, source table/receipt bindings, original CSV row digest and normalized-text UTF-8 SHA. These are positional witnesses from **scored final text**, not a new comparison against raw native ASR logs. Timing, endpoint/reset incidence, first audible syllables, finalization latency and reset causality are unobserved by this helper.
- `ROUTE_POPULATIONS.json` keeps each route and population separate, with requested, alignment-available/unavailable and boundary-eligible scene denominators. Error/substitution/deletion/insertion sums are null when no full-reference alignments exist. Cumulative `hypothesis_words_all_scenes` counts token outputs, not unique spoken words.
- `PAIRED_SCENES.json` uses right-minus-left edit counts and retains whether the scored normalized text changed, plus both boundary operations. It has no bootstrap, significance claim or causal attribution. The matched ASR tap and actual source duration must agree. Different identity routes are explicit, as are historical cross-generation comparisons.

## Outputs

All outputs are new, no-overwrite namespaces beneath `reports/S6C/20260910T123540Z/full_token_boundaries_v1`:

1. `source_checks_v1/CHECKS.json`: source/README/pure-function bindings and model-free fixture results.
2. `draft_v1/SPEC.json`: finite unresolved selection, existing completed receipt/table declarations, three pending authorities; no score-table read and no result claim.
3. A later `admission_v1/PLAN.json`: all six completed authorities bound, original draft binding preserved; still no table read or diagnostic execution.
4. Only after owner review and authorization: a fresh `results_v1/CELLS.json`, `ROUTE_POPULATIONS.json`, `PAIRED_SCENES.json`, `RESULT.json`. The result binds every table actually read and the plan. Failure before final result publication does not certify any partial output as complete; retry uses a new name.

## PowerShell

Use the project's existing EDGE interpreter; only standard-library code is required. These first two commands are model-free and do not read actual score CSVs:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location -LiteralPath $sim
& $py -B scripts\s6c_full_token_boundaries_v1.py checks --name source_checks_v1
& $py -B scripts\s6c_full_token_boundaries_v1.py draft --name draft_v1
```

Later, after the three owners publish actual COMPLETE core receipts and the helper is reviewed, assign the explicitly supplied paths/hashes below. Angle-bracket strings are required inputs, not existing authorities or runnable examples as written:

```powershell
$spec = "$sim\reports\S6C\20260910T123540Z\full_token_boundaries_v1\draft_v1\SPEC.json"
$specSha = '<SHA printed by draft>'
$n08 = '<actual completed N08/N10 ANALYSIS_RECEIPT.json path>'
$n08Sha = '<owner supplied receipt SHA>'
$n12 = '<actual completed N12 ANALYSIS_RECEIPT.json path>'
$n12Sha = '<owner supplied receipt SHA>'
$cross = '<actual completed cross ANALYSIS_RECEIPT.json path>'
$crossSha = '<owner supplied receipt SHA>'
& $py -B scripts\s6c_full_token_boundaries_v1.py prepare --spec $spec --spec-sha $specSha --authority n08_n10 $n08 $n08Sha --authority n12 $n12 $n12Sha --authority cross $cross $crossSha --name admission_v1
# Only after the owner approves this exact prepared plan:
$plan = "$sim\reports\S6C\20260910T123540Z\full_token_boundaries_v1\admission_v1\PLAN.json"
$planSha = '<SHA printed by prepare>'
& $py -B scripts\s6c_full_token_boundaries_v1.py run --plan $plan --plan-sha $planSha --name results_v1
```

## Anaconda Prompt / CMD

No environment installation or activation is needed because the existing interpreter is explicit. Use `cd /d` for the drive/directory change. Run the first two commands once in fresh namespaces:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
cd /d "%SIM%"
"%PY%" -B scripts\s6c_full_token_boundaries_v1.py checks --name source_checks_v1
"%PY%" -B scripts\s6c_full_token_boundaries_v1.py draft --name draft_v1
```

For the later admitted step, replace every bracketed value with the supplied exact path or SHA. Do not run these lines while source slots are pending:

```bat
set "SPEC=%SIM%\reports\S6C\20260910T123540Z\full_token_boundaries_v1\draft_v1\SPEC.json"
set "SPEC_SHA=<SHA printed by draft>"
set "N08=<actual completed N08/N10 receipt path>"
set "N08_SHA=<owner supplied receipt SHA>"
set "N12=<actual completed N12 receipt path>"
set "N12_SHA=<owner supplied receipt SHA>"
set "CROSS=<actual completed cross receipt path>"
set "CROSS_SHA=<owner supplied receipt SHA>"
"%PY%" -B scripts\s6c_full_token_boundaries_v1.py prepare --spec "%SPEC%" --spec-sha "%SPEC_SHA%" --authority n08_n10 "%N08%" "%N08_SHA%" --authority n12 "%N12%" "%N12_SHA%" --authority cross "%CROSS%" "%CROSS_SHA%" --name admission_v1
set "PLAN=%SIM%\reports\S6C\20260910T123540Z\full_token_boundaries_v1\admission_v1\PLAN.json"
set "PLAN_SHA=<SHA printed by prepare>"
"%PY%" -B scripts\s6c_full_token_boundaries_v1.py run --plan "%PLAN%" --plan-sha "%PLAN_SHA%" --name results_v1
```

For repeated checks use a new `--name`, such as `review_checks_v1`; existing outputs are never overwritten. `--help` and `checks` never instantiate a model. No actual full-bank diagnostic or result interpretation has been executed at source preparation time.
