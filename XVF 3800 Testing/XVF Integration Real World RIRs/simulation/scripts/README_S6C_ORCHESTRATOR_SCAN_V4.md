# S6C coordinator scan overlay V4: pinned epoch5

Purpose: admit the separately frozen epoch5 cadence neighborhood through the same coordinator-only exact directory-enumeration optimization reviewed in V3. V3/V2/scanner/native code remain unchanged. V4 pins epoch5 SHA256 `676ead81afe85b5557494bd851e67f34799106a45976e8f7fa6e2e5900989cbc` and the exact original epoch2/epoch4 manifests. It verifies complete APP inventories, whole native execution/common module byte equality, model assets, environment, canonical input/scene authority and state policy against both epoch2 and epoch4. Registered profiles remain an explicitly additive input, not an implicit API/default change.

The V4 source is derived from the exact SHA-pinned V3 source. Only its source/schema names, explicit epoch5 pin/default, current source bindings and added exact epoch4 reference admission differ. The run, process ownership, prior-epoch closure, worker validation, scanner override and restoration paths retain V3 semantics. The separate process still calls the unchanged frozen native run/worker functions. It only temporarily replaces the coordinator's common.tree_bytes with the existing exact-current-traversal scanner; spawned native workers import the original scanner/common modules. No shared APP, model, decoder, scheduler, tracker, input or worker function is changed.

Inputs: frozen epoch5 manifest/registry/profiles/assets, a registered exact native jobs JSON, reviewed source/scanner bytes, and prior native invocation closure metadata. `test` executes source/import and temporary-directory/process-identity fixtures only, including a fresh Python import child; it constructs no model. `prepare` creates a new immutable coordinator admission. `run` creates its own durable owner/start/closure receipts and invokes the native worker pool, so only root should launch it after prior workers close. Expected cadence preparation is448 jobs over4 candidates×56 cases×2 same-tap routes.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py "$sim\scripts\s6c_orchestrator_scan_v4.py" test --epoch epoch5 --name v4_epoch5_ready
& $py "$sim\scripts\s6c_orchestrator_scan_v4.py" prepare --epoch epoch5 --jobs "$sim\reports\S6C\20260910T123540Z\jobs\epoch5\cadence_floor_v1.json" --workers 4 --name epoch5_cadence_floor_scan_v1
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
"%PY%" "%SIM%\scripts\s6c_orchestrator_scan_v4.py" test --epoch epoch5 --name v4_epoch5_ready
"%PY%" "%SIM%\scripts\s6c_orchestrator_scan_v4.py" prepare --epoch epoch5 --jobs "%SIM%\reports\S6C\20260910T123540Z\jobs\epoch5\cadence_floor_v1.json" --workers 4 --name epoch5_cadence_floor_scan_v1
```

After independent review and root's queue admission, the later execution command is:

```powershell
& $py "$sim\scripts\s6c_orchestrator_scan_v4.py" run --admission "$sim\reports\S6C\20260910T123540Z\orchestration\epoch5_cadence_floor_scan_v1\ADMISSION.json"
```

CMD equivalent:

```bat
"%PY%" "%SIM%\scripts\s6c_orchestrator_scan_v4.py" run --admission "%SIM%\reports\S6C\20260910T123540Z\orchestration\epoch5_cadence_floor_scan_v1\ADMISSION.json"
```

No run is part of preparation. Existing admissions/outputs are never overwritten or resumed under changed source bytes. Use a fresh orchestration name after an intentional checkpoint; exact native job identities and verified completed receipts remain reusable. `prior_invocations` covers recorded epoch-native owners and remaining-child identities, not every historical research process. Paced/long/HIL reservations and heavy-analysis quiet periods require their separate coordinator controls. Directory scans are current enumerations without cross-call caches; concurrent external growth is not an atomic snapshot. Optional Windows symlink/junction parity remains unproven. Default/no-profile H2 behavior is untouched.
