# Roster identity policies and developer scores

Task 04 changes the existing prototype. `mode_policy.py` defines explicit mode
semantics and bounded existing knobs; `identity_policy.py` wraps the existing
C088 name resolver with a closed-world option and score provenance;
`roster_ui.py` supplies transactional touch selection and developer score pages.
`PersonalStore.gallery(route, person_ids)` narrows actual compatible reference
matrices by UUID before lookup. These files add no model/dependency or new
research tracker. S6/S7 tracking, ASR, segmentation and model hashes are retained.

## Run

PowerShell from the repository:

```powershell
& .\prototype\Start-Prototype.ps1
```

CMD or Anaconda Prompt from the repository:

```bat
prototype\Start-Prototype.cmd
```

Inputs: the same consented microphone or prepared PCM16 mono16k file, existing
personal references, selected UUIDs and recipe/tap. Outputs: captions with
explicit name/Unknown policy, diagnostic scores, and existing local session
logs. Nothing starts capturing just because the mode picker opens.

Mode → choose an ordinary mode. A selected mode opens a draft roster. Only
references compatible with the current tap/gain/domain are selectable. Apply
requires at least one compatible UUID, stops/drains the existing source and
starts a fresh epoch if it was running. Cancel/Back sends no backend mutation.
The selected IDs persist in private `settings.json`; the application still
opens idle in Just Transcription. Deleted/missing/incompatible selected profiles
block a fresh identification start instead of silently broadening the gallery.
Names can coincide; UUIDs determine membership. Rename/delete stops the source,
invalidates current GUI identity spelling/UUIDs and requires a fresh Start.

Ordinary name modes always show one generic Unknown for unnamed people; this
does not collapse their internal tracks. Advanced provides Numbered Unknowns
(no gallery) and ALL enrolled + Numbered Unknowns. The previous global numbered
display preference no longer leaks into constant-Unknown modes.

Mode → Separate display features offers highlighting and explicitly confirmed
hiding for a chosen **independent display roster** (`display_roster_ids`, separate
from matching `roster_ids`). These changes neither stop/restart capture nor load
a different gallery; they are recorded as display-configuration events. Identification
scope belongs to the mode. Hiding requires a named mode and never enables identity
inference by itself. Show all restores full visibility without changing
the identity mode. Raw transcripts and linked archives retain every caption.

## Closed group: explicit assumption, not identity proof

The native C088 resolver still calculates its ordinary result. For a selected
closed group, an eligible current ReDimNet vector is additionally compared only
to the selected references. The current cosine winner is published even when
the open policy rejects it. A fresh direct C088 confirmation of that same UUID
is `accepted`; otherwise the decision is `forced`. A sole selected person is
explicitly a user assumption. A waiter can receive a selected person's name.

The acoustic override requires a finite nonzero 192-D voice vector, actual clean speech
support within the waveform, an associated native track, non-overlap, and age
0–2s at the actual observed policy clock. Silence, overlap, missing/stale data,
audio-gate failure or absent association never invent an acoustic name/score.
Anonymous association and all word delivery stay in S6/S7. Captions
are historical supported spans, not proof of individual overlapping words.

The vendor presentation schema uses `naming_state=confirmed` to carry a published
profile UUID. The adapter separately records `assignment=accepted/forced`,
`closed_group_assumption`, reason and raw scores; it never represents internal
`confirmed` as open-set acceptance for a forced result. Caption evidence IDs
link this decision to `prototype_assignment`. Forced captions show **· assumed**;
if the bounded evidence-link cache cannot resolve an old closed name, it is
conservatively marked `assumed_unlinked`, never silently claimed accepted.
An assignment does not write/adapt a personal reference. Existing anonymous
voice-state accumulation remains independent of the assumed personal name.

**21 September field correction:** closed mode now fulfills Always assign at the
display layer too. Every new caption in a valid selected roster gets a selected
name immediately. Missing acoustic ownership uses `closed_display_assignment`,
separate from `known_profile_id`, naming state, scores and speaker decisions.
Preference is a matching-track voice winner, then a winner within the same
utterance, then a preceding winner within2s. Evidence ending after the displayed
utterance is excluded; at most64 existing decisions are examined. Without such
evidence, the first compatible entry of the selected gallery is an arbitrary
roster fallback. Every such fallback is **Name · assumed**, with its basis and
source event IDs saved. No word timing is inferred. A later supported name takes
precedence; no assumed label trains an enrollment or enters live direction IDs.

Closed display bypasses the ordinary200ms name-stability/pending/Unknown timer.
Open-set, spatial and seat modes retain their existing behavior. Raw words and
acoustic ownership stay unchanged, including unavailable voice after an optional
identity-helper failure. Errors remain visible; a displayed assumption does not
mean the failed model is healthy. Old archives are not backfilled; rename/delete
invalidates assumptions and a new valid roster/Start is required. Matching-gallery
changes already start a fresh epoch, so evidence cannot cross sessions/rosters.

## Scores and existing controls

Settings/Mode → Advanced → Live identity scores presents up to three actual
candidates/UUID suffixes, raw cosine, next-candidate margin, threshold,
accepted/forced/rejected/pending status, speech/overlap/clean duration and
accumulated unique/disjoint evidence. It also reports the actual selected
tracker hypothesis's spatial score contribution and delivered cue age, if any.
Missing fields use `—`; a single reference has no next-candidate margin. Open
scores are the native aggregated voice query; closed assignment uses the current
vector and preserves the separate open result. No score is a probability.
The page updates at most once per second from existing in-memory events; no
additional inference or USB query is added by viewing it.

Sensitivity/weight controls support only these existing fields:

| Field | UI bound | Meaning |
|---|---|---|
| `identity.score_threshold` | 0.35–0.75, step 0.02 | Open-set raw cosine threshold; baseline 0.5128856897354127 |
| `identity.margin_threshold` | 0–0.15, step 0.01 | Gap to the next candidate; baseline 0.03 |
| `tracker.joint_spatial_weight` | 0–1.2, step 0.1 | Existing C079/C060 spatial contribution; baselines 0.60/0.90 |

Controls are disabled when inactive in the current mode. A deliberate change
is applied at a drained fresh epoch and saved in private settings; Reset restores
the exact frozen defaults. Closed mode still assigns below the threshold, so
those knobs affect accepted versus forced status there. They do not change
200ms UI label stability, clean-speech gates, voice-conflict safeguards, ASR,
enrollment quality, source gain or model weights. No threshold was tuned to
make a user's name appear. Missing XVF telemetry keeps spatial modes voice-only.

All effective modes/recipes/taps, unchanged defaults and bounds are exported to
`../docs/MODE_MATRIX.json`. Each actual epoch records its effective profile,
mode/roster/gallery binding and overrides in `prototype_mode_configuration`
and linked session metadata. Current settings are not retroactively attributed
to old epochs. See `../docs/MODE_SEMANTICS.md`, `../tests/README_ROSTER.md` and
`../tools/README_ROSTER.md` for behavior and verification commands.
