# Optional bounded source batches

`source_batch.py` adds an explicitly selected source IPC path to
`installed_source.py`. The binding must set `source_batch_ms: 100` and the live
configuration must retain `block_frames: 480`. The default is `source_batch_ms:
0`, preserving the unbatched path used by frozen build04. Enabling this in a
future immutable binding requires fresh native evidence for that configuration;
these host checks do not establish throughput or raw qualification.

The purpose is to reduce per10ms fsync/SQLite overhead observed in the initial
five-second raw trial. The subsequent actual unbatched build04 trial03 passed
exact80,000 processed/raw samples and physical/readback checks, but retained
192 queued blocks and maximum source lag1.927258052 seconds. Evidence remains
at the private `raw-qualification-03-monitor-01/closed-output/qualification/RAW_QUALIFICATION.json`
under the campaign's local live-runtime directory. Correctness of that frozen
source does not qualify this changed module or sustained performance. This
later frozen configurations require their own native qualification.

Actual source-only trial05 on frozen build06 passed with `source_batch_ms=100`
and explicit480-frame callback binding:80,000 processed/raw samples,
320,000 processed float bytes and1,280,000 four-channel PCM32 bytes, matching
source clocks and independent readback, physical source closure and restored
routes. Maximum source lag was0.035875845 seconds with3 pending blocks and51
processed acknowledgements, versus1.927258052 seconds/192 pending blocks in
unbatched trial03. Callback faults and dropped samples were zero. The private
receipt is `raw-qualification-05-monitor-01/closed-output/qualification/RAW_QUALIFICATION.json`
with SHA256 `c25235ad31d0f29362f5b6c72019c920856caf912f47c8983cb8fbe494d00391`.
This is a five-second source-only observation, not a combined model benchmark
or sustained-session qualification. Later07 source diagnostic forwarding
changes its module hash and needs fresh raw evidence; this pass is not reused
as an automatic admission for changed source.

The child collects at most10 original blocks and1600
processed samples, approximately100ms. Each original callback clock, native
extent, model extent and beam packet remains separate. No callback, calibration,
sample mapping or timestamp is changed. A deadline, final allocation boundary
or explicit Stop flushes the already-read partial batch without omitting it.

For raw capture, the retained converter flushes once per group (at most25,600
raw bytes), obtains exact `ACK_RAW` after the spool commit, and only then sends
the matching processed group (at most6,400 bytes). The parent requires this raw
extent before committing processed audio. It validates every original
CaptureTimeline extent, beam observation and spatial update, then performs one
journal append and one bounded `source_batch` event containing all original
metadata and per-block hashes. `ACK_AUDIO` follows both successful publications.
Two raw packets before the matching processed group, unbatched AUDIO in batch
mode, reordered blocks, oversized groups and wrong acknowledgements fail.

The converter's64KiB automatic flush cannot fire inside a25.6KiB group because
the pending buffer is empty after each completed group. Final raw publication
still occurs after physical Stop; with a successful last group it has no
unacknowledged raw bytes left to emit. A failed processed commit may leave an
acknowledged raw prefix; this is a failed session, never a successful paired
recording. Failure receipts retain the confirmed cursor and physical cleanup.

Additional audio buffers remain below128KiB: raw pending/flush data are each
at most25.6KiB, processed group6.4KiB, and bounded IPC/spool copies. Sending uses
memoryview pieces without constructing another full audio packet. This bound
describes added audio staging, **not total process memory**: the retained source
ring, NumPy, Python metadata objects and the operating system are separate.
Metadata is separately bounded to10 rows of at most2048 serialized bytes and
a24KiB batch header. No entire recording is loaded in RAM.

## Inputs and outputs

Inputs are the existing pinned installed source/route, explicit binding flag,
session sample allowance, and the isolated child/parent pipes. The independent
existing unit, ownership, consent, disk reserve and physical closure checks
still apply. There is no standalone capture command in this module.

Outputs retain the same exact raw/processed spool and source clock.
`SOURCE_CLOSE.json` includes `source_batch_ms` and processed acknowledgement count.
Batch mode writes `source_batch` events; unbatched mode keeps `source_block`
events. Each batch event contains every original block's metadata, source
sample start/count, beam packet and processed SHA256. Consumers must inspect
those rows rather than assume one event equals one callback.

## Focused host checks: PowerShell

The tests use synthetic samples and the pinned retained converter. They open
no model, microphone, GUI or network connection. Inputs are the immutable raw
factory path and a fresh private evidence directory; outputs are the actual
CPU14 `REGISTERED_OWNER.json`, unittest results and `TEST_RESULT.json`.

```powershell
$env:LIVE_BATCH_ENTRY = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/storage-preparation/source-batch-' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $env:LIVE_BATCH_ENTRY | Out-Null
$env:LIVE_RAW_FACTORY = 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/reference-v28/code/field_live_source_factory_v6.py'
Set-Location 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_BATCH_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_source_batch')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures)))); raise SystemExit(not r.wasSuccessful())"
```

## Command Prompt and Anaconda Prompt

Use the qualified Python directly in either prompt; no additional environment
installation or activation is needed.

```bat
set "LIVE_BATCH_ENTRY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\source-batch-%RANDOM%-%RANDOM%"
mkdir "%LIVE_BATCH_ENTRY%"
set "LIVE_RAW_FACTORY=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\reference-v28\code\field_live_source_factory_v6.py"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import os,json; from pathlib import Path; p=Path(os.environ['LIVE_BATCH_ENTRY']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_source_batch')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures)))); raise SystemExit(not r.wasSuccessful())"
```

The five checks cover ten-block splitting, the exact79,999→80,000 final sample,
one raw/processed ACK pair per group, explicit-Stop partial flush, acknowledgement
or fsync failure, duplicate/missing raw prefix refusal, and partial scatter
transport writes. Native source lag and combined CPU/RAM remain unqualified.
