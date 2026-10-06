# Kept-session replay integration

`saved_replay.py` is the next versioned derivative of build21's complete kept
recording source. It retains paced, disk-backed float32 streaming, authoritative
sample counts, full segment/hash/identity verification, shared source lease,
explicit duration policy, bounded index and ordinary Stop/EOF cleanup.

The only new data-path operation is `spatial.advance_samples(end)` immediately
before each original journal append. This makes original recorded callback,
beam and BMI evidence available before its corresponding audio is model-readable.
It never starts a live BMI worker or uses the tablet's current orientation.

Inputs are the existing disk journal, read-only session store root, kept session
UUID, source callback, duration policy, Stop event, append batch of 320–1600
samples in 320-sample steps, and optional `SavedSpatialViews`. A spatial view must
match the same resolved store, UUID, metadata SHA and complete sample count.
Mismatch rejects before index construction. Plain WAV has no rich sidecars and
is rejected for spatial/seat modes by `InstalledSession` before model constructors.

Outputs remain exact replay audio in the destination journal, bounded saved replay
index, source-start/progress/Stop receipts and explicit recorded-spatial metadata
pins. Physical microphone/current motion flags remain false. The separate
historical spatial lease is held by the installed session until model drain;
afterward it verifies recorded sources again and closes. Failure cleanup keeps
that ordering and does not clear an owned worker or failed source.

## Run

Use the single versioned Just Peachy desktop launcher. Select a kept recording,
backend and spatial or assigned-seat Mode, configure/apply the recorded-frame
seat layout where required, and Start. A plain saved WAV can still run acoustic
modes; it cannot substitute current live pose for missing spatial sidecars.
This module is an injected source API and has no direct microphone/activation CLI:

```python
source = SavedSessionSource(journal, store_root, session_id, callback, policy,
                            stop_event, spatial=recorded_views)
source.start()
# Original engine completion/drain precedes recorded_views.close().
```

For the focused host check, use a fresh label. PowerShell:

```powershell
$replaySource = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$replaySource\check_seat_integration.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\seat-spatial-integration-check-01'
```

CMD or Anaconda Prompt:

```bat
set REPLAY_SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%REPLAY_SOURCE%\check_seat_integration.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\seat-spatial-integration-check-01"
```

See `README_SEAT_BACKENDS.md` for source backups, outputs and check limits, and
`README_SAVED_SPATIAL.md` for recorded pose/beam validity. Synthetic source-loop
checks establish append ordering and bytes, not live seat accuracy, native model
performance, acoustic synchronization, calibrated TitaNet identity or absolute
room translation.
