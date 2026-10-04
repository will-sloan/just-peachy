# Backup reconciler V4: bounded receipt repair and same-snapshot continuation

Purpose: repair the actual V3 host failure after a natural read-only ready probe.
V3 called undefined `save` while publishing SSH_CLOSURE and again in its failure
branch. Its preserved attempt has an actual early native owner but no reconstructed
SSH closure receipt. V4 uses the existing common fsync/independent-readback writer,
with an explicit cumulative262144-byte/8-file per-phase cap before publication.
It also removes the leftover adaptive segment code referencing undefined `started`;
the reviewed V3 exact1MiB transfer plan is now used throughout. V3 remains unchanged.

Inputs: the same actual backup02 JOB, frozen10 package copy, seed mapping and the
failed pre-transfer output. No new guard launch, native output root, boot, admission,
expiry or deadline is created. The original deadline is1791084418.9216013 Unix
(03:26:58 UTC). V4 counts every retained old preparation/phase byte once against
the same16MiB preparation allocation and carries forward its phase count. Actual
prior usage was137102 bytes/one phase when prepared. A running prior host, different
JOB, symlink, over-budget receipt, or previous payload/guard mirror is refused.
This narrow continuation is for a failed pre-transfer attempt only.

Outputs: a fresh production-backup-02-reconcile-02 tree, PRIOR_ATTEMPT with original
deadline and explicit old utility-closure gap, new exact probe receipts, transferred
payload, and the unchanged final census/source-rehash/closed-guard/readback proofs.
COMPLETE remains impossible until all original final checks pass. No old missing
closure is fabricated; a later fresh native owner inspection must check its actual
early utility independently. Native guard lifetime/resource limits stay unchanged.

## PowerShell (root operator only; contains SSH through the reconciler)

Do not re-run the backup dispatch. Start this against the existing guard within
its original finite lifetime, after the failed host process is closed:

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$n/reconcile_production_backup_external_v4.py" --job "$q/production-backup-02-preparation-01/production-backup-02-JOB.json" --package-copy "$q/audit-preparation/package-preparation-3b8ec5e1d68d406ea1f126e834c16288/package" --seeds "$q/production-backup-02-preparation-01/SEEDS.json" --prior-output "$q/production-backup-02-reconcile-01" --output "$q/production-backup-02-reconcile-02"
```

## Command Prompt / Anaconda Prompt

Enter `powershell -NoProfile`, then run the complete block. No environment
installation/activation is needed. The reconciler publishes its CPU14 owner before
project/data reads and enforces the existing C:50GiB/G:75GiB independent reservations.

Host-only focused checks use the early-owner wrapper in README_STORAGE.md with
`test_backup_reconciler_v4`. Four checks cover natural non-mirror ready EOF and its
durable independent closure, original transport-failure preservation, refusal before
phase over-allocation, cumulative same-JOB prior cost/deadline, payload-resume refusal,
and a recursive symtable scan of all global references against module symbols and
builtins (including the formerly missed `save`/`started`). These tests run no SSH,
native process, source capture or model. The actual first-attempt metadata was also
read-only accounted; host checks do not claim native transfer completion.
