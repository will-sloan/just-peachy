# Backup V5: native POSIX scope decoding on the Windows host

Purpose: correct the actual V4 catalogue refusal without changing the frozen
common/native helper or relaxing its checks. Native `/home/...` strings were
being passed to host Windows `Path`, which rejects their absolute form. V5 clones
only the pinned pure `validate_spec` function AST and changes its two `Path`
references to `PurePosixPath`. Every schema, finite reservation, lifetime, root,
traversal, overlap, alias and external-asset check remains. Host seed/source paths
continue using ordinary Windows filesystem paths. The common module is not patched.

Inputs: the unchanged actual backup02 JOB and original03:26:58 UTC deadline,
frozen10 package/seed inputs and both failed pre-transfer attempt paths. V5 retains
the V4 bounded durable publisher and exact1MiB segments. It charges each existing
attempt tree's actual bytes once, rather than summing nested ledger counters;
omitted predecessors or duplicate paths fail. Actual retained usage was277211 B
and3phases at preparation. Original16MiB preparation allocation,640MiB payload,
all free-space floors, final verification and native lifetime remain unchanged.

Outputs: fresh reconcile03, PRIOR_ATTEMPT listing both immutable old attempts,
bounded transport/closure proofs and the original complete-backup outputs only
if all native final rehash/closure and independent PC readback checks succeed.
V3/V4 failures and missing utility-closure receipts remain preserved, not repaired
retrospectively. No new native snapshot, root, admission or time extension occurs.

## PowerShell (authorized root operator; contains SSH)

Use the existing guard, not another backup dispatch:

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$n/reconcile_production_backup_external_v5.py" --job "$q/production-backup-02-preparation-01/production-backup-02-JOB.json" --package-copy "$q/audit-preparation/package-preparation-3b8ec5e1d68d406ea1f126e834c16288/package" --seeds "$q/production-backup-02-preparation-01/SEEDS.json" --prior-output "$q/production-backup-02-reconcile-01" --prior-output "$q/production-backup-02-reconcile-02" --output "$q/production-backup-02-reconcile-03"
```

Command Prompt/Anaconda: enter `powershell -NoProfile`, then the complete block.
No environment installation is required. Host-only checks use the early-owner
CPU14 wrapper in README_STORAGE with `test_backup_reconciler_v5`:7focused checks
pass, including actual scope06 CENSUS_BEGIN→END on Windows with exact owner/hash
framing, relative/Windows/traversal/overlap/alias rejection, both actual failed
attempt byte counts and missing/duplicate predecessor refusal, retained natural
EOF/failure paths and all-function global-reference scan. No test contacts the
Pi. The synthetic empty census framing is a protocol test, not an actual full
native file-census or transfer claim; its scope is the unchanged actual26-root input.
