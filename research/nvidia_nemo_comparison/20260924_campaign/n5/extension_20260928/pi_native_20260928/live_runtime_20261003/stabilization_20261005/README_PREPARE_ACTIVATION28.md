# Prepare actual build28 desktop activation

Purpose: prepare the unchanged SHA-pinned V4 desktop-only transaction from a
new independently finalized native build28 PASS and real prior build26 desktop
activation. It performs no native action and does not start capture or models.
The native transaction separately checks the current boot, package/proof,
current shortcut/autostart hashes, baseline resources and closed capture before
backups, atomic mutation and readback. One launcher shortcut and disabled login
startup remain. Build26 and all existing data/galleries/releases are preserved.

Inputs: actual `NATIVE_CHECK_V2.json` in the new full finalized PC mirror,
matching actual finalizer dispatcher `RESULT.json`, actual current boot UUID and
manifest SHA. The finalizer's proof must exactly match the copied receipt and
recorded native path, and its exact same-boot utility identity must be absent
after SSH. The proof must explicitly pass portrait UI, capture function,
worker/main/unit closure and independent native finalization.

The fixed prior build26 receipt at
`operation-stabilization-desktop26-01/dispatch/RESULT.json` supplies expected
desktop SHA `d014baa64a8330bc802a59616c8d3a0874a97402d6ff9cef77d29c6dd8d24fe4`
and disabled-autostart SHA
`8841a9fe0f62b662906bb9cb0d8914ac9bab86ebb7c4d28f7699194971f39206`.
That historical receipt's boot is preserved as history; it is not substituted
for the explicitly supplied current boot. Those prior file hashes are compare
and swap expectations, not invented current observations. The native unchanged
transaction rechecks actual bytes before mutation.

Outputs: a unique private CPU14/exact-FILETIME registration, original 2MiB/
600-second scope, preparer/README/action/proof/finalizer/prior-desktop/payload
with independent backup/restore copies, `INPUT_REVIEW.json` and
`SOURCE_CLOSED.json`. C:50GiB/G:75GiB floors remain. Native activation separately
reserves 16MiB for complete target and PC metadata/restore copies. Preparation
does not publish activation success or a new native qualification.

## PowerShell

Replace the finalizer-result placeholder with the actual newly closed
dispatcher result path. Run after the complete finalized mirror exists.

```powershell
$S='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$S/prepare_stabilization_activation28.py" --native-check-file "$Q/classic-ui-check-32-finalized-monitor-01/closed-output/NATIVE_CHECK_V2.json" --finalizer-result 'ACTUAL_FINALIZER_DISPATCH_RESULT' --boot-id 31ead85c-17cf-49c3-909a-8f2e1108a151 --manifest-sha256 ACTUAL_BUILD28_MANIFEST_SHA
```

## CMD and Anaconda Prompt

```bat
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
set "Q=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/prepare_stabilization_activation28.py" --native-check-file "%Q%/classic-ui-check-32-finalized-monitor-01/closed-output/NATIVE_CHECK_V2.json" --finalizer-result "ACTUAL_FINALIZER_DISPATCH_RESULT" --boot-id 31ead85c-17cf-49c3-909a-8f2e1108a151 --manifest-sha256 ACTUAL_BUILD28_MANIFEST_SHA
```

After exact host closure Root uses printed ACTION/PAYLOAD through
`host_stabilization_operations_v5.py --label stabilization-desktop27-01 --writes`.
See `README_STABILIZATION_ACTIVATION_V4.md` for native transaction/rollback and
complete private readback. A short successful check does not establish all
mode combinations, sustainable real-time operation or speaker accuracy.

