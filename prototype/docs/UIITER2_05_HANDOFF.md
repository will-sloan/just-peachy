# Task 05 — Assigned seats and spatial controls

Implemented locally, 20 September 2026, on the existing tasks 01–04 prototype.
**229 software checks PASS; three native saved-audio cases PASS.** Directions in
those native cases were explicitly synthetic; live XVF/person seating accuracy
is **NOT_TESTED / awaiting participation**, as are physical touch and CM5.
Task 06 has not been started. No new model/dependency, training, sweep, firmware
steering, production enrollment, automatic commit/push or release rebuild.

## Run and use

From `C:\Users\amiri\Documents\GitHub\just-peachy` in PowerShell:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD / Anaconda Prompt:

```bat
prototype\Start-Prototype.cmd
```

The app opens idle; Start retains its microphone consent flow. Open Mode:

| New real menu entry | Behavior |
|---|---|
| Assigned seats - Direction only (closed seating) | Fresh, model-speech-gated direction selects a unique assigned region. The name is **· seat assumed**, not verified voice identity. No personal gallery comparison. |
| Assigned seats - Voice + direction + Unknown | Actual assigned-UUID ReDimNet/C088 gallery plus retained soft C079 / strong C060 prior. Unknown remains; conflicting strong voice releases spatial trust. |

Tap a name then the arc, or drag a name/point. Angle and region controls step by
1°. Default tolerance is **±25°**, bounded 1–45°; at most 16 UUID seats. The native
0–180° linear projection cannot separate front/back. Red overlapping regions
require an explicit ambiguous-outcome acknowledgement or an edit. Their
intersection cannot yield a direction-only name. Hybrid may use qualified voice
with the spatial ambiguity recorded.

Apply anchors at the present location and safely changes the processing epoch
if running. Cancel/Clear draft are inert until Apply. Save template is separate
and never makes a valid physical anchor; Load only populates the draft. Stop,
natural session end, leaving the seat mode, person changes and app restart
require review/re-anchor. **Tablet moved** invalidates the anchor immediately
while captions and native voice memory continue; Apply re-anchors in a new epoch.
No IMU/camera is configured; the motion service is explicitly a stub.

The closed-table/no-movement assumption can misname a visitor, singer or person
who changes seats. Missing/stale directions, non-speech, overlap, incompatible
beam evidence and unresolved collisions never force a direction-only name.
Neither mode learns personal references from direction. All words remain.

## What changed and effective settings

`app/seats.py`, `seat_identity.py`, `seat_controller.py` and `seat_ui.py` add the
session state, causal telemetry checks, native scorer adapter and touch editor.
The existing mode registry, pipeline/controller and read-only spatial projection
wire these into the same shared models, source owner and linked session archive.
Full run/input/output descriptions are in `app/README_SEATS.md`.

Hybrid reuses actual `S6CTracker._joint_scores`, with C079/C060 weights **0.60/0.90**,
voice scale **0.15**, spatial width **25°** and joint margin **0.10**. It retains
C088's **0.5128856897354127** voice floor, **2s** unique support and **two** disjoint
observations. Seat prior support can resolve a qualified voice-margin ambiguity;
it cannot waive those voice gates. Strong current voice conflict (retained 0.65
cosine) releases involved seat priors until re-anchor. Voice memory remains
separate. Missing spatial evidence can produce an explicit voice-only hybrid
decision, never a quiet substitution. Direction-only keeps fixed C079 settings;
its identity/weight controls are inactive.

Cue admission retains the **0.25s upstream-availability** bound; a separate
**0.75s actual decision-age** limit rejects directions that expire during scheduler
waiting. Raw radians/degrees, receipt/callback provenance, both ages, assignment
basis and released trust are logged. No source timestamp is clamped or invented.
Signal semantics were checked against the matching XMOS guide; links and exact
gates are in `docs/SEAT_SEMANTICS.md`.

The implementation keeps the existing segmentation/embedding lanes even in
direction-only for speech gating and caption ownership; **no compute saving is
claimed**. There is no extra neural pass, second capture or second USB owner.
All frozen vendor/configuration files and task 01 audio/timing, task 03 storage,
personal gallery/model files and original 46 default mode configurations remain
unchanged. `MODE_MATRIX.json` now exports **54 defaults + 4 strong hybrid-seat
variants**; actual private epochs additionally export the applied UUID map,
anchor revision, parent/overrides and gallery binding.

## Executed checks

| Check | Result / scope |
|---|---|
| Full software suite | 229 PASS; no errors/failures/skips. Exact elapsed time/source bindings in `UIITER2_05_CHECKS.json`. |
| Synthetic logic/Tk | Stable and changing bearings; same/near/front-back-equivalent regions; stale/missing cues; non-speech/music gate; overlap; no beam energy; raw-field/clock mapping; voice conflict; actual soft/strong scorer; motion; UUID rename/delete; template restart; tap incompatibility; drag/tap/fine adjustments; Cancel/Clear; portrait layout. |
| Direction-only, real A audio + synthetic positions | 20 seat assumptions / 26 unavailable decisions; both assigned positions reached native names; **seat assumed reached the actual Tk caption widget**. Manual motion retained the same source/engine/model instances and then suppressed seat names. |
| Hybrid, real A + conflicting synthetic direction | 22 accepted / 20 rejected / 4 unavailable; accepted A, never falsely named B. |
| Hybrid outsider B, only A assigned | 42 rejected / 4 unavailable; no confirmed name. |
| Three native cases | Three existing 12s prepared files; **41.016s** including model/UI setup. One ASR load, one speaker-model load, three streams; reference/query source hashes were disjoint and fixture references unchanged. |
| Resources | Maximum sampled process RSS **516.99 MiB**; final cumulative process CPU counter **19.469s**. No comparison baseline or claimed saving; not CM5 total-RAM qualification. |
| UI / cleanup | Exact **480×800 physical client**, 96 DPI, five screenshots. Reviewed actual assumed caption and collision display. Workers/owners closed; Windows default output observations unchanged; no microphone or audible playback. |

The first native attempt exposed a new seat-adapter clock mistake: checking the
0.25s admission gate after scheduler watermark release rejected every cue.
It was repaired by retaining the two distinct clocks above, then revalidated.
The failure receipt remains local. No native/source timing gate was weakened.
The final native run predates only a help-paragraph clarification of reset behavior;
the final full software suite covers that text, and exact reverse-patch hashes
bind the final UI to the native screenshots. No inference code changed afterward.

These mechanics and saved-model checks do **not** validate field seat recognition,
singing/music robustness, real overlapping people, relocation accuracy or fresh
hardware telemetry-to-person correspondence. Brief participatory live checks
(stable person, two bearings, collisions, front/back, music, speaker change and
tablet reset) remain the next field validation. No broad HIL bank is required.

## Evidence and rollback

Compact receipt: `prototype/docs/UIITER2_05_CHECKS.json`. Screenshot copies:
`prototype/docs/evidence/uiiter2_05`. Full private evidence and pre-task source ZIP:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Resumes\.uiiter2_05
```

Native receipt: `native_final/SEAT_NATIVE_CHECK.json`; final unit receipt:
`unit_final_v2/UNIT_CHECKS.json`. Earlier attempts remain historical. Model paths
and production people were not changed. This update is in the exportable source
checkout; existing 0.1.4 release archives were not rebuilt.

Close the prototype, then from the repository root in PowerShell:

```powershell
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_05\restore_before_05.py
# After reviewing the dry run, only if rollback is desired:
& .\.edge-speech-env\python.exe -B .\Resumes\.uiiter2_05\restore_before_05.py --apply
```

CMD/Anaconda Prompt uses the same commands without `&` or the comment line.
The script hash-checks paths/files, refuses later edits, restores the completed
local tasks 01–04 snapshot and moves new Python files to a private backup. It
never deletes people, templates, conversations or models. New docs/evidence stay
historical. Older UI versions cannot render task 05's seat-assumption markers;
keep those archives' explicit assignment records. Only the dry run was executed.
