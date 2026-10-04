# Persistent session storage

`storage.py` implements the disk storage layer for the isolated live runtime.
It does not capture audio, load a model, connect to a network, install software,
or access a Raspberry Pi. `test_storage.py` uses only synthetic audio and private
temporary directories. Python 3.11 or later and its standard library are enough.

## Inputs and outputs

Create `SessionStore(root, StoragePolicy(...))` with a dedicated empty directory
or an existing directory previously created by this module. The default reserve
is the larger of **5 GiB** and **5% of the actual filesystem capacity**. It does
not assume a 32 GB device. Deployment policy changes require measured capacity
and the deployment's approval; tests explicitly use a zero reserve in their own
temporary stores.

`begin(spec)` takes these JSON-compatible fields:

| Field | Meaning |
| --- | --- |
| `duration_seconds` | Positive maximum allocated session duration; required. |
| `sample_rate` | Processed mono rate, default 16000. |
| `mode` | `processed` (default) or `raw_processed`. |
| `metadata_reserve_bytes` | Additional native/event/trace disk allocation, default 0. The controller must separately enforce this allowance on its metadata writers. |
| `raw` | Required in raw mode: `sample_rate`, `channels`, `sample_width_bytes`, `encoding`, and `qualification`. |

For the existing audioraw route, specify **4 channels × 16000 samples/second ×
4-byte PCM32**, not a presumed 48 kHz route. Other explicitly qualified raw
formats can be described. `qualification` must contain `qualified: true` and
evidence metadata (for example a qualification receipt identifier). Storage
checks that metadata is present; the capture integration supplies real evidence.
An explicit source-only qualification may instead set `raw_qualification: true`
and `{qualified: false, qualification_run: true, evidence: <admission>}`. This
preserves experimental capture evidence without inventing a qualification pass;
the normal model worker rejects that mode. See `README_RAW_CAPTURE.md`.

Each `begin` returns a `SessionSpool` with a unique persistent `session_id`.
Outputs live under `sessions/<session_id>/`: an owner marker, specification,
sealed exact little-endian mono float32 segments, PCM16 replay WAV segments,
optional raw segments, and an atomically replaced `session.json` receipt.
SQLite stores indexed history, sample counts, segment metadata, captions, every
caption revision event, failure events, and registered artifact paths. Memory
does not grow with the audio duration or the number of historical sessions.
Caption payload size and history page size are bounded; caption count is not
silently capped at 2048.

## Integration contract

1. Call `store.capacity(spec)` to preflight the actual volume. Admission accounts
   for exact float32 audio, PCM16 replay, qualified raw, segment overhead, and
   `metadata_reserve_bytes`. This is a conservative logical allocation, not an
   OS disk reservation; other processes can consume space. Each append rechecks
   the reserve and fails closed if space is unavailable.
2. Call `spool = store.begin(spec)`. A nonblocking kernel file lease allows one
   active session across processes. Failed and cancelled sessions consume disk
   for their receipts/data but never consume a fixed recording slot. Opening a
   store queries SQLite and does not enumerate past session directories.
3. Feed bounded `spool.append_processed(start_sample, float32bytes)` calls.
   Samples must be contiguous, finite, mono float32 little endian. The maximum
   input block is `spool.store.policy.max_append_bytes` (default 4 MiB). A full
   append flushes and fsyncs its files and commits its sample cursor before
   advancing `spool.processed_samples`. A failed append does not advance that
   published cursor. Use a writer worker, not an audio callback, for these
   blocking filesystem operations.
4. Optional `spool.append_raw(start_sample, raw_bytes)` uses raw **frame** offsets
   and the qualified raw format. `read_processed(start_sample, count)` on the
   spool returns bounded exact bytes from old or current committed segments;
   it never materializes the full recording. This method also works after stop.
   `spool.raw_receipt()` independently hashes committed raw segments with bounded
   reads and returns authoritative frame/byte counts and readback SHA256.
5. Stop capture, drain every accepted upstream block, and only then call
   `spool.stop(final_sample=expected_processed_count)`. A mismatched boundary is
   rejected. Stop seals all segments and releases the active lease. A stopped
   session survives restart while the user chooses its disposition.
6. Choose `store.keep(id, include_raw=False)`,
   `store.keep(id, include_raw=True)`, or `store.discard(id)`. Raw plus processed
   requires qualified raw covering the same duration. Keeping processed only
   removes raw audio explicitly. Discard retains a diagnostic receipt and
   removes audio and registered native artifacts. A kept recording requires the
   distinct deliberate `store.delete(id, confirm=True)` operation to delete.

Other API calls:

- `spool.fail(reason)` / `spool.cancel(reason)` close the active session, retain
  its receipt, and release the lease. Failed partial files remain for explicit
  discard/delete. After a process crash, the next `begin` marks the single
  abandoned active row failed; it does not delete personal recordings.
- `store.history(limit=25, before=None)` returns `items` and a `next_cursor`.
  Pass that cursor as `before` for the next, older page. `store.read(id)` returns
  one metadata record and its authoritative processed/raw sample counts.
- `store.iter_processed(id, block_samples=16384)` yields `(start_sample, bytes)`
  for a stopped or kept recording with no full-audio allocation.
- `store.write_caption(id, caption_id, start_sample, end_sample, text,
  speaker=None, provisional=True, provenance=None)` updates a stable caption ID
  and appends its next revision event when a stable field changes. Identical
  fields/provenance preserve the revision and create no repeated event or GUI
  refresh. `store.captions(id, limit=25, after=0)` and
  `store.events(id, limit=25, after=0)` return chronological metadata pages.
  Pass `next_cursor` as `after`. The controller supplies source-time intervals;
  storage never substitutes wall-clock arrival time for source time.
- `store.write_event(id, event_type, payload_dict)` persists a fault or other
  event, including after a session has failed.
- `store.latest_captions(id, limit=40, after_revision=None)` returns an indexed
  chronological tail and `revision_cursor`. Pass the cursor as `after_revision`
  on the next poll; `changed: false` returns no rows. Corrections to stable IDs
  advance the revision cursor, including after the history exceeds 100 captions.
- `store.register_artifact(id, 'work/native/result.json', role='native')`
  registers a completed file beneath the session's owned `work/` directory.
  Register every intended native metadata file before keep/export/delete.
  Unregistered files prevent deletion; they are never silently removed.
- `store.export([id1, id2], new_zip_path)` streams selected kept sessions to one
  new ZIP. A single session uses the same API with one ID. Each directory in the
  ZIP includes audio segments, source-time metadata, `segments.jsonl`,
  `captions.jsonl`, `events.jsonl`, and `artifacts.jsonl`. Replay WAV chunks are
  ordered by the manifest; individual WAVs remain below large-WAV file limits
  with the default segment size. The source recordings are preserved.
  ZIP central-directory metadata remains in Python RAM, so the configurable
  `max_export_entries` defaults to16,384 entries per export. Preflight refuses
  larger selections before creating the ZIP and requests smaller batches. This
  does not limit the number of stored recordings or history pages.
- `store.close()` fails and releases any unfinished active spool it owns.

`SessionStore(root, read_only=True)` requires an existing owned store and opens
SQLite with `mode=ro`/`query_only=ON`. Whole-recording replay uses shared session
leases and `processed_segment_page(..., after=-1, limit=32)` to avoid holding a
SQLite reader transaction while audio is paced. Shared readers exclude keep,
discard and delete operations. See `README_SAVED_REPLAY.md` for complete-session
float32 replay and its index/hash/source-clock checks.
The general segment/artifact iterators also release their SQLite connection
after each indexed32-row page, before yielding to slow export or playback I/O.
An old-session export therefore does not hold a database read transaction across
the audio transfer and block another live session's metadata commits.

## Long-session metadata and discard scope

Audio memory remains bounded by append/read block size;300s and3600s produce
30 and360 default10-second segments respectively. History reads only the
requested indexed page (25 by default,100 maximum), latest captions keep40
rows, the controller caches128 caption rows and120 health rows, and no startup
scan walks all recording directories. Those bounds do not qualify the resident
native model footprint; native memory telemetry remains separate.

SQLite metadata now has a persistent per-session conservative logical ledger.
For legacy specs its allocation is `metadata_allowance_bytes + metadata_reserve_bytes // 6`
and native segmented writers retain their separate5/6 aggregate. New specs
with `metadata_split=text3_sqlite1_v1` use1/4 SQLite and3/4 text under the same
total, as detailed below; persisted prior ledger limits remain unchanged. Each stored
event is charged twice its stored payload bytes plus1024 bytes of row/index
allowance. Caption revisions include their event and current-caption payload
cost. Up to one quarter of the base allowance (at most256KiB) remains for closing
artifact-index registration after normal metadata reaches its ceiling. Admission
and every write still check the actual free-space floor; SQLite journal/file
ceilings remain independently derived. The ledger is logical accounting rather
than an exact allocator-page census. Existing sessions are counted by indexed
SQL aggregates only on their next metadata write; startup never scans history.
Exhaustion rolls back the attempted row and reports failure without consuming
another session's allocation. Bounded session/failure receipts remain available.

Independent event rows up to64KiB use fast zlib level1 only when smaller.
SQLite stores explicit `payload_encoding`, original UTF-8 length and SHA256;
plain legacy rows remain readable. Decoding checks the64KiB expansion bound,
exact length/hash, end-of-stream and absence of trailing/unconsumed bytes.
`events()` and exported `events.jsonl` expose the original fields, clocks and
sample extents, without codec wrappers. Export reservation counts the original
JSON size, not compressed storage size. Larger valid caption-revision JSON
remains plain and bounded; it is never decompressed without a finite limit.

Read-only host review of the actual five-second raw05 corpus recovered all55
events exactly:364,669 original payload bytes became76,613 stored bytes (21.0%).
Conservative ledger charge was209,546 bytes. CPU14 host codec/verification took
0.015625 CPU seconds; this is not Pi performance evidence. A naive one-hour
projection is about151MB of source-only ledger usage against about161MB
available under the current3600s metadata policy, before combined caption/health
variation. Real300s and hour native checks must confirm margin; these numbers
do not claim sustained admission or justify increasing existing resource caps.

`Discard audio` acts only on the selected unkept session's generated audio and
registered work artifacts. It retains that session's SQLite transcript/events
and diagnostic session receipt. A replay's original kept source, other sessions,
and unknown files are preserved. Deliberate individual Delete removes the
selected session's indexed transcript/events as well, but refuses unknown files.
This distinction matters for private transcript data: audio discard is not a
request to erase all metadata. Failed/cancelled sessions retain receipts and
never consume a global recording slot.

Focused growth checks use the existing registered PowerShell/CMD/Anaconda test
wrappers below, replacing `test_storage` with these exact test names when needed:
`test_storage.StorageTests.test_identical_caption_is_not_another_revision_or_ui_refresh`,
`test_storage.StorageTests.test_metadata_allocation_persists_and_failure_is_transactional_per_session`,
`test_storage.StorageTests.test_paused_old_session_iterators_release_sqlite_for_another_writer`,
`test_storage.StorageTests.test_export_metadata_bound_and_discard_preserve_source_and_other_sessions`,
and `test_storage.StorageTests.test_lossless_event_codec_exports_original_fields_and_rejects_bad_expansion`.
They use only private synthetic data; no GUI, model or native capture starts.

File publication uses fsync and atomic rename; selected ZIP publication also
refuses to replace an existing destination. Directory fsync is used on POSIX.
Python does not provide portable Windows directory fsync, so Windows power-loss
durability ultimately depends on its filesystem/device guarantees. OS leases
release on process death. SQLite is authoritative if a crash occurs between a
database commit and the JSON receipt replacement. No cleanup runs automatically.
Symlinks, Windows reparse points, hardlinks, path traversal, unowned roots, and
unregistered children are rejected. Filesystem access must still be restricted
to trusted processes; this is not a sandbox against an attacker racing path
replacement during an operation.

## Run the synthetic host tests

All host Python work in this campaign must pin itself to logical **CPU 14 before
reading project files**. Use the qualified environment below; a bare `python`
may resolve to the Windows Store alias. These commands create only isolated
synthetic test stores and run no native/audio/network/Pi workload. Their output
is the unittest pass/fail log. The tests clean up only their own temporary
directories; the private owner/test receipt directory remains.

In **PowerShell**, choose a fresh private evidence directory. Python registers
its actual PID, creation time and CPU affinity before importing project code:

```powershell
$run = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\' + [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Path $run | Out-Null
$env:LIVE_STORAGE_EVIDENCE = $run
$env:LIVE_STORAGE_TEST_ROOT = Join-Path $run 'tests'
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); assert me.cpu_affinity()==[14]; import os,json; from pathlib import Path; p=Path(os.environ['LIVE_STORAGE_EVIDENCE']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_storage')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures)))); raise SystemExit(not r.wasSuccessful())"
```

In **Command Prompt or Anaconda Prompt**, run the same commands through
PowerShell, or create a fresh private directory with a unique suffix first:

```bat
set "RUN=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\storage-preparation\manual-%RANDOM%-%RANDOM%"
mkdir "%RUN%"
set "LIVE_STORAGE_EVIDENCE=%RUN%"
set "LIVE_STORAGE_TEST_ROOT=%RUN%\tests"
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); assert me.cpu_affinity()==[14]; import os,json; from pathlib import Path; p=Path(os.environ['LIVE_STORAGE_EVIDENCE']); f=(p/'REGISTERED_OWNER.json').open('x'); json.dump(dict(pid=me.pid,create_time=me.create_time(),affinity=me.cpu_affinity()),f); f.flush(); os.fsync(f.fileno()); f.close(); import unittest; r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_storage')); (p/'TEST_RESULT.json').write_text(json.dumps(dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures)))); raise SystemExit(not r.wasSuccessful())"
```

Tests cover 31 sessions across restart and history pages, selected exports,
authoritative sample counts and PCM replay, old-offset disk reads, raw format
qualification and post-stop choices, capacity exhaustion, fsync and publication
faults, interprocess exclusion and crash recovery, failed/cancelled receipts,
registered native artifacts, caption revisions, and deletion/path isolation.
The subprocess fixtures also pin CPU 14 before importing project code. These
tests do not qualify live Pi throughput, native algorithms, microphone capture,
storage endurance, or power-loss behavior.

## Versioned metadata allocation for new build08 sessions

`metadata_limits(spec, metadata_allowance_bytes)` returns disjoint `text_bytes`
and `sqlite_bytes`. An absent `metadata_split` retains the historical5/6 text
and1/6 SQLite split. New sessions explicitly select
`metadata_split="text3_sqlite1_v1"`:3/4 text and1/4 SQLite, with the existing
base metadata allowance assigned only to SQLite. Integer rounding goes to
text, so both allocations sum exactly to the unchanged total reservation.
Unknown explicit versions are rejected before session creation. Persisted
SQLite ledger ceilings never change; the helper initializes only missing
ledgers for the explicitly written session and never scans all history.

Actual short07 saved output projects377.71MB/hour of native text and31.67MB/hour
of SQLite; adding measured raw05 source-row projection150.873MB/hour gives
182.55MB/hour of combined SQLite versus the new241.17MB allowance. This is
an estimate from separate short runs, not an hour or combined native pass.
The former161MB SQLite allowance had only a narrow margin for source metadata.
The new split changes no global reservation, free-space floor or old session.
Inputs/outputs and PowerShell/CMD/Anaconda commands above remain unchanged;
callers creating new08 specs add the explicit version. Run only
`test_storage.StorageTests.test_metadata_split_is_disjoint_and_absence_remains_legacy`,
`test_storage.StorageTests.test_new_metadata_split_preserves_prior_persisted_ledger`
and the existing transactional metadata-allocation check through the same
early CPU14 owner test wrapper to verify this change.

## Actual immutable08 GUI02 storage and replay evidence

The closed `gui-qualification-02-monitor-01` PC mirror and independent
`storage-preparation/gui02-review-02/REVIEW.json` confirm a300-second live
recording:4,800,000 processed and qualified physical raw samples,30 segments per
stream, Save raw + processed after closure, full History replay to natural EOF,
replay-only Discard and Exit. Original kept session
`5e9d3ff46f654c178ea2e2dffa497433` remains intact. The review checked all201 files,
contiguous clocks and concatenated raw SHA, without media or transcript display.
See README_GUI_RECORDING_REVIEW.md for exact aggregates, commands and limits.

Both sessions have zero caption rows, so this run establishes no caption-render,
recognition-quality or speaker-accuracy result. Programmatic Tk actions and10
stable480x800 fullscreen checks do not establish physical touch or visual quality.
External export01 subsequently failed before storage import; its closed failure
is preserved. External export02 then failed the read-only lease contract. Repaired fresh-child export03 passed the data path and complete PC ZIP readback. This does not qualify the ordinary History Export widget; that separate check remains pending. See README_OWNED_EXPORT.md. No hour-runtime claim follows from
this300-second recording/replay result.

## Current History versus retained recordings

The v29 launcher lists the indexed sessions belonging to its selected store.
Preserved v27/v28 recording trees and their old slot journals remain separate
rollback/backup roots. This storage layer does not automatically migrate or
import them into current History. Complete backup and selected export retain
those original bytes independently; there is no new recording migration here.
Gallery namespaces and speaker identity thresholds are unchanged.
