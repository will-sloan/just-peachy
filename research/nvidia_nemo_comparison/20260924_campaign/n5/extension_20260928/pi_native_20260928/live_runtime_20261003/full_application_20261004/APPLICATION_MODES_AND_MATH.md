# Application Modes above the backend

Build21 selectively reconnects the original `prototype/app` UI and policies.
Backend, source, application Mode, participant roster and display roster are
separate choices. The backend supplies speech/voice evidence; the Mode decides
how the existing association and presentation policies use that evidence.

| Original Mode ID | Display and evidence behavior |
|---|---|
| `caption_only` | All captions; no personal lookup or speaker inference. |
| `enrolled_names` | All compatible enrolled UUIDs; insufficient evidence is one Unknown. |
| `selected_focus` | Match selected compatible UUIDs only; outsiders may remain Unknown. |
| `selected_closed` | Always displays a selected name, including explicitly assumed fallback. It can misname outsiders; an assumption never trains identity. |
| `spatial_assisted` | Retained C079 spatial association with all compatible names; naming still requires voice evidence. |
| `strongly_spatial_assisted` | Retained experimental C060 stronger spatial association, with conflicts/freshness/decay gates. |
| `spatial_selected` | C079 association over the selected compatible roster. |
| `strongly_spatial_selected` | C060 association over the selected compatible roster. |
| `assigned_direction` | A unique fresh direction within an applied seat region supplies an explicit closed-table assumption, not verified voice identity. |
| `assigned_hybrid` | Selected voice gallery plus an applied seat prior; Unknown remains possible and strong voice conflicts release seat trust. |
| `anonymous_conversation` | Numbered anonymous continuity, no personal-name lookup. Tracks may split or merge. |
| `open_with_names` | Cautious personal names plus numbered anonymous continuity. |

Anonymous backend selections support transcription and anonymous Mode only.
Spatial Modes require Live input; synchronized historical spatial replay is not
connected. Assigned-seat Modes currently require Pyannote + ReDimNet because the
recovered resolver depends on C088 voice-event/calibration semantics. Nemotron
or TitaNet seat naming is explicitly unavailable, rather than silently using
those thresholds. A saved seat template is not a current physical anchor; Apply
anchors the current location and motion invalidates that trust.

The original fast/classic/balanced/patient recipes are retained. Fast captions
has no speaker inference. Classic continuity is a Pyannote transcription or
anonymous recipe. The controller validates these dependencies before Start.

# Architecture and exact source connections

`mature_frontend.py` reuses the original Modes, Advanced, People, roster, seat
placement and Settings pages. `application_controller.py` bridges their methods
to the current manager and gallery helper. `application_contract.py` validates
an exact bounded intent containing Mode, recipe, O0 tap, participant/display
UUIDs, seating and settings. The worker receives that intent unchanged.

`installed_engine.py` constructs the existing `effective_profile` and retained
identity/seat resolvers with the selected named gallery. It keeps the current
isolated source, model/runtime, scheduler and archive. The separate
`retained_caption_projection.py` extracts the original supported-segment display
loop from the pinned installed Controller. Display filtering does not change the
underlying accepted audio or identity evidence.

The GUI never loads speech models or voice vectors. Explicit-consent enrollment
uses the original paragraph, progress/quality and Save methods in a separately
owned `gallery_worker.py`, with parent/child identity ACK before project imports.
The helper is closed before live model construction. ReDimNet and TitaNet have
separate writable, hash-bound personal namespaces seeded from independent copies
of the older gallery. No cross-encoder vector conversion occurs.

# Voice and spatial mathematics

For normalized query and reference embeddings, voice similarity is cosine:
`s = q·r / (||q|| ||r||)`. Existing score, next-candidate margin, clean-speech,
non-overlap, unique-duration and disjoint-evidence gates remain authoritative.
Reducing the selected roster does not silently reduce thresholds. Nemotron and
TitaNet retain their own model/domain calibration; baseline developer overrides
cannot replace it.

Direction-only seats require exactly one applied region satisfying
`abs(observed_angle - seat_angle) <= tolerance`, plus the original fresh clean
model-speech and causal-direction gates. This is the retained linear 0–180-degree
array representation: it cannot resolve front/back ambiguity. Multiple regions,
stale cues or released anchors do not force a name.

Hybrid seats use the actual `S6CTracker._joint_scores` from the retained code.
The prior can resolve an otherwise insufficient naming margin only after the
original voice floors, prototype evidence and duration gates pass. A strong
voice/direction disagreement releases spatial trust. Location is never written
into the enrollment embedding. See `prototype/app/seat_identity.py` and
`edge_speech_pipeline/research_tracking_v3.py` for the exact score terms, and the
existing `ARCHITECTURE_AND_MATH.md` for microphone-center geometry and BMI270
rotation. No reliable absolute room translation or heading is invented.

# Session clocks, storage and replay

`spatial_archive.py` attaches a lightweight observer to the existing BMI update
under its existing lock; it adds no polling thread or second sensor read. Each
pose and beam-control read keeps its actual monotonic observation time. Exact
audio callback/sample anchors are a separate stream. These allow an honest join
to the source timeline; they do not prove the DSP's acoustic observation time.
Reference changes and gaps are explicit. The observer is restored at Close.

Normal conversations use manual Stop. A storage-derived ceiling independently
reserves recording and export space:
`seconds = floor(((free - safety_reserve)/2 - fixed_metadata) / bytes_per_second)`.
The current conservative rate includes 96,000 B/s for float32 plus PCM16 model
audio, 256,000 B/s for qualified four-channel16k PCM32 raw when enabled, and a
separate metadata allowance. This is a safety allocation, not a five-minute
timer. Rolling queues/caches and segmented disk files remain bounded. Model
load, backlog, drain and cleanup retain finite deadlines. A safety fault can
Stop a session before the operator does.

After Stop/drain: Save session retains audio, captions/revisions, transcript,
configuration, gallery pins/snapshots and available beam/motion timelines.
Save without physical raw omits that raw audio. Discard removes this entire
temporary session, including its transcript/artifacts. Saved UUID recordings
are paged and capacity-driven, with no four-session deployment counter.

Local store: `/home/peachyprototype/JustPeachy/data/runtime-v29/recordings`.
Each active session spools under its UUID here; Save changes its retention state,
rather than moving it to another hidden folder. Export folder:
`/home/peachyprototype/JustPeachy/data/runtime-v29/recording_exports`.
ZIP entries are `<uuid>/session.json`, segment/caption/event/artifact JSONL,
human transcript, exact segmented float/WAV, qualified raw binaries and
registered private artifacts. Session/segment/artifact indices describe the
actual clocks, format, sample counts and hashes. Keep the complete ZIP, not just
one WAV, for later analysis. Historical spatial replay and batch comparisons
remain future work; current saved-WAV modes consume the processed timeline.

# Explicit limits

The optional historical DPDFNet route, adaptive-reference promotion and
Windows-only transcript-review model are not connected to this isolated CM5
runtime. Their controls explain the dependency; no silent bypass is offered.
Problem markers save metadata; the older RAM audio-excerpt writer is not bound.
The old dual-diarizer refinement admission binds earlier content and stays
disabled. These are remaining restoration limits, not successful features.

Native checks cover representative backends, actual UI workflow, a310.2-second
manual Stop, both enrollment model preparations, anonymous Discard and selected
rich export. They do not establish human enrollment quality, every Cartesian
Mode/backend combination, physical touch, noisy-room accuracy or hour-long
whole-application stability. The earlier failed whole-application hour remains
failed. See `RESTORATION_FINDINGS.md` for the exact evidence and failures.
