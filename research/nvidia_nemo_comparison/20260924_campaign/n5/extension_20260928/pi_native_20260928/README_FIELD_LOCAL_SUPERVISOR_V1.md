# Local supervisor V1: prepared native gate integration

Purpose: connect the finite local journal to the existing broker gate. These sources are PREPARED and native UNEXECUTED. They do not admit a production lifetime, activate an app, authorize new capture, recover a failed recording, or qualify offline operation.

Selected changes:
- field_local_release_files_v4.py corrects the service role: MainPID must equal the broker OWNER PID. The external gate has a separate PID. Journal3's old MainPID gate comparison was wrong. The original Journal3 and its host fixture result remain immutable.
- field_local_supervisor_v1.py supplies reserve, gate registration, finish and read-only reopen phases. Every mutating phase publishes its actual current launch OWNER. EXIT records intent while that owner lives; the next launch requires actual prior owner death.
- field_operator_broker_gate_v9.py pins the separate manager capsule before importing its supervisor, checks loaded module origins, and calls recording_started before the existing ACK. Actual broker constructors remain behind ACK. Gate close publishes only EXIT intent. A separate finish process is required after actual gate death for CLOSED and complete local BACKUP.
- check_field_local_start_binding_v1.py checks the changed pure identity-role validation. Historical v6 ENVELOPE/OWNER/GATE_OWNER bytes supply PID roles; ActiveState is explicitly a synthetic fixture because ENVELOPE did not retain that property. This is not a current service/process observation or native journal qualification.

Inputs: a separately reviewed exact local release policy and manifest, one-slot broker policy, actual source root and owner files, fresh LOCAL_RELEASE_QUALIFICATION operation, finite recording/launch slots, complete independent local mirror allocation, and exact code pins. Binding fields are schema (just-peachy.local-gate-binding.v1), root, release_sha256, manifest_sha256, recording_slot, launch_slot and operation. Operation has issued_utc, expires_utc and purpose. Slot names are recording-01..04 and launch-01..16 within the actual allocation.

Outputs: immutable RESERVED/STARTED/CLOSED/BACKUP and current OWNER/EXIT journal records, complete independent local backup, bounded OWNER/RESULT or FAILURE stdout records. The adapter adds no recording payload writer and no metadata slot. Failed metadata, consumed slots and uncertified copies remain fenced and preserved. No retry, deletion or failure clearing is implemented.

## Host changed-check commands

Use the campaign Python with psutil installed. The checker sets CPU14 and registers itself before reading project evidence. Output must be a fresh unique directory in an admitted host preparation; an existing output is consumed. Historical source is the already verified host mirror. Do not rerun an unchanged passing check merely for a new version.

PowerShell:
```powershell
$native = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$evidence = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$native\check_field_local_start_binding_v1.py" --source "$evidence\field-operator-sessions-v6-admission\host-backup-mirror" --output "$evidence\operator-local-supervisor-v1-preparation\start-binding-v1"
```

Command Prompt:
```bat
set "NATIVE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
set "EVIDENCE=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%NATIVE%\check_field_local_start_binding_v1.py" --source "%EVIDENCE%\field-operator-sessions-v6-admission\host-backup-mirror" --output "%EVIDENCE%\operator-local-supervisor-v1-preparation\start-binding-v1"
```

Anaconda Prompt: use the same Command Prompt commands above. The explicit campaign interpreter is intentional; no environment changes or package installations are needed.

## Native API sequence and deployment boundary

These APIs require the existing Linux CPU3/128MiB hard AS/1MiB stack/32MiB FSIZE envelope and a fresh operation of at most600seconds including cleanup and complete host backup before2026-10-01T17:42:44Z. The app retains its separate original shared CPU2,3/200%/Tasks64/768MiB AS unit, recording120second stop and all storage guards. AS is not a hard RSS limit.

A future admitted supervisor must:
1. Install the exact independently backed manager capsule and policy in a fresh root; reserve a recording through phase(binding, 'reserve') in a fresh process, then reap and verify that owner dead.
2. Stage one exact fresh one-slot broker and bind its CONFIG local_manager to that manager, operation and next launch slot. Run Gate9 once. GateLink records actual current broker/gate identities and service MainPID before ACK.
3. Reap the gate and prove its exact death before calling phase(binding, 'finish') in another fresh process. The journal reads actual gate/model/archive/controller/source closure, calls the V132 complete copier once, independently reads back the source/copy, and publishes BACKUP.
4. Reap that process and call phase(binding, 'reopen') in another fresh bounded process to recheck certified copies. This read-only phase publishes no new journal launch record; its early stdout OWNER still requires separate actual closure accounting.

The native CLI accepts a bounded JSON object {phase, binding} on stdin and emits its real owner before project reads. Only a fresh reviewed dispatcher may launch the pinned script with stdin EOF, collect bounded output, prove exact process closure and make a complete independent host backup. No bare SSH deployment command is supplied because the required fresh dispatcher, one-session broker driver/builder, issuer, complete manager-tree backup and new journal-owner collector bindings are not yet implemented. Existing two-session or consumed dispatchers do not authorize this composition.

The manager capsule remains at most16files/2MiB,128KiB per module. Every recording retains the original one-slot broker151114284target/155308588host plus an independent151114284local mirror. Do not substitute the V132 two-slot tree, grant unused/failed/deleted credit, remove a guard or relabel the proposed86400second idle lifetime as admitted. Production activation/rollback, failed-source backup and automatic recovery remain open. Display270 and capture-off baseline must be preserved.
