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

**N4 is not complete.** The supervised `local/n4/d0-bank-v1` now collects actual
D0 components on all 480 saved scene/tap files, first E0 then E1 sequentially.
Its immutable admission SHA-256 is
`1a99b124348d6e933665efb268edbfc0864191880400d469804ab0f65b4c42af`.
Inspect this newer run's result, exact PID creation identities and the shared
worker heartbeat before numerical work. README_D0_BANK.md describes the
4-GiB bounded compressed store and unchanged fixed-cadence causal speaker lane.
This is 960 component jobs, zero completed integrated scene/tap results.

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
admission semantics. It has not yet reviewed the running full-bank collection.

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

> Continue N4 from the accepted N3 source and fresh n4-catalog-v3 derivative.
> Read UPSTREAM_ACCEPTANCE_20260925.json, current process identities, worker
> state and resource ownership. First follow the newer d0-bank-v1 run;
> never duplicate it or edit its bound source/code. The C collection/review
> finished and the single frozen scale fit failed; preserve that result without
> retuning. Review the full-bank exact E0/E1 geometry after completion using
> review_d0_bank.py (README_REVIEW_D0_BANK.md), after the exact coordinator exits.
> The activity observer and two-cell native policy ordering probe are implemented
> with 33 passing tests; use README_D0_ACTIVITY.md and D0_IMPLEMENTATION_CHECK_V1.json.
> They do not establish S7 observed-clock Controller parity or a global-source
> decoder. Preserve explicit unassigned/conflicting/overlap support when wiring
> the real integrated activity output; do not promote the diagnostic to DER.
> N1/N2/N3
> acceptance is complete; do not repeat their old queues. Implement the full
> D0 anonymous activity output, keep D0/E1's calibration limitation visible,
> then integrate exact component caching and the
> verified new-run storage lifecycle into a full-bank runner. Freeze a new
> derivative for source changes; do not edit accepted releases. Admit the
> numerical plan only with complete contracts, resource ownership and a bounded
> remaining disk allocation. Execute the actual 7,680-cell matrix with honest
> failure/incompatibility/missing counts, followed by common-GUI paced panels,
> continuity and whole-stack resource checks. Keep frozen baseline/model/event
> policies and calibration/test separation. Complete the N4 report/selection,
> then N5 validation and releases. Preserve every earlier artifact and all
> desktop/Pi/privacy constraints; do not extend the packaging cutoff/deadline.

The registered in-task heartbeat continues. The full-bank D0 component collector
is the sole N4 model worker; it earns no integrated-cell credit by itself.
N5 preparation is not a completed-stage deliverable.
