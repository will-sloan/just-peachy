# Updated draft compact score catalog V2

Purpose: `s6c_score_catalog_draft_v2.py` prepares an explicit **DRAFT_PARTIAL_CATALOG**, using the reviewed `s6c_score_tables.py` schema. It cannot export because the collector rejects draft status. It neither scores nor selects outcomes. The old RECOMMENDED_INPUT_CATALOG_DRAFT_V1.json remains unchanged. This code and README are maintained together.

Inputs: exact candidate_support/SPEC_WORKING_V1.json SHA769f201ae9d5f116028f0f94a50f35eca0e0324dd85e21dfdc9a97668a1eb244 with31 completed core authorities, the current immediate report-root child NAME_ANALYSIS_RECEIPT.json files with completed name schemasV1/V2/V3, the original draft, and the held collector/source review. The collector SHA must remain2c9bd02ec318a34fc2f7a0d07004a5b099c2afd5f404a6a362e3302bca747406. Authority JSON buffers are hashed before parsing and checked again at publication. No prediction/index payloads, events, audio, vectors, models, rows from score CSVs or recursive report trees are scanned.

For each core authority the draft requests SCENE_RESULTS_COMPACT, PROFILE_RESULTS, SHORT_REPLY_RESULTS, PAIRED_COMPARISONS and TRACK_LIFECYCLE_RESULTS when available. Scene keys include profile_id,stream,identity_tap when actually present,case_id,population; historical schemas do not gain a fabricated identity column. Only present recipe_costs/strata/normalized_final_text may be omitted. Every other scalar or nested source cell is retained by the collector. Aggregate/lifecycle tables use byte-exact copy, no recomputation or invented uniqueness key. Other original core tables remain local with exact authority pointers, hashes, sizes and explicit reasons.

Names request intact PROFILE_NAME_RESULTS and EMPTY_CONTROL_RESULTS, and all existing TURNS, PEOPLE, QUERIES, RETAINED_ROWS, NAME_REVISIONS and COVERAGE tables of at most8MiB each. The8MiB bound is a prospective size limit for details, not a row/outcome filter; larger tables remain completely local and indexed. The detail rows are copied intact, without guessing a unique key or aggregating names by scene. Scalar/empty/null text remains exact; CSV cannot distinguish original null from an empty string. Known/unknown/intended-unavailable denominators remain those of each original authority. Separate scopes, repetitions and method aliases are never pooled.

Each selected table gets only a bounded64KiB maximum first-line/header read and before/after file size/mtime check. **Header previews do not verify whole CSV bytes.** The full original binding comes from the exact authority; authorized export later hashes/parses the full buffer. Tables whose original CSV has no valid nonempty header cannot be consumed by the held collector, even in copy_intact mode. They remain explicitly indexed local-only rather than inventing headers or changing the collector. Such tiny blank original files may be admitted as exact raw-file package companions separately if desired.

Scope_kind is restricted by the held collector enum. The historical44-scene challenge and6-output name smoke use its coarse native category with explicit descriptive labels stating their actual counts. That label does not assert new inference or a56/240-case population. Main/full/panel/native distinctions remain descriptive source labels; completed score receipt status is not native execution or whole-study acceptance.

Outputs in a new directory are RECOMMENDED_INPUT_CATALOG_DRAFT_V2.json, LOCAL_TABLE_INDEX.json (every original table, selected or local), HEADER_PREVIEWS.json, NAME_AUTHORITY_DISCOVERY.json, and DRAFT_CATALOG_RECEIPT_V2.json. The receipt reports selected source bytes, intact versus to-be-compacted bytes, local-only bytes and omission reasons. These sums estimate **source-read volume**, not actual compact output size or ZIP compression. Provenance and omission schema/hash sidecars add output bytes. No final<=20MiB claim is possible before actual export/packaging measurement.

PowerShell preparation (standard library only; no Conda activation):
```powershell
$simTask='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$pyTask='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $pyTask -B "$simTask\scripts\s6c_score_catalog_draft_v2.py" --output "$simTask\reports\S6C\20260910T123540Z\compact_score_tables\catalog_draft_v2"
```
Anaconda Prompt / CMD:
```bat
set "S6C_CATALOG_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_CATALOG_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6C_CATALOG_PY%" -B "%S6C_CATALOG_SIM%\scripts\s6c_score_catalog_draft_v2.py" --output "%S6C_CATALOG_SIM%\reports\S6C\20260910T123540Z\compact_score_tables\catalog_draft_v2_cmd"
```
These commands prepare only a draft and refuse existing output directories. Reproduction observes current immediate name-receipt metadata, so new completed names require a fresh timestamped catalog; this is not automatic source equivalence. Core sources remain exactly the31 supplied authorities. Later full N03/new native outputs must be added only after an actual completed score authority exists, in a separately reviewed draft. Do not wait for or infer unfinished tables.

Future export, **only after root approval of a separately saved explicit specification and its exact externally supplied SHA**:
```powershell
& $pyTask -B "$simTask\scripts\s6c_score_tables.py" export --spec 'C:\exact\APPROVED_SCORE_TABLE_SPEC.json' --spec-sha256 EXTERNALLY_APPROVED_SHA256 --output "$simTask\reports\S6C\20260910T123540Z\compact_score_tables\approved_working_export_v1"
```
```bat
"%S6C_CATALOG_PY%" -B "%S6C_CATALOG_SIM%\scripts\s6c_score_tables.py" export --spec "C:\exact\APPROVED_SCORE_TABLE_SPEC.json" --spec-sha256 EXTERNALLY_APPROVED_SHA256 --output "%S6C_CATALOG_SIM%\reports\S6C\20260910T123540Z\compact_score_tables\approved_working_export_v1"
```
Replace paths/hashes only with the approved binding. Do not compute a new arbitrary hash and call it approval, or change this draft's status in place. All source artifacts, prior draft and failed attempts remain preserved. A draft receipt reports no export, scoring, model call or final study completion.
