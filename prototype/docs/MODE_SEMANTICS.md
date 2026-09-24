# Product modes — tasks 04 and 05

Authoritative machine export: `MODE_MATRIX.json`, generated from current
`app/mode_policy.py` and actual frozen profile parsing. Mode selects roster and
naming/Unknown behavior; recipe selects existing evidence/decoder/tracker
policy; O0/O1 selects a compatible input/reference domain. No gallery narrowing
is inferred from display highlighting or hiding.
The two assigned-seat modes additionally follow [SEAT_SEMANTICS.md](SEAT_SEMANTICS.md),
including manual anchoring, front/back ambiguity, motion invalidation and explicit
seat-assumption labels. The matrix now exports 54 default profiles and four
strong hybrid-seat variants without personal data.

| Internal ID / screen mode | Matching roster | Evidence / Unknown | Visibility / status |
|---|---|---|---|
| `caption_only` / Just Transcription | None | ASR only; neutral label | All captions; ✓ established simulation path |
| `enrolled_names` / ID from ALL Enrolled names - Constant Unknown | All compatible enrolled UUIDs | C088 voice rejection; one Unknown | All captions; ◇ personal field use |
| `selected_focus` / ID from SELECTED names - Constant Unknown | Only chosen compatible UUIDs | Same C088 policy; outsiders can be Unknown | All captions; ◇; this ID now genuinely narrows matching |
| `selected_closed` / ID from SELECTED names - Closed group (Always assign) | Only chosen compatible UUIDs | Clean/fresh cosine winner; missing ownership gets a separate marked display assumption | Every new caption has a selected name; ◇ closed-world assumption |
| `spatial_assisted` / Spatial-assisted - ALL Enrolled names - Constant Unknown | All compatible UUIDs | C079 anonymous association + C088 names | All captions; ◇ |
| `spatial_selected` / Spatial-assisted - SELECTED names - Constant Unknown | Only chosen compatible UUIDs | Same retained C079 + C088 | All captions; ◇ |
| `strongly_spatial_assisted` / Strongly Spatial-assisted - ALL Enrolled names - Constant Unknown | All compatible UUIDs | Retained C060 stronger location weighting + C088 | All captions; ◇ |
| `strongly_spatial_selected` / Strongly Spatial-assisted - SELECTED names - Constant Unknown | Only chosen compatible UUIDs | Same retained C060 + C088 | All captions; ◇ |
| Advanced `anonymous_conversation` / Numbered Unknowns | None | Native anonymous voice tracks; numbered labels | All captions; ✓ established simulation path |
| Advanced `open_with_names` / ID from ALL Enrolled names - Numbered Unknowns | All compatible UUIDs | Native anonymous tracks + C088 names | All captions; ◇ personal field use |
| `assigned_direction` / Assigned seats - Direction only (closed seating) | Manual UUID seat map; no voice gallery | Fresh model-speech + native direction; unique region or ambiguous/unavailable; explicit seat assumption | All captions; ◇ unvalidated closed seating |
| `assigned_hybrid` / Assigned seats - Voice + direction + Unknown | Compatible enrolled UUIDs in the applied map only | C088 voice + retained soft C079 / strong C060 prior; Unknown alternative | All captions; ◇ unvalidated hybrid seating |

Status marks do not disable experimental modes or promise field accuracy.
Balanced/Patient support all modes; Fast supports Just Transcription; Classic
supports Just Transcription and Advanced Numbered Unknowns. Patient retains the
actual C067 longer evidence policy. Model/checkpoint and source gain bindings are
unchanged. Selected spatial modes reuse complete C079/C060 trackers, not a new
angle-to-name rule. Missing direction cues cause explicit voice-only fallback.

## Roster transaction, identity and failure conditions

Selected mode entry opens a touch draft picker. Compatible references are
computed against actual current tap, gain, preprocessing and waveform domain.
Names are labels; UUIDs control selection, matching, rename and deletion.
Cancel/Back has no backend side effect. Empty selection cannot identify. Apply
validates the entire roster before stopping, drains the existing source/lanes,
then creates a fresh epoch if running. No old/new gallery is mixed mid-epoch.
Model objects are reused. Roster UUIDs persist in private settings.

Missing/deleted selected UUIDs or any incompatible selected reference block a
fresh identification start instead of broadening or silently dropping people.
An empty all-enrolled store runs with Unknown; an entirely incompatible existing
store reports a capability error. Compatible people can still be used when
other unselected people lack references for the tap. The picker exposes those
unavailable references. Rename/delete stops capture and invalidates displayed
identity; historical immutable logs remain historical. Duplicate names never
collapse UUIDs. No personal store is preloaded with research or synthetic people.

Open modes preserve C088's cosine/margin, unique clean duration, disjoint evidence
and current-voice conflict conditions. They can reject outsiders; imperfect
reference/model conditions can still produce errors. No name requires captions
to wait. One generic Unknown does not mean all unknown turns are one speaker:
segmentation, anonymous association, diagnostic UUIDs and internal tracks remain.

Closed mode retains native anonymous association, then compares the current
finite nonzero ReDimNet vector only to the selected gallery. To force a label it
requires actual clean support within that input window, speech=true,
overlap=false, an associated track, no audio-gate rejection and source-window
age 0–2s at observed policy execution. Invalid/stale/missing voice keeps acoustic
identity pending/unavailable with no invented similarity. A currently
accepted direct C088 result for the same winning UUID remains accepted;
otherwise it is marked forced. Current contradictory voice can change the
winner; a stale name is not silently reused as fresh forced evidence.

A single selected person is a user-assumed label. A waiter can be forced to a
selected name. Closed mode cannot recover missing words, prove personal identity
or reliably identify each overlapping word. No forced decision changes a
personal reference, enrollment or model. Existing anonymous voice-state updates
are not training a named person. Native `confirmed` is the presentation schema
for a published profile; use the separate `assignment/forced` fields for its
actual acceptance status. UI forced captions say **· assumed**; unresolved old
closed provenance is conservatively marked assumed as well.

The 21 September field fix separates **always-selected display** from acoustic
identity. Missing caption ownership gets `closed_display_assignment`; it does
not populate raw `known_profile_id`, change speaker decisions or add a score.
It uses existing valid same-track/same-utterance voice winners, then preceding
voice within2s, otherwise the first compatible selected-gallery entry. That
last option is arbitrary and always marked **· assumed**. The search is bounded
to64 prior decisions; evidence must not end beyond the utterance. Token-time
alignment remains unavailable. Later acoustic ownership supersedes the display
fallback. Every new caption in this mode has a name immediately, bypassing the
ordinary pending/name-stability timer; all other modes retain it. Reopened old
archives are not re-guessed. Invalid/deleted/incompatible rosters still require
correction before a fresh Start. The assumptions cannot affect reference learning.

## Independent visibility and developer scores

Separate display features optionally highlight a display roster or, after an
explicit warning, hide other/Unknown rows. This does not narrow or broaden the
matching gallery. Matching `roster_ids` and display `display_roster_ids` are
independent UUID lists. Display changes do not restart capture; they are logged
as display-configuration events. Hiding requires an already selected named mode
and cannot turn Just Transcription into identification. Full text remains archived; Show all restores visibility while
retaining the identity mode. Both selected matching modes preserve all captions
unless the user separately chooses this display filter.

The Advanced score panel reads bounded existing events at ~1Hz. It displays top
three raw cosine candidates, UUID suffixes, margin, threshold, decision status,
source-window/clean/unique/disjoint support, overlap/freshness, actual spatial
term and cue age where available, plus the decision's effective recipe/tap.
Current selection and last-decision configuration are distinct. A one-person
gallery has no next-candidate margin; `—` means unavailable. Scores are not
probabilities, watts, SNR or proof of identity.

Only existing `identity.score_threshold`, `identity.margin_threshold` and
`tracker.joint_spatial_weight` have bounded developer controls. Defaults remain
0.5128856897354127 / 0.03 / C079 0.60 or C060 0.90. Reset restores exact defaults.
Overrides apply at a safe epoch and are recorded in the private settings,
`prototype_mode_configuration` event and linked epoch's effective profile.
Closed thresholds change accepted-versus-forced acoustic classification; the
always-selected display fallback is independent. Other modes retain200ms GUI
label hysteresis; closed-group display names are immediate.
No new parameter sweep, threshold fitting or model update was performed.

`app/README_ROSTER.md` gives run commands and formats; `UIITER2_04_HANDOFF.md`
records actual verification and outstanding human/live/CM5 limitations.
