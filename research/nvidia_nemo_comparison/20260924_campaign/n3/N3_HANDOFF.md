# N3 implementation checkpoint — not complete

N3 is implemented and undergoing numerical review; stage acceptance is pending.
N2's 422-cell run, final checks, reviewed report and accepted handoff are closed.
The latest N3 recovery is v4, not the historical v2 plan described below. Read
RECOVERY_V4.md and the fresh private numerical-v4 RESULT before doing work.
A2/A3 native conformance, CPU, paced, lower-buffer, screen and regression jobs
completed. V4 is terminal: 29 complete jobs, three failed (the A1 post-export
checker and two GUI panels). Aggregate lexical/text/route reports exist and
need interpretation. A fresh A1 model then passed eight strict encoder/cache
cases on the preserved graph, maximum absolute error 3.0517578125e-5. Portable
frontend/decoder/EOU and real-audio parity are still outstanding; the original
post-export mismatch has not yet been causally resolved.

Both GUI failures were the same corrupted expected-label suffix in the test.
Actual Tk labels were correct. The unchanged application is now undergoing all
six GUI cells through `plan-guilabelsv1.json`, with only two test literals and
the private module identifier corrected. See README_A1_DIAGNOSTIC.md and
README_GUI_RECOVERY.md. No duplicate numerical owner or tolerance change was
introduced. RECOVERY_REVIEW_V4.json binds the terminal evidence and diagnosis.

## Implemented and checked

- Exact native A2/A3 Q8 CPU/CUDA streams, raw/lexical/formatted/manual layers,
  complete journal/tail handling, persistent identity state and private runtime
  catalogs; explicit English, greedy decoding and right-context settings.
- A1 actual recurrent EOU reference and A2/A3 FP32 NeMo reference. A1's two
  official service files are extracted with attribution and one import change;
  no Pipecat/server dependency was installed. All reference imports pass.
- Frozen common 480x800 UI and mode contract. New ASR composition selection
  changes Controller/model wiring; the six UI/presentation files and layout
  configuration have matching N1 hashes. Baseline assets remain unchanged.
- 24 model-free tests pass. Native C header ABI checks compile. The NeMo-derived
  ITN subset passes 110 numeric FST comparisons and all 110 Windows trace/toggle
  cases. Source, asset and configuration checks are separate from neural tests.
- Five exact official model artifacts are downloaded and hash verified. P2,
  alignment and reconstruction decisions are in SOURCE_DECISIONS.md.

## Numerical plan and current evidence

The historical v2 plan had 32 sequential jobs. The v4 recovery includes the complete frozen
prototype test suite; real smokes; A1 empty/silence/replay and stateful ONNX
attempt; A2/A3 CPU conformance and reference/native comparisons; one lower-buffer
contrast; 384 screen cells, 32 regression cells, paced cases, six actual GUI
cells; lexical, punctuation/ITN and route comparison reports. Nothing uses
prerecorded transcript substitution or evaluator truth inside inference.

Private root: `G:\Just_Peachy_N1\20260924_campaign\local\n3`.
Active plan: `plan-v4.json`. Frozen source: `..\releases\n3-common-v4\prototype`.
Live status: `numerical-v4\RESULT.json`. The queued diagnostic uses
`plan-a1diagv1.json` and `numerical-a1diagv1\QUEUE_RESULT.json`, then RESULT.json.
That diagnostic is now terminal. The live GUI recovery uses
`plan-guilabelsv1.json` and `numerical-guilabelsv1\RESULT.json`.
V2 failed a bytecode-binding preflight. V3 attempted all jobs but its native
initialization and A1 metadata failures prevented dependent runs. V4 reuses
eleven verified unchanged jobs with explicit original-event and timing receipts.
No v1 numerical run was launched. Its preparation files are preserved as
superseded evidence after the module-name and reference-import preflights.

`N3_METRICS.json` and PREPARATION_TESTS.json are preparation snapshots. Null
accuracy, CPU and VRAM measurements are intentional. Read the live private
results for later numerical changes; do not treat this checkpoint as acceptance.
EXECUTION_ADMISSION.json and GITHUB_BACKUP.json record admission/backup once
created. Both now exist: the hidden waiter was verified at PID 13640 with its
creation time, in WAITING_N2. A source tag named integration/rc is not a validated
backend release. A combined live-ledger update was blocked by automatic approval
review (only "blocked by policy" was supplied); the live ledger was left
unchanged and the separate execution receipt is authoritative for queue status.

## Run, rollback and resume

README_QUEUE.md gives exact PowerShell and CMD/Anaconda commands for checking
and supervising the plan. README_RUN.md covers actual saved-audio inference;
README_GUI.md describes private-desktop tests. Every new executable/helper has
a README describing purpose, inputs, outputs and invocation.

The numerical queue uses the existing OS supervisor, disk reserves and campaign
deadline. It starts no LLM and changes no user desktop focus. The Pi stays off;
there is no SSH, device enumeration, recording, playback or new acoustic bank.
It writes an exact-task manual resume request on completion/failure. The
registered in-task heartbeat `continue-just-peachy-n1-n5-campaign` now provides
15-minute LLM continuation through the campaign deadline; it has actually
triggered follow-ups. Existing owned scheduled probes remain active. The
numerical queue's older manual-only notice describes its own dispatch method.

Rollback: the original checkout, normal launcher, assets and personal data are
untouched. In a candidate Controller select Baseline and start a fresh session.
Do not terminate N2 or unrelated processes. A queue failure preserves evidence;
create a new reviewed run path for changed or failed cells.

Exact resume instruction for this existing task:

> Complete N3 in G:\Just_Peachy_N1\20260924_campaign\worktree. Inspect N2's
> numerical-v2 RESULT/CHAIN_RESULT and N3's numerical-v4 RESULT plus the queued
> numerical-a1diagv1 and numerical-guilabelsv1 QUEUE_RESULT/RESULT and
> live PID creation times. Do not duplicate either stage. If N3 finished,
> review every job, denominator and private GUI capture; diagnose failures;
> finish A1 portable frontend/predictor/EOU parity if feasible; publish actual
> lexical/PnC/ITN/resource and capability tables; update N3_HANDOFF, metrics,
> limitations and proposed workbook update; create a final small analysis ZIP
> and verify the scoped GitHub backup. Preserve failed evidence. Continue the
> already-authorized N4 after reviewed prerequisites, regenerating its catalog
> from the accepted N3 source. Keep the desktop available and the Pi offline.

Open acceptance items: actual model/GUI/file evidence and interpretation; native
reference comparisons; A1 portable qualification or documented tested failure;
final artifact/Git receipts. CPU/ARM64/CM5 2-GB qualification remains explicitly
separate. No model is declared the winner from the 48-scene screen.
