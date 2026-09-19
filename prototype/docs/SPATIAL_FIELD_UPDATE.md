# PROTO1 0.1.4 — existing spatial methods for field testing

This update exposes existing alternatives in the Windows/CM5 prototype. It is
not a new optimization study. Open the normal application and choose Balanced
or Patient, then **Spatial-assisted** or **Strongly spatial-assisted**. Enable
**Settings → Live spatial display** for the compact panel above the transcript.
The app still opens with its microphone off. Restart an older open app to load
this update. Run commands, inputs and outputs are in `../START_PROTOTYPE.md`.

The two modes reuse the complete retained C079 and stronger C060 tracker/XVF
settings with the existing S7 frontend and C088 voice-name resolver. C060 gives
spatial scores 50% more weight; severe voice disagreement, strong-voice recovery
and decaying position memory remain active. Neither mode is advertised as a
simulation winner. Both are selectable with ◇ experimental badges. Existing
five modes, applicable recipes, O0/O1 taps, enrollment and private profiles remain.

The optional 125-pixel display uses existing read-only XVF telemetry. Solid
arrows are fresh; dashed arrows or hollow positions are last-known. Speech uses
existing mono segmentation, energy is raw DSP energy, and `≈` labels are estimated
voice-position matches. They are not independent proof that a beam belongs to
that person. Names require confirmed voice evidence and expire back to anonymous
labels. **Reset positions** starts a new session epoch after tablet movement
while retaining saved people. No motion sensor is assumed.

Fusion retains the historical selected-processed cue for both O0/O1; the panel
highlights the tap's selected direction separately. The cue must meet callback,
waveform-window, freshness and reliability gates. Missing or invalid cues fall
back to voice; no other angle is silently substituted. The small scheduler hook
passes actual audio-window bounds to the live provider without changing legacy
providers. No new neural model, endpoint policy, firmware or beam steering was added.

## Executed verification

| Check | Result and limit |
|---|---|
| Full focused software/GUI suite | 146 passed, zero failures/errors/skips; includes clock/ownership, private people/enrollment, exact retained profiles, stale/future cue rejection and 480×800 layout. |
| Actual native models, two spatial modes | 12 seconds each; 17 qualified tracker cues per mode; one ASR and one speaker model load reused across both. Directions were explicitly synthetic 70° fixtures, not hardware measurements. |
| Real Windows XVF input/telemetry, stronger mode | 20.02 seconds, zero dropped frames, clean native completion and device restoration. 291 successful telemetry getters at snapshot; no query errors. |
| Physical identity limitation | The room sample had zero qualifying processed/speech cues (processed angle NaN, auto energy zero). Voice fallback and beam display transport worked; human spatial identity accuracy was not established. No WAV or enrollment was saved. |
| Export | Immutable source ZIP; relocated payload hashes, Windows imports and configuration/shared-model validation. No model weights or personal journals included. |

`SPATIAL_FIELD_CHECKS.json` preserves sanitized counters and exact tested runtime
and test hashes. Full bounded receipts remain private in local staging. These
results do not extend the earlier long-session evidence to a new hardware target.
Actual CM5 audio/control/touch, real-people enrollment, movement and overlapping
speaker usability still require field testing. No new sweep or threshold tuning
was performed to make an experimental mode selectable.

See `../MODE_GUIDE.md`, `SPATIAL_PROFILE_PROVENANCE.md`, `UI_SPATIAL_DISPLAY.md`,
and `../app/README_SPATIAL.md` for the evidence used, tradeoffs and reproduction.
The same source ZIP uses the existing `PI_DEPLOYMENT_WORKFLOW.md`; target-specific
native XVF control and dependencies must already be provisioned on the CM5.
