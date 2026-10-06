# Prepare immutable build28 staging

Purpose: bind the actual closed build28 archive and expanded package to the
unchanged SHA-pinned stage24 installer/action. This host preparation never
deploys, activates the desktop or starts an application, microphone or model.
Build26 and earlier releases remain immutable rollback points.

Inputs: the actual closed package folder and archive, exact archive/manifest
SHA and a freshly verified current Pi boot UUID supplied with `--boot-id`.
The old stage24 payload is retained only for its installer/action and schema;
its historical boot is not reused as current authority. The preparer verifies
the supplied UUID shape and binds it into the new payload. The guarded native
dispatcher must still independently verify that boot and current resources.
Full archive and expanded member membership/bytes are independently verified.

Outputs: a unique private CPU14/exact-FILETIME registered preparation with
backed action, installer, payload, README and preparer, independent restore
copies, complete readback and `SOURCE_CLOSED.json`. The original 2MiB archive,
8MiB/600-second preparation, disk floors, per-target allocation and exact
installer/action SHA guards remain. Allocation is the whole expanded package
+ archive + `(directories+1)*65536` + 65536, independent of PC evidence copies.

## PowerShell

Replace the placeholders with `BUILD_RESULT.json` values and the fresh
read-only baseline's actual boot; never copy a historical boot blindly.

```powershell
$S='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$S/prepare_stabilization_stage28.py" --package 'ACTUAL_PACKAGE28' --archive 'ACTUAL_ARCHIVE28' --archive-sha256 ACTUAL_ARCHIVE_SHA28 --manifest-sha256 ACTUAL_MANIFEST_SHA28 --boot-id ACTUAL_CURRENT_BOOT_UUID
```

## CMD and Anaconda Prompt

```bat
set "S=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%S%/prepare_stabilization_stage28.py" --package "ACTUAL_PACKAGE28" --archive "ACTUAL_ARCHIVE28" --archive-sha256 ACTUAL_ARCHIVE_SHA28 --manifest-sha256 ACTUAL_MANIFEST_SHA28 --boot-id ACTUAL_CURRENT_BOOT_UUID
```

After actual host closure, Root dispatches the printed ACTION/PAYLOAD under
unused label `stabilization-stage28-01` using
`host_stabilization_operations_v5.py --writes` and its fresh measured guards.
Native package inventory/readback is distinct from functional qualification.

