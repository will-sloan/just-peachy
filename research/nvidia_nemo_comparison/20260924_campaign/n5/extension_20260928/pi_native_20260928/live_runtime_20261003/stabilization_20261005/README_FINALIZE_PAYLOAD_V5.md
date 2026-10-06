# Prepare a closed human-window job for native finalization (V5)

Purpose: prepare the existing check helper's unchanged `finalize` operation after
its real worker and service have ended and the complete output has been copied
independently to the PC. The helper prepares payloads only. The native operation
independently rechecks current owners, full package inventory and empty cgroup,
then publishes `NATIVE_CHECK_V2.json`. Host preparation never publishes PASS.

Inputs: actual `classic-ui-check-NN-JOB.json`, its completed
`classic-ui-check-NN-monitor-01`, and one unused `classic-finalize-NN-MM` dispatch
label. This iteration is pinned to build25 manifest
`6f548c3aa4005a43aaf4da378c364b0a2c5f17a90a36c223474e85c3b2468df8`
and actual boot `0561d730-3cad-48e0-940a-fe3930c89665`. A reboot requires a
fresh reviewed derivative. It works only for this exact V5 live-check helper; saved checks use their own preparer.
It does not assume that quiet capture establishes speech or embedding quality.

Outputs: fresh private preparation directory, early actual CPU14 owner,
1 MiB/600s scope, exact source/README/action/payload plus separate backup and
restore files, compact full-mirror binding review and source closure. The native
action source remains byte-for-byte identical. The only payload fields are
`operation`, `output_root`, `package`, `package_manifest_sha256`, and `data_root`.

Checks bind original JOB backup/restore, monitor-only root-identity augmentation,
all mirrored member hashes/membership, natural return0, exact owner/cgroup
closure, complete workflow receipt and unchanged pure worker closure checker.
They preserve incomplete or failed evidence and refuse its finalization.

## PowerShell

```powershell
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$source = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$private = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
& $py -B "$source/prepare_stabilization_finalize_v5.py" --job "$private/classic-ui-check-21-JOB.json" --monitor "$private/classic-ui-check-21-monitor-01" --label classic-finalize-21-01
```

After exact host-owner closure and the complete current-owner preread, use the
printed preparation path for the existing authorized native dispatcher:

```powershell
$prep = 'ACTUAL_PREPARATION_PATH'
& $py -B "$source/host_stabilization_operations_v2.py" --label classic-finalize-21-01 --action "$prep/ACTION.py" --payload "$prep/PAYLOAD.json" --writes
```

## CMD or Anaconda Prompt

Use the installed environment directly; no package installation is required.

```cmd
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_PRIVATE=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/prepare_stabilization_finalize_v5.py" --job "%JP_PRIVATE%/classic-ui-check-21-JOB.json" --monitor "%JP_PRIVATE%/classic-ui-check-21-monitor-01" --label classic-finalize-21-01
set JP_PREPARATION=ACTUAL_PREPARATION_PATH
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/host_stabilization_operations_v2.py" --label classic-finalize-21-01 --action "%JP_PREPARATION%/ACTION.py" --payload "%JP_PREPARATION%/PAYLOAD.json" --writes
```

Replace the job, monitor and both labels together for checks16 onward. Use a
new dispatch suffix for each separately authorized attempt; preserve failures.
Native finalization writes inside the existing owned output, so `--writes` is
required. Copy and verify the new native receipt afterwards. A previously closed
pre-finalize mirror cannot contain the future receipt and is not relabeled.


This derivative uses the actual external native_stabilization_check_v5.py source
SHA 0690f255b0fc8fef4ee76b6c32aefc2297de9751d18508ac0a29a7e89a5e1dce.
Human check18 changes its source ceiling to70s, ordinary Stop to60s, and independent
output/copy reservations to256MiB each. These affect the launch contract only;
the native finalize function remains exactly identical. The preparer retains
all original owner, boot, package, natural exit, full mirror and cleanup guards.
V1/V2/V3 remain immutable and refuse V4 JOBs because their helper-source identity differs.
Do not generate a finalize payload until the matching actual monitor is complete.

V3 repairs only the external chooser instrumentation title using an ASCII escape.
Check16 remains failed and preserved; it cannot be finalized as a successful session.
All nativefinalizeAST and host owner/closure/hash/membership guards remain exact.

V4 source70 plusload120 plusdrain120 pluscleanup60 totals370s. The retained
150s authorization reserve requires520s remaining inside540s, leaving20s startup
room. Stop60 leaves10s before EOF. Check17 was rejected by this exact guard
and remains failed. Finalization requires the successful actual18 closed monitor.

V5 selects the fresh build25 speech-storage/cleanup candidate and exact helper V5. Native finalize AST is unchanged from V4; only source/package identities change in this preparer. Failed19 remains preserved and cannot be finalized. Fresh70s metadata uses double reserve, half text/half SQLite and separately allocated256KiB terminal cleanup pool. No actual check21 success is claimed by preparation.
