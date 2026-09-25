# Integration findings after D1 full-bank preparation

The initial findings below are a source-inspection checkpoint. The later
implementation update at the end records the first modeled D0/E0 adapter;
neither establishes inference or stage acceptance. The immutable source is
`local/releases/n4-catalog-v3/prototype`, receipt SHA-256
`8050c8bee52a6ec83c95f3514cb81219c3664dd43e172a477d35a54888e610d5`.
It explains the next implementation constraints while full ASR collection runs.

## Preserve two distinct application paths

`app/n2_pipeline.py:N2Engine._accept_activity` consumes each native D1 update,
uses the actual ActivityTimeline contiguous exclusive-window selector, calls
the compatible encoder and resolves the result through N2NameMap. Its native
slot identifiers persist within that independent scene. It retains temporal
name support and calls `_revise_supported_spans`. The latter associates actual
presentation word spans with predicted activity, targets the exact text revision
and span IDs, and publishes `transcript_label_revision`. The `_emit` override
also tries these revisions after raw text publication.

Therefore D1 embeddings must not be passed through D0's anonymous clustering
tracker merely to reuse D0 command replay. That would change the application.
D1 joint replay needs the actual N2 naming/history/span-revision path, with
fresh per-scene state and the intended gallery/mode. The captured anonymous
speaker decisions cannot be silently reused for a different gallery condition.
E0 and E1 namespaces remain separate; only their verified matching D1 query
geometry is shared. D0 queries are different and remain separate evidence.

D1's `_speaker_loop` advances the speaker source watermark after each actual
100-ms read and all activity/embedding work for that read. It processes the
native finish update and its caption revisions before the final infinite
watermark. Its local `ready` argument at final close still holds the last push
value; it is not the time at which native finish/revisions completed. Preserve
call order and the true source-delivery census when reconstructing closure.

## Execute the real S7 policy semantics under an explicit clock contract

`vendor/edge_speech_pipeline/research_s7_policy.py:ObservedClock` accepts an
injected `clock` callable and a once-bound origin. This is an available seam for
testing; no global clock patch or edit to the accepted release is needed.
`ObservedEligibility._eligible` checks current clock age and decision readiness,
in addition to source support and admitted-event ordering. `publication_freshness`
checks the age again under publication. A plain S6C batch result omits these
rules and is insufficient evidence of application parity.

`ObservedPolicyDispatcher` retains the same bounded worker and source-watermark
protocol. Finite source watermarks cannot be ahead of the clock. Its input
allowlist excludes evaluation truth. A future deterministic cache replay must
preserve these rules, predictor commands, worker order and source delivery;
sorting only ASR words or substituting readiness for source watermarks is wrong.

The clock injection API does not by itself qualify replay as observed. If a
modeled clock is used, the enclosing result must say so even though inherited
S7 field names contain `observed` or `monotonic`. Such results cannot supply
first-visible or hardware latency. The current ComponentPresentation adapter
explicitly rejects observed-clock records; a new separately versioned adapter
and tests would be needed to consume actual S7 policy output under any declared
modeled contract. Preserve all original raw ASR and final formatting parents.

Actual Controller parity must be demonstrated separately, with unchanged common
source/UI and explicit event-clock evidence. Per-component isolated call costs
do not measure contention, policy-queue delay, widget application or complete
stack memory. The required source-paced retained-stack panels and continuity
runs remain necessary. No coupled or GUI cells have been counted here.

## Available evidence and next work

- D0 full-bank review: 960 cells passed; global persistent-source activity output
  still needs implementation. Unassigned/conflicting/overlap/tail regions remain
  explicit; embedding windows are not a substitute for DER.
- ASR full bank: active under its immutable admission. Preserve all its bound
  code and run the terminal full reviewer after its exact coordinator exits.
- D1 full bank: 960 cells prepared, with a runtime predecessor gate requiring
  passed ASR full-bank review. No D1 numerical worker or waiter has started.
- Existing command and presentation helpers have narrow tested scopes. Build
  their causal joint integration, gallery/mode factors and metrics without
  promoting a helper test or cache-collection count to integrated acceptance.

All source inspection is read-only. For the exact current process/admission
state and continuation commands use N4_HANDOFF.md and the per-run READMEs.

## First implemented modeled S7 path

`component_s7_replay.py` now merges reconstructed ASR/D0 commands and invokes
the actual S7 dispatcher, observed-eligibility mixin, tracker, publication
freshness check and caption state with an injected zero-origin modeled clock.
The source-progress watermark is never replaced by availability. D0 partial-tail
closure retains its original ready argument and separately waits for source
delivery. Policy queue/compute/publication delay are explicitly zero assumptions;
native worker mixed-clock ages are omitted. No first-visible latency is claimed.

Twelve tests passed, including stale evidence under another lane's delay,
publication expiry, strict watermark equality, stale caption rejection, exact
raw/final preservation, command validation and real worker failure cleanup.
`probe_component_s7.py` then passed eight A0/A1/A2/A3 x O0/O1 development replays
with the accepted D0/E0 component pair. Every source file and compressed/expanded
event binding was reverified. Model loading was forbidden. The output preserved
all 350 raw ASR observations and 27 final utterances; each worker fully drained.
`COMPONENT_S7_REPLAY_CHECK_V1.json` binds the private receipt and exact code.

This path is restricted to Balanced anonymous D0/E0. Its native `observed` and
GUI field names contain modeled values only; complete Controller/widget parity
is still unqualified. Next implement the actual N2NameMap gallery/mode and D1
activity/history/span paths, then qualify exact application parity and integrate
full activity/scoring. Do not generalize this adapter to D1 by using the D0
cluster tracker. Integrated acceptance remains 0/7,680; read
README_COMPONENT_S7_REPLAY.md for API, purpose, limits and all shell commands.

## D1 anonymous application-method integration

`component_d1_replay.py` now executes the unchanged N2Engine activity, query,
N2NameMap(None), temporal-history and span-revision methods with sealed native
frames and compatible cached vectors. A cooperative worker yields inside
`embed` while retaining the actual N2 RLock. Raw ASR publication and the actual
nonblocking caption-revision call can run during that wait; they cannot use a
query before its modeled completion. D1 embeddings never enter D0 clustering.
Actual query waveform hashes, slot/session identity, native coverage and all
short-run denominators must reproduce the sealed component exactly.

Nine tests passed, including text arriving while the real lock is held, precise
target revision/span IDs, overlap rejection, short speech without an embedding,
tail/formatting preservation, corruption and thread cleanup. Sixteen modeled
development checks then passed with the accepted smoke evidence: four ASRs x
two encoders x both taps, 312 replayed queries, 700 raw observations and 54 final
utterances across those compositions. These counts include intentional reuse;
they are not 16 new neural inferences. Private receipt:
`local/n4/component-d1-probe-v1/RESULT.json`, SHA-256
`1bb7c21dea22065bfb7e6f5a8baa0908f1cf07a5064c4ab2e950ef52c467f21b`.
COMPONENT_D1_REPLAY_CHECK_V1.json binds the exact code and evidence.

The scope remains anonymous. Native name-history/embedding host timestamps and
name compute are diagnostic values outside the injected modeled clock. Native
frame receipt/availability in replay uses the dispatch-completion endpoint, not
a measured input receipt. No first-visible or full-stack resource claim follows.
The next integration work is the correct model-bound E/C/Q gallery and distinct
named/selected/closed mode/display paths, global D0 activity mapping, and exact
Controller parity. Use the accepted source's real N2Gallery/N2NameMap and
PrototypeIdentityResolver/annotation paths appropriate to each catalog tuple;
do not infer named behavior from these anonymous probes. Then run/scoring-bind
the full matrix and qualify retained stacks at source speed. All 7,680 integrated
acceptance cells remain pending. README_COMPONENT_D1_REPLAY.md gives the complete
inputs/outputs, limitations and PowerShell/CMD/Anaconda commands.

## Fixed galleries and catalog-correct naming modes

README_MODE_GALLERIES.md now documents verified primary 15-second E0/E1
galleries. Twelve integrity/mode tests and 160 actual begin-method checks
passed. MODE_GALLERIES_CHECK_V1.json binds private mode-galleries-v1/RESULT.json,
SHA-256 `13ca4c7c749df7399a8ddaeb44b045524e513937cc475f5981184f5a907a70b1`.
The original extraction/publication/gate transformations and every immutable
source file were checked. Baseline uses actual ResearchGallery/ProfileStore
with a private exact float32 bridge; N2 uses its real encoder-specific gallery.
Missing E references remain 10/34 open and 1/4 selected for each encoder.

Actual catalog routing differs from simply grouping by D0/E0: baseline uses its
original resolver, while all other 15 entries use N2NameMap. Baseline nominal
thresholds do not enforce N2's processed-query reject-all gates. Closed baseline
display can fall back to a marked roster assumption without voice; N2 annotation
does not implement that fallback. MODE_POLICY_FINDINGS_V1.md records this exact
source behavior and its effect on interpreting SCORING_PLAN.md. Do not silently
fix, suppress or call baseline names calibrated. This is an observed product
implementation gap, not a measured recognition outcome.

component_mode_replay.py now connects those actual mode-begin methods to the
tested causal D0/D1 paths. Eight integration tests passed, including actual D1
lock timing, unknown/closed state, overlap, exact queries, separate published
annotation versus caption state, formatting, namespace errors and worker cleanup.
README_COMPONENT_MODES.md supplies its inputs/outputs, limitations and all shell
commands. Native host timing stays diagnostic and modeled publication stays
modeled. Next qualify complete actual Controller event/label projection parity,
global D0 activity and bank scoring. Do not infer GUI delivery, accuracy or
hardware fit from these method checks; integrated acceptance is still zero.

The sealed-evidence mode probe passed all 160 combinations at 05:56:59 UTC:
four ASRs x both diarizers x both encoders x five modes x both taps. The two
existing smoke source files were deliberately reused; no new model inference
or independent scene coverage is implied. It preserved 7,000 raw observations,
540 final utterances and 20,673 modeled annotated displays over 146,300 commands.
Every actual policy/cooperative worker exited; 160 private round-trip-verified
gzip files total 117,570,100 bytes. COMPONENT_MODES_CHECK_V1.json binds the
private component-modes-probe-v1/RESULT.json, SHA-256
`eac273f168f5cc7e7be46677a23514752c7586cfcc1c308b965f6000e8498b01`.
The actual application methods are now exercised for fixed named galleries;
next work is complete Controller event/label projection parity, global activity
and the admitted/scored matrix. Keep the original method limitations intact.

## Downstream Controller projection and remaining producer qualification

The new controller_projection.py runs actual Controller construction, backend
selection, mode switching, caption-consumer threading, snapshot label/text
projection, closure and cleanup over sealed modeled display records. Eight
tests passed. README_CONTROLLER_PROJECTION.md gives the API, exact input/output
bindings, isolated research roster, limits and all shell commands. There is no
model Start, neural inference or GUI. CONTROLLER_FINDINGS_V1.md records the
selected-focus constant-Unknown description versus numbered output discrepancy
and keeps closed display assumptions distinct from confirmed profile IDs.

This qualifies a downstream consumer path, not the complete producer chain.
The next independent implementation must exercise the actual source methods
below before claiming complete application replay parity:

- PipelineEngine._transcript_event emits the research observation and independent
  raw s6d_text_ready before policy admission, with its actual ASR serial, token
  IDs and text revision. Its source-start, raw final and formatting parents must
  exactly match the component evidence.
- PipelineEngine._scheduled_event expands D0 speaker_decision fields into the
  published payload while preserving S7 availability fields. Existing modeled
  policy records retain nested decisions; they are not identical serialized
  application publication events.
- PipelineEngine._emit assigns publication_sequence across all event kinds,
  source cursor and session fields, performs publication_freshness under its
  event lock, consumes the actual presentation state and recursively emits
  s6d_display. PrototypeEngine annotates the immediate display, and N2Engine
  invokes its nonblocking D1 revision hook after raw/policy text events. A
  caption-only synthetic sequence is not an exact full publication sequence.

Use a separately bounded derivative/harness and preserve all existing source
and result hashes. Check full event ordering and fields, stale publication,
raw-text independence, revision/span targeting, tail/final formatting and drain.
Any modeled clock remains explicit; it cannot supply first-visible hardware
latency. Compare resulting display output through the actual Controller path
already exercised here. Complete coupled inference/GUI/resource confirmation
still requires the source-paced retained-stack runs. Global D0 activity and
full-bank scoring remain separate open requirements; no integrated acceptance
credit follows from either helper alone.

The sealed production probe passed all 160 consumer/projection cases at
06:28:18 UTC. Every one of 20,673 inputs was consumed, every primary raw-text
fragment remained visible and all actual closure/owner checks passed. Exact
private receipt SHA-256 is
`b8cda6e34779b93a51295e1eab7360802e1b08c80319305b05b47b2dc035c18b`
at local/n4/controller-projection-v1/RESULT.json. The 160 compressed outputs
total 23,342,988 bytes. CONTROLLER_PROJECTION_CHECK_V1.json binds the evidence
and tests. Counts include deliberate reuse and unchanged snapshot context;
they are not accuracy, independent-scene coverage or integrated acceptance.

## Actual publication methods and successful empty outputs

The producer-method gap above now has a bounded implementation in
application_publication.py. Actual constructors, begin routing, transcript,
scheduled decision, watermark, formatting and inherited emit methods execute
against the sealed components. Only session/model/source startup is suppressed;
the publication observer sits at the real events.put seam. Module-local clock
facades preserve modeled timing without changing the global clock, filesystem
source or another process. The actual emitter assigns serials, flattens the
scheduled decision payload, applies freshness/state and recursively publishes
annotated displays. Actual D1 lock/history/query/revision behavior remains in
the path. These are harness-scoped serials: startup/I-O and ASR/D0 dispatch
diagnostic events are omitted, so full-session publication parity is unqualified.

Nine tests passed. The 16-case selected-closed O0 smoke matched all earlier
caption histories and final projections; the expanded 160-case check reused
those 16 unchanged artifacts and matched all 160 histories/finals at
2026-09-25 06:58:55 UTC. It retained 189,662 actual publications, 20,673 displays,
7,000 raw observations and 540 finals across deliberate source reuse.
APPLICATION_PUBLICATION_CHECK_V1.json and README_APPLICATION_PUBLICATION.md
record evidence, inputs/outputs, modeled-clock limitations and run commands.
Private publication-modes-v1/RESULT.json SHA-256 is
`6360ff7d520789d7bbe3b76f62a105f8d5f8e0a22dbfa6baaa489be29591d186`.

The closed A0 index also exposed 19 files with zero ASR observations. V1's
nonempty display admission could not represent these successful executions.
The fresh controller_projection_v2.py accepts an empty result only with a
fully drained, closed publication trace, one exact closing watermark per lane,
zero raw/final/formatting counts and no hidden text/caption event. Actual
Controller consumer/closure succeeds without a made-up caption. Four tests
passed, including nonempty regression and invalid empty-trace rejection; all
19 closed files x two baseline modes then passed (38 cases). The ASR terminal
review remains pending. EMPTY_CONTROLLER_CHECK_V1.json and its V2 README bind
this development result. Private empty-controller-v1/RESULT.json SHA-256 is
`43c1ebc1f90810e51978944f37843a004e11f0795fdc118840add878a1bb434a`.

All 396 compressed/expanded artifacts and 198 Controller closure bindings were
reverified, and both exact helper owners exited. No numerical model was loaded.
These completed helpers and their code/README bindings are now immutable.

Remaining integration work, in dependency order:

1. Inspect the current ASR supervisor/coordinator/model PID creation identities,
   resource affinities and heartbeat. After terminal completion and coordinator
   exit, run the already-prepared full ASR reviewer. Only its passed review may
   admit the existing D1 full-bank plan; do not launch a duplicate model/waiter.
2. The bounded complete-bank join/runner is now implemented and tested in
   integrated_bank_plan.py and integrated_bank.py. After all three reviews pass,
   prepare the exact main plan and execute under fresh storage admission using
   README_INTEGRATED_BANK.md. Then admit the separate mode panel. Keep execution,
   missing input, successful empty hypothesis and unqualified measurements
   distinct. Preserve the new code/README bindings and use derivatives for fixes.
3. Use integrated_scoring_adapter.py with immutable Q references only after
   prediction closure. The full-bank driver, exact-owner per-cell metric timeout
   and paired/stratified reporting are now implemented in scoring_bank.py,
   metric_process.py and scoring_report.py; follow README_SCORING_BANK.md.
   Empty successful hypotheses count missed reference words; execution failures
   remain failures. Preserve fragments, source overlap, speaker identity and all
   denominators. Existing D0 speech/overlap masks and sparse track support do not
   supply a persistent global-speaker timeline; do not manufacture D0 DER.
4. Qualify the source/model/journal/Controller chain on the predeclared panels
   and retained stacks, then actual private-desktop GUI delivery, continuity
   and whole-stack resources at source speed. Modeled timestamps and this
   helper's partial publication trace cannot establish observed GUI latency,
   complete source/session parity or hardware fit.

N4 acceptance remains 0/7,680 integrated cells. N5 remains preparation until
accepted N4 configurations and offline release validation exist. The packaging
reserve and campaign deadline remain unchanged; live CM5 checks stay deferred.

The complete-bank implementation passes 13 tests, including full 7,680/1,536
fixture counts, all 960 real D0 parent bindings and actual baseline, A3/D1/E1
and empty-output prediction boundaries. Main mode was declared open_with_names
before bank execution; four additional modes use the unchanged 24-cell panel.
The unavailable multitalker placeholder is recorded separately, while all 16
core tuples remain mandatory. A real prepare call verified the source and
qualification receipts, then refused missing ASR/D1 terminal reviews. No plan
or worker exists yet. INTEGRATED_BANK_IMPLEMENTATION_V1.json binds the results.
The initial catalog-placeholder failure is preserved; code now uses the same
factorial inventory as accepted preparation and keeps unavailable entries visible.

The runner has a single OS writer lock, CPU14/no-model execution, at most 8 GiB
per run, 70-MiB cell peak, drive floors, periodic shared-inventory rechecks and
the original packaging cutoff. Failed predictions retain evidence and explicit
remaining counts; pre-cell resource stops do not become failed predictions.
Complete lossless publication/projection artifacts and real Controller closure
are retained for each result. Its terminal review still grants only modeled
method qualification, not N4 acceptance or physical GUI timing.

## Evaluator boundary checked on sealed method output

integrated_scoring_adapter.py now verifies gzip hashes/CRC and expanded bounds,
reconstructs raw words from contiguous token fragments and requires agreement
with actual caption state and Controller raw rows. It never imports predictor
code. D1 uses all actual native slots with the frozen .5 activity threshold and
intersection with delivered waveform support; native overhang remains explicit.
D0 binary masks and sparse embedding tracks do not become a global speaker
timeline. D0 DER/JER remains unavailable. Formatting is only an ASR-word
preservation diagnostic without formatting gold. All-one-name and all-Unknown
controls expose the fact that permutation-invariant scores cannot certify names.

Ten tests passed. The real saved-evidence probe then scored 32 main-mode checks
from the same two nonoverlap smoke sources plus 19 A0 empty outputs; all 51
passed. All real empty cases were empty-reference controls and had zero
insertions. Missed-word, overlap and incomplete-reference behavior was checked
with dictionary fixtures, not additional saved-scene predictions. There were
no lexical formatting edits in the saved subset. These are development checks,
not new neural inferences or bank results. INTEGRATED_SCORING_CHECK_V1.json binds
the probe receipt, source, tests and the original metric environment; 5,931
installed code/native files were reverified. The exact probe worker exited.

README_INTEGRATED_SCORING.md has purpose, inputs/outputs and all shell commands.
The new scoring driver consumes terminal, hash-verified complete or explicitly
partial prediction banks, preserves every failed/missing denominator, bounds
individual native-library calls using exact owned process identities, and
produces per-composition/mode/tap counts plus paired/stratified reports.
Do not pool reused smoke cases into a scientific aggregate or substitute
modeled publication clocks for widget visibility. N4 integration acceptance,
GUI/name/resource evidence and N5 releases remain separate pending work.

## Persistent metric process and bank-report implementation

Eleven tests now pass for full main/mode-panel census, causal-key corruption,
explicit failed-prefix denominators, weighted/paired counts, actual established
scorer empty-versus-failed behavior and process/pipe fault cleanup. A 51-case
saved-output probe then produced identical metric objects through one persistent
worker. Every installed evaluator code/native file (5,931) was verified again.
All exact launcher/interpreter identities exited. SCORING_BANK_IMPLEMENTATION_V1.json
binds the code, test log and private probe; README_SCORING_BANK.md provides the
complete run contract. No production method bank or scoring run has started.

The driver requires complete-bank terminal review or an explicitly preserved
failed prefix; a still-running or silently reduced bank is rejected. Timeouts
and metric-input errors retain execution COMPLETE with unavailable metrics,
while failed/not-tested predictions retain their own denominators. After three
consecutive scoring errors it stops new metric work and accounts for the rest.
Each scorer run uses an OS writer lock, CPU14, no model loading, a 512-MiB output
bound, drive floors and the existing shared allowance/reservations. Timed calls
never kill by process name or a recycled bare PID. All raw artifacts remain private.

Reports keep composition, mode and tap separate; edit counts and duration are
pooled, not scene percentages. Paired baseline comparisons state excluded cells
and reference denominators and use the existing dependency-cluster bootstrap;
both taps stay together, with room/actor/family sensitivity. The whole bank is
still seen engineering evidence. Names, widget visibility, complete source/GUI
parity and hardware feasibility cannot be inferred from these modeled results.
Run the production driver only after the actual bank is admitted and closed.

The production conversion boundary additionally passed three newly sealed V2
method replays at 08:00:54 UTC: baseline, A3/D1/E1 and successful empty A0. They
match the earlier semantic predictions and reject changed publication counts;
the missing production bank is still refused. These are model-free development
replays, not new neural results. README_SCORING_BANK_BOUNDARY.md documents the
probe. Its first exploratory attempt used older V1 artifacts and was rejected
because they lack V2's explicit empty-session field; that attempt is preserved.
No frozen code was changed to accept the wrong artifact version.
