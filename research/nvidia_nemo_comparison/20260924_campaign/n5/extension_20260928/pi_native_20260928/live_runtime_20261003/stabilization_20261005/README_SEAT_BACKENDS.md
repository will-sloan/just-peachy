# Backend seat adapters

`seat_backend.py` implements the assigned-seat extension for the next versioned
runtime. It does not edit build21, load a model, open a device, change a gallery or
manufacture a calibrated identity threshold. `check_seat_backend.py` checks the
changed pure decisions with explicitly synthetic galleries, cues and tracks.
Native use still needs the focused application acceptance described below.

## Purpose and evidence components

| Component | Retained implementation | Scope in the extension |
|---|---|---|
| Seat UUID/angle/tolerance, collision acknowledgement, Apply/revision/release | `app/seats.py:SeatSession` | Generic across named encoders; at most 16 seats, linear folded 0–180° frame, no front/back or distance claim |
| Beam fields, speech energy, callback availability, source support, BMI reference | `SeatSpatialProvider` / a recorded provider with the same checks | Generic observation geometry, not an identity score or calibrated acoustic clock |
| Clean non-overlapping audio and a genuine diarizer track | Actual Pyannote event or Nemotron exclusive-slot waveform slice | Track domains remain `pyannote-online-track:ENCODER` and `nemotron-native-session-slot:ENCODER`; no cross-domain numerical-ID merge |
| C088 unique/disjoint clean support, voice/prototype floors, retained S6C joint score | Original `SeatIdentityResolver` | Kept exactly for Pyannote + ReDimNet; not reused as TitaNet or Nemotron calibration |
| N2 voice and naming evidence | Actual `N2NameMap` and admitted encoder/domain/roster gallery | Only the existing C-calibrated gate can verify a name; no spatial promotion of a failed voice margin |

Assigned direction takes the unique seat within its configured tolerance when
clean speech and causal direction are eligible. It is explicitly **a closed-table
assumption**, never verified identity. It does not query a voice gallery. The
shared diarizer/embedder still supplies the original speech/ownership event; no
claim of saved inference work is made.

For the new N2 hybrid routes, the voice delegate must already accept the same
person using its own current and accumulated evidence. Its actual score threshold
and margin threshold are read from that exact admitted gallery gate. A conflicting
strong current voice releases the relevant seats; accepted voice can remain a
marked voice-only fallback. An ambiguous angle never manufactures a name.

The writable TitaNet personal store currently declares
`UNCALIBRATED_PERSONAL_DOMAIN`. ReDimNet used through N2 also does not acquire a
C088/N2 calibration merely because its vectors have 192 dimensions. Therefore
hybrid executes with explicit **Unknown** until an independently admitted
encoder/query-domain/roster C gate exists. `calibration_receipt()` reports this
concrete blocker. Direction assumptions remain usable without that gate.
This is not permission to copy the ReDimNet threshold into TitaNet.

## Runtime integration

Inputs: a supported `selection.diarizer`/`selection.embedding`, one assigned Mode,
the original anchored `SeatSession`, names from the **selected encoder** gallery,
the actual spatial provider, observed policy clock and existing voice delegate.
Output: existing resolver decision/caption schema plus `identity.seat`,
`prototype_assignment`, `seat_identity_verified`, encoder calibration and track
domain diagnostics. Assignment memory is capped at 4,096 exact evidence IDs.
No personal-reference adaptation is permitted.

Call `make_resolver(selection, mode, legacy_factory=..., settings=..., gallery=...,
seats=..., names=..., provider=..., tracker_config=..., clock=..., voice_map=...)`.
The Pyannote/ReDim branch passes the original arguments to the original
`SeatIdentityResolver` unchanged. Other branches return `BackendSeatResolver`.

The stabilization `installed_engine.py` now installs the adapter **before
model/source threads start**:

1. `install_factory_hook(pipeline, manifest['app/pipeline.py']['sha256'])` reads
   the actual loaded source, rejects any hash or loaded-method drift, and derives
   only `PrototypeEngine.begin` in memory. It changes exactly one constructor
   callee to `getattr(self,'_seat_identity_factory',SeatIdentityResolver)`.
   Exhaustive AST reversal verifies every other statement and argument is
   unchanged. Original globals, defaults and closure cells are reused, including
   a zero-argument `super()` class cell where present. The default remains the
   original class, disk source and model thresholds remain unchanged, and a
   receipt records both AST digests.
2. For a N2 seat engine, construct the adapter around its already-created
   `engine.n2_name_map` before `begin`, replace `engine.n2_name_map` with the
   adapter, and set that instance hook to return the same adapter. This prevents
   even temporary use of the C088 resolver on a TitaNet/Nemotron event. The
   existing `N2Engine.begin` then selects the same adapter for D0 dispatch and
   the D1 exclusive-window loop. Do not change `_speaker_loop` ownership or
   source admission.
3. Keep the original N2 event `tracker_id` and actual native slot provenance.
   Preserve its embedding event ID in the existing `evidence_ids` of every
   late-caption revision. The adapter keeps bounded assignment/verification
   diagnostics keyed by that exact ID. Do not derive identity from a numeric slot.
4. Before the original retained caption projection, apply
   `engine.prototype_identity.annotate_caption(row)` for seat routes. That marks
   names `seat_assumed` so the existing GUI shows “· seat assumed”, and rejects
   missing evidence linkage or a changed/released anchor. Late-label and saved
   transcript paths need that same marking; a “confirmed” display state alone
   must not be described as verified identity.
5. Allow supported named combinations in the new application contract. Keep the
   actual independent saved-spatial admission and original seat/roster/Apply
   checks. An unavailable calibration is a visible Unknown/hybrid diagnostic,
   not a fabricated threshold or a generic “wrong backend” restriction.

Changing `n2_name_map` after `begin` is too late: the original method constructs
C088 before the N2 override. The reviewed one-callee derivative preserves the
default and chooses a per-instance factory only for the selected N2 seat engine.
Its clock is the actual `engine._s7_observed_clock.relative()`; the deferred clock
lambda is not called until that original clock exists.

### Delayed and saved clocks

Nemotron can legitimately produce an exclusive audio window well after that
audio was captured. Comparing a 21-second-delayed model result to a *current*
beam would associate the wrong conversation instant. The adapter instead calls
`provider.seat_evidence_for_source(start,end)` when implemented. Its fallback on
the original live provider calls `seat_evidence(start,end,end)` with an explicitly
logged historical source-clock basis. That preserved provider still selects only
mapped callback evidence at or before `end`, checks source-window coverage,
energy/angles/receipt delay, motion generation and the anchor. The actual
`available_at_sec-end` delay is logged without clamping timestamps.

For saved replay, use a recorded provider with
`historical_source_evidence=True` and a two-argument
`seat_evidence_for_source(start,end)`. It must use the recorded beam and BMI pose
and their original sample/callback anchors; the tablet's current orientation must
not enter the query. Missing historical data returns no cue. A recorded reference
change must invalidate incompatible assigned-seat anchors. None of these paths
claim exact DSP/acoustic synchronization or absolute room translation.

## Run the focused host check

Use a **fresh** output label. The checker sets CPU14 and persists its actual
Windows PID/create-time before project reads, checks C≥50/G≥75 GiB free, then
makes exact source backups plus independent restores before importing the
adapter. Total output has a fixed 1 MiB ceiling. It never contacts the Pi or
opens audio/GUI/model/native libraries.

PowerShell:

```powershell
$seatSource = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$seatSource\check_seat_backend.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\seat-backend-check-01'
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005\check_seat_backend.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\seat-backend-check-01"
```

Do not rerun a passed unchanged check just for a new version. Outputs are actual
`REGISTERED_OWNER.json`, exact `source-backup`/`source-restore`,
`SOURCE_CLOSED.json`, and `RESULT.json`. Synthetic test calibration is never
usable as a runtime gate.

## Focused native acceptance

After launch/audio startup repair and fresh native admissions, test only the
changed integration. Keep normal capture-off startup, manual Stop and full
closure/Save/Discard protections:

- Pyannote + ReDimNet: original direction/hybrid route and original C088 factory
  must remain unchanged, with no new threshold.
- Pyannote + TitaNet and each retained Nemotron encoder pair: anchor one seat,
  obtain clean speech/exclusive-track plus matching direction, verify the
  direction label is explicitly assumed and encoder embedding executes. Missing
  or overlapping bearings must yield Unknown. No solicited speech is authorized
  by this module; use only the session's separately authorized test plan.
- Hybrid: inspect the actual gallery calibration receipt. For an uncalibrated
  personal gallery, record the exact blocker and Unknown rather than report a
  verified identity. With an independently admitted C gate, a current accepted
  voice conflicting with the seat releases that seat and retains a marked
  voice-only fallback; no personal reference changes.
- Delayed/saved: inspect historical query and actual model-delay fields, ensure
  a source-window beam is used rather than a current beam. Verify archived
  captions/late revisions retain the “seat assumed” distinction and exact
  embedding evidence IDs.
- Motion/re-anchor and next session: invalidate old assumed names without
  touching the gallery; no old track/session may acquire the new seat anchor.

Pure checks establish implementation behavior only. They do not establish live
seat accuracy, physical motion validity, native model performance, TitaNet
calibration, real-time qualification or a noisy-room identity measurement.

## Changed integration check

`check_seat_integration.py` verifies the new constructor hook separately from the
already passed adapter cases: default versus per-instance choice, original
`super()` closure, wrong-source and loaded-method drift rejection, and the actual
pipeline begin AST without importing its model graph. It executes the changed
saved-source loop on 960 explicitly synthetic float samples with fixture storage
and an array stand-in, verifying each historical advance precedes the exact audio
append, metadata pin drift rejects, and source lease/EOF close naturally. Engine
hook/drain wiring is AST checked. No native runtime qualification is implied.

PowerShell (set `$seatSource` as above; choose an unused output label):

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$seatSource\check_seat_integration.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\seat-spatial-integration-check-01'
```

CMD and Anaconda Prompt:

```bat
set SEAT_SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SEAT_SOURCE%\check_seat_integration.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation\seat-spatial-integration-check-01"
```

The check registers CPU14/PID/create time before project reads, independently
backs up/restores all changed integration sources and READMEs before import, and
retains `SOURCE_CLOSED.json`, `RESULT.json` and fixture bytes under a 1 MiB output
and 60-second check lifetime. Labels are one-use. Runtime use goes through the
versioned application launcher; the hook is not a standalone admission or Pi CLI.
