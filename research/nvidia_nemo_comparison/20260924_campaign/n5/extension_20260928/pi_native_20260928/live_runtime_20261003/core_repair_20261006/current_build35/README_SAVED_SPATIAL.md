# Kept-session recorded spatial replay

`saved_spatial.py` connects an existing kept recording's beam and BMI270 logs to
the restored spatial and assigned-seat providers. It never opens I2C/USB, starts
audio, loads a model, writes the original recording, or uses the tablet's present
orientation. Plain WAV files do not contain these clocks and remain unavailable
for spatial Modes.

Final source verification runs after model/presentation drain. Any verification
or cleanup error is latched and every repeated `close()` raises it again;
cleanup repetition can never turn failed readback into certified replay. Both
the shared lease and read-only store are closed even when source verification
fails. `source_verified` is set only after the original logs and metadata pass
their final checks. Constructor cleanup without verification cannot certify a
later successful verified closure.

## Inputs and outputs

Inputs are a read-only `SessionStore` root, its canonical kept session ID, the
selected tracker configuration, an optional applied `SeatSession`, and an
explicit recorded-axis compensation policy. Required registered artifacts are
`work/spatial/beam_angles.jsonl.index.json`, its completed numbered segments,
`work/motion/orientation.jsonl.index.json`, and its completed numbered segments.
The final original audio anchor must equal the session's processed sample count.
The two logs must share the recorded source epoch. Missing, incomplete,
duplicate-field, reordered, foreign-epoch, oversized, or changed logs fail before
model playback. The source's shared recording lease remains held through replay.

Outputs are the retained `DeliveredSpatialObservation`, retained seat detail,
recorded direction display, and a small `just-peachy.saved-spatial-replay.v1`
receipt containing source metadata and log hashes, actual consumed row counts,
reference losses, and clock limitations. Voice identity remains the selected
encoder's responsibility; direction does not establish identity.

## Source clock and geometry

`advance_samples(end)` must run **before** the saved source appends those samples
to the model journal. It consumes only original audio anchors whose sample end
is at or before `end`. Beam control receipts are delivered to the first containing
or later original callback, preserving their actual original control-read
duration and callback delivery delay. The observation availability is projected
to that recorded sample end for the replay scheduler. This is a causal delivery
bound, not an acoustic timestamp or a claim that the DSP measured that sample.

Pose lookup is the latest original pose at or before the original control time;
its maximum age is the unchanged 150 ms guard. There is no extrapolation or
interpolation across a reference change, unsafe generation, invalid pose, or
gap. The microphone-axis horizontal projection and original half-plane ambiguity
rules are retained. They solve `axis_xy · [cos(theta), sin(theta)] = cos(alpha)`;
only one eligible 5–175 degree intersection receives drift-weighted evidence.
Neither absolute heading nor translation is reconstructed.

Queries select the historical pose corresponding to their source window, even
when a delayed diarizer returns much later. `seat_evidence_for_source(start,end)`
uses source-window availability; inference delay remains separately measured.
Reference/safety changes clear spatial memory and invalidate a seat layout.
For saved seating, an operator-applied layout means the **recording's reference**,
not the device's location at replay time. The adapter explicitly changes the seat
anchor clock to the recording epoch and labels this assumption.

Preparation scans complete logs once, hashes each segment, and retains only one
sparse offset per 128 relevant rows (at most 65,536 checkpoints). Queries seek
into original files; full pose/beam timelines are never copied into RAM. No new
pose polling thread, inference worker, or full disk index is created. All source
identities and hashes are checked again at closure.

## Runtime integration

Deploy as part of a fresh versioned runtime; do not replace build21 in place.
After the installed `app` modules are verified/imported, construct:

```python
from saved_spatial import SavedSpatialViews
spatial = SavedSpatialViews(saved_store_root, saved_session_id, profile.tracker,
    enabled=mode in SPATIAL_PARENTS, seats=seat, compensation=True)
```

Pass `spatial` to the engine's existing `spatial_provider`. Do not create a live
BMI worker or `ArchivedSpatialViews` for this source. Add optional
`spatial_provider=None` to `SavedSessionSource`; in its paced source loop, call
`spatial_provider.advance_samples(end)` immediately before `metrics.append(...)`.
The kept-source start receipt should set `motion_applied=True` and include
`recorded_spatial=True` when this provider exists. The engine's existing
`source_started` path can call `bind_origin(replay_epoch)` once; this stores the
new pacing epoch without replacing the original recorded reference.

Require `spatial.metadata_sha256 == saved_source.metadata_sha256` before Start.
After all model and presentation consumers close, persist `spatial.receipt()` and
call `spatial.close()`; errors must fail closure while preserving evidence. Also
close the provider if model/source initialization fails. History's existing
Replay action already supplies `saved_session_id` and `saved_store_root`.
Allow saved spatial compatibility only for that kept-session route; a plain WAV
should show `Choose a kept recording with completed beam/BMI clocks`.

`historical_source_evidence=True` and `seat_evidence_for_source(start,end)` are
provided for the N2 seat adapter. These do not transfer Pyannote/ReDimNet voice
calibration into TitaNet or Nemotron.

## Focused host check

The check validates causal delayed-window lookup, callback/sample alignment,
stale/reference gaps, segmented completion guards, and unchanged source pins.
It does not start models, microphone, GUI, or sensor hardware. The CLI registers
an actual owner on CPU14 before importing project code, and requires a new output
directory. Back up/restore these sources before executing the check.

PowerShell:

```powershell
$src = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py "$src\check_saved_spatial.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\saved-spatial-check-NEW'
```

CMD or Anaconda Prompt (using the pinned Python avoids environment substitution):

```cmd
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005\check_saved_spatial.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\saved-spatial-check-NEW"
```

Use `--recording-directory` only with a previously verified closed rich recording
mirror to verify its actual schema without copying or displaying private audio,
transcripts, names, or angle values. The result contains counts and hashes only.
Native acceptance is one kept-session replay through a spatial/seat Mode with
positive recorded beam/pose consumption, ordinary Stop/closure, and current live
BMI absent. Until observed, native integration remains pending.
