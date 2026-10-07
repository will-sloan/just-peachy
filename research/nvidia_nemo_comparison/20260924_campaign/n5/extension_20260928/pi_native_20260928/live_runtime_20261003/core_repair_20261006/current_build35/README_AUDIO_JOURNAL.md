# Disk audio journal

`audio_journal.py` adapts the installed pipeline's `MemoryJournal` interface to
the segmented processed-audio files owned by `storage.SessionSpool`. ASR and
diarization readers keep absolute sample cursors and can read old audio from
disk after capture has advanced. The adapter does not retain an entire
recording or an audio queue in RAM, and does not impose a five-minute limit.

## Inputs and interface

Construct a fresh `DiskAudioJournal` with:

```python
journal = DiskAudioJournal(
    spool,
    policy=spool.spec,
    fault_receipt=lambda receipt: spool.store.write_event(
        spool.session_id, 'journal_fault', receipt),
    observer=observe_accepted_audio,
    request_stop=request_source_stop,
)
```

The policy must explicitly contain a positive finite `duration_seconds` and
`sample_rate=16000`, matching the actual spool's session policy. A fresh
processed cursor is required. `spool.store.policy.max_append_bytes` limits
append and read allocations. `max_read_samples` optionally lowers the read
bound; its default is the smaller of ten seconds and the spool's I/O bound.
These I/O bounds are not session-duration limits.

The methods/properties used by the installed pipeline are `append(samples)`,
`read(cursor, maximum_samples, wait_sec=.25)`, `finish(error=None)`,
`committed_samples`, `duration_sec`, `sample_rate`, `finished` and
`fatal_error`. `snapshot()` exposes the selected limit and fault state.
`close()` finishes only this view; the session owner closes the spool.

`append` accepts one-dimensional finite mono float32-compatible samples. The
spool performs a complete fsynced append before either published cursor
advances. A rejected/failed append leaves the journal cursor unchanged,
records a fault, requests Stop, wakes readers, and raises. Existing committed
samples remain readable even if a failed physical write left an uncommitted
tail in the file.

The observer is invoked once after a successful append. If it fails, those
samples remain accepted: the method returns, publishes a fault with the
accepted count, and sets the terminal error/EOF state. This preserves the
installed source adapter's increment-after-append accounting. Both observer
and Stop callbacks must be short; Stop must request shutdown rather than
recursively calling `finish` from the append callback. Fault publication
failure is retained separately in `fault_receipt_error`; it is never reported
as a successfully persisted receipt.

Read waiting is at most one second per call, and each read allocation is
bounded. There is no background queue to lose or abandon on Stop. Disk writes,
fsync and reads are synchronous operating-system I/O; a process owner still
needs its external deadline for an unresponsive device. This module does not
claim that Python can interrupt a hung kernel disk operation.

## Run the checks from Anaconda Prompt or cmd.exe

No new environment or package installation is needed. Use the existing Python
environment, which supplies NumPy:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_audio_journal.py --output-root "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation"
```

## Run the checks from PowerShell

```powershell
Set-Location -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_audio_journal.py --output-root 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation'
```

Run the test file directly, not through unittest discovery: its entry point
sets CPU14 affinity and writes a unique `REGISTERED_OWNER.json` before any
project imports or data reads. A machine without CPU14 fails immediately.

## Outputs and validation scope

Each invocation creates a unique `audio-journal-tests-<id>` directory under
the supplied private output root. It preserves the owner record, processed
test audio, fault receipts, `RESULT.json`, and `EXIT.json`. It returns exit
code zero only when every check passes. The long synthetic stream contains
301 seconds of generated samples, emitted using small fixed-size blocks;
it is not paced and is not a microphone, native-model, endurance or real-time
test. The checks also cover old-offset disk reads, concurrent EOF drainage,
partial-write cursor integrity, once-only observer accounting and invalid
input. The fixtures use the same spool interface with a deliberately
injectable physical writer; storage's own tests qualify its segmentation and
SQLite behavior.

See `native_audit.md` for native timeline, archived-caption and existing
artifact limits that a disk journal does not solve.
