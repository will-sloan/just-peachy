# Fresh whole-study execution inventory

`s6c_inventory_refresh_v1.py` closes the stale-base gap in inventory V7. The old `snapshot_v2` is a partial historical observation, with 13 index references outside its enumeration. V7 alone cannot discover later offline sessions. This helper first executes a fresh, source-pinned legacy census, then appends every explicitly admitted fast manifest through unchanged V7. It never uses snapshot_v2 as its counting base.

This is metadata accounting, not scientific scoring or final acceptance. Do not run it during paced/long/native work or concurrent research writes. Source review and tiny fixtures are permitted now; no actual census has been run by this source preparation.

## Inputs and exact scope

Provide a SHA-bound JSON specification:

```json
{
  "schema": "s6c-inventory-refresh-spec.v1",
  "status": "REGISTERED_FINITE_REFRESH",
  "late_pool_rollup": {"path": "ABSOLUTE_REPORT/DELEGATED_NATIVE_QUEUE_COMPLETION_V1.json", "bytes": 13120, "sha256": "ddc6ed906207a1551c0b229c7fa4354e7e87109c3a2b8f9b489feba6e833f6e3"},
  "legacy_manifests": [],
  "fast_manifests": [{"path": "ABSOLUTE_MANIFEST", "bytes": 0, "sha256": "REPLACE_WITH_ACTUAL_SHA"}],
  "observer_index": {"path": "ABSOLUTE_OBSERVER_INDEX", "bytes": 0, "sha256": "REPLACE_WITH_ACTUAL_SHA"}
}
```

These placeholders are documentation, not an executable or completed authority. Use exact current bindings; populate all prepared original legacy manifests needed by V6, and **all** actual/prepared fast manifests, including unexecuted v1 preparations, the failed C065 fast_v1 attempt, and fast_v2. Empty legacy list is allowed only when no legacy manifests are discoverable; original missing-manifest guards otherwise report gaps. The observer index uses unchanged V7 schema `s6c-fast-observer-index.v1`, status `COMPLETE_METADATA_ENUMERATION`, and explicit exact post-restoration receipt bindings. A prepare-only receipt does not substitute for a run/worker exit.

The required rollup contains the six late delegated pools: endpoint advice 224, cadence floor 448, full N03 480, N08/N10 960, N12 480, cross 480. Its 3,072 requested references contain 2,512 new jobs and 560 verified reuse references. Those are closure declarations, not amounts to add to the census. Exact review/results/prediction-index buffers are read at census time, and each result receipt reference must be present in newly enumerated physical evidence. Parity bindings are carried, not reopened. Earlier recipes/full N01 and all other legacy branches are still freshly enumerated without a finite-pool restriction.

Also provide a separate SHA-bound root authorization:

```json
{
  "schema": "s6c-inventory-refresh-authority.v1",
  "status": "AUTHORIZED_POST_CLOSURE_METADATA_CENSUS",
  "spec": {"path": "ABSOLUTE_SPEC", "bytes": 0, "sha256": "REPLACE_WITH_ACTUAL_SHA"},
  "helper": {"path": "ABSOLUTE_HELPER", "bytes": 0, "sha256": "REPLACE_WITH_ACTUAL_SHA"},
  "all_model_paced_long_work_closed": true,
  "no_concurrent_research_writers": true
}
```

Only root may declare these conditions after actual closure. The helper separately refuses any active/preserved `PACED_QUIET_OWNER.json` before admission, during traversal, between stages, and at completion. It never removes leases, terminates processes, or starts models.

## Discovery adaptation and accounting

Seven pinned function discovery sites are compiled into private globals: the base payload walk, original long STARTED discovery, V3 outer-long admissions, V4 canonical manifests, its existing sentinel literal adaptation, V5 B36-long manifests, and V6 cross manifests. Only the iterator results change. Original native receipt validation, grouping, index references, failures, unknowns, and V3 finite-owner checks remain. Original module globals and files are never patched.

Admission explicitly verifies the full base/V3/V4/V5/V6 source chain and import locations, plus held V7 and all fast sources; every relevant README is included in the source receipt and final equality check. The preliminary source/check receipt is preserved under `STAGING/inventory_refresh/before_source_closure_v1/SOURCE_INDEX.json`. Source-only check V2 adds this complete dependency closure without changing discovery behavior.

Every excluded root must be derived from a manifest already admitted by held V7. Paired runs exclude exact owned report/payload namespaces. Historical controls exclude **only output_root**; their `payload_root` is a global budget root and is never an exclusion. B36-long excludes its exact report/payload namespace. C-long excludes its outer manifest namespace and separate native report/payload namespaces. Input/composition/assets, global budget roots, family roots, and unknown/unlisted fast-looking namespaces stay visible. Root resolution changes, overlapping exclusions, or duplicate manifests are rejected. Explicit exclusions and encountered filtered paths are recorded. Traversal errors fail closed; there is no suffix-wide skip and no time cache.

Fresh enumeration retains all known failed/partial/unknown attempts and index mismatches. V7 then retains exact physical identities, per-worker maximum cumulative model loads, failed native-complete/outer-failed attempts, spawn-only uncertainty, and reuse references without counting them as new sessions. Six-pool coverage gaps are preserved in the outer refresh receipt even if V7 itself has no corresponding flag. All three receipts (legacy, V7, refresh) must be consumed together; the inner base `code` identifies its original implementation while the outer receipt identifies this discovery adaptation. No receipt asserts final S6C completion.

## Run later: PowerShell

Use the pinned EDGE interpreter directly. Fill in an independently reviewed finite spec and actual post-closure authority first. Do not create either by changing placeholders to invented hashes.

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B s6c_inventory_refresh_v1.py collect --version final_refresh_v1 --spec 'ABSOLUTE_SPEC_JSON' 'EXACT_SPEC_SHA256' --authority 'ABSOLUTE_ROOT_AUTHORITY_JSON' 'EXACT_AUTHORITY_SHA256'
```

## Run later: Anaconda Prompt / CMD

No environment installation or activation is needed; the exact interpreter is invoked explicitly. The same commands work in Anaconda Prompt and Windows CMD.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_inventory_refresh_v1.py collect --version final_refresh_v1 --spec "ABSOLUTE_SPEC_JSON" "EXACT_SPEC_SHA256" --authority "ABSOLUTE_ROOT_AUTHORITY_JSON" "EXACT_AUTHORITY_SHA256"
```

## Outputs

Under `REPORT/execution_inventory/<version>`: exact admission/exclusions, preserved input metadata, `LEGACY_REFRESH_RECEIPT.json`, and `REFRESH_RECEIPT.json` or `FAILURE.json`. Fresh base tables/metadata go in sibling `<version>_legacy`; V7 physical rows/metadata in `<version>_fast`. All namespaces must be new. A failed append leaves the earlier enumeration inspectable, with no final refresh receipt. Old inventory/source/output files are untouched.

The final refresh status remains `REFRESH_COMPLETE_WITH_FLAGS` if inherited or new coverage/closure issues exist. Missing owners stay unknown. Missing sessions are never zero inferred sessions. This is a read interval, not an atomic filesystem transaction or complete process census; root closure and writer exclusion remain prerequisites. No journals, audio, vectors, embeddings, model weights, prediction payloads, or scoring tables are opened. JSON metadata bindings can transitively describe them without revalidation.

## Tiny source/metadata checks

`test_s6c_inventory_refresh_v1.py` uses synthetic directories and bound in-memory JSON only. It exercises owned-root restrictions, filtering, unknown namespaces, private function context, missing-index/reference retention, and actual tiny rollup binding. It does not call `collect`, enumerate real output banks, or inspect live cells.

```powershell
& $edgePython -B test_s6c_inventory_refresh_v1.py --output "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\refresh_source_checks_v1\SOURCE_CHECKS.json"
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_inventory_refresh_v1.py --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\refresh_source_checks_v1\SOURCE_CHECKS.json"
```
