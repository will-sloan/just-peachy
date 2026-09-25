# N4 implementation checkpoint — upstream accepted, integrated run pending

New scoring boundary: integrated_scoring_adapter.py uses only the isolated
evaluator and standard-library artifact readers, with no application/model
imports. Ten tests passed in 5.158 seconds. The subsequent model-free probe
scored all 32 open-mode composition/tap smoke checks and all 19 closed A0 empty
outputs. Every raw fragment rejoined exactly; D1 actual native activity was
retained and D0 global-speaker DER/JER stayed unavailable. Formatting made no
lexical edits in this subset. All real empty cases were empty-reference controls
and scored zero insertions; missed words, overlap and incomplete-reference
handling were tested with explicit fixtures, not new saved scenes.

INTEGRATED_SCORING_CHECK_V1.json and README_INTEGRATED_SCORING.md bind code,
tests, purpose, inputs/outputs and all shell commands. The probe verified all
5,931 installed evaluator code/native files and used the unchanged pinned
MeetEval 0.4.3/pyannote.metrics 4.1 environment. The exact worker
14504 / 1790321651.3604755 exited; it loaded no models. Private result:
local/n4/integrated-scoring-probe-v1/RESULT.json, SHA-256
`57720d1273239bd065059deb102079724aac830eb5da240000d12c2909066feb`.
All per-check receipts and code hashes were reverified. These 51 checks are
development evidence with deliberate smoke reuse, not full-bank accuracy.

Next independent work: connect this adapter to a closed complete/partial bank
scoring driver with exact-owner per-cell timeouts, then the existing paired
and stratified report tools. Keep successful empty, failed and not-tested rows
distinct; actual first-visible/naming/complete-stack metrics remain unavailable
until their required observations exist. Preserve all bound helpers and the
ongoing ASR numerical worker. N4/N5 are not accepted.

New complete-bank implementation: integrated_bank_plan.py requires passed,
terminal, owner-closed ASR/D0/D1 reviews and rejoins all 3,840 component parents
against exact audio/source/profile/cache/gallery namespaces. integrated_bank.py
executes the actual publication and empty-safe Controller paths, preserves full
private gzip/closure evidence and provides a strict terminal reviewer. Main mode
is predeclared open_with_names for 7,680 cells; the frozen 24-cell panel adds
four modes (1,536 cells). Unavailable multitalker remains outside the 16 core
tuples with its reason and zero credit. D0/E1 stays nominal and unqualified.

Thirteen tests passed in 19.804 seconds. They include the full matrix fixture,
all 960 real reviewed D0 bindings, actual baseline and A3/D1/E1 replay boundaries,
a real empty-output boundary, incorrect parent/namespace/owner rejection and
failed-versus-not-tested lifecycle counts. The initial catalog-placeholder
failure and passing retests are preserved. INTEGRATED_BANK_IMPLEMENTATION_V1.json
binds code and private logs. A real production prepare call then refused the
still-missing ASR/D1 terminal reviews; no production plan, waiter or worker was
created. Private gate: local/n4/integrated-bank-development-v1/PREPARATION_GATE_CHECK.json,
SHA-256 `649b2acfbf02d01ddf77e99ffa30f271ed1f0a8c2ba53bc7f473f9d6966d656b`.

Read README_INTEGRATED_BANK.md for complete commands and resource admission.
After accepted ASR and D1 component reviews, prepare and execute the main method
bank, then the separate mode panel under a new allocation. Do not overlap either
with controlled source-paced/resource qualification. The runner remains a
modeled method execution: scoring, full source/session/GUI/resource confirmation
and N4 acceptance must still follow. No accepted integrated cells are claimed.

Latest qualification at 2026-09-25 06:58:55 UTC: nine tests and all 160 actual
publication/Controller method checks passed. application_publication.py uses
the actual engine constructors, begin routing, raw transcript publication,
scheduled decisions, watermark, punctuation and inherited emit methods with
isolated module-local modeled clocks. Full projected history and final rows
match the preserved mode/consumer results in 160/160 cases. The two smoke
sources remain deliberate reuse, including 16 reverified smoke checks; this
is not new inference or independent full-bank coverage. Counts are 189,662
publications, 20,673 displays, 7,000 raw observations and 540 final utterances.
APPLICATION_PUBLICATION_CHECK_V1.json and README_APPLICATION_PUBLICATION.md
bind code, purpose, limits, inputs/outputs and all shell commands. Private
local/n4/publication-modes-v1/RESULT.json SHA-256:
`6360ff7d520789d7bbe3b76f62a105f8d5f8e0a22dbfa6baaa489be29591d186`.

controller_projection_v2.py additionally admits only proven complete empty
publication sessions. Four tests and 38 saved-evidence checks passed at
06:58:59 UTC: 19 closed A0 zero-output files x anonymous/selected-closed
baseline modes, each joined to reviewed D0/E0 evidence. No placeholder text
or identity is generated. Later scoring must count the empty hypotheses'
missed words. The ASR full-bank terminal review is still pending; this is
development evidence, not bank acceptance. EMPTY_CONTROLLER_CHECK_V1.json
and README_CONTROLLER_PROJECTION_V2.md bind the fresh derivative and commands.
Private local/n4/empty-controller-v1/RESULT.json SHA-256:
`43c1ebc1f90810e51978944f37843a004e11f0795fdc118840add878a1bb434a`.

All 396 gzip artifacts (153,576,504 compressed bytes; 3,145,968,702 expanded)
and 198 closure receipts were independently reverified. The exact probe owners
45044 / 1790318773.1361148 and 30588 / 1790319398.284181 exited. Neither probe
loaded a model or opened a GUI. ASR remains the sole numerical run, D1 remains
prepared without a waiter, and integrated N4 acceptance remains 0/7,680.
Continue with fresh numerical ownership/progress inspection and the actions
in the final section of INTEGRATION_NEXT.md; preserve these bound helpers.

Earlier downstream qualification: eight tests and 160 actual Controller consumer
and label-projection checks passed at 2026-09-25 06:28:18 UTC. Each isolated
Controller selected its real backend/mode, consumed the sealed modeled displays
on its actual consumer thread, preserved raw words, wrote its closure receipt
and closed. All 20,673 displays were delivered across the reused 16 x 5 x 2
cases; no model, microphone, GUI or personal profile was used. Private result:
local/n4/controller-projection-v1/RESULT.json, SHA-256
`b8cda6e34779b93a51295e1eab7360802e1b08c80319305b05b47b2dc035c18b`.
Its 160 private gzip outputs total 23,342,988 bytes. All code/closure bindings
and the exact probe process exit were verified. CONTROLLER_PROJECTION_CHECK_V1.json
and README_CONTROLLER_PROJECTION.md bind scope and all run commands.

CONTROLLER_FINDINGS_V1.md records actual numbered fallback in every one of the
32 selected-focus development cases, despite the constant-Unknown description.
Keep these observed projections, and retain closed display assumptions separately
from confirmed profile IDs. Do not silently rewrite the baseline. This is
downstream method qualification only: upstream publication ordering/stamping,
complete coupled Controller parity, physical widget delivery, global D0 activity,
integrated scoring and paced resource tests remain pending. INTEGRATION_NEXT.md
now identifies the exact producer methods and gaps to address next. The probe
ran on CPU14 without competing model inference; ASR remains the sole numerical
owner, with D1 prepared but not started. Existing receipt-bound code is immutable.

Latest independent integration work: fixed E0/E1 primary galleries and actual
catalog/mode routing are implemented. MODE_GALLERIES_CHECK_V1.json binds 12 tests
and 160 actual begin-method checks; private mode-galleries-v1/RESULT.json SHA-256
is `13ca4c7c749df7399a8ddaeb44b045524e513937cc475f5981184f5a907a70b1`.
README_MODE_GALLERIES.md and README_COMPONENT_MODES.md give inputs/outputs and
all run commands. The new causal mode adapter passes eight integration tests
and preserves immediate display annotation separately from raw caption state.
MODE_POLICY_FINDINGS_V1.md records baseline-versus-N2 resolver/calibration and
closed-fallback differences. Original nominal baseline behavior is preserved;
N2 open names reject, closed labels remain unverified assumptions. These method
checks do not establish Controller/GUI parity or any accepted integrated cell.

The subsequent mode probe passed 160/160 at 05:56:59 UTC. Its 16 catalog tuples
x 5 modes x 2 taps preserved 7,000 raw observations, 540 finals and 20,673
modeled displays over 146,300 commands, reusing the two smoke-source files.
COMPONENT_MODES_CHECK_V1.json binds code and private receipt SHA-256
`eac273f168f5cc7e7be46677a23514752c7586cfcc1c308b965f6000e8498b01` at
local/n4/component-modes-probe-v1/RESULT.json. All policy/activity workers exited;
private gzip output totals 117,570,100 bytes. No neural model or GUI started.
This completes the modeled mode-method development check, not Controller parity,
visible naming metrics or integrated acceptance. Latest resource inventory plus
full ASR/D1/contingency and extra gallery/probe reservations was 41.598 GiB under
50 GiB, with 33 active/prepared code bindings unchanged. Do not edit code now
bound by these new completed receipts; extend in a fresh derivative if needed.

README_PREPARATION_V2.md describes the regenerated preparation-v2 inputs from
the accepted 16-entry derivative. All 480 waveforms were reverified; the five
data/provenance payloads are byte-identical to v1, and all 16 matrix rows now
bind actual catalog entries. PREPARATION_V2_CHECK.json records zero inference
credit and 7,680 cells still NOT_TESTED.

N1/N2/N3 are accepted in their stated offline/component scopes. N3's accepted
source tag is n3-accepted-20260925-v1; its 34-file analysis ZIP and exact remote
commit were verified. Its report preserves the A1 paced-count correction and
A3 one-core failure/two-core functional qualification. Read the final N3 handoff.

N4 now has a fresh 16-composition derivative from that accepted source:
local/releases/n4-catalog-v3/prototype. Its source receipt verifies unchanged
common UI/layout and only the catalog/expected-set fixture changes. Actual
Controller selection and cleanup passed for all 16 entries, with model
acquisition/enrollment forbidden and zero hardware/audio/GUI starts. This is
wiring evidence, not inference. ACCEPTED_SOURCE_CATALOG_CHECK.json and
UPSTREAM_ACCEPTANCE_20260925.json bind the transition and exact source.

**N4 is not complete: 0/7,680 integrated cells.** The sole current numerical
run is `local/n4/asr-full-bank-v1`, started 2026-09-25 04:30:24 UTC. It collects
1,920 actual component cells: A0/A1/A2/A3, all 480 files each, sequential owners.
Admission SHA-256: `f5c5868f5e9237e25e7c3241d3f5e66f28d46cd03bc83c01c3d42b2762cf33a7`.
Read README_ASR_FULL_BANK.md and ASR_FULL_BANK_START_V1.json. Its coordinator is
initially PID 38788 / creation 1790310624.1776628, supervisor 28376 /
1790310624.033616, both CPU14; initial A0 model 40244 / 1790310626.0298579 uses
CPU4. These are discovery hints, not durable ownership: inspect fresh result,
worker heartbeat, exact PID creation and resource ownership before work.
Do not edit code, tests or README bound by this admission while it runs.

The full-bank ASR runner and terminal reviewer passed 11 tests, including a
complete 1,920-cell integrity fixture, missing-cell/index rejection, source/gain
firewall, actual endpoint/tail capture and bounded UTF-8 storage. Preparation
reverified every waveform and all upstream smoke/source/runtime bindings. The
fresh inventory was 35.9996 GiB; adding full ASR 2 GiB, pending D1 smoke 2 GiB,
future D1 bank 2 GiB and contingency 1 GiB totals 42.9996 GiB beneath 50 GiB.
This conservatively counts already-written smoke bytes as well as future
reservations. Per-cell expanded text is capped at 32 MiB, run allocation at
2 GiB, C/G floors at 50/75 GiB, and the existing packaging cutoff is retained.
No new model download, numerical waiter or concurrent model was launched.

D0 full-bank collection finished 960/960 at 04:02:47 UTC; strict review passed
at 04:11:11 UTC. D0_FULL_BANK_REVIEW_V1.json binds 480 cells per encoder,
13,006 exact matched query windows per encoder (7,404 short, 5,602 mature),
43,388 segmentation calls per encoder, all rejection categories and
2,621,822,924 fully verified expanded event bytes. Eight no-query files per
encoder remain counted. Its exact old coordinator/model/supervisor exited.
The full receipt is private: local/n4/d0-bank-review-v1/REVIEW.json, SHA-256
`0c2eb703ee2cf66d6cd328032fa36507fd3f1cd77281c8cca3668cdae3abc725`.
This is matched component evidence, not calibrated D0/E1, global activity,
integrated/GUI execution or complete-stack resource qualification.

ASR smoke passed 8/8 at 04:21:20 UTC. ASR_SMOKE_REVIEW_V1.json binds all four
variants' two actual application-loop cells. Source 100-ms reads, exact tails,
EOU/reset/drain, original raw/native finals and final-only formatting passed.
Formatting remains actual P0/native P1 in a separately modeled FIFO after ASR
closure, not observed GUI/worker timing. The full-bank run reuses the same
frozen loop/owner contracts and recollects every file, including the smoke pair.
Historical ASR_SMOKE_PREPARATION_V1.json remains an immutable earlier snapshot.

D1 smoke passed 4/4 at 04:29:22 UTC: both encoders, first O0/O1 pair. All 4,470
native frames per file and 20 O0 / 19 O1 query windows match across E0/E1;
two O0 and four O1 short exclusive runs are retained. D1_SMOKE_REVIEW_V1.json
binds the review, SHA-256 `765a5f1d70a871b05e80f2bc193767a9d8ecd3ab3f8ee36f60a03b97fbe15c31`.
README_D1_COMPONENTS.md and README_REVIEW_D1.md describe the exact unchanged
N2Engine speaker loop and activity-window selector. All four cells retain
nominal 1.04-second D1 input buffering and admitted CPU1 runtime, actual frames,
overlap/silence and query bytes. Twenty-two protocol/review tests passed.
These workers exited before ASR full-bank launch. A fresh D1 full-bank runner,
admission and reviewer are now prepared at `local/n4/d1-full-bank-v1`, not started.
Its admission SHA-256 is
`7a290ff7ba55a790c7f5c129eed125af538fbae48d66fc195c2a77ef77d960f5`.
D1_FULL_BANK_PREPARATION_V1.json binds nine passing tests, including complete
960-cell D1 and 1,920-cell ASR predecessor fixtures. README_D1_FULL_BANK.md has
purpose, inputs/outputs and PowerShell/CMD/Anaconda instructions. The real
predecessor check currently refuses model start because the ASR full-bank review
is not yet available; no D1 model or waiter was launched. Preparation reverified
the four smoke cells and all 480 waveform files. Fresh inventory plus this
2-GiB allocation, the full active ASR 2-GiB reservation and 1-GiB contingency
is 41.0163 GiB beneath the shared 50-GiB allowance. Each cell is capped at 32 MiB
expanded text and a 2-MiB serialized summary. The earlier smoke runner still
refuses full scope; its code/admission/results remain unchanged. Preserve both
prepared and active admissions; further changes require a fresh derivative.

The earlier `d0-calibration-v1` finished 734/734 jobs. The strict review passed
3,409 matched windows per encoder (1,985 short, 1,424 mature); no C clip lacked
an admitted window. D0_COLLECTION_REVIEW_V1.json binds this evidence. The single
predeclared C scale fit FAILED its validation tradeoff: balanced error rose
2.583 percentage points versus E1 nominal, beyond the allowed 2.0. Preserve
D0_SCALE_FIT_V1.json/D0_C_SCALE_DECISION_V1.md; do not tune on validation or Q.
The profile was not applied. Nominal D0/E1 remains an explicitly unqualified
comparison condition, not an accepted calibrated release. Its window selection
does not use tracker scores, so full-bank component collection remains valid.
The collector/reviewer/fitter/bank runner have 8/6/8/5 passing tests.

The full-bank acceptance checker is now implemented: README_REVIEW_D0_BANK.md
and `review_d0_bank.py`. It requires terminal 960-cell coverage and an exited
exact coordinator, verifies all bindings, full gzip bytes/CRC, every dispatch
and rejected admission, exact vectors/waveform slices, and paired segmentation/
admission semantics. The completed full-bank review passed as recorded above.

The new `D0ActivityEvidence` observer retains total scene coverage, first/latest
mask observations, exact clean track support, conflicts, overlap and unobserved
tails. It never collapses all unassigned speech into an invented person. Its
real closed-cell probe replayed 41 O0 and 42 O1 E0 embeddings through the frozen
native nominal anonymous scheduler; incremental/batched causal ordering matched.
Thirty-three tests pass (15 review, 12 activity, six reused geometry tests).
D0_IMPLEMENTATION_CHECK_V1.json binds this work; README_D0_ACTIVITY.md documents
the API, constraints and probe commands. Probe root: local/n4/d0-activity-probe-v1.
This is development evidence, with no ASR/gallery or neural model loading, not
S7 observed-clock Controller parity or a global-source decoder. The two probe
files expose 1.82/1.59 seconds of unassigned single speech and 2.39/3.77 seconds
of conflicting track support; these regions must not disappear from evaluation.
The whole-bank distribution remains unmeasured. Global D0 DER stays unqualified.

Zero of 7,680 intended integrated scene/tap cells have executed. Complete D0
activity/application integration, component-cache/archive integration and the admitted
integrated runner; preserve D0/E1's calibration limitation. Then perform paired scoring,
GUI/paced/continuity and resource selection. N5 remains preparation only.
Earlier READINESS/MATRIX snapshots and 12-entry releases remain historical.

Joint-replay building block: `component_presentation.py` connects causal raw ASR,
actual caption-policy and formatting records to the frozen S7/N1 presentation
state. Seven tests pass; COMPONENT_PRESENTATION_CHECK_V1.json and
README_COMPONENT_PRESENTATION.md bind purpose, inputs/outputs and commands.
It preserves all raw tokens, exact-final formatting, same-boundary EOU finals,
session identity and coarse source-span ownership. Observed-clock inputs are
rejected; all inherited presentation `monotonic` fields are explicitly modeled.
This adapter is not the scheduler merge, S7 observed-clock parity or Controller
execution. Do not count it as an integrated cell or claim first-visible timing.
Source inspection confirmed that observed S7 eligibility also checks current
source freshness and publication age; a plain S6C batch replay is insufficient
evidence of that behavior. The integrated runner must resolve and test this
contract rather than silently replacing the observed application clock.


Command reconstruction now preserves actual ASR/D0 scheduler push/watermark
sequences, including partial tails and rejected D0 queries. Seven actual-loop
stub tests passed, followed by successful reconstruction from 12 closed real
component cells (eight ASR smoke, four D0). COMPONENT_COMMANDS_CHECK_V1.json and
README_COMPONENT_COMMANDS.md bind this evidence. D1 commands and the causal
joint merge are still required. The probe does not establish Controller/policy
parity and supplies zero integrated-cell credit.

The first causal S7 integration path is now implemented for Balanced anonymous
D0/E0: `component_s7_replay.py`. Twelve real-policy/worker/span tests passed.
An eight-composition development probe reused the sealed ASR smoke evidence
(four variants x both taps) and matching D0/E0 pair, with model loading forbidden.
It reverified source, waveform, profile, compressed/expanded event bindings,
all 350 raw observations and 27 exact final-formatting parents. Actual S7
freshness/publication checks and caption guards executed, and every real bounded
worker drained. COMPONENT_S7_REPLAY_CHECK_V1.json and README_COMPONENT_S7_REPLAY.md
bind the evidence and run instructions. Private receipt:
`local/n4/component-s7-probe-v1/RESULT.json`, SHA-256
`8feb8b09bef81f504ef4b739b46bd6c8dfe72e4208405501bad4a2f20d2f13ed`.
These are modeled development replays with zero policy queue/compute/publication
delay assumptions, not observed Controller/GUI or accepted integrated cells.
Inherited observed/monotonic/GUI field names are explicitly modeled; invalid
mixed-clock worker ages are omitted. No component or release source was edited.
D1 and named modes were next at that checkpoint; the later helpers now implement
their modeled method paths. Global D0 activity and complete Controller parity
remain required; the eight earlier probes do not complete the matrix.

The separate anonymous D1 path is now implemented in `component_d1_replay.py`.
It executes unchanged N2Engine activity/query/name-history/span methods using
sealed frames and vectors, with a cooperative cached embed call retaining the
actual identity lock. Raw ASR can arrive during that call, and the real
nonblocking revision method must wait for eligible activity/query completion.
D1 embeddings never enter D0 clustering. Nine tests and 16 modeled smoke-derived
checks passed (four ASRs x E0/E1 x both taps), reproducing all exact query windows
and short-run coverage, preserving 700 raw observations and 54 final utterances
across the reused combinations. Both actual helper workers exited cleanly.
COMPONENT_D1_REPLAY_CHECK_V1.json and README_COMPONENT_D1_REPLAY.md bind the code,
private receipt, limits and all shell commands. Private receipt SHA-256:
`1bb7c21dea22065bfb7e6f5a8baa0908f1cf07a5064c4ab2e950ef52c467f21b`, under
`local/n4/component-d1-probe-v1/RESULT.json`. Its 16 private gzip outputs total
11,603,787 bytes. No inference worker, model weights or common source changed.
This is anonymous application-method development evidence. Later mode helpers
add fixed named galleries. Full Controller/GUI parity, global D0 activity and
full-matrix scoring remain pending. Timing is explicitly modeled and supplies zero accepted
integrated cells or measured first-visible/resource qualification.

## Implemented and actually checked

- All 480 accepted prepared waveform files were independently rehashed, checked
  as mono16k PCM16, and matched to 240 same-pass O0/O1 pairs. Prepared gain is
  applied exactly once. The complete audio-only manifest retains every scene.
- Reference population is 156 non-overlap, 47 overlap, 26 incomplete ambient and
  11 empty-control scenes. Private evaluator strata preserve room, quality,
  orientation, canonical noise/SNR, levels, short turns and dependency groups.
- Twelve A0/A2/A3 compositions are wired in a separate source derivative. Actual
  Controller selection/cleanup passed for all 12 with model loading forbidden.
  Fifteen inherited catalog/native-protocol/text tests pass. These are wiring
  checks, not model execution. A1 now has actual Controller/GUI
  validation in the accepted N3 source; the historical 12-entry derivative does not contain it.
- Thirty-five N4 tests pass: missed-word/failure/empty/overlap denominators,
  established cpWER/MIMO and estimated-activity DER/JER, cache invalidation,
  paired clusters, coverage, RAM headroom, process identity and archive corruption.
  Two completed N2 cells also passed the new evaluator's real-evidence smoke.
  They receive zero N4 execution credit.
- MeetEval 0.4.3 and pyannote.metrics 4.1 are isolated with 31 exact dependency
  versions, file hashes and license notices. MeetEval's initial default MSVC
  build failed; C++20 flags built the unmodified source successfully. Empty
  reference JER is explicitly unavailable; false alarms remain counted.
- Lossless archival was verified on one completed N2 cell: 59 bound files,
  35,893,789 input bytes, 2,934,765 archive bytes, no original changed or removed.
  Archive-aware scoring now has eight passing additional fixtures, including
  identical predictions/metrics after deleting only temporary test originals.
  It rejects changed, duplicate, outside and unbound inputs, and checks the
  full scorer's archive-index path. ARCHIVE_READER_CHECK.json records exact
  prediction/metric equality on the real N2 probe cell without extraction or
  source changes. The new evidence_store.py lifecycle now passes 12 temporary-data tests: exact
  binary/JSON archival, interruption recovery, refusal of corruption or late
  unbound writes, failed-cell preservation, OS writer locking, disk floors and
  restoration of the caller's CPU allocation. It refuses existing directories.
  EVIDENCE_STORE_CHECK.json binds the final check. Production-runner integration,
  a measured cell peak and aggregate remaining allocation are still pending;
  no existing campaign evidence was removed and no N4 cell was executed.

No candidate has been selected, promoted or assigned a measured deployment tier.
`MATRIX.json`/`MATRIX.csv` retain all 16 intended profiles, 480 rows each, with
zero completed, zero failed, zero proved incompatible and 7,680 NOT_TESTED cells.
Missing adapters are not counted as scientific model-family failures.

## Findings that affect the full run

The bank has only nine broad connected dependency groups after linking repeated
actors, text, sources, noise seeds and matched cases. Both taps remain paired;
bootstrap intervals will be descriptive and fragile. `BANK_COVERAGE.png` shows
reference capability and group sizes, not model quality.

D0/E1 currently inherits D0's original anonymous association settings. Its own
C-only scale/profile is not validated. Processed-query operational naming is
uncalibrated and must remain Unknown; closed labels remain assumptions. D0 also
lacks a recorded complete anonymous activity timeline in current Controller
evidence. Inspection confirmed that `research_evidence_v3.py` already emits
full speech/overlap/posterior frames. What is absent is a total mapping from
that activity to persistent anonymous tracks, including unassigned speech and
overlap. The embedding admission windows are not that mapping. Preserve the
actual source/availability times and unsupported regions; do not invent names,
extend track support or substitute an embedding-window proxy for DER.

Completed N2 D0/E0 and D1/E0 screens retain about 25.86 and 35.25 MiB of bound
evidence per cell. Their simple 480-cell extrapolations are 12.12 and 16.52 GiB
per composition, excluding other files. Repeating this format for N4 violates
the disk reserve. Compact lossless storage and exact cache reuse need admission
before the large run. The one-cell compression probe is not a full-bank bound.

## Source, launch and rollback

Worktree: `G:\Just_Peachy_N1\20260924_campaign\worktree`, branch
`codex/n1-foundation-20260924`. Private N4 root:
`G:\Just_Peachy_N1\20260924_campaign\local\n4`.

Historical derivative: `local\releases\n4-catalog-v2\prototype`; its source receipt binds
the N3 v2 parent and exactly two changed files: backend catalog and its expected
set test. The six common UI/presentation files retain SHA-256
`54c0283b8058978eca87dc9b0461a15addf804200856e41d2c83b55bff590456`.
V1 is preserved as superseded preparation. No live N2/N3 source was modified;
N3's exact 32-job admission hash check passed again after N4 preparation.

README.md and README_METRICS/SCORING/RESOURCES/EVIDENCE/PACKAGE describe purposes,
inputs, outputs and PowerShell plus CMD/Anaconda commands. Original app launch
and personal data remain untouched. Use explicit isolated research roots for
candidate data; select Baseline and start a fresh epoch for backend rollback.
No research gallery becomes a personal profile. The Pi remains powered off.
No desktop input/focus control, SSH, microphone, USB, playback or new capture ran.

## Exact continuation in this existing task

> Continue N4 in this same worktree from accepted n4-catalog-v3. N1/N2/N3 are
> accepted in their stated offline/component scopes; do not restart their old
> queues. The current model run is local/n4/asr-full-bank-v1. Inspect fresh
> RESULT.json, panel progress, exact worker/coordinator/model PID creation and
> CPU/resource ownership. Preserve its frozen code and let healthy work continue.
> D0 full bank (960), ASR smoke (8) and D1 smoke (4) all passed separate strict
> reviews; public *_REVIEW_V1 receipts bind those results. Do not repeat them.
> After ASR full bank is terminal and its exact coordinator exits, use
> review_asr_full_bank.py from README_ASR_FULL_BANK.md for all 1,920 cells.
> Queue completion does not establish review/acceptance.
>
> Full-bank D1 is prepared at local/n4/d1-full-bank-v1 (960 cells); read
> D1_FULL_BANK_PREPARATION_V1.json and README_D1_FULL_BANK.md. Preserve its
> bound code. Its coordinator/child enforce a passed complete ASR review and
> unchanged predecessor evidence before model loading. Charge actual payload
> and reservations accurately; no parallel model or waiter. Launch through
> the existing supervisor only after ASR review and fresh exact ownership
> verification, then run review_d1_full_bank.py on terminal 960-cell evidence.
> During healthy ASR work continue useful unbound application
> integration meanwhile: exact ASR/D0 commands and modeled span presentation
> are tested. The causal merge and actual S7 eligibility/publication freshness
> now pass the modeled D0/E0 adapter's 12 tests and eight sealed-evidence probes;
> see COMPONENT_S7_REPLAY_CHECK_V1.json. Anonymous D1 activity/name/span methods
> now pass nine tests and 16 modeled smoke-derived checks; see
> COMPONENT_D1_REPLAY_CHECK_V1.json. The new mode_galleries.py and
> component_mode_replay.py add fixed rosters, actual catalog resolver selection
> and named/selected/closed histories and display annotations. Read their two
> READMEs and MODE_POLICY_FINDINGS_V1.md before generalizing prior anonymous
> results. COMPONENT_MODES_CHECK_V1.json records 160 passed modeled development
> replays, all worker cleanup and exact raw/final census; it does not establish
> new inference or integrated coverage. CONTROLLER_PROJECTION_CHECK_V1.json now
> adds eight tests and 160 actual downstream consumer/snapshot/cleanup checks,
> with every sealed display and raw fragment retained. Read
> README_CONTROLLER_PROJECTION.md and CONTROLLER_FINDINGS_V1.md. Complete
> upstream publication/coupled Controller parity remains unresolved; the
> producer qualification checklist at the end of INTEGRATION_NEXT.md gives
> the specific next work. INTEGRATION_NEXT.md
> records the verified source APIs: D1 uses its actual N2 activity/name/history/
> caption-span revision path, not D0 clustering. ObservedClock accepts an
> injected clock, but inherited observed field names cannot turn modeled replay
> into observed latency. Plain S6C batch replay is not Controller parity. D0 diagnostic masks are not a persistent-source
> decoder: retain unsupported/conflicting/overlap/tail regions and never use
> embedding-window proxies as DER. The C-scale fit failed and was not applied;
> keep nominal D0/E1 explicitly unqualified, without validation/Q retuning.
>
> Implement the actual 7,680-cell coupled matrix with exact cache keys, bounded
> evidence storage, present/absent gallery and mode comparisons, honest failed/
> unavailable counts and paired metrics. Then complete common-GUI source-paced
> panels, timing repeats, continuity and whole-stack resource selection. Preserve
> baseline/event policies and calibration/test separation. Complete N4 reporting
> and selection, then N5 validation, packages, documentation and verified Git.
> Preserve earlier artifacts and the user's desktop/Pi/privacy constraints.
> Packaging reserve starts Sep28 02:48:19 UTC, deadline Sep28 14:48:19 UTC;
> do not extend them. If coverage cannot finish, classify the actual gap and
> package supported candidates within the reserve rather than fabricate success.

The registered in-task heartbeat continues. ASR full-bank components are the
sole active numerical workload at this checkpoint; integrated count stays zero.
N5 remains preparation only until accepted N4 configuration selection.

Latest scoring implementation: `scoring_bank.py`, `metric_process.py` and
`scoring_report.py` now provide terminal-bank admission, a bounded persistent
established-metric worker, explicit execution-versus-metric failure counts and
count-weighted paired/stratified reporting. Eleven tests passed and 51 saved
checks retained identical metric objects; all exact metric owners and pipe
threads exited. Three actual V2 method cells (baseline, A3/D1/E1, empty A0)
also passed the production conversion boundary, matching their older qualified
semantic parents and rejecting changed counts. An initial check supplied older
V1 artifacts without V2's explicit empty-session field and was rejected; it is
preserved as a schema-mismatch attempt, not a production failure or source fix.

Use README_SCORING_BANK.md and README_SCORING_BANK_BOUNDARY.md for purposes,
inputs/outputs and all shell commands. SCORING_BANK_IMPLEMENTATION_V1.json binds
the qualification evidence. Complete prediction banks require their passed
review; preserved partial runs retain their full declared population. There is
still no production method-bank plan, method worker or bank scoring result.
Continue ASR review, then the single D1 collection, then actual method-bank
admission/execution/review/scoring. The source-paced common-GUI panels,
continuity, naming visibility and whole-stack resources remain outstanding;
none of these model-free helpers adds integrated acceptance credit.

Viewport qualification now adds seven passing private-desktop GUI regressions
and 160 saved-output render checks (same two smoke sources deliberately reused).
The unchanged 480x800 frontend keeps active rows elided in history and visible
in its active pane; an applied caption may also be offscreen, and its heading
can scroll away independently. widget_visibility.py records these distinctions
without advancing label state or changing UI data. V1's saved-reader import
failure is preserved; V2 supplies the exact script import directory and passes.
Use WIDGET_VISIBILITY_CHECK_V2.json and the two README_WIDGET_VISIBILITY files.
Private child closure and unchanged user input desktop were verified. These are
point observations, not continuous name exposure, source-paced inference or
physical scanout; no integrated cells are accepted from them.

PACED_APPLICATION_FINDINGS.md is the next source-level guide. The complete
baseline Controller requires actual gallery query counts absent from the plain
research bridge, and its source clock does not use the N2 observer factory.
Qualify narrow research-store and common clock/resource hooks before admitting
the 24-cell shortlisted application panels. Keep CPU4 collection healthy and
do not start another neural owner or controlled timing run alongside it.

The narrow roster/clock hooks are now qualified in paced_adapters_v2.py. Seven
model-free tests passed: 160 verified gallery/mode/tap cases preserve scores,
template bytes, counts and fixed rosters, and all three actual engine classes
publish fixture source-start events through their unchanged Controller consumer
and final drain. V1's plain wrapper failed the baseline's ResearchGallery type
admission; that attempt is preserved. V2 subclasses the actual gallery while
delegating scores unchanged and checks the complete S6D publication metadata.
The source origin, publication stamp and consumer receipt remain distinct;
duplicate starts, changed epochs/sessions and event sequence gaps invalidate
observer evidence. See PACED_ADAPTERS_CHECK_V2.json and README_PACED_ADAPTERS_V2.md.

These checks run no source audio, models or GUI and confer no integrated or
latency acceptance. Still implement/join actual FileSource sample and journal
closure, bounded viewport histories and whole-application resource receipts,
then execute the predeclared shortlisted panels/repeats/continuity after the
component and full modeled-bank reviews. ASR moved from A1 to A2 during this
checkpoint; the sole model slot remains occupied and D1 is not started. The
existing in-task follow-up was changed to every 30 minutes at the user's request;
its deadline and meaningful-change notification policy are preserved.

Use paced_adapters_v3.py for the future full application. V2 exercised constructor
queues, but full startup replaces them with EventInbox: it adds consumer timing
fields and can coalesce obsolete partial events. V3 now exercises all three
engines' actual emission through that inbox and the original Controller drain.
Nine tests passed, including the 160 gallery cases, real permitted coalescence
and rejection of an unexplained missing publication. After drain, reconcile the
published serial with consumed events plus the inbox's own coalescence count.
V2 remains method-only evidence. PACED_ADAPTERS_CHECK_V3.json binds this repair;
README_PACED_ADAPTERS_V3.md has inputs, outputs and all shell commands.

viewport_ledger_v2.py now stores changed viewport rows once and keeps compact
first/final/latest references. Eight tests passed; all 160 prior saved GUI
histories reconstruct exactly. The synthetic 8,192-span/40-observation fixture
wrote 483,963 log bytes and a 5,750,345-byte summary with no caption-body copies
in span metadata. These are serialized sizes, not application memory or an
actual continuity result. Disk/span bounds, corruption and clock errors fail
explicitly. V1's shared-reference expansion failure and oversized formatted
summary are preserved. VIEWPORT_LEDGER_CHECK_V2.json and its README bind scope
and commands. Never expand these summaries inside a measured application.

Next full-application closure work must retain the engine reference before
Controller.close clears it. FileSource ends by finishing its journal; it emits
no source_stopped event. Check its sent count, each source/ASR/identity journal,
worker exit and the finalization receipt's source/identity counts against the
admitted WAV. Reuse the existing joined archive-integrity validator rather than
accepting an earlier session summary as proof of writer closure. Keep archive,
consumer and all lane/policy/punctuation/text/source owners in the closure census.
The source-paced panels and continuity still cannot run alongside component
extraction, and controlled whole-application resource evidence is still missing.
