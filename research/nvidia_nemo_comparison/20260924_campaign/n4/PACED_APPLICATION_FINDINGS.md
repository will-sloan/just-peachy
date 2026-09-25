# N4 actual application panel: inspected integration requirements

This is a read-only source checkpoint, not an executed neural/GUI panel or
shortlist. Source is the unchanged n4-catalog-v3 release, receipt SHA-256
8050c8bee52a6ec83c95f3514cb81219c3664dd43e172a477d35a54888e610d5.
It records concrete differences from the accepted narrow N3 GUI helpers.

The future main panel must use PREPARATION_V2_CHECK.json's exact 24 audio-only
jobs (12 frozen scenes, both taps). Select baseline plus supported alternatives
only after the full matrix is reviewed. Do not reuse N3's three-example A1-only
or A2/A3/D1/E0 roster assumptions as the N4 population. The separate mode panel
uses the fixed N4 conditions in mode_galleries.py; open, selected and closed
conditions have different intended/available rosters. No scene-driven roster
selection, E-vector recomputation, naming threshold fit or source reset at known
turn boundaries is implied by this checkpoint.

## Actual Controller startup and gallery interface

Controller._start_session obtains the gallery from store.gallery with the
actual query route and selected IDs, then chooses PrototypeEngine, N2Engine or
N3IdentityEngine from its selected catalog composition. It constructs the
archive, calls engine.start_prepared_file, and runs the actual caption consumer.
FileSource, memory journals, model calls, S7 scheduling, event publication,
archive and consumer must all run for the paced application. Do not reuse the
method harness's suppressed session startup or completion marker here.

N4's ResearchGallery baseline bridge preserves exact E0 centroids and the
baseline resolver. However ResearchGallery lacks query_count, whereas the
actual Controller._consume reads engine._research_gallery.query_count at final
drain. Normal PersonalGallery supplies that count and optional adaptation fields.
The earlier model-free projection supplies a zero counter because it executes
zero queries; that is insufficient for actual inference. A paced research-store
adapter must count the actual delegated score calls, preserve the same matrix
and ResearchGallery.score results, and expose adaptation-off metadata. Verify
this against saved-vector fixtures before a live model slot is acquired. Do not
change the frozen baseline source or turn its original nominal C088 thresholds
into a claim of processed-query calibration. A compatible research facade is
instrumentation; it must not touch/import the user's PersonalStore.

The other 15 catalog entries use N2NameMap and the actual compatible N2Gallery.
Its query_count exists. The mode-bound N4 gallery contract is authoritative;
N3's helper hard-coded expected_query_domain='XVF_query', while N4's prepared
N2 galleries are admitted as XVF_processed_predicted_windows. Use the verified
N4 loader/namespace, not a new unverified alias. D0/E1 remains nominal and
unqualified because the predeclared association scale fit failed.

## Clock and visibility evidence

The existing N3 helper gets source_started through n2_observer_factory. The
baseline Controller path supplies no N2 factory, so this cannot provide all
N4 origins. All actual engine events reach Controller._consume and its existing
_adaptation_event hook before normal consumer processing. A narrow observer can
record the original source_started payload there while delegating the original
method unchanged. Record the payload's source_epoch_monotonic_sec, not the time
the observer noticed it. Preserve event ordering, full source sample counts and
source/journal closure. The observer's receipt time is a separate measurement.

The common UI's record_presentation explicitly measures Tk text application,
not viewport visibility or scanout. Its history Text marks active rows with an
elide tag and renders those rows in a separate active Text pane. Long active
paragraphs can scroll a heading out of view while caption text remains visible.
widget_visibility.py now checks the actual pane geometry and exact marked text;
its private-desktop qualification is separate from observed source-paced timing.
Attach it after actual render/layout and on relevant scroll/layout observations.
Do not call _display_row again from the observer: it advances GUI label state.

Keep first-visible, first-final-visible and latest sampled states, strict-filtered
rows, heading suppression, offscreen rows and missing observations. Point samples
do not establish continuous wrong-name exposure between samples. The helper
does not infer correct people, turn approximate ASR spans into phonetic timing,
or grant complete pipeline latency qualification merely because a source origin
was supplied. Source-paced actual inference, source delivery, captions, archives,
timing-sensitive repeats and continuity remain separate required evidence.

## Controlled resource and desktop scope

N3's existing run_private_desktop launcher creates a separate Windows desktop,
never switches to it and records input-desktop preservation and clean process
exit. Reuse the admitted launcher with hidden parent processes; no visible app,
mouse/keyboard injection, microphone, playback, USB or Pi operation is needed.
Do not run a neural GUI candidate while the ASR or D1 component owner is active.
Existing resources.py pins its CLI to CPU4; do not run that CLI concurrently with
the current CPU4 neural owner. Future resource measurement must account for
the actual complete application/child tree, cold load, warmed sessions, gallery,
archive, GUI, caches, private commit versus resident memory, and teardown.
Keep controller/GUI observer cost and sampling limitations visible. No correction
of pacing error or desktop-to-CM5 real-time claim is authorized by these helpers.

Next: complete the verified component and modeled-bank reviews/scoring, implement
and qualify the actual research-store/clock/resource hooks without model loading,
then admit one shortlisted actual application at a time. The packaging reserve
and deadline remain unchanged; no part of this checkpoint grants stage acceptance.
