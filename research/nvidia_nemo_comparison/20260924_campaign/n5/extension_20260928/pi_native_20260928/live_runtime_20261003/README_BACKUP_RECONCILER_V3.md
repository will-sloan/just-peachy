# Current-release backup reconciliation: bounded large transfers

`reconcile_production_backup_external_v3.py` is a host-only derivative of V2.
It copies only missing bytes from the existing admitted, exclusively locked native
snapshot. Exact seed SHA checks, source identity checks, all original owner and
closure receipts, independent PC readback, native final rehash, and the compatible
COMPLETE/FULL_BACKUP formats are unchanged. V2 and frozen runtime packages remain
unchanged. Preparing or testing this code does not execute a native command.

Actual scope06 contains 26 roots, 1,932 files and 657,980,201 bytes. Its current
data tree has 358 files / 637,445,973 bytes, with a largest file of 64,782,446
bytes. These source files have no 32 MiB cap: transfer uses at most 1 MiB per
phase and 16 KiB protocol frames. The 640 MiB full-copy reservation, 16 MiB
separate preparation reservation, and C:50 GiB/G:75 GiB host free-space floors
stay unchanged. Native scope remains 64 roots, 4,096 files and a 2 MiB census.

V2 adapted its transfer size downward after short files and assigned only 4 MiB
to repeated phase receipts. V3 uses the existing 1 MiB protocol maximum and
records the exact missing-file phase count after actual seed verification.
There are still at most 8,192 phases, with a finite admitted job deadline and
unchanged per-probe watchdogs. It accounts receipts against the entire existing
16 MiB preparation allocation, reserving 4 MiB + 256 KiB for final manifests and
failure evidence. Each phase may persist at most 256 KiB of protocol receipts.
Payload files and the ordinary closed guard mirror have separate allocations;
they cannot consume preparation room. Exhaustion refuses the next write/phase,
preserves evidence, and cannot publish COMPLETE. Network speed and native
completion within the admitted 1,800 seconds still require actual measurement.

## Inputs and outputs

Inputs: the actual returned production-backup-NN JOB JSON, an independently
verified copy of that exact admitted package, and explicit seed mappings.
The current prepared scope/payload/seeds are under
`production-scope-06-preparation-01`. Scope SHA is
`cd4a92a7ec2c524c73e2b0fa993a264de40d85286fdfe1548851a1558b826af6`.
Fresh expiry/boot admission must be created by the root operator while preserving
the earlier payload. Seeds are candidates; no reuse is claimed before equality
to the actual native census. Immutable model assets outside copy roots remain
separately verified references. Eighty historical campaign roots are explicitly
preserved outside this selected-current-release backup claim.

Outputs in the fresh private reconciliation directory: early CPU14 OWNER,
PC_RESERVATION, source backup/restore copies, JOB, CENSUS, RECONCILIATION,
TRANSFER_PLAN, all per-phase actual owners and SSH/segment closure proofs,
payload, ordinary closed guard mirror, MANIFEST, COMPLETE, FULL_BACKUP and RESULT.
Failure emits FAILURE and never marks a partial backup complete.

## PowerShell

Only the authorized root operator executes the SSH-containing dispatch and
reconciliation commands, after all other native jobs have closed. `$job` is the
actual action_result saved from the dispatcher, never a fabricated owner.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$packageCopy="$q/audit-preparation/package-preparation-3b8ec5e1d68d406ea1f126e834c16288/package"
# $freshPayload: reviewed scope06 derivative with current expiry and production-backup-01 label.
& $py -B "$n/host_operations_v3.py" --label production-backup-01 --action "$n/launch_backup_external_action_v2.py" --payload $freshPayload --writes
# Save only the returned actual action_result as $job, then run immediately:
& $py -B "$n/reconcile_production_backup_external_v3.py" --job $job --package-copy $packageCopy --seeds "$q/production-scope-06-preparation-01/SEEDS.json" --output "$q/production-backup-01-reconcile-01"
```

## Command Prompt and Anaconda Prompt

Enter `powershell -NoProfile` and run the complete PowerShell block above.
The exact interpreter requires no environment installation or activation.
For host-only checks, use the early-owner CPU14 test wrapper from README_STORAGE.md
with `test_backup_reconciler_v3`. Tests exercise large-file/empty-file/seed phase
counts, refusal before an over-budget write, final-receipt reserve, and malformed
phase membership. They do not establish native transfer success.

## Activation dependencies

The root operator must first finish the actual optional qualification and
targeted History Export check, then obtain this actual complete selected-release
backup and independent restoration proof. Production acceptance and exact asset
pins must match the production package. `install_candidate` requires the full
backup proof and expected prior desktop SHA; it does not start capture. The
separate desktop consolidation action requires the reviewed complete 11-shortcut
path/hash census and backup/restore copies before archiving the other owned
shortcuts outside Desktop. Existing startup-disabled settings, display rotation,
unrelated icons, old runtime sources and the retained selected recording remain
preserved. Read README_DESKTOP_ACTIVATION.md and README_DESKTOP_CONSOLIDATION.md
for the explicit reverse operation; package activation alone does not consolidate
the desktop or prove physical touch behavior.
