# Final census input assembly

`s6c_final_inventory_inputs_v1.py` binds the actual original observer metadata to the already reviewed 49-manifest final inventory assembly. It performs metadata preparation only. It does not collect the final inventory, check current owners, read native payloads, launch models, change any original file, or issue root authorization. The held final refresh integration and its README remain unchanged.

## Inputs and scope

Supply the exact `execution_inventory/final_integration_v1/ASSEMBLY_DRAFT_V3.json` binding: SHA256 `96ea87b7031cf8860b1aa34b4a18226219fefe775a9f089b50a3daf77a94fc27`. Its 49 manifests remain 37 fast, nine explicit legacy, and three original C-long references retained in automatic V3 discovery. The five required continuous targets are C065/C067/C088/C091 O0 fast V2 and exact historical B36 O0 fast V1. Prepared and failed versions remain listed.

Discovery reads only `REPORT/observer_fast_v1/attempts/*.json`, `REPORT/observer_fast_v2/attempts/*.json`, and `observer_invocations/*/SCANNER_OUTCOME.json` under the declared historical paced/B36-long report namespaces. It never recursively traverses payload, audio, assets or native session directories. Every matching original observer is retained, including preparation, failures and any unmatched manifest; no outcome filter is applied. Unknown observer schemas or nonfinite owners fail admission. Bindings are computed from the same JSON buffers that are parsed and saved by the original MetadataReader; the original path set and every file binding are checked again before preparation completes.

The base V7 index validator is used only for original schema and owner-shape admission. The controls recovery facade's 80-cell/current-owner admission is deferred to the authorized census. Observer receipt count is neither a physical-attempt count nor a native-session count. `unmatched_manifest` includes preparation receipts whose original fields do not identify one of the finite fast manifests; those receipts stay visible.

`REGISTERED_SPEC.json` is produced by the unchanged `s6c_final_inventory_refresh_v1.py resolve-spec` function. It verifies the whole current immediate manifest set against the frozen assembly and retains the exact controls-recovery and six-late-pool bindings. This is a finite input, not evidence that a final inventory or study acceptance occurred.

## Outputs

Use a fresh immediate child of `REPORT/execution_inventory`. Outputs are immutable `OBSERVER_INDEX.json`, `OBSERVER_METADATA_ROWS.json`, `REGISTERED_SPEC.json`, `ROOT_AUTHORITY_DRAFT.json`, `PREPARATION_RECEIPT.json`, and exact original metadata snapshots. All JSON outputs have exact path/bytes/SHA bindings. Existing namespaces are never overwritten.

The authority template has `DRAFT_NOT_AUTHORIZED`, false closure/writer declarations and null closure/diagnostic evidence. Its continuous manifest list identifies required targets only. Root must issue a **new** authorized document after original current closure and long diagnostics have been independently admitted. The original refresh's `helper` field binds `s6c_inventory_refresh_v1.py`; `integration_helper` separately binds the new private integration. Do not rename the helper authority or edit the template into a historical success.

The later census is invoked only after root GO. It performs fresh legacy enumeration, checks the six later native pools, and appends all admitted fast branches through controls recovery → B36 V2 → original V7. Failed C065 V1, unknown orphaned coordinator exits, original controls scanner FAILED/exit1, exact external recovery with zero new native sessions, and the distinct B36 V2 archival chain remain explicit. The old partial snapshot is never its counting base.

## PowerShell

Invoke the existing EDGE Python directly. This command prepares metadata; no Conda environment change is needed. Choose a new output name if reproducing after the supplied namespace exists.

```powershell
$simRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$edgePython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
Set-Location "$simRoot\scripts"
& $edgePython -B s6c_final_inventory_inputs_v1.py --assembly "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_integration_v1\ASSEMBLY_DRAFT_V3.json" '96ea87b7031cf8860b1aa34b4a18226219fefe775a9f089b50a3daf77a94fc27' --output "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_inputs_v1"
# Future root-only census after exact final authority and independent input review:
& $edgePython -B s6c_final_inventory_refresh_v1.py collect --version final_whole_study_v1 --assembly "$simRoot\reports\S6C\20260910T123540Z\execution_inventory\final_integration_v1\ASSEMBLY_DRAFT_V3.json" '96ea87b7031cf8860b1aa34b4a18226219fefe775a9f089b50a3daf77a94fc27' --spec 'ABSOLUTE_REGISTERED_SPEC_JSON' 'EXACT_SPEC_SHA256' --authority 'ABSOLUTE_AUTHORIZED_ROOT_JSON' 'EXACT_AUTHORITY_SHA256'
```

## Anaconda Prompt / CMD

Both shells can run the exact existing interpreter without activation or installation. The second command is documentation only until root authorizes it.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_inventory_inputs_v1.py --assembly "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_integration_v1\ASSEMBLY_DRAFT_V3.json" "96ea87b7031cf8860b1aa34b4a18226219fefe775a9f089b50a3daf77a94fc27" --output "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_inputs_v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_final_inventory_refresh_v1.py collect --version final_whole_study_v1 --assembly "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\reports\S6C\20260910T123540Z\execution_inventory\final_integration_v1\ASSEMBLY_DRAFT_V3.json" "96ea87b7031cf8860b1aa34b4a18226219fefe775a9f089b50a3daf77a94fc27" --spec "ABSOLUTE_REGISTERED_SPEC_JSON" "EXACT_SPEC_SHA256" --authority "ABSOLUTE_AUTHORIZED_ROOT_JSON" "EXACT_AUTHORITY_SHA256"
```

Preparation verification uses actual small original observer buffers and the existing source/index/assembly guards. No previous fixture suite, scientific conversion, score calculation, native result or original raw log is rerun. Independent review should compare exact discovery membership/bindings, retained failures and final spec equality before the census is authorized.
