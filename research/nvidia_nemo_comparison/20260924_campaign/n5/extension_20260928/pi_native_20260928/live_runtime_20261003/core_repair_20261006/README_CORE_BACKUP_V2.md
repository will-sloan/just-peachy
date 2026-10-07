# Current runtime backup on Windows

Purpose: reuse the pinned production reconciler while treating the Pi's absolute
paths as POSIX paths during host validation. Native helpers, schema checks,
source hashes, snapshot locks, lifetime and independent copy verification remain
unchanged. CPU14 and an early host owner precede project reads. The old failed
catalogue and its bytes remain preserved.

Inputs: actual active production-backup JOB, exact PC package copy, explicit seed
map, and a fresh private output directory. Outputs: complete source census,
missing-only transfer, independent hash/readback and exact natural native closure
before COMPLETE. An expired snapshot must be closed and freshly admitted; this
wrapper cannot renew it. A copy-only success is not a verified backup.

PowerShell:

```powershell
$n='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B "$n/core_repair_20261006/reconcile_core_backup_v2.py" --job "$q/production-backup-11-JOB.json" --package-copy "$q/audit-preparation/stabilization-package-0c72a531741047998278d56d381effc2/package" --seeds "$q/audit-preparation/core-full-backup-seeds-02.json" --output "$q/production-backup-11-reconcile-01"
```

Command Prompt and Anaconda Prompt: run `powershell -NoProfile`, then use the
same block. No installation or environment change is needed. The command
contacts the Pi with the existing strict SSH transport. Preserve failed outputs;
use fresh labels and a current admission if the original snapshot expired.

V2 removes the artificial cumulative 4 MiB protocol receipt quota. Each frame
and source segment remains bounded. Actual disk floors are checked before every
phase, and the source snapshot still has a finite admitted lifetime. The current
633 MB scope has a separate 2 GiB copy reservation and an 1800-second transfer
window. Failed backup10 and its partial copies remain preserved; its deadline
was not extended.
