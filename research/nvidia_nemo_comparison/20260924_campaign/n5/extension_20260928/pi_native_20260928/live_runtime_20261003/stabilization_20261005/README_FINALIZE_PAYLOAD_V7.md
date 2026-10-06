# Prepare actual closed build27 job finalization

Purpose: derive a fresh finalization payload for the exact external
`native_stabilization_check_v6.py` after the actual job has completed naturally
and its complete output has been independently copied to the PC. It performs
no native action and never publishes PASS. The native helper independently
rechecks current owners, package inventory and an empty cgroup before publishing
`NATIVE_CHECK_V2.json`.

Inputs: the actual `classic-ui-check-NN-JOB.json`, completed matching
`classic-ui-check-NN-monitor-01`, unused `classic-finalize-NN-MM` dispatch label,
current boot UUID, actual build27 manifest SHA, exact helper6 SHA and the actual
closed expanded host package. All three identities are explicitly supplied;
historical boot, helper or manifest values cannot qualify a changed job.
The supplied expanded package must be a canonical private audit preparation's
`package` folder and its manifest/retained closure checker must match the job.

The complete V4 closed-monitor/job checks remain: original JOB backup/restore,
monitor-only root-identity augmentation, full per-member hashes and membership,
natural zero exit, exact recorded owner/cgroup closure, full workflow and the
unchanged pure `require_closed` worker checker. Failed/incomplete mirrors are
rejected. Native helper6 action bytes must match the actual JOB's helper SHA.
Existing preparers V1 through V6 remain immutable.

Outputs: unique private CPU14/exact-FILETIME owner, original 1MiB/600-second
scope, preparer/README/action/payload with independent backups and restore
copies, compact `INPUT_BINDING_REVIEW.json` and `SOURCE_CLOSED.json`. Host
C:50GiB/G:75GiB floors, member/tree bounds and all closure checks remain.

## PowerShell

Replace the helper SHA with the actual backed helper6 SHA bound by JOB32.

```powershell
$S='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$S/prepare_stabilization_finalize_v7.py" --job "$Q/classic-ui-check-32-JOB.json" --monitor "$Q/classic-ui-check-32-monitor-01" --label classic-finalize-32-01 --boot-id 31ead85c-17cf-49c3-909a-8f2e1108a151 --manifest-sha256 914e644c89af7a875f2aa91171e2a04264cd8cd698dafdb6331dda7380a53b94 --helper-sha256 ACTUAL_JOB_HELPER_SHA --host-package "$Q/audit-preparation/stabilization-package-795d5493134f4aeda678054394b15c43/package"
```

## CMD and Anaconda Prompt

```bat
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
set "Q=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/prepare_stabilization_finalize_v7.py" --job "%Q%/classic-ui-check-32-JOB.json" --monitor "%Q%/classic-ui-check-32-monitor-01" --label classic-finalize-32-01 --boot-id 31ead85c-17cf-49c3-909a-8f2e1108a151 --manifest-sha256 914e644c89af7a875f2aa91171e2a04264cd8cd698dafdb6331dda7380a53b94 --helper-sha256 ACTUAL_JOB_HELPER_SHA --host-package "%Q%/audit-preparation/stabilization-package-795d5493134f4aeda678054394b15c43/package"
```

After exact host closure and complete current-owner preread, Root dispatches
printed ACTION/PAYLOAD using `host_stabilization_operations_v5.py --writes`.
Copy and verify the newly published native receipt in a new full mirror.
The pre-finalization closed mirror cannot contain the future receipt and must
not be relabeled. Short functional qualification is not sustained or accuracy
evidence.

