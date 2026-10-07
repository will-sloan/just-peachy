# Owned recording export

Actual external export02 closed before copying because immutable Store.export
requests its default exclusive lease, which a read-only store refuses. The fresh
repair uses a read-only export adapter that selects the existing shared kernel
lease for that unchanged export implementation. SQLite remains query-only;
concurrent deletion/exclusive writes remain refused. A focused check uses the
real Store to export under shared leases and verify deletion is blocked. Earlier
external V1/V2 and unstaged09 sources/evidence remain preserved. The repair is
packaged separately in10 and the external entry is now
`launch_recording_export_action_v3.py` with a fresh recording-export-03 label.

`owned_export.py` provides `ExportTask` for History → Export. It runs the
unchanged `SessionStore.export` in a fresh Python process, leaving Tk responsive.
Select one or more kept recordings, choose a new ZIP path, and wait for the
export result. Start and deletion wait while that export is active. Exit requests
child cancellation and waits for its direct reap before closing the launcher.
No capture, model construction, source deletion, or whole-recording RAM copy occurs.

Inputs are the existing store, selected session IDs, destination, private work
directory, verified Python interpreter, and remaining service lifetime. The plan
uses the same segment/artifact sizes and decoded event allowance as Store.export.
It reserves the complete output and another 64 KiB for control receipts above the
configured free-space floor. Parent file and address-space limits stay unchanged.
The fresh child keeps CPU2–3 and the same systemd cgroup, AS128 MiB and stack1 MiB.
Only the child's FSIZE limit becomes the finite planned ZIP bound, and only when
that bound fits the inherited finite hard ceiling. It retains the allocator
variables `MALLOC_ARENA_MAX=1`, `MALLOC_MMAP_THRESHOLD_=131072`, and
`MALLOC_TRIM_THRESHOLD_=131072` before exec.

The actual child `OWNER.json` (PID/start ticks/boot) is fsynced before request or
project reads. The parent verifies this exact direct child and cgroup before ACK.
Storage and helper source hashes, request hash, selected metadata hashes, and the
reservation are rechecked before export. Private outputs below `data/exports/UUID`
include REQUEST, parent and child memory/limit snapshots, child CLOSED, EXPORT,
and CHILD_CLOSURE receipts. The requested destination contains the atomic ZIP.
Timeout is130 seconds by default (bounded1–300); termination has a5-second grace
then direct-child kill. The surrounding finite owned service remains the final
closure boundary. Errors retain evidence and original recordings.

This repairs two distinct conditions: the external export01 failed while lowering
a threaded wrapper to AS128 before importing storage; ordinary GUI export also
inherited a32 MiB soft file cap. Neither failure establishes physical RAM shortage.
The new child avoids imposing the small address-space limit on the existing
wrapper and derives its file allowance from the selected recording. Native memory,
large export, and UI success still require actual evidence; host tests do not
establish those outcomes.

## Host tests: PowerShell

Use the qualified interpreter. The wrapper pins CPU14 and fsyncs the exact early
PC owner before project imports. Tests create only bounded synthetic private data,
exercise a34 MiB export, check the independent plan against Store.export, reject
an insufficient hard file ceiling, and check failed-owner/Exit closure. They also
verify the external V2 helper bytes and its exact frozen08 wrapper derivation.

```powershell
[System.Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[intptr]16384
$env:EXPORT_SOURCE_ROOT='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$q='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
$env:EXPORT_TEST_RECEIPT=Join-Path $q ('storage-preparation\export-test-'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $env:EXPORT_TEST_RECEIPT | Out-Null
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); assert me.cpu_affinity()==[14]; import os,json; from pathlib import Path; p=Path(os.environ['EXPORT_TEST_RECEIPT']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import tempfile,sys,unittest; (p/'tests').mkdir(); tempfile.tempdir=str(p/'tests'); sys.path.insert(0,os.environ['EXPORT_SOURCE_ROOT']); r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_owned_export')); raise SystemExit(not r.wasSuccessful())"
```

## Command Prompt or Anaconda Prompt

Run `powershell -NoProfile` and paste the same block. It uses the exact qualified
interpreter; no environment activation or package installation is required.
Do not manually invoke `--child`: it is an internal parent-owned protocol,
requiring a pinned request, fresh owner directory and exact parent ACK.

## External export of an existing closed recording

`launch_recording_export_action_v3.py` embeds the exact same helper source for
use with immutable08. It derives the owned wrapper from that package, keeps the
existing full package/source-job/closed-owner checks, and uses the existing
host_operations and closed-mirror transfer protocol. It publishes the result
again at output-root `EXPORT.json` for the offload verifier. Its180-second service
and independent full ZIP+16 MiB PC/native reservation remain unchanged.

Use the commands in README_NATIVE_EXPORT.md with the **V3 action filename**, a
fresh `recording-export-03` label and freshly stamped reviewed payload. Preserve
recording-export-01 and its failure evidence. No package modification or repeated
capture is required. After the complete closed PC mirror, verify the actual Pi
ZIP SHA/bytes with `verify_recording_offload.py`; export or copy success alone
does not establish caption or audio quality.
