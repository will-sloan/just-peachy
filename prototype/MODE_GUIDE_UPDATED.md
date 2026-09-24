# Modes, recipes and personal references

Start the app using `Start-Prototype.cmd`, or run these commands from the
repository directory. It opens idle unless you have enabled saved microphone
permission and **Listen when app opens** in Settings. The CM5 installation can
launch and listen automatically using its local models, without internet.

On the configured CM5, **Settings → Motion sensor · relative direction** shows
BMI270 status and experimental rotation assistance. The sensor is currently
electrically connected but unmounted: native XVF angles remain in use. After
assembly, use **Confirm mounted as described** once in the motion page. A fresh relative frame starts
automatically after two quiet seconds at startup. Three-dimensional turns and
ordinary tilt preserve the reference. Acceleration clears uncertain old locations;
sensor interruptions automatically start a new frame without reusing old angles.
Gyro drift, translation, and linear-array front/back ambiguity remain limits.
Assigned seats require Apply after relocation. The same corrected evidence feeds
existing spatial modes; raw angles remain in
Beam diagnostics. See [motion guide](app/README_IMU.md) for limits and controls.

PowerShell:

```powershell
& .\.edge-speech-env\python.exe .\prototype\main.py gui
```

CMD or Anaconda Prompt:

```bat
.edge-speech-env\python.exe prototype\main.py gui
```

The input is consented XVF speech or an explicitly selected prepared file.
Outputs are captions and optional provisional identity labels. Choosing a mode
controls the matching roster and identity/Unknown policy; a recipe controls inference policy; O0/O1 select a
compatible audio tap. The backend validates combinations and starts a fresh
audio/identity epoch when a change needs it. Finished captions remain visible.

The selector uses **✓ simulation-supported** for the established captions and
anonymous paths, and **◇ experimental / real-world validation needed** for
personal-gallery and spatial compositions. ✓ does not promise field accuracy;
◇ is selectable and does not mean broken or forbidden. Recipe-specific tradeoffs
still apply. No new dataset sweep or threshold optimization was used here.

| Mode | What appears | Important limit |
|---|---|---|
| Just Transcription ✓ | All words under a neutral label | Optional speaker inference is off; previously loaded weights may remain resident. |
| ID from ALL Enrolled names - Constant Unknown ◇ | Match all compatible enrolled UUIDs; one Unknown otherwise | Internal segmentation/association is retained; no field-accuracy guarantee. |
| ID from SELECTED names - Constant Unknown ◇ | Match only chosen compatible UUIDs; one Unknown otherwise | Roster genuinely narrows the reference matrix; it does not just filter captions. |
| ID from SELECTED names - Closed group (Always assign) ◇ | Every new caption displays a selected name; missing/weak evidence is marked **· assumed** | Uses available voice, then same-utterance/recent continuity; with no usable match, the first gallery entry is an arbitrary assumed fallback. Outsiders/overlap may be misnamed. |
| Spatial-assisted - ALL Enrolled names - Constant Unknown ◇ | C079 direction supports voice association, C088 personal names | Weak/stale/missing cues fall back to voice. |
| Spatial-assisted - SELECTED names - Constant Unknown ◇ | Same C079 method with a narrowed selected gallery | Nearby seats/reflections can confuse association; captions remain intact. |
| Strongly Spatial-assisted - ALL Enrolled names - Constant Unknown ◇ | Retained C060 location weighting with all compatible names | Default spatial weight .90 versus C079's .60; greater seat-confusion risk. |
| Strongly Spatial-assisted - SELECTED names - Constant Unknown ◇ | Same C060 method with a narrowed selected gallery | Strong voice disagreement, movement recovery and decay remain active. |
| Advanced: Numbered Unknowns ✓ | Existing anonymous numbered continuity, no gallery | Tracks can split or merge; numbers are not verified people. |
| Advanced: ID from ALL Enrolled names - Numbered Unknowns ◇ | Cautious names plus existing numbered continuity | Comparison mode, not the ordinary Unknown default. |

Opening a selected mode opens a **draft roster**. UUIDs distinguish duplicate
names; incompatible current-tap references are visibly unavailable. Cancel/Back
leaves the current mode untouched. Apply needs at least one compatible person and
takes effect at a Stop/drain/new-epoch boundary, retaining cached models. Saved
rosters persist locally, but startup remains idle in Just Transcription.

Closed group is an explicit product assumption, not a new learned identity
algorithm. It queries the current valid ReDimNet voice against selected profiles
and logs accepted versus forced decisions. No forced assignment updates an
enrollment/reference. When clean, fresh voice/association is missing, the acoustic
identity stays unavailable but a separate **Name · assumed** display label fills
the caption. That includes initial fragments and overlap. With no usable match
at all, the first selected-gallery entry is a placeholder, not recognition.
ASR text is never invented to fill silence. Overlap annotations are not
word-by-word source certainty. See `docs/MODE_SEMANTICS.md` for exact rules.

Mode → **Separate display features** offers highlighting and selected-only filtering with a warning. Filtering
hides text based on identity; it does not remove other voices acoustically.
The full retained transcript remains internally available. A small **Show all**
action appears in the top bar whenever this actual hiding filter is on; it
restores all words while keeping the identity mode. The display roster is a
separate UUID list; changing it never changes the gallery or restarts capture.
Highlight/hide never substitutes
for selected-gallery matching. There is no permanent full-width banner.

## Recipes and audio taps

| Recipe | Existing implementation reused | Availability |
|---|---|---|
| Fast captions | C065/M0 accepted greedy ASR with no speaker calls | Caption-only |
| Classic continuity | Actual B36 original tracker inside the corrected scheduler | Caption-only or anonymous |
| Balanced identity | C065 short/mature evidence; C088 conservative personal naming where enabled | All ten modes |
| Patient identity | C067/N03 longer mature evidence plus short path, C088 naming where enabled | All ten modes; initial identity can take longer |

The menu uses the backend's current supported list and reasons. There is no
invented B28 or multibeam substitute. O0's required host +3 dB is applied once
by the live adapter; prepared O0 files already carry their gain. O1 is unity.
The UI performs no gain processing or hardware routing itself.

Spatial assistance is now a **mode**, used with Balanced or Patient. Both use
actual ReDimNet voice evidence, anonymous continuity, the retained position
memory/decay and recent live XVF telemetry. C088 names still require voice
reference evidence: a seat never creates a person or an enrollment. The stronger
mode keeps severe voice-conflict rejection, reduced spatial influence for strong
voice matches and relocation updates. Old positions lose influence with the
existing 12-second decay. Enrollment collection and private storage are unchanged.

Settings → **Live spatial display** adds a compact optional panel above captions.
Solid beams are fresh; dashed beams/positions are last-known. The speaking badge
requires recent existing speech evidence. Colors identify hardware outputs;
`≈ Name` or `≈ Speaker` denotes the pipeline's estimated voice-position match.
Names do not turn this into independently verified person localization. Multiple
beams can follow one voice, music or reflections, and the mono identity stream
does not identify every simultaneous beam. The device-relative 0–180° frame folds
front/rear together. After moving the tablet, **Reset positions** starts a fresh
epoch without deleting saved people. Strong voice can also relocate a remembered
speaker naturally; no uninstalled motion sensor is assumed.

The existing detailed Beam diagnostics page remains available. The compact
display can be hidden without disabling the selected spatial mode. A missing
XVF cue is a voice-only fallback, not a reason to disable a mode. File replay
without a declared cue fixture also runs voice-only. See `app/README_SPATIAL.md`
for timing, selected beam versus fusion cue, bounds and reproduction commands.

## People and enrollment

People → Add person opens a touch keyboard. Names need not be unique: independent
UUIDs identify profiles, and the short ID is visible in lists. Rename, delete,
add-reference, import and export are separate actions. The default personal
store is empty, outside the code/release. Research galleries are not preloaded.
Import/export requires explicit consent because ordinary profile archives contain
sensitive voice data and are not claimed to be encrypted.

Choose **Target: unique usable speech** at 15/30/60 seconds (30s default), or
**Read paragraph → Done** without a timed quota. Consent, then Start recording.
The editable guide need not be read verbatim. Timed targets may need more than
one paragraph: continue with different natural speech. Neither option stops
automatically before the existing 180s cap. Done/Stop drains pending analysis;
Save requires READY, real quality and capture integrity. Paragraph mode accepts
the existing model's minimum admitted 0.5s window but marks references under 15s
as **limited evidence**, not a claim that such short speech identifies reliably.

Progress separates captured audio, measured level activity, quality backlog and
verified unique speech. The bar animates only toward verified support. In Done
mode it represents the verified portion of captured audio, with no target.
Ordinary shared ASR also estimates script coverage/agreement after each quality
block and on Stop. This can lag by 10s; skips, paraphrases, names or ASR errors
never gate voice quality. Only paragraph mode retains the offered text/hash as
reference metadata, alongside raw ASR endpoint text and approximate source
bounds. ReDimNet consumes audio, not the script. No forced alignment, training,
new model or improved-accuracy claim is involved. See `docs/ENROLLMENT_GUIDE.md`
and `docs/UIITER2_06_HANDOFF.md`; live participant and CM5 checks remain pending.

Live enrollment requires the actual person. No unattended microphone capture or
synthetic saved reference substitutes for that check. On return, the user should:

1. Start with consent and read a short passage; confirm real partial/final captions.
2. Stop, add their own reference, inspect usable time and save.
3. Close/reopen; confirm the person persists and test different fresh speech.
4. Try another consenting speaker and silence; inspect Unknown/wrong-name behavior.
5. Exercise selected focus and its full-caption rescue on the physical touch target.

These human checks remain pending. File replay, stub tests and research fixtures
are recorded separately; they do not establish room-specific enrollment accuracy.

## Display, storage and device limits

Task 02 defaults to **Compact 21px**, tighter paragraph gaps and **Immediate**
text. Normal 25px, Large 31px and Extra large 37px remain available. Existing
saved preferences take priority. Settings offers optional 150/300ms display
smoothing; the first pending change sets a fixed deadline, so continuous
partials cannot postpone text indefinitely. It changes only presentation, not
ASR, endpointing, evidence windows, raw journals, audio or embeddings. The
80ms snapshot poll and desktop scheduling add their own delay; smoother text
does not establish better WER.

Words appear while an unresolved identity shows **••• · collecting voice**.
At the next display update after a 1.2s deadline from the first displayed
utterance, unresolved identity becomes one **Unknown**. The 80ms poll, chosen
smoothing and OS scheduling can add to that visible interval. A supported name must remain
unchanged for 200ms before display; strong contradictory/revoked display
evidence removes the old name on the next applied snapshot. A stable late name
can still replace Unknown. Explicit unavailable/invalidated evidence is shown
as **Unknown · voice unavailable**. These are UI rules, not new naming thresholds.
Tentative decisions, scores and raw caption identity remain in Diagnostics and
the existing private event journals. Dots animate only in the GUI.

**Advanced → Numbered Unknowns** and **ALL enrolled · numbered Unknowns** retain
Speaker_1/Speaker_2-style comparisons. Ordinary name/spatial modes always use one
Unknown, even if an older saved global numbered-label preference was enabled.
Generic Unknown does not identify one person: those rows are kept separate.
Repeated headings are grouped only for adjacent supported tokens on the same
track inside one native utterance; a handoff, UUID conflict or missing support
breaks the group. Historical names annotate past words, not current positions.

Settings offers caption sizes and high contrast without reloading models. The
480×800 pixel-check is distinct from comfort zoom. Back to live restores caption
following after scrolling. Diagnostics shows raw text separately from provisional
and final display text. UI verification commands and inputs/outputs are in
`docs/UI_ITERATION.md`.

The optional beam panel is 145px tall at 100%, with focused/scanning/output
shapes, colour keys, a ring for the selected fresh output and dots for estimated
voice-position matches. Dashed/hollow marks are stale. The board-relative 90°
front/rear fold is shown. Tap the panel to collapse it; enable it again in
Settings. Hiding it leaves the selected spatial mode intact. Idle correctly
shows “No fresh direction.” Active navigation tabs are highlighted; Start/Stop
continues to reflect the recording state separately.

**Advanced → Live identity scores** shows up to three actual candidates, UUID
suffixes, raw cosine, next-candidate margin, accepted/forced/rejected/pending
decision, threshold, evidence duration/quality and spatial contribution/age.
Raw cosine is not a probability. No second candidate means no measured margin;
missing evidence is displayed as unavailable. The panel distinguishes the last
decision's recipe from the current selection and refreshes at most once/second.

Developer controls expose only existing cosine threshold (0.35–0.75), margin
(0–0.15) and spatial joint weight (0–1.2). Deliberate changes start a safe epoch,
are logged, and persist until Reset restores exact frozen defaults. Default
thresholds were not lowered. These differ from 200ms UI label stability and do
not tune ASR, enrollment or model weights. See `app/README_ROSTER.md` for precise
fields, launch instructions and tradeoffs. `docs/MODE_MATRIX.json` exports all
54 supported default mode/recipe/tap configurations plus four strong hybrid-seat variants; actual private epochs also
log their selected roster and effective overrides.

Stop delegates actual capture release to the controller. The evaluation firmware
has an eight-hour limit; stop between sessions and follow the device recovery
guide. The app must not reset the device during speech or change default speakers.
Personal reference data is durable; session buffers and journals are bounded by
the documented backend policy. The UI does not start ambient recording on open.
Settings/Diagnostics → Mark a problem offers a diagnostic mark without audio,
or a separately consented saved copy of up to 30 seconds already in RAM. The
excerpt may contain others' voices; obtain their consent. Nothing is played or
newly captured by this action. The saved location is reported in status and
Diagnostics. Session text journaling can be turned off/on when offered by the
backend; existing private references and pinned problem evidence are preserved.
The supported retention controls offer 3/10/20 completed sessions,
64/128/256 MiB session quotas and 60/120 seconds of RAM history. RAM changes take
effect for the next session. Settings also reports remaining disk capacity.
CM5 performance, physical touchscreen comfort and unspecified camera/IMU/GPIO
wiring remain hardware-pending.

**Developer Sessions (task 03):** Settings now offers a linked conversation
archive, separate from those bounded diagnostic logs. New text-only is the
default; New transcript + exact audio requires participant consent. Press Start
separately. Audio recording displays a visible indicator. New preserves the
previous draft; Save pins it. A pinned conversation is never appended to. Mode,
recipe and tap changes reuse models and create a distinct capture epoch.

Reopen restores indexed raw/automatic text and coarse utterance audio links;
notes/corrections remain explicitly user-authored. Playback requires an explicit
output choice and fully stopped capture, and is blocked during enrollment.
Start stops playback first. The master is exact 16k mono float32 model input,
not raw microphones/all beams. One source serves current ASR and identity.
Full ZIP exports contain sensitive audio/identity events; text-only ZIPs omit
audio/vectors/roster. Both are unencrypted and remain local. Delete requires
confirmation and never removes enrolled people.

The linked archive has its own 2 GiB target, 10 inactive-unpinned-draft policy,
256 MiB audio/64 MiB metadata payload caps per epoch and 2 GiB free-space floor.
Pinned data is protected from automatic cleanup; recording loss is visible and
does not silently pad missing samples. Full bounds, paths, source-window export
commands and failure policy are in `app/README_SESSIONS.md`. CPU/RSS/resource
samples describe measured process load, not power, SNR or CM5 qualification.

Task 01's live timing update binds capture to stream startup and counted native
frames, including route priming; it does not use reported input latency as a
hard bound or alter any mode/recipe. Stop retains recoverable captions and the
original failure record, joins workers, and releases the device. A fresh Start
clears the previous GUI error only after cleanup succeeds. Actual gaps or clock
mismatches still stop explicitly. See `docs/UIITER2_01_HANDOFF.md` for executed
checks, limitations and rollback. No timing-adjustment toggle is required.

**Assigned seats (task 05):** Mode now also offers **Assigned seats - Direction
only (closed seating)** and **Assigned seats - Voice + direction + Unknown**.
Both are ◇ experimental user seating assumptions. They do not steer hardware
beams. Use the 0–180° editor: tap a name then a position, or drag a name/point.
Names use UUIDs, so duplicates and renames retain distinct people. Fine controls
adjust angle and region in 1° steps. Default tolerance is ±25°, not the old RIR
measurement uncertainty. Overlapping projected regions are red and require
explicit acceptance of ambiguity or an edit. Front/back-equivalent people cannot
be distinguished by this linear array.

Apply / re-anchor confirms the current location, starting a safe epoch if running.
Cancel and Clear draft do not alter the active layout. Save template is separate:
a saved template never declares a valid physical location. Stop, session end,
leaving the seat mode and app restart require re-anchoring before a new seat run.
**Tablet moved** immediately invalidates seat trust while captions continue and
voice memory is retained. Arrange the draft and Apply again. No automatic IMU or
camera motion detection is configured.

Direction-only uses fresh speech-gated direction to choose a unique assigned
region. It displays **· seat assumed**, with no voice-profile comparison. Missing,
stale, multi-bearing or overlapping-region directions remain unavailable/ambiguous;
all words remain. A visitor, singing voice or detector error can still be misnamed.
The existing segmentation/embedding lanes remain for speech/ownership; no CPU saving
is claimed. Hybrid uses only the assigned UUID gallery and keeps the C088 voice
floor and unique/disjoint evidence requirements. Its soft C079 / strong C060
control changes the retained spatial prior; Unknown remains. Strong voice conflict
or relocation releases involved seat priors until re-anchor. A missing/conflicting
direction can leave a clearly reported voice-only decision. A spatially resolved
voice margin displays **· spatial support**, never certainty from an angle alone.

Advanced scores explain the decision basis, direction/age, anchor, conflicts and
released priors. Native radians, degrees and mapping provenance are retained in
diagnostics. See `app/README_SEATS.md`, `docs/MODE_SEMANTICS.md` and
`docs/UIITER2_05_HANDOFF.md` for parameters, checks and the field-test limits.
## Task 07 — Text assistance is separate from identity

Settings → Text assistance / vocabulary offers Suggestions and Approved
automatic rules, both initially Off. The original compact dictionary produces
possible spellings for review; it cannot prove a word was misheard. Explicitly
approve a name/context word or alias, with a required independent context and
individual approval for any automatic rule. Amir and Emir have no universal
replacement; another enrolled Emir, a title, a substring, conflicting rules or
protected content prevents an automatic change. Renaming/deleting a linked
profile disables its preference until re-approved. A speaker label never forces
their name into the sentence, and corrected text never supports identity.

✎ marks optional assisted caption text. Either switch Off restores original
formatting. Raw ASR, provisional case, learned final formatting, assisted text
and manual edits retain distinct provenance/source links. Review recent finals
shows eight captions; stop/drain before using its touch keyboard to make a manual
correction. Sessions shows separate corrections and Undo; the original journal
is unchanged and exports retain the log. Manual edits remain labelled in review
and annotations; they are not assigned new speaker-owned word tokens.

“Bias enrolled names” is visibly unavailable: Sherpa 1.13.4 has the API but the
qualified Giga ASR lacks a matching bound BPE vocabulary. The punctuation BPE
cannot substitute. Greedy decoding, models, S6/S7 recipes and all identity/spatial
modes stay unchanged. No hotword/beam A/B, noisy-word reconstruction, acoustic
confidence or general recognition gain is claimed. See `app/README_TEXT_ASSISTANCE.md`
for bounds and `docs/UIITER2_07_HANDOFF.md` for actual checks/limitations.
# Consolidated release status — proto1-0.2.0

Includes tasks01–07: timing/Stop, calm captions/touch, linked audio sessions,
roster/Unknown/scores, assigned seats, paragraph enrollment, and default-off
text assistance. All existing modes/recipes and applicable O0/O1 choices remain.
The simulation/experimental symbols retain their previous evidence meanings;
packaging and software checks do not establish live recognition accuracy.

Task08 adds an optional **motion-event contract**, with the physical BMI270
driver disabled. Moving/settling/uncertain events invalidate assigned-seat
confidence, display re-anchor guidance and preserve voice enrollments.
Stationary does not automatically re-anchor. Manual Tablet moved still works.
This is not room tracking or absolute yaw; no rotation compensation is applied.
No sensor is needed for captions, enrollment or saved-file replay. Camera/GPIO
drivers, physical touch and CM5 performance remain pending. Acoustic enrolled-
name bias also remains unavailable; text suggestions/rules are separate from
speaker identity. See `docs/UIITER2_08_HANDOFF.md` and the wiring checklist.

## Task09 optional paragraph evidence and reference comparison

This is an **experimental diagnostic**, independent of the existing mode/recipe/
tap choices. Settings → Advanced → Text-aware reference selection defaults Off.
When On for paragraph enrollment, ordinary unbiased ASR and the existing audio
quality gate describe coverage and select up to six contiguous 2–4s contexts.
Intended words and correction notes never become verified speech automatically.

In a name mode, the comparison page shows original versus alternate **voice
cosines** for the latest query, with its age. The original enrolled reference
still supplies the actual name/Unknown decision. It does not enable name bias,
add an ASR worker, change a seat assumption or make angle/text prove identity.
Captions, Anonymous, Enrolled Names, Conversation + Names, Selected Focus,
Balanced/Patient/Classic and applicable O0/O1 choices keep their existing behavior.

No calibrated matched-content/phonetic score is available. Installed transducer
emissions provide approximate token timing, not validated phone boundaries or
reliable query-content confidence. Alternate scores can be lower or higher:
the small actual-audio check is functional evidence, not an accuracy gain or new
simulation-supported mode. Toggle Off, then Stop/Start, to remove advisory
comparisons without changing profiles. See `docs/ENROLLMENT_GUIDE.md` and
`docs/UIITER2_09_HANDOFF.md`. Task09 is local source; task08's ZIP remains intact.

## Optional enhancement routing — independent of mode and recipe

Advanced → Noise / model routing: Bypass is the default; ASR, identity and both are ◇ experimental. Existing modes, recipes and O0/O1 remain selectable. Selection stops/drains the current epoch and requires a new Start. ASR-only retains original voice references; identity/both require enhanced references with matching helper hash, tap and domain. Original references remain stored.

The coordinator reuses current Pyannote speech/overlap, Sherpa progress, ReDimNet quality, waveform and valid XVF evidence. It reports freshness/uncertainty and yields the optional helper under backlog; it neither invents names nor treats quiet/accent/missing words as noise. No additional beam polling or model swarm.

The fixed native check helped one quiet example and harmed stationary-noise WER. Enhancement also admitted some overlapping speech through the unchanged enrollment gate; do not enroll while others speak. Original and enhanced paths are available for consented session listening. No overall accuracy gain or CM5 readiness is claimed. See [task10 handoff](docs/UIITER2_10_HANDOFF.md) and [exact route/reference/frame contract](app/README_NOISE.md).

## Optional session references — task11

Advanced → **Session references / Undo** exposes Collect, Review, Use approved
bank, Promote selected, Discard and Undo. Collection and matching are **Off** on
launch. This ◇ experimental feature changes reference data only; every existing
mode/recipe/tap remains available. Use a voice-name mode for collection/matching.
It is not an additional neural model or a claim of noise adaptation.

Pending windows need explicit confirmation of the person actually heard **and**
agreement with immutable original voice anchors. Seat-only, forced closed-group
and corrected-text labels cannot certify a candidate. Only disjoint mature
speech counts; usable seconds are visible. Matching gives approved references
at most 10% weight, keeps the original winner and full-roster base gate, and can
raise or lower coverage. Switch Off for original scores; Start fresh to clear
identity history and unpromoted candidates. Earlier captions are never rewritten.

Strong confirmation conflict, overlap/music evidence, motion, clock errors and
incompatible domains freeze collection/matching. Music/noise is not independently
classified; the user must attest to clean solo speech or use Freeze. New Start
clears a freeze. Promotion is explicit, stops capture and preserves clean anchors;
Undo works after restart. O0/O1, beam stream and enhancement model/configuration
must match. Existing archives can retain diagnostic metadata after Discard.

The small native check retained the same held-out name with Off/On/Undo and
rejected outsider contamination. It demonstrates functionality, **not improved
accuracy**. Live human confirmation, room changes and CM5 remain pending.
See [instructions and data schema](app/README_ADAPTATION.md) and
[handoff](docs/UIITER2_11_HANDOFF.md).

## Optional recorded-audio transcript review — task12

Advanced → **Audio transcript review** is Off on launch and Windows desktop only.
Sessions → Reopen → Review this utterance selects one complete ≤20s recorded ASR
excerpt. It reuses the original decoder settings and model cache for a fresh
unbiased decode. This is one alternate hypothesis, not N-best or independent
acoustic confirmation. Names/vocabulary do not bias it or generate missing words.

Original words and any alternative are shown separately, with `−`/accented `+`
changes and warnings for sensitive distinctions. A differing candidate defaults
to abstention; only explicit user adoption adds a separate correction with Undo.
Raw/final ASR and identity/enrollment remain unchanged. Choose an output explicitly
before listening. Review is deferred during live capture, and a new source epoch
invalidates pending results. Existing name/spatial modes and task07 preferences
are independent.

No Qwen/llama.cpp helper is installed. The limited native examples demonstrated
no accuracy improvement; the same recognizer can repeat an incorrect word. A
language model has no justified acoustic recovery role here. Missing/unreliable
audio remains uncertain; live people and CM5 qualification are pending. See
[run/data instructions](app/README_TRANSCRIPT_REVIEW.md) and
[task12 handoff](docs/UIITER2_12_HANDOFF.md).
