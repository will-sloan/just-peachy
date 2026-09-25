# N4 implementation checkpoint — upstream accepted, integrated run pending

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
D1, named galleries/modes, global D0 activity and exact Controller parity remain
the next integration requirements; the eight probes do not complete the matrix.

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
> see COMPONENT_S7_REPLAY_CHECK_V1.json. Named/D1 paths and actual Controller
> parity remain unresolved. INTEGRATION_NEXT.md
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
