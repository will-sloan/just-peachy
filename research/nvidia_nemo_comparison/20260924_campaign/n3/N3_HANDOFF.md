# N3 implementation and evaluation checkpoint — not complete

Updated September 25, 2026, approximately 00:51 UTC. N1 is complete within the
agreed offline scope; N2 is accepted with 422 evaluations, final checks, report,
handoff ZIP and verified Git backup. N3 remains IN_PROGRESS. N4/N5 preparation
is not stage completion. The Pi stays powered off throughout the campaign.

## Latest verified progress

A1 now has an actual portable CPU service using ONNX Runtime, NumPy and SciPy.
The exact nominal encoder/decoder, frontend, caches, tokens and EOU behavior
passed four saved-audio cases plus an exact replay: 2,875 steps in total. Six
additional dynamic encoder/cache cases passed. Float tolerances remain combined
rtol/atol 2e-4; integer lengths and text/control outputs are exact. This is host
component parity, not a CM5 or performance qualification.

Two concrete export details were repaired in fresh v2 derivatives: export setup
resets the service's one-frame streaming geometry unless explicitly restored,
and the decoder expects INT32 targets/lengths. The separately constructed
reference feature processor was actually in training mode. The new nominal
explicitly uses eval without random dither. Old A1 reference predictions remain
historical; the new screen performs actual inference rather than reusing them.
The original failed exports, v1 service attempt and source hashes are preserved.

The independent two-cell A1 smoke passed in the ordinary application Python,
without importing Torch/NeMo. Its fresh 96-cell screen is running. Eight
regressions, four source-paced cases and updated lexical/text comparisons follow
in that same sequential plan. Existing A0/A2/A3 predictions are hash-bound for
matched scoring. A1/P0 is also wired into the shared Controller with D0/E0,
separate recurrent state per scene and model release on backend close. Six
package/lifecycle tests and four catalog tests pass. Its full source suite and
three actual private GUI cells are queued; implementation is not acceptance.

The GUI final-state observer now checks the actual widget after render returns,
including the unchanged-text path. It never fabricates a first-display receipt
or forces redraw. All three A2 cells pass. A3's previous label-corrected panel
passed three cells, but its latest boundary retest failed: the ASR lane exceeded
the existing 60-second finalization join, leaving an unsuccessful archive. That
later failure is preserved and remains an unresolved CPU-runtime limitation.
The read-only GUI_DRAIN_REVIEW_20260925.json now verifies equal application,
runtime, audio, UI and CPU contracts for the two boundary attempts. The passing
A3/D1/E0 CPU4 run finished ASR at 103.192 seconds for 44.695 seconds of audio;
the failed run's last recorded ASR dispatch left 7.975 seconds unprocessed;
finalization failed at the existing 60-second lane join. This is a limitation of that tested complete stack/resource profile,
not a rejection of every A3 configuration. Audit/host/queue activity differences
prevent attributing the slowdown to one change. README_GUI_DRAIN.md documents
the invariant checks and redacted report. No timeout or source was changed.
Do not collapse the two runs into a claim that the latest six-cell panel passed.

PORTABLE_RECOVERY_REVIEW_20260925.json binds these results without publishing
private captions, audio, vectors or weights. README_A1_PORTABLE.md,
README_A1_SCREEN.md, README_A1_CONTROLLER.md and README_GUI_RECOVERY.md provide
purpose, inputs, outputs and PowerShell/CMD/Anaconda commands for new code.

## Current numerical ownership and exact paths

Private root: `G:\Just_Peachy_N1\20260924_campaign\local\n3`.
Read fresh receipts and exact PID creation times; this dated checkpoint is not
an ownership lock.

- Active: `plan-a1nominalv1.json`, SHA-256
  `9da6747a0133683d257785286bdc9649a194c8104cd27689f2bb9f34aebef880`.
  Live result: `numerical-a1nominalv1\RESULT.json`. Supervisor PID 42408,
  creation 1790296689.4198787; coordinator PID 44592, creation
  1790296689.5662203 at admission. Both were freshly verified alive.
- Queued: `plan-a1controllerv2.json`, SHA-256
  `b087ff40538008edcf89f17627944abcbc61e10a5505e387d747f9224ea6f465`.
  Waiter PID 33444, creation 1790297346.0805807; queue status READY means
  waiting for the occupied numerical slot, not stage acceptance. Inspect
  `numerical-a1controllerv2\QUEUE_RESULT.json`, then RESULT.json after dispatch.
  Frozen source: `..\releases\n3-common-a1controllerv2\prototype`.
  V1 Controller preparation was never launched; v2 includes the separate NeMo
  license/notice in its source inventory. Both preparations are preserved.
- Completed component check: `numerical-a1servicev2\parity\RESULT.json`,
  SHA-256 `e0bb6a3b0fa35a070745ced8a53c014aa0e1c0895bea3649ccb36716c0ba5854`.
- Latest native GUI: `numerical-guifinalv1\RESULT.json` is terminal, one
  complete A2 panel and one failed A3 panel. Earlier GUI evidence lives in
  `numerical-guilabelsv1`. No GUI numerical process remains from those attempts.

Only one numerical candidate owns resources. A lightweight waiter coordinates
the next plan through the existing supervisor; it does not run a second model.
The active screen uses its previously frozen source. New Controller source is
in a separate immutable derivative. Do not edit sources bound to either plan,
start duplicate workers, or retry manual shared-ledger writes.

## Earlier evidence retained

V3 attempted 32 jobs: 15 complete, three failed, 14 dependency-skipped. V4 fixed
the explicit native streaming geometry and A1 export metadata; it finished 29
jobs with three failures (A1 checker and both original GUI panels). A2/A3 native
smoke, conformance, CPU, source-paced, lower-buffer, 96-cell screen and eight
regressions completed. Eleven unchanged jobs carry explicit original-event and
timing reuse receipts. The frozen v4 source suite ran 448 tests, zero failures
and two platform skips. The common six UI/presentation modules and 480x800
layout retain N1 hashes in both v4 and the new A1 Controller derivative.

A fresh-reference diagnostic passed eight strict encoder/cache cases on the
preserved first export. That diagnostic is separate from the later complete
service-geometry parity. The original corrupted expected-label suffix was a
test defect; actual Tk labels were correct. The subsequent missing finality
observation and latest A3 drain timeout are separate findings.

P0/P1 comparisons, the licensed portable ITN subset and source-accurate P2,
alignment/reconstruction decisions remain available. The 110 ITN grammar and
Windows trace/toggle cases passed earlier. Final numerical interpretation must
use the new deterministic A1 screen. N3_METRICS.json and other admission JSONs
remain immutable preparation snapshots while plans bind them; do not interpret
their earlier null values as the latest measured results.

## Remaining acceptance and continuation

Review the completed A1 nominal screen, regressions, source-paced events and
Controller/GUI output. Investigate or explicitly qualify the latest A3 CPU
finalization failure before accepting the affected runtime. Do not lengthen a
timeout merely to claim real-time success; report actual backlog, elapsed time,
CPU and memory separately. Finish native/reference comparisons and lexical,
overlap/control, PnC/ITN, capability and resource tables. On four fixed paired files, A2 native CPU/CUDA and native/FP32 reference lexical
outputs agree 4/4; A3 agrees 3/4 and 1/4 respectively. Its differences are retained,
not converted into a tensor-parity claim. Native CPU component compute RTF was
about 0.55–0.58 on that panel, while the full GUI/identity stack can fall behind.
The private v4 ROUTE_COMPARISON.json remains the bound comparison source. No
winner follows from the small screen alone. Complete limitations, WORKBOOK_UPDATE.md, the small
analysis-first ZIP and remotely verified scoped Git backup.

Then regenerate N4 inputs from the accepted N3 source and complete its missing
integration, full-bank evaluation, calibration, paced/continuity and resource
selection. N5 uses accepted configurations for Windows/ARM64 software checks,
release packaging and backup. Actual CM5 checks remain deferred until the user
reconnects it. An ARM64 build or emulator result is not target performance.

The existing in-task heartbeat `continue-just-peachy-n1-n5-campaign` supplies
15-minute LLM continuation. Numerical queues and OS probes coordinate processes;
READY_FOR_REVIEW only means the plan finished attempting its jobs. The packaging
reserve begins September 28 at 02:48:19 UTC; the campaign deadline remains
September 28 at 14:48:19 UTC. Stop the recurring follow-up on offline completion
or at that deadline; do not extend either limit.

Use saved, hash-bound audio only. Keep the desktop available, all process
launches hidden and GUI tests on their private desktop without input injection
or switching. No Pi contact, microphone enumeration, new capture, playback,
training, human enrollment or personal-data modification. Preserve the original
checkout and all evidence. C:50 GiB/G:75 GiB reserves and admitted CPU/GPU/download
limits remain enforced. Rollback selects Baseline and starts a fresh session.
