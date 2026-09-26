# N4 and N5 execution order and acceptance gates

### 2026-09-26 15:38 UTC — D1 fully reviewed; integrated main bank running

Fresh audit found D1 terminal 960/960 at 14:52:54 UTC and supervisor completion
at 14:52:58. Exact owners 32696/1790350774.0235264,
4092/1790350774.1659436 and 51884/1790392138.9657671 had exited. Accepted N2/N3,
prior Git backup a78cb6681e7a0179fd755b00c2a8cf4b51a40c8b and Pi requirements
were reverified. Historical N2/N3 queue labels are superseded by those receipts.

The original full D1 review failed on an exact-decimal frame assumption. V2
uses the bound native float32 10-ms interval for endpoints and ActivityTimeline;
its full review exposed a separate query-event clock assumption. V3 checks raw
query event clocks against native window ends while retaining exact rounded
waveform sample support. No tolerance was widened, source event edited or
neural model rerun. Original and V2 failed executions, qualifications, tests
and source snapshots remain private. V3 passed 18 regression checks and then
all 960 actual cells, 480 paired files, 1,111,489,288 expanded event bytes,
7,412 query windows and 2,179,000 frames per encoder. Each encoder retains
298 short runs and 16 files without queries. D1_FULL_BANK_REVIEW_V3.json binds
private d1-full-bank-review-v3/REVIEW.json SHA-256
`d349772e90e786735e61bbd59aac7e57677aa51af12243e1668c519da65671b4`.

The explicit integrated V2 derivative propagates the scanner correction.
Its first probe preserved one artifact-cap failure. The qualified derivative
retains full histories with a 64-MiB per-artifact cap and 140-MiB cell reserve;
16 checks pass, including four full saved-audio boundary cases. Original
publication/Controller behavior and limits remain unchanged. Read
README_D1_FRAME_CLOCK_V3.md and README_INTEGRATED_BANK_CLOCK_V2.md.

Production plan integrated-main-plan-v2.json (7,680 rows) SHA-256
`c42150c83eb007bf976418233d4f53ebe0ccc6b77dc8e317511a97764b0de8d5`
is admitted from all three passed component banks. Existing supervisor phase/
start interfaces launched run `8d0e7a5cee5d46cc887b4777ebf48450` at 15:36:49 UTC:
supervisor 48424/1790437009.6059947; method worker 13032/1790437009.773104.
Both CPU14/BelowNormal, hidden, no models or GUI. Initial verified progress
18/7,680; follow local/n4/integrated-main-v2/PROGRESS.json and worker.json, not
stale shared panel_progress.json. Actual allocation 5 GiB retains 6 GiB pending
reservations plus 1 GiB contingency under 50 GiB. Prior shared-state snapshots
are preserved; no manual ledger mutation. INTEGRATED_MAIN_STARTED_V2.json and
README_INTEGRATED_MAIN_RUN_V2.md give exact evidence and commands.

Do not edit code bound to this plan or start another bank. While it runs,
qualify an explicit scorer/reviewer derivative for the 64-MiB artifacts; the
original 32-MiB reader will reject some complete histories. After terminal
owner exit, use integrated_bank_v2.py review, then scoring. The separate
1,536-case modes bank and actual selected paced/GUI/resource, continuity and
restart execution/review remain pending. The restart native-content component
still needs composition with the complete run and admitted roster/timing.
Accepted integrated N4 credit remains zero; N5 packaging/ARM64 software work
is incomplete and live CM5 checks wait for reconnection. The unrelated
cmd.exe 40092 AccessDenied remains unresolved for exclusive application
admission; no gate was bypassed. The Pi stayed off; deadlines are unchanged.

Checkpoint 2026-09-26 14:22 UTC: D1 E1 **937/960**, exact owners unchanged.
**23 released native-content development checks pass**. The new
`review_restart_native_content.py` preserves the full job while interpreting the
first delivered prefix, then matches retained/current widget captions against
their own native histories and original clocks. Partial-only text, overhang,
missing caption revisions, unobserved spans and ambiguous predecessors remain
explicit. Real pure parsers/state code run on synthetic clocks/geometry; no
actual production pair, source, model or GUI was executed.

RESTART_NATIVE_CONTENT_CHECK_V1.json SHA-256
`8fc6d8fa710f70bc2b22674a047c01be13559e1bdd854371e8fd803a91674a6d`
binds 202 code records. README_RESTART_NATIVE_CONTENT.md documents guarded tests
and internal APIs. Next independent work: join this component to the qualified
complete run/owner/lifecycle/delivery and fixed roster, then timing/functional
acceptance. The earlier selected-run reviewer remains immutable and does not
yet invoke it. D1 must become terminal and pass independent review before
integrated main/mode plans can be prepared; do not admit its active prefix.

Integrated N4 acceptance remains 0/7680. N5 and live CM5 acceptance are not
complete; the Pi remains disconnected and off. The existing reserve/deadline
and unresolved cmd.exe 40092 AccessDenied census observation remain unchanged.

Checkpoint 2026-09-26 13:19 UTC: D1 E1 **893/960**, exact owners unchanged.
The new `review_restart_complete.py` composes transport, pair, viewport and
resource checks over the reconstructed complete selected population. It checks
cross-reader bindings, owner/session separation, ordered source clocks and every
input again at completion. Missing resource observations retain explicit gaps.
**24 development checks pass**; synthetic cell leaf outputs/payloads and production
plan admission are mocked in the documented tests. No actual production review
or restart acceptance is claimed.

RESTART_COMPLETE_REVIEW_CHECK_V1.json SHA-256
`5f951f21f50b17525430cf00316eb3ba8d05b9b5c3e97a7c7286d452cd4bf0c7`
binds 182 code records. README_RESTART_COMPLETE_REVIEW.md gives the probe and
later stopped-run commands. All previously qualified code remains immutable.
Next independent work: native caption semantics/timing and functional restart
acceptance. Next numerical transition: verify D1 terminal completion and exact
owner exit, run `review_d1_full_bank.py`, then admit main/modes full-bank execution
and scoring before the selected actual application runs. Do not infer acceptance
from queue completion. The unrelated cmd.exe 40092 AccessDenied census observation
still requires resolution through existing admission policy, with no bypass.

N4 integrated accepted credit remains zero, N5 is incomplete, the Pi is untouched,
and the original packaging reserve and deadline are unchanged.

Checkpoint 2026-09-26 12:26 UTC: D1 E1 reached **855/960** with unchanged exact
owners. **22 restart observation development checks pass**, using synthetic saved
logs and real viewport/resource reconstruction. Two composition tests mock the
pair reader and preparation resolver. The new component partitions retained
captions by original caption-key session and source clock, joins terminal GUI
state/geometry, and partitions resource samples by full measurement intervals.
Cross-boundary samples are counted separately; missing measurements remain missing.

RESTART_OBSERVATION_CHECK_V1.json SHA-256
`55fe93f294861faf2a8f85db21113cc3c14c03df85370723d7c714b813a24925`
binds 177 code records. See README_RESTART_OBSERVATIONS.md for guarded commands,
inputs, outputs and scope. The earlier run reviewer is immutable and does not
invoke this new component. Next independent work: compose it into a fresh
qualified selected-run reviewer and add native caption semantics/timing and
functional acceptance. Actual model-backed runs still require completed D1,
full-bank integration, selection and exclusive resource admission. Unrelated
cmd.exe 40092 AccessDenied remains an unresolved census observation.

No actual restart run or integrated N4 cell is accepted by this preparation.
No CM5 connection occurred. Packaging reserve and campaign deadline are unchanged.

Checkpoint 2026-09-26 11:22 UTC: **29 independent restart review development
checks pass**, including seven saved native lifetime classifications. The new
transport reader checks split manifests, the fixed child argv, exact closed
process/lease/slot/parent receipts and an independent pair reread. The run reader
reconstructs the accepted plan and enforces the complete selected O0/O1 pair
population, both sessions, midpoint policy, exact progress/order and no extra
or missing cells. A late cleanup failure cannot pass via COLLECTED.json alone.

RESTART_REVIEW_CHECK_V1.json SHA-256
`b423f826c7d0cec5ea8a486e7bac1a44cd93c565c9b8c8e2f2541fdf048706c6`
binds 155 code records. Positive transport/population fixtures are synthetic;
their pair leaf review and production plan admission are mocked. No actual
complete production run was reviewed or accepted. The terminal lease and
sampled process history keep their explicit limits. See README_RESTART_REVIEW.md
for probe and later production review commands in all requested shells.

Next: restart viewport attribution with retained old caption history and separate
source clocks, plus resource/timing interpretation and actual functional
validation. D1 is healthy at 810/960 during publication. Full-bank review,
main/modes execution/scoring, selected actual application runs, N4 acceptance and
final N5 validation/package/backup remain. Integrated N4 credit stays zero; the
Pi and the original packaging reserve/deadline remain unchanged.

Checkpoint 2026-09-26 10:19 UTC: **24 supervised restart coordinator development
checks pass**. RESTART_RUNNER_CHECK_V1.json SHA-256
`e4f13abcf99148bfa637a3533912a182824e17376bb3afb07734c363150c42a8`
binds 148 parent dependencies. The fixed child and its permit retain exactly
122/128 records. The new coordinator prepares worker configuration, reconstructs
the admitted plan under existing supervision, collects sequential private Job
pairs, verifies normal lifetime/child closure and invokes the independent pair
reader. Lease checks, failure cleanup, post-exit resource/deadline checks and
terminal-attempt preservation passed mocked wiring tests; no production worker
was prepared or started. See README_RESTART_RUNNER.md for all run instructions.

Next: independent complete restart transport/selected-pair population review,
then viewport/resource/timing interpretation. Check every PARENT_CLOSURE even
when COLLECTED.json exists; late slot-release failure cannot qualify. Preserve
the separate manifests and fixed child argv without the old child subcommand.
Actual execution still requires reviewed D1, main/modes banks, scoring and
selection. D1 is healthy at 766/960 during publication. Accepted integrated N4
cells remain zero, N4/N5 are incomplete, and the Pi remains untouched.

Checkpoint 2026-09-26 09:23 UTC: **18 restart pair evidence development checks
pass**. The new parent-only reader independently invokes the qualified released
trace, engine/archive and native readers and joins their full job, delivered
count, epoch/session, source origin, terminal census and completion order.
The pair composition checks the admitted stop threshold, recorded shared
Controller/UI/worker/model ownership, fresh sessions and second-source start
after the first release. Old viewport history keeps explicit session scope.

RESTART_PAIR_EVIDENCE_CHECK_V1.json SHA-256
`499f083745652b57e7d6d0a8bac26c4be55aca81620b6ae5cceee5b215e02346`
binds 137 parent dependencies. The immutable child stays at 122/128. Positive
file-composition tests mock the three previously qualified leaf readers and use
synthetic metadata; no production restart result exists. Review-pair success
does not qualify transport provenance, viewport rows, resource samples, timing,
selected-pair coverage or N4. See README_RESTART_PAIR_EVIDENCE.md.

Next: implement the separate parent coordinator and independent full transport/
selected-pair review, then viewport/resource interpretation. Retain the existing
suspended private-process and lease gates; no duplicate numerical worker or
manually invented permit. D1 remains healthy at 727/960 during publication.
Full D1 review, main/modes banks, scoring/selection, actual paced/continuity/
restart evidence, N4 acceptance and final N5 validation/package/backup remain.
The packaging reserve and hard deadline below are unchanged; Pi stays offline.

Checkpoint 2026-09-26 08:22 UTC: **34 development checks pass**: 19 explicit-prefix
native-reader checks and 15 fixed-child wiring checks. The native derivative
preserves the full planned job and verifies a separately declared delivered span;
all nine historical missing-prefix classifications stay unchanged. The fixed
child now calls the same-Controller pair lifecycle through the unchanged live
ChildAdmission gate and records failure through cleanup. Positive application
objects/admission are mocked in these checks; no actual restart pair ran.

RESTART_NATIVE_CHECK_V1.json SHA-256
`0d7f3b84bdfaea4186d672302c359f73fe01d76c38f887a12448af49b2bbc253`
and RESTART_CHILD_CHECK_V1.json SHA-256
`79131545b8c870631e9bcbd1f42bc875653ba57e0bacdb84dbf82b63fef61b8f`
bind the exited probes and immutable code. All 117 prior dependencies stay in the
fixed child, which has 122/128 records. Parent-only native/review code has a separate
manifest; the earlier monolithic binding-limit concern is resolved by this explicit
boundary without removing child dependencies or raising the limit.

Next: parent coordinator/launcher, complete per-session native/delivery/engine/
archive and pair/process joins, then viewport/resource review. Launch the fixed
child script with --permit/--nonce in the existing suspended owned private Job;
do not use the old single-source runner or manually synthesize a permit. Actual
execution still follows full D1 review, main/modes execution/scoring and selected
configurations. D1 is healthy at 690/960 during publication. N4/N5 are incomplete;
CM5 work remains offline. See README_RESTART_NATIVE.md and README_RESTART_CHILD.md.

Checkpoint 2026-09-26 07:18 UTC: **16 selected restart planner checks pass**,
covering all 16 backend routes and 62 fixture pairs. The fixed S45_03_03 O0/O1
anchors are identical across candidates, with their real saved hashes/headers
verified read-only. Each candidate will receive two pairs/four sessions: stop a
positive first prefix at the predeclared midpoint threshold, fully drain it,
then restart the unchanged full file from zero in the same Controller/UI/models.
RESTART_PLAN_CHECK_V1.json SHA-256
`1be341cbf182806712f37d742b4a574391416b0e8d24ff6e4d5a8d6bd7929798`
binds 117 code records and the exited private probe. No production selection,
plan, actual application or new model run was fabricated. See README_RESTART_PLAN.md.

Next implement the fixed exclusive paired runner, independent native prefix/full
and source-delivery envelopes, then session-aware viewport/resource interpretation.
The projected runner dependency union already reaches 128 before a separate new
prefix reader; preserve the existing child limit and plan the bounded dependency
layout explicitly. The existing single-source/continuity runner cannot execute
restart plans. D1 remains healthy (652/960 at publication). Full D1 review,
main/modes execution and scoring, selection, actual paced/continuity/restart
validation, N4 acceptance and final N5 releases remain. The Pi stays offline.

Checkpoint 2026-09-26 05:46 UTC: **21 same-Controller lifecycle/archive development
checks pass**. RESTART_APPLICATION_CHECK_V1.json SHA-256
`9d07ed6a2d7d1c70e0e86c09452e0d72d76719f8d88935ac430e294c2270c608`
binds 102 code records. The paired cell retains Controller/UI/model store,
drains a deliberate first prefix and then starts the same full file from zero
with new epoch/session/source/journal/consumer/clock/viewport objects. It keeps
old captions and explicitly marks their different session/clock scope.

Use restart_archive.py's explicit open-Controller archive composition for the
between-session boundary. The older restart_session_closure.validate_complete
requires full Controller shutdown through its original archive validator and
cannot serve this boundary. Earlier code/qualifications remain preserved.
Three private attempts and source snapshots are retained; the first two failures
were synthetic equal-timestamp fixture errors, not a runtime model failure.

Next: selected-job restart planner, exclusive launcher integration and independent
two-session native/delivery/viewport review, then actual execution after reviewed
D1/main/modes/selection prerequisites. No real GUI/source/model or Pi ran in the
development probe. Runtime engine capture and model-backed restart remain
unverified. D1 is healthy at 588/960 during publication. Continuity interpretation,
remaining naming metrics, N4 acceptance and final N5 work are still outstanding.

Checkpoint 2026-09-26 05:19 UTC: **22 released-session development checks pass**.
RESTART_SESSION_CHECK_V1.json SHA-256
`4f0604a3f095fb5907aa52137530b741d48af3be050160fb90bd26b3e5592ad7`
binds 96 code records. The new explicit stop/release primitive preserves the
full planned job, records delivered prefix length separately, retains an open
Controller/model store and requires drained source/consumer/journal/worker and
archive ownership. Both private probe attempts and source snapshots are retained;
the final attempt also rejects false acceptance claims and accurately records
closed Controllers in failed evidence. See README_RESTART_SESSION.md.

Next build the actual two-session lifecycle coordinator: one Controller/UI and
model store, positive mid-file stop, complete prefix drain, then new source at
sample zero with fresh session/engine/journal/clock observers. Existing full-file
readers cannot accept prefix evidence. Runtime engine capture and the real
restart pair still need execution; no new source/model/GUI ran in this check.
D1 E1 remains healthy (570/960 at publication). Preserve its resources while
continuing independent implementation. Main/modes banks, scoring/selection and
exclusive application tests must precede N4 acceptance and final N5 releases.

The detailed earlier checkpoints below remain as historical context.

Checkpoint 2026-09-26 04:50 UTC: explicit continuity transport, joined-cell and
selected-population readers now have **43 passing development checks** (19/11/13).
CONTINUITY_REVIEW_CHECK_V1.json SHA-256
`b37890e429b9144c98c371a8d01f97879a1fba3c4041f571cce47eeffd881079`
binds 168 read-only code records. The child runner still has 125/128 bindings.
The production reader reconstructs the qualified continuity plan, fixed runner,
exact 1–6 candidate population, same full O0 file, native/delivery envelopes,
source/consumer/viewport clocks and complete shutdown. It preserves unknown
historical lease/process coverage and does not subtract producer overhead.
See README_CONTINUITY_REVIEW.md for purpose, inputs/outputs and all shell commands.

Private final scopes: continuity-transport-review-probe-v4,
continuity-cell-review-probe-v2, continuity-population-review-probe-v2; aggregate
continuity-review-qualification-v1. Two failed long synthetic fixture attempts
are preserved; their one-second terminal counts/cursors were corrected without
weakening production checks. Final tests include a synthetic full 60,339-record
delivery trace and seven saved native lifetimes. No real continuity/app/model
run or positive production plan review occurred. Success is evidence coverage,
not N4 acceptance, latency/resource thresholds or functional restart.

Next: genuine same-Controller mid-file stop/restart with partial-source closure,
then supported continuity semantic/timing/resource interpretation and remaining
naming metrics. The required order remains D1 terminal review, full main/modes
comparison and scoring, selection, actual short paced panels, actual continuity/
restart validation, N4 acceptance, N5 release work. D1 E1 remains healthy at
549/960 at publication. N4 accepted integrated cells remain 0/7680; N5 is not
complete and the Pi stays off. The preceding missing continuity reader item is
superseded by this checkpoint; functional restart and actual validation remain.

Checkpoint 2026-09-26 04:18 UTC: the selected continuity planner and fixed runner
are implemented with **36 passing development checks**. The planner reconstructs
the qualified V3 selected short-panel plan, independently compares the prepared
27-session 20:06.78 O0 PCM with original saved captures, and produces one full
file per selected candidate with no internal joins or evaluator labels in the
child. CONTINUITY_APPLICATION_PLAN_CHECK_V1.json SHA-256
`0d6a60b803c9997a39ca09cac171ecb908941a374d6f6afd81e94aeb9e294db5`
binds 14 tests/31 fixture payloads/115 code records. The separate fixed runner
keeps V3 lease, private desktop, full source-delivery/native envelope and cleanup
gates. CONTINUITY_APPLICATION_RUNNER_CHECK_V1.json SHA-256
`4749e6c8eed8f0afe3a4f074a39bfbbff32731f28b17c21b68cb878bb8b456fe`
binds 22 tests and 125 code records, within the unchanged 128-binding ceiling.
See README_CONTINUITY_APPLICATION_PLAN.md and
README_CONTINUITY_APPLICATION_RUNNER.md for purpose, inputs/outputs and all shells.

Next implement the distinct continuity result reader and exact candidate census,
then genuine mid-file stop/restart using the same Controller/UI and explicit
partial-delivery closure evidence. Existing full-file cell.close shuts the
Controller and cannot establish restart. Do not fake shorter job.frames or reset
at internal joins. Full main/modes scoring and selection plus actual selected
short panels precede actual continuity tests. No production plan, application,
model or saved-audio run was created in this checkpoint; development tests do
not confer acceptance. D1 E1 remains healthy (528/960 at publication), accepted
integrated N4 remains 0/7680, N5 depends on accepted N4, and the Pi stays off.
The previous checkpoint's missing continuity planner/runner is now superseded;
post-run review, functional restart and actual evaluation remain outstanding.

Checkpoint 2026-09-26 03:46 UTC: V3 content/timing/heading/reference/name
composition and full-panel diagnostics now have 42 passing development checks.
APPLICATION_SEMANTICS_CHECK_V3.json SHA-256
`e8f13f0a66a4627b297cedc299b00c3c0b252b41855c143ac77f7a8e6f75b1c5`
(20 checks, 207 code bindings) and SEMANTIC_PANEL_CHECK_V3.json SHA-256
`e7b64d16b900b28b46cfb4d1f5d9ca7a36a2fb6a872835f5ecb8263ed3c49718`
(22 checks, 232 code bindings) are immutable qualifications. Private attempts:
`application-semantics-v3-probe-v3` and `semantic-panel-v3-probe-v2`; three prior
failed attempts remain preserved. README_APPLICATION_SEMANTICS_V3.md and
README_SEMANTIC_PANEL_V3.md document the exact APIs and all shell commands.

The evaluator context migrates only identical gallery-manifest bytes to their
new qualified path. Full-panel compaction preserves raw delivery in its verified
envelope and retains its hash; maximum synthetic report plus a 2-MiB registry/
admission reserve is 8,264,416 bytes within the unchanged 8-MiB ceiling. Actual
production registry size remains unknown. Rates sum counts; scopes and missing
observations remain explicit. No new application/model/source execution or
positive production plan/panel review occurred. These are not N4 acceptance.

Next: implement/qualify the actual continuity and functional stop/restart path.
After complete main/mode scoring and selection and actual V3 paced execution,
`review_semantic_panel_v3.py` supplies whole-panel content and conditional naming
diagnostics. Timing/resource/continuity and remaining supported naming metrics
still require their own evidence. Preserve all newly bound code. D1 E1 is the
only numerical worker (505/960 at publication). N5 remains dependent on accepted
N4 configurations; keep the Pi off and retain its reconnection handoff.

Latest checkpoint (2026-09-26 03:18 UTC): explicit V3 transport, observation,
composed-cell and full-panel readers now match the qualified V3 planner/runner.
APPLICATION_TRANSPORT_REVIEW_CHECK_V3.json records 18 checks, including seven
saved native lifetimes. APPLICATION_CELL_REVIEW_CHECK_V3.json records 11 actual
reader-composition checks on synthetic facts. APPLICATION_PANEL_REVIEW_CHECK_V3.json
records 10 exact-population/delivery-scope checks. No actual application or
production panel ran. Every acceptance flag remains false. Read their respective
README_APPLICATION_TRANSPORT_REVIEW_V3.md, README_APPLICATION_CELL_REVIEW_V3.md and
README_APPLICATION_PANEL_REVIEW_V3.md for purpose, inputs, outputs and run commands.

Next connect supported content/timing/naming review explicitly to V3; the existing
qualified wrappers still use V2. Reuse pure components without changing bound
APIs. Continue continuity/functional restart implementation and required retests.
The actual comparison/scoring/selection and exclusive application tests remain.
D1 completed the E0 half and began E1, reaching 486/960 during this checkpoint.
Its sequential child transition is expected; inspect fresh exact identities and
source bindings. The prior pending V3 transport/cell/panel item is superseded.
N4 is incomplete, N5 requires accepted selections, and CM5 remains offline.

Latest checkpoint (2026-09-26 02:51 UTC): the new V3 panel planner and runner
explicitly bind `paced_application_cell_v2.py` and its source-delivery policy.
PACED_PANEL_PLAN_CHECK_V3.json qualifies 11 regression checks and 1,240 fixture
payloads, with all 16 actual prestart receipts reverified. PACED_RUNNER_CHECK_V3.json
qualifies 20 lifecycle, cleanup, native-log and delivery-envelope development
checks. The parent independently parses delivery evidence before collection.
Neither a production shortlist/plan nor an actual source/model run was created.
Read README_PACED_PANEL_PLAN_V3.md and README_PACED_APPLICATION_RUNNER_V3.md.

Next implement an explicit V3 transport/cell/panel reader, then connect existing
content/timing/naming review without changing qualified V2 APIs. Continue actual
continuity/functional restart support. Full comparison/scoring/selection precede
exclusive source-paced application runs; development checks do not satisfy those
gates. D1 advanced 453 to 466/960 under the unchanged worker during this checkpoint.
N4 acceptance remains zero and the Pi remains off. Older checkpoints below are
historical; their pending V3 planner/runner item is superseded by this entry.

Latest checkpoint (2026-09-26 02:20 UTC): the explicit
`paced_application_cell_v2.py` variant now captures source delivery and requires
its independent engine/source/consumer clock join before successful closure.
APPLICATION_DELIVERY_CHECK_V1.json binds 16 model-free launch/join/cell wiring
checks; DELIVERY_APPLICATION_PRESTART_CHECK_V1.json binds four lineage and nine
actual invisible GUI/prestart checks, including all 16 implemented backends.
No source or model started. All prepared Controllers and the owned native job
closed; one short-lived process assignment remains unobserved, explicitly
limiting lifetime history. See README_APPLICATION_DELIVERY.md and the newer
README_DELIVERY_APPLICATION_PRESTART.md for scope and run commands.

The original source/cell and V2 runner/planner are immutable. A new explicit
runner/planner/reader must bind this cell and its new success status; the old
runner does not collect delivery evidence. Continue that work, then actual
20-minute continuity/functional restart and remaining supported metrics. The
healthy D1 numerical worker progressed from 432/960 to 444/960 during this
checkpoint. Read fresh identities/progress before acting. Full-bank comparison,
scoring and selection still precede actual paired source-speed GUI runs. N4
acceptance remains zero, N5 requires accepted configurations, and CM5 stays off.

Latest implementation checkpoint (2026-09-26): SOURCE_DELIVERY_CHECK_V1.json
qualifies the bounded `source_delivery.py` instance observer and independent
binary trace parser with 18 isolated exact-class development checks. It measures
FileSource input-journal append times against the unchanged absolute source
schedule and retains exact samples, partial stops, failures and signed lateness.
The binary cap is 5,220,000 bytes per hour. No actual application/WAV/model/GUI
ran, and no old source/runner was changed. Read README_SOURCE_DELIVERY.md for
scope and PowerShell/CMD/Anaconda commands. The actual cell/child/runner/planner
still need a new explicit integration variant, independent source-origin/count
joins, prestart/closure qualification and controlled source-speed tests. This
is not microphone callback, GUI latency, continuity or Controller restart proof.
Continue with that integration and continuity/restart support while D1 owns the
numerical slot; retain equal observation overhead across paired candidates.
The 01:32 audit found E0 411/960; publication reached 422/960 under the same
healthy exact owners. Read current evidence before acting. Accepted N4 cells
remain zero, and N5 release acceptance still depends on accepted N4 evidence.

This is a continuation guide, not a completion receipt. Read fresh worker/result
records before each action. Preparation and model-free development can overlap a
healthy component worker on the admitted helper CPU. Numerical model workers run
one at a time. Controlled application/resource tests additionally require their
exclusive slot. A task title or a finished queue does not establish acceptance.

N1 is accepted within the offline scope. N2's authoritative receipt is
`../n2/FINAL_REVIEW.json`; N3's is `../n3/N3_ACCEPTANCE.json`. The recurring prompt's
older N2/N3 description is historical. Preserve those accepted source hashes and
the failed attempts that preceded them. The Pi stays disconnected throughout.

Transition recorded 2026-09-25 15:39 UTC: ASR's full 1,920-cell component review
passed, its owners exited, and the prepared 960-cell D1 run started. See
ASR_FULL_BANK_REVIEW_V1.json and D1_FULL_BANK_STARTED_V1.json. Read live private
results for later progress; the latter is only a launch snapshot.

| Order | Required work | Gate before advancing |
|---|---|---|
| 1 | Finish A0–A3 on all 240 scenes and both taps, 1,920 component cells | Exact ASR coordinator/model exit and `PASS_ASR_FULL_BANK_COMPONENTS_ONLY` after full raw-event review |
| 2 | Prepared D1 bank: E0 and E1 on all 480 scene/tap inputs, 960 cells | Bind the accepted ASR predecessor, free numerical ownership, unchanged admission; terminal full D1 review must pass |
| 3 | Main 16-composition association/display comparison, 7,680 cells; four additional mode conditions on the fixed panel, 1,536 cells | Reconstruct exact ASR/D0/D1/source/gallery joins; execute the real qualified methods and review all raw evidence |
| 4 | Score both complete banks and produce paired reports | Pinned metric environment, complete failure denominators, full metric-input/report review; unavailable references remain unavailable |
| 5 | Select the baseline plus useful alternative configurations | Explain every selection/exclusion from complete evidence; retain failed/unqualified rows, no forced winner or default promotion |
| 6 | Actual shortlisted Windows application panels and repeated timing examples | Qualified panel plan, exact private process/supervisor ownership, unchanged source/backend/gallery, controlled exclusive slot, complete source/consumer/archive/UI/resource review |
| 7 | Actual host-continuity run for each retained release candidate | Same verified 20:06.78 O0 sequence and global actors; qualified continuity runner, no internal join resets, complete closure and functional stop/restart evidence |
| 8 | Complete N4 report and handoff | Coverage accounting, functionality/accuracy/naming/timing, resource planning tiers, sensitivity/limitations and explicit omissions reconciled |
| 9 | N5 Windows and ARM64 software qualification and releases | Use accepted configurations; actual saved-WAV model execution, launch/rollback checks, notices/manifests, private-data-free packages and verified Git backup |

D0's existing 960-cell component review is reusable only with its exact bindings.
The failed D0/E1 calibration remains failed; a nominal profile is not a calibrated
identity operating point. No Q tuning, per-scene threshold changes or idealized
retroactive names can fill this gap. Keep that distinction in selection/reports.

The D1 smoke observed approximately 83–84 seconds per 44.7-second file on the
admitted CPU placement, separately for each encoder. Scaling those four smoke
cells to the full 21,787.81 seconds per encoder gives about 22.75 hours of D1
inference. This is a planning extrapolation from one paired scene, not a measured
full-bank ETA or guarantee; use actual full-run progress once available. The
other comparisons, paced panels, continuity and N5 still require additional time.

Existing application infrastructure is qualified only to its declared scope.
Private process lifetime, child admission, fixed runner wiring, viewport/resource
reconstruction and input preparation do not replace the first real source run.
Full-panel evidence-population review is now implemented and development-qualified;
its positive production plan/run path awaits real complete inputs. Raw native
text, caption partitions, recorded pane content and fixed-roster consistency
now have qualified readers and a complete-panel wrapper. Evaluator-only naming
and timing interpretation and the continuity runner still require implementation
and qualification. The frozen application source/drain branch has not yet been
validated on the proposed complete stacks. If that first run finds a common bug,
preserve it and use a versioned repair with affected paired retests.

The stopped-cell transport join is now separately qualified by
APPLICATION_TRANSPORT_REVIEW_CHECK_V1.json. Its internal `review_cell` API
requires independently reconstructed plan expectations. It checks input,
permit, exact process/command, final lease, initial slot census and parent
closure joins. Use README_APPLICATION_TRANSPORT_REVIEW.md for its guarded
model-free probe. It does not replace full-panel review: source, workers,
archive, viewport content, naming/timing and resources still need composition
and review. Complete lease and short-lived-process histories are unavailable
in the existing runner evidence and must not be inferred.

APPLICATION_OBSERVATION_REVIEW_CHECK_V1.json now qualifies the composition of
source/worker/archive closure, resource replay and viewport replay with the
prepared backend and final Controller state. The internal
`review_collected_cell` API in review_application_observations.py runs the
transport join first. Positive qualification uses explicitly synthetic owner,
clock, resource and viewport facts plus copied historical terminal metadata;
it is not an actual N4 application test. Full-plan/population reconstruction,
native publication and actual pane-string scoring, naming/timing evaluation,
continuity and stop/restart still remain. See
README_APPLICATION_OBSERVATION_REVIEW.md for scope and probe commands.

Native journal retention gate added 2026-09-25: all nine historical N3 GUI logs
lost their initial event prefix through the original 1-MiB/two-backup rotation.
NATIVE_JOURNAL_REVIEW_CHECK_V1.json qualifies strict envelope/census review and
explicit incomplete-tail classification. These old tails cannot supply complete
N4 content/timing evidence, even though their terminal queue counts close.
Use README_NATIVE_JOURNAL_REVIEW.md for the 12-check model-free reader probe.

NATIVE_JOURNAL_RETENTION_CHECK_V1.json binds a fresh private source derivative,
local/releases/n4-complete-journal-v1/SOURCE_RECEIPT.json, with an event-only
256-MiB complete sink that fails instead of deleting its prefix. Eight checks
passed on the copied actual AsyncText and isolated factory; no application or
model ran in that writer check. Its status remains IMPLEMENTED_NOT_APPLICATION_ADMITTED.
Include the same logging policy and
overhead in all paired measurements. Do not substitute it into a bound old plan
or change the active numerical source. See README_NATIVE_JOURNAL_RETENTION.md
for its guarded builder, inputs/outputs and all three shell commands. Native
payload semantics, actual pane words/names and latency interpretation still
require review beyond the now-qualified envelope census.

JOURNAL_APPLICATION_PRESTART_CHECK_V1.json now qualifies the explicit source
context and actual private Tk/Controller preparation/closure for all 16 backend
rows. Four lineage tests plus nine GUI/factory tests passed with model/source
start forbidden. The context records both original component parents and new
application bindings; gallery metadata changes only the byte-identical catalog's
location. No actual source run is certified. See README_APPLICATION_SOURCE_CONTEXT.md.

PACED_PANEL_PLAN_CHECK_V2.json qualifies paced_panel_plan_v2.py: six tests and
1,240 development payloads passed. This version retains the fixed panel and
child allowlist while binding that explicit derivative context. It can prepare
and independently reconstruct production plans only after full main/modes score
reviews and a justified selection exist. No production plan exists yet. Use
README_PACED_PANEL_PLAN_V2.md; preserve V1 plans and do not pass V2 plans to the
V1 runner. The V2 runner and transport reviewer are now qualified to their
development scope by PACED_RUNNER_CHECK_V2.json and
APPLICATION_TRANSPORT_REVIEW_CHECK_V2.json. Use their V2 READMEs and fixed runner
filename. The runner checks complete native event envelopes after normal child
closure and before recording a collected cell; the stopped reviewer reconstructs
that envelope independently. Sixteen runner tests and 15 reviewer tests passed,
including rejection of freshly rebound truncated logs. No actual application
source/production-plan admission occurred. Next implement the native/pane content,
naming and timing review. Then reconfirm source/GUI/worker closure under the new
logging policy. Continuity and stop/restart remain separate outstanding work.

The existing observation review's `review_collected_cell` wrapper still selects
the V1 transport reviewer. For V2 use `review_application_cell_v2.review_cell`,
qualified by APPLICATION_CELL_REVIEW_CHECK_V2.json. It composes the V2 transport
and existing observation readers, joins common evidence/native terminal bindings,
source origins/publication clocks and event populations. Eight synthetic checks
passed with actual readers and the qualified derivative context. Its output is
still evidence consistency, not semantic/accuracy/performance acceptance.

APPLICATION_PANEL_REVIEW_CHECK_V2.json qualifies the exact population validator
and compact evidence output in `review_application_panel_v2.py`: eight tests on
40/240-cell development populations and missing-input refusal. Its production CLI
reconstructs the real V2 plan/run, verifies stopped owners and fixed runner,
requires every expected directory/progress/collected binding, and calls the joined
cell reader for every row. Use README_APPLICATION_PANEL_REVIEW_V2.md only after
the real application run is complete. The positive production path has not run.
PASS_COMPLETE_V2_PANEL_EVIDENCE_COVERAGE_ONLY must not be treated as N4 acceptance.
Do not redirect or overwrite the V1 wrapper/qualifications.

NATIVE_TEXT_REVIEW_CHECK_V1.json now qualifies `review_native_text.py` for private
raw-ASR/text-publication lineage and separate punctuation. Twelve development
tests passed; all nine incomplete historical journals remain unusable for this
purpose. Use README_NATIVE_TEXT_REVIEW.md and compose its `review` API with an
independently reconstructed V2 cell envelope. Preserve earlier qualified cell
and panel readers instead of editing their bound code. This component does not
yet join pane strings, names or visible timing to raw text, and no actual complete
application source history has been projected. Partial-only utterances remain
explicit; they require a separate completeness decision before final-only
accuracy metrics. Raw hypotheses, formatted display, inferred speaker labels and
evaluator truth must remain separate. The accepted integrated count is still zero.

NATIVE_CAPTION_REVIEW_CHECK_V1.json adds `review_native_captions.py`: twelve
development tests call the unchanged pure S6D/S7/N1 span-state code with synthetic
protocol facts, then verify raw/caption/word-fragment lineage. It preserves track
zero and missing display-revision denominators; label fields remain predictions.
Use README_NATIVE_CAPTION_REVIEW.md. No actual complete source history or widget
content was joined. Next compare native segment histories with the existing
Controller/viewport records, retaining ambiguity when identical states have
multiple possible native publications. The viewport has no text-revision/native
publication field, so do not invent exact event attribution or latency. Preserve
the existing source and qualified readers; add a separately qualified composition.

The separately qualified NATIVE_WIDGET_REVIEW_CHECK_V1.json now provides
`review_native_widget.py` for primary native caption/recorded viewport joins.
Twelve checks passed with synthetic events and geometry and unchanged pure
application span/casing code. It checks raw and formatted pane text, clock
origin/order, first/final/latest references, missing visibility and ambiguous
native predecessors. Recorded headings are predictions, not verified names;
there is no exact consumed-event attribution or qualified latency. See
README_NATIVE_WIDGET_REVIEW.md for purpose, inputs, outputs and run commands.
Next compose it with a reconstructed V2 cell and the actual prepared display
roster and primary settings. Its caller-supplied roster is not independently
admitted by this helper. No real complete application history has passed this
join, and accepted integrated N4 cells remain zero. Preserve earlier qualified
readers and add a separate composition rather than editing their bound files.

APPLICATION_CONTENT_CHECK_V1.json now qualifies `review_application_content.py`
to compose the V2 cell evidence reader with fixed-roster and native/widget
content interpretation. It derives names from the admitted research gallery
and checks both final snapshot people fields, primary settings and shared
bindings. Twelve checks passed using actual readers and synthetic cell facts,
including both baseline name sorting and N2 document order. See
README_APPLICATION_CONTENT.md. No real complete application history has been
reviewed by this composition. The original immutable panel wrapper retains
its narrower cell reader; use the separately qualified content wrapper below
with reconstructed plan/run expectations. Naming,
timing, continuity and stop/restart remain separate work; no acceptance count
has changed. Preserve all existing code and source qualifications.

APPLICATION_CONTENT_PANEL_CHECK_V1.json qualifies
`review_application_content_panel.py`, which applies the content composition to
the exact full stopped V2 panel population. Fourteen development checks passed
on synthetic populations and a saved synthetic cell. It retains a deduplicated
input-binding registry, full-review fingerprints and per-composition/kind/tap
counts for missing captions, missing visibility and ambiguous native states.
Use README_APPLICATION_CONTENT_PANEL.md for development and actual stopped-run
commands. PASS_COMPLETE_V2_PANEL_CONTENT_COVERAGE_ONLY is evidence consistency
and coverage only, not naming/timing/resource, continuity or stage acceptance.
No actual production plan or complete application panel has run. The next
independent work is evaluator-only naming/timing interpretation and the
continuity/stop-restart runner, preserving all original source and reader hashes.

APPLICATION_TIMING_CHECK_V1.json adds the separately qualified
`review_application_timing.py` composition. Thirteen tests passed with actual
readers and synthetic cell facts plus hand-calculated timing cases. It preserves
first native publication, first final publication, compatible-event elapsed
ranges and signed source uncertainty intervals, with null visibility stages and
separate empty-caption denominators. See README_APPLICATION_TIMING.md. Recorded
visibility is per caption row, not per-word glyph: clipping can hide a word in a
row that has other visible text. Exact event attribution, phonetic alignment,
continuous exposure and source-callback deadlines remain unavailable. This is
recorded timing arithmetic, not qualified latency. No actual complete source
run or N4 acceptance was added. Naming interpretation and bounded instrumentation
for unresolved timing claims remain open, as do continuity and stop/restart.
Do not edit the existing source or qualified readers to conceal these limits.

APPLICATION_LABEL_CHECK_V1.json adds `review_application_labels.py` with 16
passing development checks and an actual-reader synthetic composition. It
interprets exact observed active/history heading strings against the already
joined display roster, with native-profile disagreements, suppressed/absent/
pending/Unknown/forced/ambiguous categories and same-pane visibility diagnostics.
Read README_APPLICATION_LABELS.md. It does not replay the GUI identity state
machine, infer a suppressed heading from a neighboring row, or select one name
when panes conflict. No evaluator truth is loaded and naming accuracy is still
unqualified. The next scoring layer needs an independently admitted evaluator
truth/roster identity join, missing and approximate-support denominators, and
constant-name/all-Unknown controls. Stable/native span populations are not
reference word counts. Source-paced naming acquisition, continuous wrong-name
exposure, continuity and stop/restart still require their own evidence. Existing
panel readers remain immutable and must not be relabelled as naming-scored.

NAMING_REFERENCE_CHECK_V1.json now qualifies the evaluator-only reference join
in `naming_reference.py`. Sixteen checks passed over all 480 existing reference
cells, both actual E galleries and the saved synthetic heading review. Read
README_NAMING_REFERENCE.md for the fixed input bindings, API and probe commands.
The exact observed INPUT.json and actual roster ordering are joined before any
reference support is described. E provenance yields 24 available of 34 intended
profiles per encoder; missing E members are not automatically treated as genuine
outsiders. Multiple intersecting identities, no activity, incomplete target-only
references, empty/zero windows and out-of-file native windows remain explicit.
Estimated activity intersections never establish exact word identity or phonetic
timing, even when only one reference identity intersects. Contexts and mappings
remain evaluator-private and never enter the runtime or Git. No naming metric or
actual GUI measurement has yet been produced. Next qualify fixed-identity
scoring and constant-name/all-Unknown controls with appropriate approximate and
missing-reference denominators, then invoke them explicitly on real complete
application evidence. Existing qualified readers/runner/source remain unchanged.

OBSERVED_NAME_SCORING_CHECK_V1.json now qualifies `score_observed_names.py` for
conditional estimated-support diagnostic counts/rates in each pane at first,
first-final and latest observations. Eighteen development tests passed, including
the saved actual-reader synthetic cell and hand-computed fixed-name/Unknown
controls. Read README_OBSERVED_NAME_SCORING.md before using `score_cell`; it
repeats the admitted reference join. Counts include missing and offscreen spans,
unresolved support, forced choices and separate empty-caption exclusions. There
is no identity permutation, inferred suppressed name or winner between conflicting
panes. The controls hold observed joint visibility opportunities fixed; no actual
control GUI was rendered. These are native-span diagnostics, not exact word or
speech-duration naming accuracy, certified outsider rate or exposure duration.
Use a separately qualified full-panel composition to invoke this scorer on
complete actual histories. Returning-person/fragmentation metrics, unresolved
source timing instrumentation, continuity and functional stop/restart still need
implementation/qualification. Accepted integrated N4 cells remain zero.

NAME_PANEL_CHECK_V1.json now qualifies the explicit complete-panel composition
`review_name_panel.py`: 18 development checks, including inherited exact census
tests, saved synthetic all-reader/scorer compaction, unequal-denominator summed
rates and a 240-cell/96-group output-budget fixture. Use README_NAME_PANEL.md's
production CLI only after an actual admitted V2 panel has stopped. It verifies
all planned cells and preserves a conflict-checked input registry, full result
fingerprints and lossless count vectors. Groups separate composition, tap,
panel/repeat kind and reference class; fixed roster/control/context drift fails.
PASS_COMPLETE_V2_PANEL_NAME_DIAGNOSTICS_ONLY is conditional diagnostic coverage,
not exact naming/latency/resource or stage acceptance. No actual production plan
or full panel has run. Source callback deadline instrumentation, continuity and
functional stop/restart are still outstanding, as are supported acquisition,
exposure and returning-person/track metrics. Preserve all qualified source and
readers; prepare explicit derivatives for any new instrumentation.

The user's 2026-09-25 Pi reminder is recorded in
`../n5/PI_RECONNECTION_REQUIREMENTS.md`: prioritize a short verified reconnect/
install/launch path, one shared GUI with accepted backend choices, actual storage
preflight and optional shared model assets, preserved data and rollback. Prepare
and validate offline now; on-device installation/integration checks wait until
the Pi is reachable. This does not authorize a Pi connection during this campaign.

An earlier read-only census could not inspect an unrelated `cmd.exe` process.
Re-observe at actual application admission. The exclusive application gate must
continue to refuse unresolved ownership uncertainty; do not stop that process,
bypass permissions, weaken the gate or take over the user's desktop.

The prepared continuity input is under private `local/n4/continuity-sequence-v2`.
Its public binding is `CONTINUITY_INPUT_PREPARATION_V2.json`. It is a lossless
concatenation of whole saved sessions with separate evaluator truth, not a new
acoustic bank or continuous physical XVF state. Use only its audio-only job in
prediction. V1's failed assembly remains preserved and must never be substituted.

N5's existing Windows/CM5 packages, ARM64 ELF checks and QEMU loader/CLI tests are
preparation evidence. They do not establish ARM64 model inference, source-paced
performance, physical 2-GB fit or live CM5 operation. Live hardware checks remain
explicitly deferred until the user reconnects the Pi.

Packaging reserve begins **2026-09-28 02:48:19 UTC**. The hard campaign deadline is
**2026-09-28 14:48:19 UTC**. Do not extend either. If full confirmation cannot fit,
preserve the supported baseline/candidates, classify missing coverage PARTIAL and
spend the reserved time on runnable packages and exact resume instructions.

Run commands and input/output contracts are in README_ASR_FULL_BANK.md,
README_D1_FULL_BANK.md, README_INTEGRATED_BANK.md, README_SCORING_BANK.md,
README_SCORING_REVIEW.md, README_PACED_PANEL_PLAN.md,
README_PACED_APPLICATION_RUNNER.md, README_RESOURCE_REVIEW.md,
README_VIEWPORT_REVIEW.md and README_CONTINUITY_SEQUENCE_V2.md. Do not infer
launch authorization from this order guide: use the already-authorized scope
and each existing admission/supervision interface with fresh evidence.
