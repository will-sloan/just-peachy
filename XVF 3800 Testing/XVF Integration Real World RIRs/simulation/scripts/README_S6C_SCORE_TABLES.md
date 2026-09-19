# S6C compact score-table collector

`s6c_score_tables.py` exports existing completed score CSVs for a compact handoff. It never loads a model, reads prediction payloads, computes a score, averages a metric, filters an outcome, joins experiments or decides which candidate is a finalist. It uses Python's standard CSV/JSON library to preserve original numerical text and quoting semantics. It creates data tables, not a formatted spreadsheet workbook.

Every input is an explicit immutable score receipt or score index with an exact SHA256/byte binding, its expected schema and completed status, a scope kind and descriptive scope label. A JSON pointer selects a CSV binding inside that authority. A prediction-only index cannot substitute for a score authority. Current S6C core v3 and historical S6B core receipts expose CSV bindings through `/tables/<index>`. Their completed status is `COMPLETE_REQUESTED_INDEX`, which does not by itself imply all-240 confirmation. Name-analysis receipts use `COMPLETE_REQUESTED_NAME_INDEX`; their aggregate tables may be copied without inventing a scene-level naming aggregation.

## Input specification

The specification has schema `s6c-score-table-collection-spec.v1`, a status, and an explicit `inputs` list. A discovery catalog uses `DRAFT_PARTIAL_CATALOG` and cannot run an export. The coordinator later supplies `APPROVED_EXPLICIT_EXPORT_SCOPE` for the selected complete authorities. This status records the selected scope; it is not a general accuracy or completeness certification.

Each input contains:

- `source_id`: a unique output namespace, using letters, digits, hyphens or underscores.
- `scope_kind`: exactly one of `panel56`, `full240`, `gate6`, `split`, `native`, `finalist`.
- `scope_label`: explicit experiment context. It is retained in compact rows and the manifest.
- `authority`: `{path, bytes, sha256}` for the completed score receipt/index.
- `expected_authority`: exact `{schema, status}`; status must start with `COMPLETE`.
- `tables`: explicit table names, authority `binding_pointer`, `mode`, `row_key` and `omit_fields`.

`compact_rows` requires an explicit row key including `case_id`. For current S6C core tables use `profile_id, stream, identity_tap, case_id, population`; historical S6B tables omit `identity_tap` because it is not a source column. The collector never invents the missing column, maps aliases or changes profile IDs. All other columns are retained unless they occur in the exact allowed omission list: `recipe_costs`, `strata`, `normalized_final_text`. Declare only fields present in the chosen table. Small nested JSON cells such as `lineage_counts` and `transcript_event_counts` remain exactly as supplied.

`copy_intact` copies the authoritative aggregate CSV bytes exactly, including existing nested statistics and the source's aggregation. It cannot omit fields. An optional explicit row key checks duplicates; an empty key means no uniqueness assertion is made. No aggregate is recalculated from scene rows. Every selected table remains under its own input namespace, so identical candidate/case keys in different experiments are retained. Duplicate keys inside one compact table, duplicate source namespaces, or the same authority/scope/table supplied twice are rejected.

Example shape (replace every illustrative binding with the real authority's exact values):

```json
{
  "schema": "s6c-score-table-collection-spec.v1",
  "status": "DRAFT_PARTIAL_CATALOG",
  "inputs": [{
    "source_id": "family_native_gate6",
    "scope_kind": "gate6",
    "scope_label": "Epoch4 accelerated native family gate; separate from paced diagnostic",
    "authority": {"path": "C:/exact/path/ANALYSIS_RECEIPT.json", "bytes": 123, "sha256": "replace-with-exact-64-character-hash"},
    "expected_authority": {"schema": "jp_s6c_core_analysis.v3", "status": "COMPLETE_REQUESTED_INDEX"},
    "tables": [{
      "name": "SCENE_RESULTS_COMPACT",
      "binding_pointer": "/tables/0",
      "mode": "compact_rows",
      "row_key": ["profile_id", "stream", "identity_tap", "case_id", "population"],
      "omit_fields": ["recipe_costs", "strata", "normalized_final_text"]
    }]
  }]
}
```

## PowerShell

Use the existing native Python without installing packages. `checks` runs small isolated fixtures only:

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_score_tables.py'
& $s6cPython $s6cScript checks
```

After the coordinator has selected the final completed inputs, use its separately saved approved specification and exact hash. The output path must be new:

```powershell
$s6cSpec = 'C:\replace-with-selected-scope\APPROVED_SCORE_TABLE_SPEC.json'
$s6cSpecHash = (Get-FileHash -LiteralPath $s6cSpec -Algorithm SHA256).Hash.ToLowerInvariant()
$s6cOutput = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\compact_score_tables\final_v1'
& $s6cPython $s6cScript export --spec $s6cSpec --spec-sha256 $s6cSpecHash --output $s6cOutput
```

When a hash was supplied with the approved specification, compare `$s6cSpecHash` with that supplied hash first. Calculating a current hash is not proof that an unreviewed edit was approved.

## Anaconda Prompt or Windows CMD

The explicit Python path uses the existing environment; no `conda activate` or package installation is needed:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_score_tables.py"
"%S6C_PYTHON%" "%S6C_SCRIPT%" checks
set "S6C_SPEC=C:\replace-with-selected-scope\APPROVED_SCORE_TABLE_SPEC.json"
set "S6C_SPEC_SHA=replace-with-the-exact-approved-specification-SHA256"
"%S6C_PYTHON%" "%S6C_SCRIPT%" export --spec "%S6C_SPEC%" --spec-sha256 "%S6C_SPEC_SHA%" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\compact_score_tables\final_v1"
```

## Outputs and exact preservation

Each compact scene CSV retains every non-omitted source cell character-for-character and appends seven `__collection_` provenance columns: source namespace, scope kind, scope label, authority hash, table hash, original data-row number, and row-key hash. Original header order is retained. The added row number counts logical CSV data records, not physical newline count inside quoted fields. Commas, quotes, Unicode and embedded newlines use normal CSV escaping. Numeric precision and existing booleans remain unchanged. Source empty cells remain empty; CSV itself cannot distinguish an original null from an empty string. No missing value becomes zero or false.

For each omitted cell, `<table>_OMISSIONS.jsonl` preserves the original cell's UTF-8 byte length and SHA256, parsed schema ID, top-level item/property or character count, original row number and exact row key. `<table>_OMITTED_SCHEMAS.json` maps each schema digest to its structure. These hashes cover decoded CSV cell text, not the surrounding CSV quote characters; the entire original CSV's byte hash remains in every exported row and the manifest. Retained nested JSON text is not normalized. All originals remain at their bound local paths.

Aggregate outputs are byte-identical copies, with their authority path/hash, scope and row counts recorded in `COLLECTION_MANIFEST.json`. The manifest also records input headers, transformations, omitted-schema bindings, original authority counts/status and the exact helper/README hashes. It certifies this explicit export operation only. It does not certify a new full-bank population, native execution, holdout accuracy or CM5 performance.

All JSON authorities and source CSVs are parsed from the same buffers whose hashes were verified. Small authority/specification bindings are checked again at closure. Sources above 512 MiB are rejected to keep this compact operation bounded. No raw audio, vectors, model weights or prediction/event trees are read. Partial output is preserved if an input fails; retry into a fresh namespace after resolving the cause, never overwrite a completed collection.

The fixtures cover scalar/bool/null/nested serialization, CSV/JSON quoting and newlines, omitted cell hashes/schemas, duplicate JSON/header/row/scope keys, malformed CSV, changed source bytes, exact-buffer parsing, 75/77-column mixed experiments, preserved candidate aliases, completed-status admission, draft rejection and byte-exact aggregate copying. They are synthetic guard evidence, not empirical scores. The recommended catalog remains partial until the coordinator chooses the completed score authorities for the final export.
