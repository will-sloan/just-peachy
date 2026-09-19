# S6C actual working score-export review V1

Purpose: independently reconcile the already completed, explicitly approved working export with its draft selection, local source-table index, original CSV headers and root compression measurement. This review does not export tables, rescore predictions, run models, or create a ZIP. It is an audit of working artifacts, not final S6C acceptance.

## Inputs and checks

The script pins the exact SHA-256 values of six JSON inputs under `reports/S6C/20260910T123540Z/compact_score_tables`: `working_v1/COLLECTION_MANIFEST.json`, `APPROVED_WORKING_SPEC_V1.json`, `WORKING_V1_COMPRESSION_MEASUREMENT.json`, and the V2 draft catalog, `LOCAL_TABLE_INDEX.json` and `HEADER_PREVIEWS.json`. The approved input list must equal the preserved draft's 38 authorities and 207 selected tables. The original draft remains a draft; the separate root approval authorizes this working export.

All 239 actual exported CSV/JSON buffers (176,747,852 bytes) are read once for independent SHA-256/length admission. Every exported CSV is parsed to verify its header, logical row count and field shape. The 31 compact scene tables retain every source column except the explicitly declared `recipe_costs`, `strata` and `normalized_final_text` fields, and add seven provenance columns. Every compact row has its original source row number, original authority/table hashes, separate scope, and unique original row-key hash checked. Empty strings remain empty strings; no numeric, Boolean, null or metric reinterpretation occurs. The other CSV copies must hash exactly to their original authoritative source bindings.

A targeted original-source comparison reads only the first three logical CSV records from each of full anonymous S6C, historical S6B full analysis and the cross-route panel. All retained cell strings and the corresponding 27 omission-ledger cell hashes/schema records are compared. Whole actual exported smoke and full naming TURNS tables are hash-identical to their source declarations. The original source CSV bodies are not all rehashed. Source authority and table bindings remain explicit in the receipt.

The 31 local omission JSONL ledgers have their sizes checked; their full bodies are not rehashed. Their byte bindings remain in the export manifest, and they are not part of the 239 measured payload buffers. The sum of the existing raw-DEFLATE measurements is checked, but compression is not repeated and no ZIP overhead, future outputs, final report or figures are included. Aggregate row totals count table records only and are never a pooled scientific denominator across scopes, metrics or repeats.

## Output

A new JSON receipt records exact source and code/README bindings, checks, row counts for every selected table, compact empty-cell counts, targeted retained/omitted-cell comparisons, the measured-byte reconciliation and explicit limitations. It refuses to overwrite an existing receipt. `PASS_ACTUAL_WORKING_EXPORT_RECONCILIATION` applies only to this fixed working export; `whole_study_complete` stays false. Any future expanded export needs its own source bindings and review.

This script reads about 176.75 MB of completed exported CSV/JSON files. It does not read prediction files, native events, audio, PCM, model weights or private enrollment data, and does not perform a second export. Run only in a parent-authorized read-only analysis interval; it does not start or stop native workers.

## PowerShell

Use the repository's existing EDGE interpreter; no installation or activation is needed. From any PowerShell directory:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edge = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edge -B "$sim\scripts\s6c_score_export_review_v1.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\SCORE_WORKING_EXPORT_COMPONENT_REVIEW_V1.json"
```

## Anaconda Prompt / Windows CMD

The same absolute interpreter works from Anaconda Prompt and ordinary CMD without changing their environments:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "EDGE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%EDGE%" -B "%SIM%\scripts\s6c_score_export_review_v1.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\SCORE_WORKING_EXPORT_COMPONENT_REVIEW_V1.json"
```

For an explicitly requested independent reproduction, select a new output filename (for example `SCORE_WORKING_EXPORT_COMPONENT_REVIEW_V1_RECHECK.json`); do not delete or overwrite the first receipt. The script's fixed input hashes intentionally reject changed working export sources.
