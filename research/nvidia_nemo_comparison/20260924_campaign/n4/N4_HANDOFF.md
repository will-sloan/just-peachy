# N4 partial checkpoint — preparation complete, comparison pending

Latest code checkpoint, September 25: A1 now has a qualified host portable
component and a passing application smoke; its 96-cell nominal screen is complete, with regression/paced and Controller/GUI
validation still pending. `compose_release_v3.py` is prepared for
the eventual accepted N3 source and builds all 16 intended compositions. Five
new model-free integrity tests pass, including A1/P0/bundle preservation and
refusal to silently omit A1. `check_catalog_v3.py` is prepared for actual
16-entry Controller selection. Neither a new N4 derivative nor N4 inference has
been started from the pending N3 source. See README_COMPOSITIONS.md and
COMPOSITION_BUILDER_CHECK.json. The older 12-row preparation remains historical.

**N4 is not complete.** The full 7,680 intended integrated scene/tap results,
shortlist, resource qualification and actual-application confirmation have not
run. N2 is accepted. N3's deterministic A1 screen runs in numerical-a1nominalv1,
with numerical-a1controllerv2 queued behind it. A2 GUI has three passing cells;
A3's latest D1/E0 single-CPU boundary test timed out during finalization despite
an earlier passing panel. N3 acceptance remains pending. N4 creates
no duplicate worker or automatic inference queue. `READINESS.json` is a dated
snapshot; read the live private upstream status files for later changes.

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
  checks, not model execution. A1 now has a separately implemented adapter pending actual Controller/GUI
  validation; the older 12-entry derivative does not contain it.
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
evidence. Its DER cannot be replaced with an embedding-window proxy or zero.

Completed N2 D0/E0 and D1/E0 screens retain about 25.86 and 35.25 MiB of bound
evidence per cell. Their simple 480-cell extrapolations are 12.12 and 16.52 GiB
per composition, excluding other files. Repeating this format for N4 violates
the disk reserve. Compact lossless storage and exact cache reuse need admission
before the large run. The one-cell compression probe is not a full-bank bound.

## Source, launch and rollback

Worktree: `G:\Just_Peachy_N1\20260924_campaign\worktree`, branch
`codex/n1-foundation-20260924`. Private N4 root:
`G:\Just_Peachy_N1\20260924_campaign\local\n4`.

Derivative: `local\releases\n4-catalog-v2\prototype`; its source receipt binds
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

> Complete the already-authorized N2, N3 and N4 campaign in
> G:\Just_Peachy_N1\20260924_campaign\worktree. First inspect live N2
> local/n2/numerical-v2 RESULT/CHAIN_RESULT and N3 local/n3/numerical-a1nominalv1
> RESULT plus numerical-a1controllerv2 QUEUE_RESULT/RESULT with exact PID creation
> identities. Do not duplicate or
> interrupt their admitted owners. Review completed N2/N3 evidence and finalize
> their acceptance reports; preserve every failed attempt and diagnose actual
> failures before changing frozen choices. N4 is authorized after prerequisites
> pass, superseding older stage-specific "do not start N4" handoff prose.
> Finish N4's integrated runner/admission, validated D0/E1 association profile,
> A1 integrated adapter or documented bounded rescue outcome, full D0 activity
> observability and archive-aware evidence lifecycle. Keep exact source/event
> policy common and reconfirm affected paired results. Run admitted full-bank
> combinations with honest 7,680-cell accounting, score with pinned evaluators,
> and retain gallery/mode controls and dependency-aware strata. Measure each
> candidate alone for whole-app CPU/GPU resources. Select functioning alternatives
> without forcing a winner; run actual common-GUI 24-cell paced panels, timing
> repeats and each candidate's 20-minute saved-audio continuity test. Finalize
> N4 metrics, limitations, deployment tiers, workbook proposal, scoped Git backup
> and the final small handoff ZIP. Keep the desktop free and Pi off. Preserve the
> 2026-09-28T02:48:19.949192Z packaging cutoff; report PARTIAL if coverage remains.

The registered 15-minute in-task campaign heartbeat has triggered continuations.
N4 inference has not started. N5 has independent packaging/cross-build
preparation, but final accepted configurations depend on N4. This preparation
ZIP is not a completed-stage deliverable.
