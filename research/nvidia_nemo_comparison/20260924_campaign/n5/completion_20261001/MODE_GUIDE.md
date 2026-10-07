# Mode guide

Current build35 scope: build35 is activated through the Just Peachy shortcut.
Opening stays idle with capture off. Choose one of six backend combinations,
Live microphone or Saved WAV, then Open Application and a Mode. Eleven Mode
policies are visible; backend, identity policy and calibration are separate.

Ordinary Pyannote + ReDimNet Start captured 12.5 s and completed Stop and the
selected full Discard in normal03. That whole check FAILED its later Settings
observer. Separate exit-only05 passed idle Open Application, Settings and Exit
with no Start, capture, models or worker launch. These are distinct scopes.
Live53 passed quiet capture after one verified recovery; Saved54 processed C24
speech with 137 indexed parts, 40 text rows and 117 embedding queries.

Hour08 completed 3600 s / 57.6M samples and all 20 source/model/closure gates.
Backlog grew to 495.360 s; source-to-EOF took 4090.959 s. Completion passed,
but sustainable real-time operation did not. Speech/name accuracy, natural
conversation and biometric calibration remain unqualified or UNCALIBRATED.

Normal live uses manual Stop and storage capacity without arbitrary duration,
recording, people, reference or slot counts, or a fixed ordinary backlog cutoff.
Actual memory/AS/free-space, finite capacity-derived file/drain allowances,
bounded queues, source/lease/owner, I/O and cleanup guards remain. Individual
lane delay labels are unavailable; aggregate backlog remains in health metadata.
Model geometry, thresholds and calibration math are unchanged.

## Select a combination, then a Mode

The ordinary chooser has six rows: Pyannote, Nemotron CurrentDelayed, or Nemotron
Chunk52 with two native graph threads, each with ReDimNet or TitaNet. Select
Live microphone or Saved WAV independently and press Open Application. The
retained portrait app opens idle with Start, Mode, People and Settings.

Backend selects diarization timing and voice encoder. Mode selects identity,
continuity and presentation policy. Sherpa ASR/PnC are shared by all six rows.
There is no ordinary Anonymous backend row. The underlying contract retains
12 Mode keys; the mature menu filters standalone Numbered Unknowns
(anonymous_conversation), leaving 11 visible keys across Mode and Advanced.

| Visible Mode | Meaning and limit |
| --- | --- |
| Just Transcription | All words, neutral label, no personal lookup. |
| All enrolled - one Unknown | Compare compatible people in the active encoder gallery; inadequate/conflicting voice stays Unknown. |
| Selected names - one Unknown | Only selected compatible UUIDs enter matching. Outsiders may stay Unknown; all captions remain visible. |
| Selected - closed group | Always show a selected display name. Usable voice chooses its roster winner; absent voice can use a source-linked current/recent assumption or first roster fallback. Assumed names are unverified, may misname outsiders/overlap, and cannot train identity. |
| Spatial - all enrolled | C079 source-clock cues support voice association; missing/stale cues fall back to voice. Directions do not verify names. |
| Spatial - selected names | The same conservative association with only the selected compatible matching roster. |
| Strong spatial - all enrolled | Experimental C060 stronger spatial weighting; freshness, motion, conflict and decay guards remain. Names retain their independent voice gate. |
| Strong spatial - selected | The same stronger association within the selected matching roster. |
| Seats - direction only | A fresh unique manually anchored direction region supplies a closed seating assumption, not verified voice identity. Missing/stale/ambiguous directions stay unavailable. |
| Seats - voice + direction | Exact calibrated voice plus retained seat/conflict policy. Apply at this location; Stop or motion requires re-anchoring. The calibration blocker remains explicit. |
| All enrolled - numbered Unknowns | Names plus anonymous numbered continuity; tracks can split/merge. Available through Advanced. |

Matching roster and display roster are separate. Selected-only display hides
text; it does not acoustically remove voices or restrict the matching roster.
The full internal transcript remains. Seats use the recording's original array
orientation. Plain WAV has no beam/BMI timeline; saved spatial replay needs a
kept rich recording and uses recorded cues, never current motion.

## Unknown, assumptions and calibration

ReDimNet2-B2 FP32 and TitaNet-Large FP32 have separate galleries/namespaces.
Enrollment supplies compatible references; it does not fit calibration. Raw
cosine is not a probability. A supported anonymous track is not an accepted
personal identity, and a displayed roster name is not a verified biometric name.

Pyannote/ReDimNet retains the original C088 resolver/gates; its personal-domain
accuracy remains unevaluated by the repair fixtures. The other five ordinary
rows require independent calibration for the exact encoder, voice-query domain
and roster before biometric naming. Their actual voice queries can execute and
report scores/rejection reasons while names remain Unknown. No C088 threshold
transfers to TitaNet or Nemotron. Closed-group and direction-seat assumptions
are displayed separately from that verification gate.

## Read captions and History

Immediate partials and same-parent revisions remain. The recognizer still
resets internally near 20 seconds to bound native state; this is not automatically
a completed spoken utterance. Actual BPE word-start markers determine whether
the next piece needs a space or continues a word; genuine repetitions remain.
PnC follows assembled speech at pause/Stop through bounded windows and lexical
guards. Raw words, source intervals and delayed speaker revisions are retained.
Token emissions/coarse source windows are not phonetic word timestamps.

Atomic storage replacement retires old children of the exact parent and keeps
source/token order even when a later child's coarse clock falls back. Unknown
text without an actual track can share an explicitly unattributed paragraph;
that presentation grouping never claims a common speaker. Known track changes,
source gaps and explicit breaks remain boundaries. Compact default is 19 px;
larger accessibility choices and saved preferences remain. Pending styling is
steady. Manual scroll freezes its parent window; older History pages preserve
the anchor, and Return to live resumes the current tail.

## Ordinary workflow and storage

1. Choose combination/source while idle, open the app, then select Mode/rosters.
2. For names, use People with deliberate enrollment consent for each encoder.
3. Start authorizes listening. Opening remains capture-off; autostart is disabled.
4. Stop and wait for drain, source/model/worker closure.
5. Save processed or qualified raw+processed session, or Discard the complete
   temporary UUID, including transcript, spatial work and index rows.
6. Use History to reopen/export or deliberately Delete a kept session. Settings'
   Return to backend combinations closes the controller and returns idle to the
   chooser; Discard itself does not invoke that transition.

Normal live duration uses manual Stop and actual storage/resource protection,
not an arbitrary recording count or 120/300-second conversation timer. Logical duration-derived metadata quotas are removed. Activated build35 removes inherited gallery count/reference/snapshot/export ceilings. Paged History and segmented files preserve growing history with bounded
RAM. Real free-space reserves, finite file allowance, queues/payloads and
source/queue-health and finite drain/cleanup guards remain; ordinary manual Stop has no fixed backlog cutoff. A physical I/O fault can stop safely.

Known limit: writable SQLite admission needs 8 MiB above the physical reserve
even before deletion validation. Near that floor, Discard can fail before its
first unlink; the frozen candidate does not establish automatic space recovery.


## Current source and evidence

The repair candidate uses capacity for total recordings and gallery contents.
People consent, separate encoder namespaces, per-item validation and real
free-space/ownership guards remain. Its streamed copies and exports have bounded
working buffers; this does not establish large-gallery speed or naming accuracy.

Read [backend combinations](BACKEND_COMBINATIONS.md),
[recovery](INSTALL_HEALTH_AND_RECOVERY.md) and the runtime
[pipeline notes](../extension_20260928/pi_native_20260928/live_runtime_20261003/CORE_REPAIR_PIPELINE_NOTES.md).
The final selected source will be listed in
[current_build35/SOURCE_MAP](../extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006/current_build35/SOURCE_MAP.md).
Its deployment installer is a separate asset. Historical Mode math remains in
full_application_20261004/APPLICATION_MODES_AND_MATH.md with its original scope.
Current35 operator behavior: individual text/speaker delay labels are unavailable;
aggregate backlog remains in health metadata and timing is unqualified.
Its ordinary manual-Stop path keeps accepted speech while work catches up,
rather than stop solely on accumulated lag. Stop still waits for finite admitted drain; a failed/incomplete drain
does not become a successful recording. Larger lag may expire voice/direction
evidence and leave Unknown; a closed roster assumption remains unverified.

