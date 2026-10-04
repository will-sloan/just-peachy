# Export one kept GUI recording without repeating capture

**Superseded external entry:** actual recording-export-01 on immutable08 failed
with MemoryError before storage import after this V1 driver lowered a threaded
wrapper to AS128 MiB. Original recording bytes were preserved and the owned
unit closed. Use `launch_recording_export_action_v2.py` and a fresh label/admission;
see README_OWNED_EXPORT.md for the shared fresh-child repair, exact file allowance,
focused checks and production History Export integration. Retain this V1 source
and failed evidence; the commands below document its earlier protocol shape.

`launch_recording_export_action.py` is an external `host_operations.py` action.
It uses the exact admitted package's `SessionStore.export([session_id], path)`
and common owned wrapper. It does not edit the package, run models, start
capture, delete audio, or require another GUI run. It therefore works against
an unchanged build07 after its actual GUI job closes.

Inputs are a reviewed payload containing `package`, `package_manifest_sha256`,
fresh actual `boot_id` and `expires_unix` (at most600 seconds), a fresh
`label: recording-export-01`, the actual complete GUI `source_job` object,
`recordings_root` equal to that job's `output_root + /data/recordings`, an exact
kept `session_id`, and `maximum_output_bytes`. Reserve the complete ZIP plus
at least16MiB overhead independently on PC and Pi; this short action accepts
16..256MiB total and retains the5GiB Pi and C:50GiB/G:75GiB floors. A too-small
reservation fails and preserves the original recording. It does not silently
increase any allowance. The service is CPU2–3/200%,64 tasks,180 seconds plus
30-second Stop,128MiB address space inside the export driver,1MiB stack, and
a finite file allowance derived from the selected output reservation.

The action rechecks exact source-job owner/start ticks/boot, systemd invocation
and cgroup closure. The existing full host/native precheck must also be clear.
It writes only a fresh `live-runtime-tests-20261003/recording-export-NN` output
and normal owned service receipts. `EXPORT.json` contains the Pi ZIP SHA256,
byte count, selected ID and source-preservation result. `JOB.json` is the usual
native-component job and is consumed by `monitor_native_job.py` without a new
transfer protocol. Keep the normal full closed mirror before verification.

## Run from PowerShell

These are operator commands after existing user authorization and fresh
machine-state admission. They were **not executed natively during preparation**.
Use actual reviewed private payload/JOB files and a fresh output suffix.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$n='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B "$n\host_operations.py" --label recording-export-01 --action "$n\launch_recording_export_action.py" --payload "$q\recording-export-01-PAYLOAD.json" --writes
# Save the returned actual action_result JOB using the existing dispatch workflow.
& $py -B "$n\monitor_native_job.py" --job "$q\recording-export-01-JOB.json" --output "$q\recording-export-01-monitor-01"
$export=Get-Content -Raw "$q\recording-export-01-monitor-01\closed-output\EXPORT.json" | ConvertFrom-Json
& $py -B "$n\verify_recording_offload.py" --zip "$q\recording-export-01-monitor-01\closed-output\selected-recording.zip" --source-sha256 $export.zip_sha256 --source-bytes $export.zip_bytes --maximum-uncompressed-bytes $export.zip_bytes --output "$q\recording-export-01-pc-readback-01"
```

`host_operations`, the monitor and offload verifier publish actual early PC
owner receipts. Use the CPU14 early-owner wrapper in `README_STORAGE.md` for
the focused host fixture `test_native_export`. It runs the exact driver with
two tiny generated sessions and a host-only resource-limit stub, checks that
only the selected ID is present, checks original metadata survives, then
uses the real independent ZIP verifier. This is a host contract test, not a
native export or real recording qualification.

## Command Prompt and Anaconda Prompt

Use the same qualified interpreter (no environment activation is necessary).
Either run the PowerShell block with `powershell -NoProfile`, or set `N`, `Q`
and `PY` to the exact values above and use:

```bat
"%PY%" -B "%N%\host_operations.py" --label recording-export-01 --action "%N%\launch_recording_export_action.py" --payload "%Q%\recording-export-01-PAYLOAD.json" --writes
"%PY%" -B "%N%\monitor_native_job.py" --job "%Q%\recording-export-01-JOB.json" --output "%Q%\recording-export-01-monitor-01"
```

Read the exact SHA and byte values from the mirrored `EXPORT.json` and supply
them to the final verifier command above. A verified ZIP is copy integrity;
it makes no audio-quality, touch-input, or sustained-throughput claim.
