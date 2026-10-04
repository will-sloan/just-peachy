# Complete bounded readback of the one-shortcut archive

Purpose: make the exact Desktop consolidation transaction independently recoverable on the PC before the idle/Exit check. V3 preserves V2's archive/restore function AST, all11 exact shortcut pins, both startup pins and canonical production metadata imports. It adds a bounded compressed return of every archive file, plus a host-only closed-operation readback CLI. No frozen runtime/package or earlier V2 source is changed.

Inputs: the exact production package/manifest, current boot/fresh expiry, selected activated shortcut and activation backup/plan, expected current hash and fresh archive path described in README_DESKTOP_CONSOLIDATION.md. Use the actual final production release ID; neither build13 nor a planned14/15 is implicitly accepted. Output after native success: the unchanged off-Desktop archive and the exact archive transport in the closed inspector result. Host output includes every original shortcut backup/restore, archived shortcuts, both new launcher copies, PLAN, move intents and CONSOLIDATED/RESTORED receipt. Unrelated Desktop entries and disabled autostart remain unchanged; no process/capture starts.

The archive transport caps64files,8directories,262144 file bytes,524288 uncompressed JSON bytes and65536 base64 characters. Each file has exact size/SHA/mode. The decoder bounds decompression, requires EOF/no trailing data, validates canonical paths, exact three directories, all11 original pins, independent copies and complete46-file consolidation membership (48 after explicit restore). Native preflight reserves return space against the existing262144-byte inspector envelope before changing Desktop. All existing16MiB/native5GiB and PC C:50GiB/G:75GiB guards remain.

## Root operator: PowerShell

After actual production staging and activation, its host-only activation readback must first pass. Construct the reviewed consolidation payload using actual activation returned values, with mode=consolidate and a new archive UUID. See README_DESKTOP_CONSOLIDATION.md for exact JSON fields. Use the current reviewed host dispatcher (V6 at preparation; verify its pinned current version before execution):

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
& $py -B "$n/host_operations_v6.py" --label desktop-consolidation-01 --action "$n/desktop_consolidation_action_v3.py" --payload "$q/REVIEWED_CONSOLIDATION.json" --writes
if ($LASTEXITCODE -ne 0) { throw 'Preserve failed transaction; no automatic retry/rollback' }
# No SSH in this readback command; requires exact natural inspector closure.
& $py -B "$n/desktop_consolidation_action_v3.py" --operation "$q/operation-desktop-consolidation-01" --output "$q/desktop-consolidation-01-readback-01"
if ($LASTEXITCODE -ne 0) { throw 'Complete PC archive proof is still missing' }
```

The host command verifies the exact executed V3 source against its independent operation backups, the actual owner/natural closure, complete bounded transport and every file digest. It writes `archive/`, independent outer result copies and `VERIFY.json` with `COMPLETE_DESKTOP_ARCHIVE_READBACK`. It does not create a success receipt for an attempted invocation or incomplete archive. Review the actual native transaction result and final Desktop membership before proceeding to idle last. No second broad production backup is needed for this small archive.

Explicit restore uses the same V3 action and the old documented mode=restore contract, fresh boot/deadline and exact archive. It never overwrites edited/unrelated entries. Native restore adds two receipts to that same preserved archive. The host readback CLI currently uses ordinary `operation-desktop-consolidation-NN` labels; choose a fresh NN for a restore action rather than inventing an unsupported readback label. Preserve failure/move intents; do not automatically rerun.

## Command Prompt / Anaconda Prompt

Enter `powershell -NoProfile`, then run the complete block with the qualified interpreter. No environment installation is needed. Dispatcher commands contact the native device and are root-only; the second command is CPU14 host-only and publishes actual PID/create_time/affinity before project reads.

## Focused host checks

Run `test_desktop_consolidation_v3` through the early CPU14 owner wrapper in README_STORAGE.md. Only new readback boundaries are tested: exact old transaction/pins, complete46-file roundtrip, missing/changed/traversal/trailing transport refusals, and exact closed owner/transaction binding. Synthetic fixtures use retained actual11 shortcut bytes but do not claim native consolidation, touch or restore proof. No native command or models are executed by these checks.
