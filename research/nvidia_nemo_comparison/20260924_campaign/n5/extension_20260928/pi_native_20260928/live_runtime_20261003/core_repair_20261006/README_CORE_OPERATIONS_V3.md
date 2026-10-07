# Capacity-bound database recovery dispatch

Purpose: keep the complete owner/lifetime, current boot/process, resource and
strict SSH checks from `host_core_operations_v2.py`, while admitting the exact
backed `recover_core_database_v2.py` action with a filesystem-derived file size
limit. Other write actions retain their existing 32 MiB helper limit.

Inputs: a fresh sealed recovery payload, accepted full-backup certificate,
original database/journal pins, and this exact action SHA256
`3f5c7e608f7e6713f0581835b8d4fcca1e2bd916948493b298b0062b4be5aac4`.
Outputs: source backups and independent restores, all-owner preread, current
native baseline, raw execution and exact utility closure, plus
`RECOVERY_FSIZE_DERIVATION.json`. Recovery does not delete recordings.

The initial hard limit is the lesser of the sealed request and actual filesystem
capacity less 5 GiB. The native action independently rechecks equality, current
free space, original source identities/hashes, and holds shared research,
hardware, launcher and recording leases during normal SQLite recovery. The
128 MiB helper address space, 1 MiB stack, CPU3 and bounded time remain.

PowerShell, after full backup and payload preparation have passed:

```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$repair='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
& $py -B "$repair/host_core_operations_v3.py" --label core-database-recovery-01 --action "$repair/recover_core_database_v2.py" --payload 'FRESH-PREPARED-OUTPUT/PAYLOAD.json' --writes
```

For Command Prompt or Anaconda Prompt, run `powershell -NoProfile`, then the
same block using the existing interpreter. Replace only the fresh prepared
payload path and unused operation label. This entrypoint is for reviewed repair
operations, not the normal desktop launcher. A changed action requires a fresh
source-bound derivative; never reuse a failed operation root or modify its data.
