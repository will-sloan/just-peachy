# Closed speech19 work-producer size inspection

Purpose: measure the actual failed speech session's native/log/text work files
without returning their contents or repeating the successful SQLite queries.
The failed recording and build24 remain unchanged.

Inputs are exactly the same current boot/build24 pin, original failed19 JOB,
request hash, session/launch UUID and clear owner census as the first numeric
inspection, with a new <=600s payload. Full package membership/pins and the
main/unit/cgroup/worker/source exact physical closure are rechecked before read.

Outputs are per-producer and per-file byte counts, total file/directory counts,
inventory digest, old owner/unit closure and source/model receipt SHA/booleans.
No transcript text, model vectors, media or file contents are returned. No
SQLite query, Store constructor, native payload write or capture is performed.

The closed work tree allows at most512files,64directories,32MiBperfile and
128MiBtotal, with an8s walk deadline and64KiB response cap. Existing session
lock is held SH if present, without creating it. Tree membership, regular file
identities and extents must match before/after; symlinks/hardlinks are refused.

The delivery task prepares exact backed ACTION/PAYLOAD/README files with an
independent restore and closes its early CPU14 owner before native dispatch.

## PowerShell

```powershell
$source = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$prep = 'ACTUAL_CLOSED_SPEECH19_WORK_PREPARATION'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$source/host_stabilization_operations_v2.py" --label speech-work-inspect19-01 --action "$prep/ACTION.py" --payload "$prep/PAYLOAD.json"
```

## CMD or Anaconda Prompt

```cmd
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_PREPARATION=ACTUAL_CLOSED_SPEECH19_WORK_PREPARATION
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/host_stabilization_operations_v2.py" --label speech-work-inspect19-01 --action "%JP_PREPARATION%/ACTION.py" --payload "%JP_PREPARATION%/PAYLOAD.json"
```

Omit --writes; retain the existing FSIZE0 metadata envelope. Root performs the
native dispatch and independently closes its utility; host preparation does
not establish a native outcome.
