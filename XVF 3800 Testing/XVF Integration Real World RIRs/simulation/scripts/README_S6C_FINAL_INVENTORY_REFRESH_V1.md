# Final inventory integration, prepared before continuous closure

`s6c_final_inventory_refresh_v1.py` composes three already reviewed metadata implementations. It creates a controls-recovery inventory with the exact external archival result `c9a3a0394f19920bb886156d8f7d8ede2773ad509f6338c61c8882e51f0007a4`, layers the B36 V2 inventory over it, and supplies that combined interface to private copies of the original refresh functions. Their Python code objects are identical. Original module globals, scientific/native workers, collectors and files are unchanged.

This preparation is not a final census. All five continuous sessions must close and root must authorize the census before `collect`. The census refuses the shared quiet lease. It never removes a lease, kills a process, launches a model, or reads audio, native events, vectors or prediction payloads. Metadata may refer to those payloads without opening them.

## Purpose, inputs and outputs

The old `snapshot_v2` predates later completed native pools. The integration uses the held refresh's fresh legacy enumeration, its seven narrowly filtered discovery sites, all six late-pool reference checks, then its V7 append. It never supplies the stale snapshot as the final counting base. Existing warnings, unknown owners, failures, index mismatches, partial attempts and native-source reuse remain visible. A reused reference does not create a physical session.

Inputs are exact SHA-bound JSON buffers:

* A finite draft assembly lists every immediate manifest under the six declared paired/long/historical families, both successful and unexecuted versions. The original failed C065 fast V1 attempt remains included. Each binding has `path`, `bytes` and `sha256`.
* The exact completed six-pool rollup remains `DELEGATED_NATIVE_QUEUE_COMPLETION_V1.json`, SHA `ddc6ed906207a1551c0b229c7fa4354e7e87109c3a2b8f9b489feba6e833f6e3`. Its 3,072 requested references include 2,512 new and 560 reused jobs. These counts are carried for coverage, never added to physical totals.
* A future explicit completed observer index uses the held V7 schema `s6c-fast-observer-index.v1` and `COMPLETE_METADATA_ENUMERATION`. It must include the actual worker/parent receipts needed by every fast branch, including the original failed controls observer and failed C065 V1 history. The special controls recovery chain admits its failed observer only with the exact external closure evidence. A preparation receipt cannot replace an execution receipt.
* A separate root authority is written only after all relevant model/paced/continuous processes have closed and other research writers are stopped. Neither the helper nor a test creates this authority.

`assemble` reads only immediate manifest JSON and source bindings, writing one immutable `DRAFT_PENDING_CONTINUOUS_CLOSURE` JSON. It does not admit native cells or infer their current status. `observer_index` and `root_authority` remain null. The five required long bindings are C065/C067/C088/C091 O0 fast V2 and exact historical B36 O0 fast V1. Each planned source is 1,827.426625 seconds, 9,137.133125 seconds total; these are source durations, not an elapsed-time or execution claim.

`resolve-spec`, used later after quiet closes, verifies the unchanged assembly against the current immediate manifest set and binds a real observer-index buffer. It writes `REGISTERED_FINITE_REFRESH`, the existing refresh specification schema. It checks the index declaration; full observer/cell/current-owner admission occurs in the held collect code. Newly created or changed manifests require a fresh reviewed assembly rather than silent omission.

`collect` adds a small integration admission/result or failure under `REPORT/execution_inventory/<version>_integration`. The untouched refresh orchestration writes `<version>`, `<version>_legacy`, and `<version>_fast` as documented in [the original refresh README](README_S6C_INVENTORY_REFRESH_V1.md). All namespaces must be new. Original refresh, legacy and appended receipts must be read together; `REFRESH_RETURNED_INSPECT_BOUND_FLAGS` does not mean that their flags vanished or that final scientific acceptance occurred.

## Explicit scope and closure distinctions

Paired C report/payload namespaces and long namespaces are excluded from legacy discovery only after held manifest admission, then handled by the explicit fast append. Historical `payload_root` is a global budget root: only historical `output_root` may be excluded. Unknown/unlisted namespaces remain visible. Input, asset and composition roots are never exclusions.

The three original epoch4 C-long manifests are recorded separately as `automatic_legacy_long_manifests`. They are left to unchanged V3 discovery of original ADMISSION chains, rather than incorrectly passed to V6's paired/B36 manifest admission. A prepared original long namespace without an ADMISSION is not a native execution.

Controls: all 80 original native cells may be complete while the original coordinator exit remains 1 and its scanner status remains FAILED. The exact original lease was externally archived on C under root authority. The original G-side closure remains absent. The reviewed recovery facade retains these facts in each relevant invocation/row. B36 V2 instead has its own original coordinator C-side `LEASE_RELEASE.json`; it is not the controls recovery. The exact held B36 facade validates that branch while leaving other branches delegated.

The census is a bounded read interval, not a filesystem transaction or a universal process census. Root's separate closure/writer declarations and the original repeated quiet checks remain prerequisites. Physical attempt counts, complete unique native sessions and reference reuse keep their original definitions. No failed/prepared namespace is turned into a successful cell by this integration.

The initial source preparation used POSIX path spelling in new binding helpers. Before use, it was preserved under `STAGING/final_inventory_integration/before_native_binding_fix_v1` with its receipt and draft assembly, then corrected to the original collector's native `str(Path.resolve())` spelling. A private original-MetadataReader roundtrip verifies dictionary equality; bytes, hash and path must all match. The corrected assembly is `ASSEMBLY_DRAFT_V2.json`; V1 remains historical preparation only.

## Root authority additions

Keep the original `schema`, `status`, `spec`, `helper`, `all_model_paced_long_work_closed` and `no_concurrent_research_writers` fields required by the original refresh. **`helper` must bind the held original `s6c_inventory_refresh_v1.py`**, because that original check executes unchanged in its private context. This is not a declaration that it executes without adaptation: the same authority must additionally contain:

* `integration_helper`: the actual binding of this new helper.
* `integration_readme`: the actual binding of this README.
* `integration_sources`: exact assembly `sources`.
* `recovery`: exact assembly recovery binding.
* `completed_continuous_manifests`: exact assembly `required_continuous_manifests`, in order, declared by root only after their actual closure.

The root authority is not generated here. Required-continuous closure in this field is an explicit root declaration; native and owner evidence remains independently classified by the held inventory admission, with any disagreement retained as flags. No completion proof is synthesized. Changing `helper` to the integration filename breaks the original admission and is rejected. Do not edit an old authority or fabricate a completed observer index.

## PowerShell commands

Use the existing EDGE interpreter; no environment changes are required. `assemble` is authorized metadata preparation. The next two commands are future commands and must wait for root's post-closure window and exact reviewed inputs.

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B s6c_final_inventory_refresh_v1.py assemble --output "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_integration_v1\ASSEMBLY_DRAFT_V1.json"
& $edgePython -B s6c_final_inventory_refresh_v1.py resolve-spec --assembly 'ABSOLUTE_ASSEMBLY_JSON' 'EXACT_ASSEMBLY_SHA256' --observer-index 'ABSOLUTE_CLOSED_OBSERVER_INDEX_JSON' 'EXACT_OBSERVER_SHA256' --output 'ABSOLUTE_NEW_REGISTERED_SPEC_JSON'
& $edgePython -B s6c_final_inventory_refresh_v1.py collect --version final_whole_study_v1 --assembly 'ABSOLUTE_ASSEMBLY_JSON' 'EXACT_ASSEMBLY_SHA256' --spec 'ABSOLUTE_REGISTERED_SPEC_JSON' 'EXACT_SPEC_SHA256' --authority 'ABSOLUTE_ROOT_AUTHORITY_JSON' 'EXACT_AUTHORITY_SHA256'
```

Replace placeholders only with real reviewed buffers and hashes. `write_new` refuses overwrite. For an updated assembly choose a fresh filename and retain the prior one.

## Anaconda Prompt / Windows CMD

The same commands work in Anaconda Prompt and CMD by invoking the exact existing interpreter. No `conda activate` is needed.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_inventory_refresh_v1.py assemble --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_integration_v1\ASSEMBLY_DRAFT_V1.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_inventory_refresh_v1.py resolve-spec --assembly "ABSOLUTE_ASSEMBLY_JSON" "EXACT_ASSEMBLY_SHA256" --observer-index "ABSOLUTE_CLOSED_OBSERVER_INDEX_JSON" "EXACT_OBSERVER_SHA256" --output "ABSOLUTE_NEW_REGISTERED_SPEC_JSON"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_inventory_refresh_v1.py collect --version final_whole_study_v1 --assembly "ABSOLUTE_ASSEMBLY_JSON" "EXACT_ASSEMBLY_SHA256" --spec "ABSOLUTE_REGISTERED_SPEC_JSON" "EXACT_SPEC_SHA256" --authority "ABSOLUTE_ROOT_AUTHORITY_JSON" "EXACT_AUTHORITY_SHA256"
```

## Focused source checks

`test_s6c_final_inventory_refresh_v1.py` checks private code identity/layering, original-global preservation, tiny owned-root and discovery guards, and synthetic authority/spec negatives. It reads held source files and its local metadata fixtures; it does not collect an inventory, re-run prior broad fixture suites, admit actual cells, open an observer index, or inspect current owner state.

```powershell
& $edgePython -B test_s6c_final_inventory_refresh_v1.py --output "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_integration_checks_v1\SOURCE_CHECKS.json"
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_final_inventory_refresh_v1.py --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_integration_checks_v1\SOURCE_CHECKS.json"
```
