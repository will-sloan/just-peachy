# Lossless delayed-frame archive queue records

Purpose: repair the observed399,670-byte delayed Nemotron frame event rejected by the archive64KiB queue-record limit. `field_archive_records_v1.py` splits only oversized `n2_diarization_frames` archive records into ordered64KiB in-memory pieces. All pieces are admitted atomically or none are accepted. The archive worker verifies length/SHA/order and reconstructs the exact serialized record before the original CompactBinary writer. No probabilities, clocks, publication sequence or final marker are changed; the persisted format and existing decoder stay unchanged.

Inputs: an actual pinned installed v12 archive/Field composition, genuine quiet authority, fresh600s PLAN and measured LIVE_RESOURCE_POLICY_V8, one fresh field-live-entry-v8 tree. Outputs: ordinary complete archive events/audio plus event-piece metrics in existing epoch/Stop receipts, actual source/model/GUI/Save/Open/closure evidence, and exact closed-tree SSH backup. Constructor/transport/Field checks and source Stop-before-diagnostics are retained.

Limits:64KiB queue pieces and physical archive-journal writes; logical serialized event1,047,552B including its full metadata, leaving1KiB below the existing1MiB journal/decoder ceiling. Queue plus assembly retains4MiB/512items, with transient serialization/reconstruction memory still under the768MiB process AS guard. Per-event eight-column rows and global13,001-frame/2,080,000-sample geometry are checked. Actual prior emissions had2,112 and484rows; this is observed geometry, not a proof of every possible future native emission. Over-ceiling records fail explicitly and Stop, never truncate. Native producer/journal retains its existing1MiB record and16MiB file limits. All per-file/aggregate/output policies remain enforced. Python interception is not a kernel quota.

The Windows verification replays the TWO retained failed-run frame events through the actual archive worker and existing decoder, proving exact payload reconstruction and joined worker/empty queue. V1 failed before the worker because Windows lacks Linux directory fsync; its source and partial receipt are retained. V2 uses an explicitly labelled Windows control-publication fixture, so it gives no Linux durability/source/model/GUI credit. Three changed input rejects and a bounded short-write reconstruction check are included. Do not rerun a healthy check merely for a version.

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\verify_field_archive_records_v2.py --output 'NEW_PRIVATE_HOST_TEST_DIRECTORY' --source-tree 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-entry-v7-evidence\host-backup-mirror' --release 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\dispatch_field_live_entry_v10.py --plan 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-record-v1-preparation\PLAN_V1.json' --owner-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-record-v1-preparation\NEW_DISPATCH_OWNER.json'
```

CMD / Anaconda Prompt:
```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B verify_field_archive_records_v2.py --output "NEW_PRIVATE_HOST_TEST_DIRECTORY" --source-tree "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-entry-v7-evidence\host-backup-mirror" --release "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_live_entry_v10.py --plan "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-record-v1-preparation\PLAN_V1.json" --owner-receipt "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-live-record-v1-preparation\NEW_DISPATCH_OWNER.json"
```

Closed plans/roots must never be reused. The dispatcher automatically runs mirror_field_live_entry_v8.py. ControllerV8/workerV7/gateV10/stagerV9/exporterV8/mirrorV8 bind the new archive adapter; the actual source/D1 chain remains unchanged. CPU14 before host reads and exclusive owner receipts precede dispatch. Pi workerCPU2,3/200%/Tasks64/768MiBAS/1MiBstack/285s runtime30s Stop; source/gate/stager/mirror retain their own bounded envelopes.5GiB Pi free/C50/G75GiB floors persist. Full admission600s includes cleanup/backup before17:42:44Z. No device maintenance is included.

Read-only closure collectorV9 accepts only LIVE_RESOURCE_POLICY_V8 exact scope/hash and does not authorize another run:
```text
python -B collect_native_closure_v9.py --version FRESH_VERSION --resource-policy LIVE_RESOURCE_POLICY_V8.json --policy-sha256 VERIFIED_SHA256 --census ABSOLUTE_FRESH_CENSUS.json --owner-receipt NEW_ABSOLUTE_OWNER.json
```
PowerShell uses the executable and leading ampersand shown above; CMD/Anaconda omit the ampersand. Backups contain exact source bytes plus independent restore copies before native dispatch. Quiet checks do not establish accuracy, physical touch, offline cold boot or noisy-human performance.
