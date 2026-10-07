# Exact build31 stage payload allowance

Purpose: dispatch the already sealed build31 stage payload through the existing
guarded maintenance dispatcher. Stage31-01 stopped on the host before SSH:
its 2,142,512-byte JSON payload exceeded the original 2,097,152-byte bound.
The failed operation and frozen V8, package, action and installer remain intact.
This derivative changes one generated `main` payload-size expression. It uses
the retained `_main_source` string because the existing compiled main has no
inspectable source file. Reversing the one replacement must restore that string
exactly before it can run.

The default remains 2 MiB. A finite 3 MiB allowance applies only to operation
`core-stage31-02` with `--writes`, exact reviewed action SHA
`4f5876f32a634db420baf78583a7a0ebac7d27b17bab52aace867d78df0d1c74`
and exact payload SHA
`5af9ec3f9c5fb8a7fedae0f7c2c00eb80515cfe8039723e23feb79b50ef8eb6d`.
No other action, label, changed payload or later build receives this allowance.
Inputs are immutable owned prepared files; the admission uses the inherited
ordinary single-link file checks, stable readback and strict duplicate-key JSON
parser before the dispatcher performs its existing source backups/readback.

The allowance also validates the following actual sealed bindings before SSH:

- Build31 manifest `4b9e8fbc5c121435ecd46684b8bf55aa0996917e23892e883979668511d43767`.
- Archive `e6d5e40c8c14ef5cc0e2e02d7d02894cdb48ac7a663cf34a334da36a0cd66db3`,
  1,592,165 decoded bytes, retaining its 2 MiB archive bound.
- Installer `b4cbc107259556f901da1e47462b9ba238b766e56b7910c3c5982ea3fee68ad6`,
  retaining its 128 KiB decoded bound. Only its pure archive validator runs on
  the host; its native stage/activation entry point does not run there.
- Root-reviewed source manifest
  `6894adf19266061a15a71dc103d7317303652d68d58a4e27b74016430caaf4ca`.
- Exact native target ending `field-runtime-v29-build-31`, current boot
  `e60e67c2-f3f5-4b8b-8eab-2613df2de37e`, all 425 regular archive members,
  7,078,265 expanded bytes, eight directories, and the complete 9,325,790-byte
  target reservation. The pinned existing validator checks every member SHA,
  safe path, unique name, manifest declaration and expanded/member bound.
- Root-accepted complete backup14 and closed owner 68815/start1489488 on that
  boot. Actual `COMPLETE.json`, `RESULT.json` and `CENSUS.json` are read again
  and checked against accepted hashes `9aa11fd4...1ee80e`, `1154c795...2f879`
  and `509432c0...8a263`. All full hashes are constants in the source. The
  existing stage admission retains its complete backup and source checks.

V8's finite native metadata envelope remains 256 MiB address space with a
978 MiB initial available-memory floor, CPU3, 1 MiB stack, subsequent 850 MiB
admission, actual peak-RSS telemetry, strict SSH, disk floors, owner/capture/
lease checks, lifetime and reservations. The host retains early CPU14 PID and
creation-FILETIME registration, source backups/restores, 600-second lifetime
and the existing 16 MiB output envelope. Runtime worker/UI/model memory limits
and recording data are unchanged. This action stages a package; activation
and actual model/capture checks are separate operations.

Inputs: the exact backed stage31 preparation below, accepted backup14 metadata,
the reviewed dispatcher source, its README and existing immutable parent
dispatcher. Outputs: fresh private early-owner/source backups, a
`STAGE31_PAYLOAD_ADMISSION.json` host receipt when the exception is actually
admitted, and the existing private operation result/raw I/O/utility ownership
and exact closure evidence. Source preparation alone is not a staging result.

Run only after root review of this source and available guarded host/native
slots. Use the fresh operation label once; preserve failed labels. PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$p='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/caption-stage31-preparation-e3fa730747104732842a8352a0a42703'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v9.py" --label core-stage31-02 --action "$p/ACTION.py" --payload "$p/PAYLOAD.json" --writes
```

Command Prompt or Anaconda Prompt: enter `powershell -NoProfile`, then paste
the same block. The pinned environment supplies `psutil`; do not substitute
the WindowsApps Python alias. The action grants no general payload-cap
increase. A new payload or operation needs its own reviewed derivative.

After actual natural return, independently verify the registered PID plus
creation FILETIME is absent and retain exact return code, source closure,
backups/restores and result evidence. An admission receipt is a host check;
only the actual native stage result and independent readback establish staging.
