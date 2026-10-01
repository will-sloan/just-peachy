# Finite local journal and verified backup binding V1

Status: PREPARED, native integration unexecuted. This source adds a recording lifecycle API to Journal3. It does not install or launch a production manager. Existing Journal2 metadata qualification and the separate V132 two-session local-copy result retain their original scope.

Purpose: admit the next finite recording only after the preceding broker has actual successful gate, process, capture, archive and controller closure plus a complete independent local backup. Each manager recording reserves exactly one existing broker allocation, including its full local mirror. A two-session broker policy is rejected even when its measured bytes would fit. No unused, failed, deleted or small-recording credit is applied.

Files:
- field_local_backup_contract_v1.py validates the exact one-broker source and complete copy-receipt shape.
- field_local_release_files_v3.py preserves Journal2's bounded metadata, current-owner, pending-file, locking and publication rules, and adds reserve_recording, recording_started, recording_closed, backup_recording and recording_failed.
- check_field_local_manager_v1.py checks only the changed pure binding using explicit fixtures.

Native API inputs are a fresh finite release root, exact policy SHA, fresh LOCAL_RELEASE_QUALIFICATION operation and recorded session slot. The source broker must match that release's allocated root and one-slot policy. Its service name is derived from the exact source root. The supervisor must actually launch and acknowledge that service before recording_started can observe its live gate/broker identities. No launcher, gate adapter, activation or rollback adapter is provided here.

recording_closed reads the actual historical capsule, ledger pins, gate result, service state, recorded owner identities, capture state and leases. backup_recording calls the already qualified copy_closed API once at a fresh destination, then reads back every source and copied file and repeats the physical closure check. Only then can BACKUP be published. Opening a journal with certified copies performs complete readback and matching actual closure checks. reserve_recording repeats those checks before consuming a fresh root. Outputs are bounded immutable RESERVED, STARTED, CLOSED, BACKUP or FAILED metadata, and the complete independent backups/recording-NN tree.

Direct recording publications and control ACTIVATION/ROLLBACK publications are rejected. Only the lifecycle methods can publish recording facts. This is a cooperative Python API guard, not an adversarial security sandbox. Arbitrary caller-supplied closure/backup booleans are not accepted as physical evidence.

A failed or interrupted copy remains at its consumed destination. A later constructor rejects any nonempty backup slot without a valid certificate; it never deletes the partial copy or retries the mutation. FAILED records remain consumed and block the next recording. Failed-source backup, automatic recovery, forced-stop recovery, cold boot, power loss and concurrent modification qualification are still open.

## Host checks

Inputs: --release-template is an existing local release policy used only as a fixture shape; no policy authority is reused. --output is a unique absent directory. Output: REGISTERED_OWNER.json and RESULT.json. Synthetic hashes, process identities, units and copy facts are fixtures, not a native filesystem or recovery result. The script sets CPU14 before project reads. It neither constructs Journal nor copies recordings.

PowerShell:
```powershell
$jp = 'G:\Just_Peachy_N1\20260924_campaign'
$code = Join-Path $jp 'worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$evidence = Join-Path $jp 'local\n5\research-extension-20260928\pi-native-20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B (Join-Path $code 'check_field_local_manager_v1.py') --release-template (Join-Path $evidence 'field-local-release-v1-admission\RELEASE.json') --output (Join-Path $evidence 'operator-local-manager-v1-preparation\host-binding-v1')
```

Command Prompt:
```bat
set "JP=G:\Just_Peachy_N1\20260924_campaign"
set "CODE=%JP%\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
set "EVIDENCE=%JP%\local\n5\research-extension-20260928\pi-native-20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%CODE%\check_field_local_manager_v1.py" --release-template "%EVIDENCE%\field-local-release-v1-admission\RELEASE.json" --output "%EVIDENCE%\operator-local-manager-v1-preparation\host-binding-v1"
```

Anaconda Prompt: run the same Command Prompt commands using the explicit interpreter above; no conda environment changes or downloads are required. The historical host-binding-v1 output is consumed after its first execution; do not rerun a passed check unchanged. Use a fresh reviewed version and absent output only for a changed hypothesis.

## Native use and bounds

There is intentionally no bare SSH or installed launcher command. A future supervisor must pin every imported module into the release manifest, reserve all independent source/mirror/host allowances, verify actual current baseline/activation identities, and issue a fresh admission before calling the API. Native module imports do not create a journal or start a session.

Example API sequence, inside that future admitted supervisor:
```python
journal = Journal(root, release_sha256, operation, create=False)
reservation = journal.reserve_recording()
# Supervisor stages and launches the exact one-slot broker with fresh guards.
journal.recording_started(reservation["slot"])
# Supervisor waits for actual natural gate/worker closure.
journal.recording_closed(reservation["slot"])
journal.backup_recording(reservation["slot"])
journal.close()
```

All current operations remain at most600seconds including cleanup and independent host backup, before2026-10-01T17:42:44Z. The proposed86400second idle lifetime remains unadmitted. Native journal/copy worker requires CPU3, hard+soft128MiBAS,1MiBstack and32MiBFSIZE, inside sharedCPU2-3/200%/Tasks64 and bounded service runtime. Actual app workers retain their separate768MiBAS envelope. Preserve minimum5GiB Pi free, C50GiB/G75GiB, RAM guards, one model thread, GPUoff, manual controls and display270.

Code and metadata maxima remain unchanged: manager code16files/2MiB/128KiBmember, each metadata primary and pending separately allocated, backup receipt256KiB including wrapper,16KiB writes, fsync and no-replace publication. The existing capsule source dependencies must fit and be individually pinned before native use. No target, production admission, accepted activation, automatic recovery or offline readiness is claimed by this preparation.

See README_FIELD_LOCAL_RELEASE_V2.md, README_FIELD_LOCAL_JOURNAL_V3.md and README_FIELD_LOCAL_BACKUP_V4.md for immutable prior qualifications. New code requires changed native composition qualification before acceptance.
