# Build29 staging preparation

`prepare_core_stage29_v2.py` prepares a reviewed host-side payload for the existing stage-only installer. It does not perform staging. It imports no application runtime or model, opens no SQLite database, runs no SSH, changes no Desktop entry, and starts no capture. Native dispatch remains a separate guarded operation after the accepted production-backup12 owner and cgroup have closed.

The input is the fresh build29 output directory, not a loose archive. The tool checks `BUILD_RESULT.json`, both closure receipts, the source review pin, every expanded package member, and the archive through the existing installer validator. The output is a new private directory under `Q/audit-preparation/core-stage29-preparation-<UUID>` containing `ACTION.py`, `PAYLOAD.json`, an exact registered CPU14 owner, hash-bound backup admission, source copies with independent backup/restore readbacks, and `SOURCE_CLOSED.json`. It keeps failed preparations in their original directories.

The derivative's exact parent is `stabilization_20261005/prepare_stabilization_stage28.py`, SHA256 `5025c86eab988737f31fc1616b10cb003f136dec943b057778fecdb1447fa359`. The stage24 installer remains byte-identical, SHA256 `b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6`. The native `stage_stabilization_action.py` remains byte-identical, SHA256 `4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74`. Only host admission, version/path selection, and proof binding are extended. None of these preparer files are inserted into the frozen runtime package.

## Exact package inputs

The accepted builder directory is `Q/audit-preparation/core-package-v1-389154acb3e04317b614c4311bb6de02`, where `Q` is `G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`.

| Input | Exact value |
| --- | --- |
| New target | `/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-29` |
| Shared user data | `/home/peachyprototype/JustPeachy/data/runtime-v29` |
| Package manifest | `331b85974c33957917f524d0796d53df78f6154be557b10ecea55524d130939b` |
| Archive | `3a4ca0f9337d2618d1fde502f84d119c9cb25c90e3f2bb03ac4c1443c7ccf928` |
| Root-approved source review | `2f2b7b92fe54c87c5f1713c3cffc2f97420b1fc5d3f7f86566c043348d01549c` |
| Immutable build28 manifest | `e3d55e232730cb3b06cc12289d94cf04539ee04b8021ebd45553e5fd5027917b` |

The builder passed, naturally returned zero, and its exact PID28256/creation FILETIME134357797287910082 is independently absent. There are419 declared members plus the manifest, with27 source input/backup/restore hashes independently verified. The failed prior build with an overlong reviewer label is preserved separately; no source or frozen package was changed to resolve that metadata limit.

## Backup prerequisite and inputs

The canonical prerequisite is `Q/production-backup-12-reconcile-01`. Before invoking this tool, root must accept that directory's actual `COMPLETE.json` and `RESULT.json` SHA256 values. Do not substitute a census, copy-progress receipt, old package's embedded backup, or a manufactured completion. The tool requires the real `selected-release-and-user-data` completion, the exact backup12 job, current boot, immutable build28 source manifest, verified before/after census and external asset pins, natural return zero, and exact owner/cgroup closure. `RESULT.json` and `FULL_BACKUP.json` must point to that same restoration payload and manifest. The completion is rechecked at the end.

Required arguments are:

- `--build-output`: the canonical fresh builder directory above.
- `--boot-id`: the actual current CM5 boot UUID. The currently observed UUID is `e60e67c2-f3f5-4b8b-8eab-2613df2de37e`; a new boot requires a new accepted backup admission.
- `--backup-complete-sha256`: the root-accepted64-character lowercase SHA256 of the actual COMPLETE receipt.
- `--backup-result-sha256`: the root-accepted64-character lowercase SHA256 of the final RESULT receipt.
- `--backup-reviewer`: a descriptive reviewer label of1–128 characters.

This preparation binds the accepted backup metadata. It does not rehash the large restoration payload, repeat reconciliation, restore files, or recover the original SQLite store. Those operations require their own admitted and independently closed receipts. The accepted full COMPLETE stays at its restoration location; the output keeps three identical copies of its small hash-bound admission, avoiding an unnecessary large receipt copy.

## Run in PowerShell

Use the exact existing Python executable below; the `python` WindowsApps alias is not used. During this session, obtain the root coordinator's host slot before running. One registered CPU14 preparation process is permitted alongside the separately guarded backup process. Set the two backup pins only after the backup is complete and root has accepted them; the placeholder strings below deliberately fail validation.

```powershell
$stageDir = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$buildDir = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/core-package-v1-389154acb3e04317b614c4311bb6de02'
$completePin = 'REPLACE_WITH_ROOT_ACCEPTED_COMPLETE_SHA256'
$resultPin = 'REPLACE_WITH_ROOT_ACCEPTED_RESULT_SHA256'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$stageDir/prepare_core_stage29_v2.py" --build-output $buildDir --boot-id 'e60e67c2-f3f5-4b8b-8eab-2613df2de37e' --backup-complete-sha256 $completePin --backup-result-sha256 $resultPin --backup-reviewer 'Codex root accepted production-backup12 restoration and exact closure'
```

Read the printed output directory. Check `SOURCE_CLOSED.json` and compare all recorded inputs and their `.backup`/`.restore` files. Independently confirm its exact registered PID is absent after natural process exit before releasing the host slot. Preserve its receipt and output whether successful or failed. The native staging payload is not authorized by preparation success alone.

## Run in CMD or Anaconda Prompt

The same existing executable is used; no new environment or dependency installation is needed. Paste these lines into CMD or an Anaconda Prompt after obtaining the host slot. Replace the two placeholder values with the accepted lowercase hashes.

```bat
set "JP_STAGE_DIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006"
set "JP_BUILD_DIR=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\core-package-v1-389154acb3e04317b614c4311bb6de02"
set "JP_COMPLETE_PIN=REPLACE_WITH_ROOT_ACCEPTED_COMPLETE_SHA256"
set "JP_RESULT_PIN=REPLACE_WITH_ROOT_ACCEPTED_RESULT_SHA256"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%JP_STAGE_DIR%\prepare_core_stage29_v2.py" --build-output "%JP_BUILD_DIR%" --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --backup-complete-sha256 "%JP_COMPLETE_PIN%" --backup-result-sha256 "%JP_RESULT_PIN%" --backup-reviewer "Codex root accepted production-backup12 restoration and exact closure"
```

## Capacity and retained limits

The existing preparation bounds are8MiB/600seconds, archive2MiB, package16MiB, host free floors50GiB onC and75GiB onG. The payload reservation is `expanded + archive + (directories + 1)*65536 + 65536`; the unchanged native action requires the independent5GiB reserve plus that reservation. These bounds limit this finite staging operation and do not limit the user's recording corpus.

Build29 removes the artificial global32MiB SQLite soft limit and logical metadata/cumulative text-writer refusals. SQLite file allowances follow actual storage capacity, existing extents, and the retained physical reserve. Bounded transaction/queue/memory work and ownership protections remain. The installed hard file limit remains finite and derives from filesystem capacity minus the reserve; an inherited hard limit that is too small must be corrected by the launcher scope, not silently ignored.

A known low-space limitation is retained in this frozen package: opening a writable store uses the shared planner, which needs at least8MiB above the physical reserve even for read operations or Discard; a requested metadata transaction additionally needs twice its estimate. Below that floor the chooser presents capture-disabled recovery. Free unrelated space or recover from the accepted backup using a separately reviewed procedure before retrying. Quota bookkeeping no longer refuses Stop/Discard, but actual physical-space admission can still refuse them. No journals should be cleared manually.

## Activation29 derivative recommendation

The exact host parent is `prepare_stabilization_activation28_v2.py`, SHA256 `796c7fed98400577eeb19a3460ff78484bf1044308254b6b0fea0e76380b369f`. Its native action is `activate_full_desktop_action_v5.py`, SHA256 `e336034c83c77e524c6f2762ac6726961c1344a35f36e1a7da448db4ee244f65`. A new version must change the action's exact package-name test from `field-runtime-v29-build-28` to29, preserving the remaining inventory, proof, backup, compare-and-swap and single Desktop-entry transaction.

The host derivative must take the actual finalized build29 `NATIVE_CHECK_V2.json`, matching finalizer result and current boot. Keep all existing proof requirements: PASS, manifest equality, portrait UI, capture verification, closed workers, absent exact main owner, empty recursive unit, independent native finalization, and absent finalizer utility. Never relabel the old build28 measurements. It must use the actual prior28 activation receipt `Q/operation-stabilization-desktop28-01/dispatch/RESULT.json`, not the parent preparer's hardcoded prior26 receipt.

The current prior28 Desktop compare-and-swap SHA is `8c917153c58c57d73d8ce0d0e5662b42b3f7d698de0cee4189b844f8cfc70ac0`; its old package manifest is the immutable build28 pin above. Disabled login-autostart SHA remains `8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206`. Use the fresh target29 manifest, current boot, actual native-check path and SHA, preserved shared data root, one exact prior Desktop path, and a fresh activation evidence UUID. Keep16MiB independent target/PC metadata reservations, exact before/restore readbacks and atomic replacement of only `/home/peachyprototype/Desktop/Just Peachy.desktop`. The prior receipt's historical boot is evidence, not a fresh observation. Recheck the current Desktop and disabled autostart in the native transaction.

Backup12 completion and any original SQLite recovery must be independently accepted before live application qualification or activation. This file records the derivative design only; it does not create activation proof or authorize native execution.

## Actual preparation/staging result - historical, do not replay

2026-10-06: production-backup12 COMPLETE was accepted: 2,724 files/ 633,265,206 bytes,
SHA256 03ffc85b2e2f3046c707879c3059f3c2e1194626f4ece11a7d385975c924bdfb.
Independent readback, source before/after stability, natural return 0, exact
owner 35878/start746141 absence, empty cgroup and released leases were verified.

The prepared payload was dispatched through the historical V5 command in
README_CORE_OPERATIONS_V5.md. Actual core-stage29-04 RESULT SHA256:
c75d0e1f69f0f513712c0e63cee04550683fed85b678bf793e0199b3aa150aed.
STAGED_ONLY: 420 files for the exact manifest above, no model/gallery copying,
runtime process/capture or Desktop change. Failed Stage02/V4 roots remain.
The consumed stage payload and completed label must not be rerun. Examples
above describe the preparation interface; future operations require fresh
admission rather than reuse of old expiry/boot/backup inputs.

Live34 now has independent native PASS (see README_CORE_NATIVE_VALIDATION_V2),
while its finalized full mirror remains pending. Six matched Saved rows,
quality/calibration, sustained behavior and activation are still pending.
Neither this maintenance README nor stage-only success activates build29.
The three maintenance READMEs changed for this status update are not among the
frozen package's419 declared members or the builder's27 input pins.