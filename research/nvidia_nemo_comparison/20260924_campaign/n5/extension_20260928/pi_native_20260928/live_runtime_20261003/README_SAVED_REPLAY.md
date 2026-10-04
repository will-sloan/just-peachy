# Replay a complete kept recording

`saved_replay.py` streams every processed float32 segment of one kept recording
through the same disk audio journal used by live capture. It preserves exact
float32 samples, their contiguous source clock and the authoritative total
sample count. It does not concatenate WAV files, quantize through PCM16, load
the full recording into RAM, or acquire a physical microphone.

In the unified launcher, choose a profile, open **Recordings**, select a kept
session, and choose **Replay recording**. This starts that complete timeline
using the current profile. **Choose saved WAV** remains available for one
external mono16k PCM16 file. Switching back to live clears saved input from the
launch request. Replay creates a new session; the original remains unchanged.

The normal GUI policy admits recordings up to five minutes. A longer kept
recording requires an explicitly authorized developer duration/storage policy;
the source rejects a complete recording that exceeds the chosen policy rather
than playing only its first segment. Through the owned headless launcher:

```text
--headless --input-source saved --saved-session-id <kept-session-id> --maximum-session-seconds 300 --keep-processed
--headless --input-source saved --saved-session-id <kept-session-id> --maximum-session-seconds 3600 --developer-soak --max-drain-seconds 1800 --keep-processed
```

`--saved-store-root` may explicitly identify the current owned recording store;
it defaults to that store and cannot select an unrelated root. Do not combine
`--saved-session-id` with `--saved-path`. The normal native authorization and
owned-service remaining-lifetime gates still apply. These are prepared native
interfaces; host tests do not qualify the GUI or model pipeline.

## Inputs, outputs and lifecycle

`SavedSessionSource(journal, source_root, session_id, callback, policy,
stop_event)` takes a fresh destination journal and an existing kept mono16k
source session. `start`, `stop` and `wait` follow the runtime source contract.
The source opens SQLite in actual read-only mode and holds a shared per-session
kernel lease throughout preparation and playback. Deliberate deletion and
retention changes require an exclusive lease and fail while replay owns it.
Independent shared readers are supported, including on Windows via LockFileEx.

Preparation pages at most 32 segment rows at a time, closes the SQLite reader
before pacing, and hashes source files with 64 KiB buffers. It records pinned
metadata, segment identities and hashes in the destination's bounded
`work/saved-replay-index.jsonl`. Playback defaults to at most 1600 float32 samples (100 ms) per
append (constructor multiples of 320, from 320 through 1600), checks each segment identity/hash and the overall count/hash, and paces
from one monotonically advancing source origin. Concurrent caption writes to
the new session do not wait behind an hour-long SQLite read transaction.

Index bytes use the destination metadata allocation, capped at 8 MiB and one
quarter of its metadata reserve. The source index is registered with other
owned work artifacts by the worker. A gap, truncation, changed hash, excessive
index, or duration mismatch fails explicitly. Stop releases the lease and
reports its accepted prefix with `complete_recording: false`. Outputs are the
new journal/spool, normal captions/events, source provenance and replay index;
no source files or history metadata are modified.

## Hardware-free source proof

Run the CPU14/actual early-FILETIME-owner entrypoint in
[README_SAVED_SOURCE_METRICS](README_SAVED_SOURCE_METRICS.md#run-the-focused-host-proof).
Its PowerShell, Command Prompt and Anaconda commands run the same qualified
interpreter and synthetic fixture script. Inputs are generated float32/WAV
fixtures and selected source; outputs are private exact-sample/hash, lease,
Stop, failure-prefix and numeric-timing results. No Pi, model, microphone,
network or real-time hour is involved. The already completed six checks need
not be rerun for packaging. `test_saved_replay.py` retains the earlier
multi-segment/shared-lease regression contracts; its append-bound assertion
now matches the selected 1600-sample maximum.

## History and rollback scope

The unified v29 History and kept-session replay use the selected v29 indexed
store. Preserved v27/v28 recordings and old slot journals are separate rollback
and backup roots; they are not automatically migrated, enumerated or imported
into this History. Export/offload and any explicit future migration are separate
operations. Gallery namespaces and speaker identity thresholds are unchanged.

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