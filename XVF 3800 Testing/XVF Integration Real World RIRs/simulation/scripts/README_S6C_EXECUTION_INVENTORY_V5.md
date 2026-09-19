# Additive sentinel and historical B36 continuous inventory

`s6c_execution_inventory_v5.py` extends the reviewed metadata-only V4 collector with two explicit schemas. It leaves V4, V3, base inventory, all native APP/worker sources and previous snapshots unchanged. `test_s6c_execution_inventory_v5.py` contains bounded synthetic metadata/source-admission checks; neither helper runs a model, plays audio, rescans native events, reads PCM/embeddings or performs policy replay.

The first branch admits only the reviewed exploratory sentinel: C088/C105, S45_08_07, O0/O1, three retained repetitions, fixed A15 roster, exact epoch4. Its12-cell schema is `s6c-paced-arrival-sentinel.v1`. It retains single-scene source semantics. The second branch admits only the reviewed exact B36 continuous wrapper schema, `s6c-exact-historical-b36-continuous.v1`: one unchanged S6B epoch2 worker/profile/APP consuming one existing S6C epoch2 composition tap for1,827.426625 seconds. No canonical case ID is invented for the continuous source.

V4's public canonical admission API remains available unchanged to the root's paced collector. V5 dispatches the same API names (`admit_plan`, `admit_complete_cell`, `admit_paced_index`) for ordinary and sentinel cells. Continuous historical metadata uses the separate `admit_long` / `admit_long_native` / `long_invocations` functions because its original native result/observer/source shapes differ. These functions admit declared JSON chains; downstream consumers must hash the exact event/trajectory/journal buffers before using their contents. They do not certify payload bytes merely from a stored binding.

## Exact admission and counting

All supplied manifest SHAs and consumed JSON buffers are verified/preserved by the original MetadataReader. The caller supplies every manifest explicitly with repeated `--paced-manifest PATH SHA256`; discovered but unadmitted namespaces remain coverage issues. There is no automatic trusted admission from a new self-consistent job digest.

The sentinel adapter compiles isolated copies of11 reviewed V4 metadata functions with a fixed five-entry **literal-only** schema/path substitution table. Its pure selector/source/native guards come from the pinned sentinel source. This changes no held module global, app policy, neural code or field interpretation. The private namespace uses the new exact schema/panel/source; ordinary/historical V4 functions remain byte-identical. Tests exercise the adapted complete-cell chain and invalid lineage, in addition to source AST admission.

The continuous branch compiles only six pure authority/job/result guards from its pinned wrapper; it never imports the worker or its model modules. It admits sealed S6B epoch2/profile plus fixed composition metadata, original child command, native launch/admission/outcome/result, exact declared artifact list, and coordinator admission/outcome/lease-release chain. Original model asset declarations are checked as nested bindings, without reopening model payloads. Actual native execution epoch and source-composition epoch are exported separately.

One finite PID/creation launch is one physical attempt. Repeated complete/index references are not new inference. A successful `CHILD_SPAWN` without a finite recorded creation identity is still an unverified physical attempt, with null ownership/closure and no proven model session. A worker result may prove native completion while outer observation/lease closure remains failed or incomplete; these statuses are kept separate. Missing/invalid lineage is never counted as a successful completed session. Continuous periodic/terminal/total row counts retain the source's explicit denominators; no JSONL is opened to reinterpret observations here. A still-exiting coordinator remains subject to the base collector's current PID/creation observation.

A stored successful continuous RESULT cannot override a failed native outcome or a changed-worker flag. A closure named `NATIVE_COMPLETE_QUIET_RELEASED` must include an actual successful lease-release record; contradictory success labels are rejected and remain unverified lineage in the collector. Earlier source/check versions are preserved and resolved by the later fixture receipt.

The successful native admission's quiet lease must equal its coordinator admission's lease. The successful result and coordinator outcome must contain the same unique PID/creation identity set, including the native child, with closed states checked separately. Incidental process-observation error strings are not required to match across those two observations.

The collector temporarily installs only the report-only base auxiliary callback, restores it in `finally`, and verifies its own held source bytes afterward. Original enrollment, prefix, epoch-native and V3 long accounting remain active. No existing snapshot is overwritten. The inherited execution/inference/load/cost scopes and missing-owner limitations remain those documented in READMEs for base/V3/V4; this adapter does not turn a scoped snapshot into final study completion.

## PowerShell

Use the exact EDGE interpreter. First run only the bounded fixtures, using a fresh receipt path. Actual collection is deferred until root requests a closed-worker snapshot and supplies all exact manifest bindings. The continuous manifest path/SHA below must come from a later real `prepare`; do not invent a binding or imply preparation has happened.

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$report = "$sim\reports\S6C\20260910T123540Z"
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py -B "$sim\scripts\test_s6c_execution_inventory_v5.py" --output "$report\execution_inventory\ADAPTER_V5_CHECKS_V1.json"
& $py -B "$sim\scripts\s6c_execution_inventory_v5.py" collect --version final_closed_v5 --paced-manifest '<canonical-manifest-path>' '<exact-sha256>' --paced-manifest '<historical80-manifest-path>' '<exact-sha256>' --paced-manifest '<historical-B36-40-manifest-path>' '<exact-sha256>' --paced-manifest "$report\paced_arrival_sentinel\arrival_boundary_v1\MANIFEST.json" '92c5d2a8fa716400d253d0b18a8ff65d901698ef29762c2b07ae19687d5dc00d' --paced-manifest '<prepared-long-B36-manifest-path>' '<exact-sha256>'
```

The inherited collector creates the fresh snapshot directory under `REPORT/execution_inventory/<version>` and writes `INVENTORY_V5_RECEIPT.json` beside the original snapshot. The new fields are `sentinel_v5` and `continuous_b36_v5`; `paced_v4` remains the ordinary canonical/historical scope. Their physical rows join the existing deduplicated physical-attempt table. Their references do not increase native counts.

## Anaconda Prompt / CMD

No new environment or package install is needed. Use the full executable path even from Anaconda Prompt.

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "REPORT=%SIM%\reports\S6C\20260910T123540Z"
set "PYTHONDONTWRITEBYTECODE=1"
"%PY%" -B "%SIM%\scripts\test_s6c_execution_inventory_v5.py" --output "%REPORT%\execution_inventory\ADAPTER_V5_CHECKS_V1.json"
"%PY%" -B "%SIM%\scripts\s6c_execution_inventory_v5.py" collect --version final_closed_v5 --paced-manifest "<canonical-manifest-path>" "<exact-sha256>" --paced-manifest "<historical80-manifest-path>" "<exact-sha256>" --paced-manifest "<historical-B36-40-manifest-path>" "<exact-sha256>" --paced-manifest "%REPORT%\paced_arrival_sentinel\arrival_boundary_v1\MANIFEST.json" "92c5d2a8fa716400d253d0b18a8ff65d901698ef29762c2b07ae19687d5dc00d" --paced-manifest "<prepared-long-B36-manifest-path>" "<exact-sha256>"
```

This README supplies reproduction commands, not a quiet-period authorization or a claim that either new native plan completed.
