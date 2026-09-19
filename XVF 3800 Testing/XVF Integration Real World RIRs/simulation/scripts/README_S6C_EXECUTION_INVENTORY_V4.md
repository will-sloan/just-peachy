# Paced execution inventory adapter V4

This additive metadata collector retains the reviewed V3 long-session adapter and original inventory. It adds canonical single-scene `CELL_RESULT` chains and exact historical B00/B01/B36 controls. It never treats the original generic native function's long-session wording as the actual input composition: a canonical cell has epoch4 execution, one unchanged paired capture, zero offset and zero inserted gap. B00 identifies its exact S6A baseline snapshot separately from the historical S6B worker/assets; B01/B36 identify S6B epoch2.

Inputs are explicit absolute paced manifest paths and SHA256 values, plus the existing inventory's receipt metadata. Each manifest must match the held schema, source pins, profile/route, original input declarations, fixed gallery and grid. No audio, vector, model, prediction, event log or process JSONL payload is read. Those bytes remain declared/transitively bound and must be verified separately by the execution or analysis owner. All consumed JSON buffers are preserved by the existing MetadataReader.

Counting distinguishes launched physical attempts, native sessions with complete result receipts, coordinator-completed logical cells, and repeated COMPLETE/COMPLETE_REUSED references. A launch does not prove a neural session started. Failed, closed-partial, active and unverified states remain separate. A known launch is retained even when later metadata fails admission. PID plus creation time prevents reuse confusion. Historical coordinator receipts do not record which completed cells were reused per invocation: that count is unavailable, never inferred from successful totals. Current owner inspection remains true/false/unavailable. The collector neither stops processes nor claims final scientific completion.

`FAILED_OUTER_NATIVE_COMPLETE` retains a fully bound completed native session when later outer work fails; it contributes to completed native-session evidence, not coordinator-completed cells. Worker argv must name the exact original driver, worker action, manifest, cell and timeout/lease switches; duplicate or override switches fail admission. Historical source admission additionally checks the exact epoch's sealed-index membership, original registered profile/app path, exact16+4 panel identifiers and canonical input/PCM/duration/gain declarations. These checks cannot be bypassed by recomputing a changed manifest's own digest.

Canonical metadata admission checks exact CELL_ADMISSION, child LAUNCH, CELL_RESULT, CELL_OUTCOME, native RESULT, session-finalization JSON and COMPLETE linkage. It preserves full journal hashes/frame counts without reopening PCM, and preserves the exact declared artifact list without reading trajectories. Source-metadata provenance does not substitute for actual downstream payload hashing. The public `admit_complete_cell` additionally requires all recorded owned processes currently confirmed closed.

The held paced driver is pinned to epoch4. Its candidates must already be registered there, with NONE/fixed A/fixed B galleries and real/off cues. It cannot admit epoch6 C195/C196, the later cadence labels, or common30 roster conditions unchanged. A separately reviewed runner/admission revision is required; byte-identical APP weights do not authorize silently substituting an epoch or gallery.

`collect` writes the original inventory's fresh `execution_inventory/<version>` snapshot and an additive `INVENTORY_V4_RECEIPT.json`. Its auxiliary `paced_v4` section contains per-manifest cell status counts and separate coordinator/index reference ledgers. Exact physical rows remain in `PHYSICAL_EXECUTIONS.json` and the standard CSV. New adapter source snapshots are included. Discovered paced manifests omitted from explicit admission make the snapshot incomplete. Existing collector/runner/source/receipts are never edited.

PowerShell (model-free tests):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py "$sim\scripts\test_s6c_execution_inventory_v4.py" --output "$sim\reports\S6C\20260910T123540Z\execution_inventory\ADAPTER_V4_CHECKS_V3.json"
```

Anaconda Prompt / CMD:

```bat
set "S6C_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set PYTHONDONTWRITEBYTECODE=1
"%S6C_PY%" "%S6C_SIM%\scripts\test_s6c_execution_inventory_v4.py" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\execution_inventory\ADAPTER_V4_CHECKS_V3.json"
```

Use a fresh receipt filename to reproduce checks. Temporary fixtures contain JSON only; their PCM/trajectory bindings are deliberately never materialized, demonstrating the metadata-only boundary. Checks also admit the three existing prepared manifests as metadata, without model or payload reads. A fixture PASS is not a full inventory run or empirical paced completion.

The first unexecuted collector/README/test and V1 fixture receipt are preserved under `staging/s6c/20260910T123540Z/execution_inventory/before_paced_lineage_repairs_v1/SOURCE_INDEX.json`. V2 and V3 checks are additive before first collection; V3 adds the explicit historical self-consistent-declaration negatives and current documentation. The earlier README bytes referenced by V2 are identical to that preserved V1 README. No base/V3 inventory, native driver, APP, prepared job or real result was edited.

After explicit authorization for the final closed inventory, the operator supplies **every** paced manifest and its reviewed SHA. Example commands with required inputs (replace the literal placeholders with the actual absolute paths and 64 lowercase hex hashes):

```powershell
& $py "$sim\scripts\s6c_execution_inventory_v4.py" collect --version final_closed_v4 --paced-manifest 'ABSOLUTE_CANONICAL_MANIFEST_PATH' 'CANONICAL_SHA256' --paced-manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_v1\MANIFEST.json' 'CONTROLS_SHA256' --paced-manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json' 'B36_SHA256'
```

```bat
"%S6C_PY%" "%S6C_SIM%\scripts\s6c_execution_inventory_v4.py" collect --version final_closed_v4 --paced-manifest "ABSOLUTE_CANONICAL_MANIFEST_PATH" "CANONICAL_SHA256" --paced-manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_v1\MANIFEST.json" "CONTROLS_SHA256" --paced-manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\b36_v1\MANIFEST.json" "B36_SHA256"
```

Public analysis API: create `base.MetadataReader(fresh_existing_output_directory)`; call `admit_plan(reader, manifest_binding)` for `(plan, binding, spec)`; `admit_paced_index(reader, index_binding, plan, binding)` validates exact completed index references; `admit_complete_cell(reader, job, plan, binding, spec)` returns job, exact COMPLETE/CELL/native documents and bindings, artifact list and current recorded-owner observations. The analysis collector then hashes/parses its selected native payload bytes once. These APIs do not start the inventory or import/instantiate models.
