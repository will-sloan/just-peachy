# S6C inventory V7: explicit prior inventory plus fast-observer attempts

`s6c_execution_inventory_v7.py` provides metadata admission and physical-attempt accounting for the held exact-stat observer versions. It preserves V3–V6, the original collectors, native workers, APP, profiles and score code. `test_s6c_execution_inventory_v7.py` supplies small synthetic closure/observer/merge checks and optional admission of the explicit prepared manifests. Neither import nor tests start a native worker, read audio/vectors/events, measure storage trees, or run a full inventory.

## Inputs and boundaries

The module pins the final canonical, sentinel, cross, historical B00/B01, B36 paced, B36 continuous, C epoch4 continuous observer sources and READMEs, plus the shared fresh-stat utility. The previous V6 chain verifies its original dependencies. Metadata admission compiles only the existing pure guards in isolated namespaces; it never installs a scanner or modifies an imported old function.

Canonical/sentinel/cross retain their original schema families, distinct exact grids and actual registered routes. Historical fast manifests use their explicit `-fast.v1` schemas and must be the exact observer-only projection of the admitted original prepared manifest: unchanged native jobs, original S6B driver/profile/assets, namespace/observer declarations and the authorized outer RAM floor. Historical B00 remains its original S6A default branch. C-long retains source composition epoch2 separately from actual execution epoch4. Historical B36-long retains source composition S6C epoch2 separately from execution S6B epoch2. A per-case canonical cell is never labeled a continuous composition.

The fresh-stat policy retains the declared limits, mandatory scans and a periodic interval measured 20 seconds after scan completion; historical outer RAM is explicitly 12 GiB. V7 does not reinterpret measured scan maxima as continuous resource maxima.

### Explicit fast_v1 and fast_v2 contexts

Both generations remain admitted under their original schema families. `kind_of(plan)` returns `canonical`, `sentinel`, `cross`, `long_c`, `controls`, `b36`, or `long_b36`; it never appends a version suffix. `fast_version(plan)` identifies the paired/C-long `_fast_v2` namespaces separately. Historical observer versions stay at fast_v1. The public analysis APIs dispatch using the admitted plan. Call `admit_plan` before consuming a plan through a closed-cell or diagnostic API.

V2 compiles the exact preserved V7 fast_v1 metadata functions from `STAGING/inventory_v7/fast_v1_context_v4/s6c_execution_inventory_v7.py` (SHA256 `55e8cff6f3803196e11e7387e3a458c8630cd8c198f5884e9d53bc7e7b209827`) into a private namespace. The finite literal substitutions change only the four explicit wrapper/README names, `_fast_v2` namespace admission and `observer_fast_v2/attempts` receipt directory. Old modules and old function globals remain unchanged. The original snapshot, test, README and source index remain available beside that snapshot.

Every V2 plan must also contain the exact `s6c-protected-native-guard.v2` policy generated from the pinned L2 structural-code functions and original protected-source bytes. A missing or changed structural hash, algorithm-source binding or wrapper source fails admission. This metadata calculation compiles original code without executing the native module. It neither installs a scanner nor loads model assets. The required observer restoration, exact worker argv, native/finalization and current-owner/quiet-lease chain remain enforced in each context. The explicit observer index can contain both generations; only exact matching action/manifest/owner receipts satisfy an admission.

`test_s6c_execution_inventory_v7_v2.py` tests these contexts with tiny complete-cell fixtures, wrong version/argv/observer-directory/source/policy cases and two already prepared V2 manifest declarations. It reuses the SHA-bound prior 78-check receipt, including the independently accounted failed V1 attempt, rather than reopening that attempt or rerunning the prior checks. It reads no current runtime outputs. The immediate prepared-manifest census covers both `_fast_v1` and `_fast_v2`; prepared plans still add no native executions.

## Analysis-compatible public API

Use `base.MetadataReader(output_directory)`; `base`, `v3`, `process_state`, `CANONICAL`, and `HISTORICAL` are exported. All bindings are exact `{path, bytes, sha256}` JSON bindings. Output directories must already exist for a Reader.

* `admit_plan(reader, manifest_binding)` returns the original compatible `(plan, binding, spec)` for paced plans; historical long retains its original extra authority/guard return values through `admit_long` below.
* `admit_paced_index(reader, index_binding, plan, binding)` admits the complete exact index grid. Index rows, including `COMPLETE_REUSED`, are references, never extra native attempts.
* `admit_complete_cell(reader, job, plan, binding, spec, state=None, *, observer_receipts=None)` preserves `job`, `complete`, `complete_binding`, `cell`, `cell_binding`, `native`, `native_binding`, `artifacts`, and owner observations, adding the worker observer exit, coordinator invocation and archived-lease proof. Analysis must separately read its already-declared event/summary/process artifacts against those bindings.
* `invocation_rows(reader, plan, binding, *, observer_receipts=None)` returns `(records, owners)` including missing outcome/closure or restoration as explicit unknown-owner evidence. `collect_job(reader, job, plan, binding, spec, *, observer_receipts=None)` preserves native-complete versus observer-complete distinction; it returns no row only without any launch/spawn/native terminal evidence.
* `validate_outer(reader, admission_path, *, observer_receipts=None)` preserves the C-long V3 fields, adding strict current-owner, full invocation and observer closure. It does not invoke scene/name scoring.
* `admit_long(reader, binding)` returns `(plan, binding, authorities, guards)`; `admit_long_native(reader, plan, binding, authorities, guards, *, observer_receipts=None)` and `long_invocations(reader, plan, binding, *, observer_receipts=None)` preserve the B36-long V5 return structures. The latter returns `(records, owners, spawns)`.

Fast completed-cell admission requires explicit observer context. Pass `observer_receipts=[binding, ...]`, or call `attach_observer_receipts(reader, bindings)` once. There is no implicit optional-keyword bypass. A source-bound index can instead be attached with `admit_observer_index(reader, index_binding)`. Its exact JSON form is:

```json
{
  "schema": "s6c-fast-observer-index.v1",
  "status": "COMPLETE_METADATA_ENUMERATION",
  "receipts": [{"path": "ABSOLUTE_RECEIPT.json", "bytes": 123, "sha256": "EXACT_SHA256"}]
}
```

The index is an explicit metadata enumeration, not a completion assertion. Include the relevant run and worker exits; preparation exits may be included but cannot satisfy a run or worker. Common-observer exits require exact owner PID/creation, wrapper/manifest/action/job argv, frozen common binding, policy, scan-counter roots and restoration/protected-admission assertions. Historical isolated adapters require their separate source-before/after and owner/wrapper outcome; no nonexistent common restoration is invented. A separate native and quiet-lease closure remains mandatory. The diagnostic APIs reject missing exits and any observed incomplete invocation, even if an earlier cell completed.

## Whole-study merge and outputs

`collect` requires an explicitly SHA-bound prior whole-study `EXECUTION_INVENTORY.json`, a bound observer index and every intended current fast manifest. It preserves every prior physical row, failed/unknown status, auxiliary enrollment/prefix lineage, index-reference accounting and existing coverage/closure flags. It appends exact current physical attempts once. Same-key jobs do not imply the same physical attempt; the actual launch/STARTED owner/path identifies one. Exact duplicate rows add zero attempts; contradictory duplicates and duplicated native session paths fail instead of silently pooling. Per-worker model loads use the inherited maximum cumulative count for each PID/creation pair, not a sum over its jobs. Prior owner observations remain explicitly preserved; finite identities get fresh current checks, while missing lineage identities stay unknown. Earlier live observations are not relabeled as current live processes.

Cross `SPAWNED_PROCESS` without finite `LAUNCH` is an unverified physical spawn, never a proven model session. Normal spawn+launch is one attempt. Failed outer closure with a validated native result keeps native completion separate. C-long requires an actual native `STARTED.json`; an outer quiet admission alone creates no native physical row. Historical schemas without fresh/reuse row counters retain that missingness.

An outer protection failure can occur after the native result was returned. V7 independently validates the exact failed outcome, launch owner/command, native source/profile/journals and finalization metadata for accounting. `FAILED_OUTER_NATIVE_COMPLETE_PROTECTION_UNVERIFIED` preserves `protected_functions_restored=false`, the original error, one physical attempt and one observed native completion. It is **not** an accepted completed cell, source-protection parity, reusable prediction or successful paced observation. Closed-cell analysis admission continues to reject it. This addition is metadata accounting only; it does not diagnose or fix the native/observer failure.

Outputs in a new `REPORT/execution_inventory/VERSION` are `PHYSICAL_EXECUTIONS.json`, `METADATA_SOURCES.json`, exact consumed metadata snapshots and `EXECUTION_INVENTORY.json`. The immediate prepared-fast manifest census adds explicit omitted-manifest flags; it does not infer those plans ran. The report is working whole-study accounting with explicit prior authority, never final S6C acceptance. The original 64 MiB per-metadata-document bound is preserved; larger authority files fail explicitly. All source declarations are metadata only; no declared PCM/model/event bytes are read by this collector.

## PowerShell

Run from the simulation scripts directory. Checks are authorized source work; **the actual collect command below requires a separately approved closed-run scope**, no active/preserved `PACED_QUIET_OWNER.json`, exact prior/index bindings and all current manifests. Replace example placeholders with reviewed real paths/hashes; do not use the example literal hashes.

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$edgePy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edgePy -B test_s6c_execution_inventory_v7.py --output '..\reports\S6C\20260910T123540Z\execution_inventory\v7_checks_NEW' --actual-prepared-metadata
& $edgePy -B test_s6c_execution_inventory_v7_v2.py --output '..\reports\S6C\20260910T123540Z\execution_inventory\v7_v2_checks_NEW'
& $edgePy -B s6c_execution_inventory_v7.py collect --version final_append_NEW --prior-inventory 'ABSOLUTE_PRIOR_EXECUTION_INVENTORY.json' EXACT_PRIOR_SHA --observer-index 'ABSOLUTE_OBSERVER_INDEX.json' EXACT_INDEX_SHA --manifest 'ABSOLUTE_FAST_MANIFEST.json' EXACT_MANIFEST_SHA
```

Repeat `--manifest PATH SHA` once for every intended fast plan; keep authorities/scopes distinct. The collector refuses an existing version and duplicate manifest arguments. To run only synthetic/source checks, omit `--actual-prepared-metadata` from the test command.

## Anaconda Prompt / CMD

No environment installation or activation is needed: use the exact admitted EDGE executable. Commands also work in an Anaconda Prompt.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_execution_inventory_v7.py --output "..\reports\S6C\20260910T123540Z\execution_inventory\v7_checks_NEW" --actual-prepared-metadata
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_execution_inventory_v7_v2.py --output "..\reports\S6C\20260910T123540Z\execution_inventory\v7_v2_checks_NEW"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_execution_inventory_v7.py collect --version final_append_NEW --prior-inventory "ABSOLUTE_PRIOR_EXECUTION_INVENTORY.json" EXACT_PRIOR_SHA --observer-index "ABSOLUTE_OBSERVER_INDEX.json" EXACT_INDEX_SHA --manifest "ABSOLUTE_FAST_MANIFEST.json" EXACT_MANIFEST_SHA
```

Source-check output is `SOURCE_CHECKS.json`, with exact helper/test/README pins, test names, optionally admitted prepared manifests and their preserved metadata sources. Synthetic process states are explicitly mocked; actual prepared admission is not an execution or current-process audit. No collection, native session or resource scan is claimed by those checks.

For the separately authorized failed first C065 cell metadata check, append `--actual-failed-cell` to either test command above. This option is fixed to the exact bound `c065_main_fast_v1` manifest and `C065_S45_01_16_O0_O0_r1`, plus root's SHA-pinned `runtime_failure_review/FIRST_C065_FAILURE_CLOSURE_V2.json`. It verifies the existing failed-outcome/native-result/finalization declarations, observes that native PID/creation as closed, and requires zero accepted cells. It carries root's broader three-identity closure census without repeating it. This reads no native event, process trajectory, audio or model bytes and does not launch a session. Actual failed-cell metadata is reported separately from synthetic fixtures and prepared-grid admission.
