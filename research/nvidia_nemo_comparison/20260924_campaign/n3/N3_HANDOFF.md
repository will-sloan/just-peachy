# N3 implementation checkpoint — not complete

N3 is implemented for supervised testing, but stage acceptance is pending.
The actual N2 v7 factorial remains the prerequisite. N3 inference is queued
only after the matching 422-cell run, passing final checks and released process
and OS-lock ownership. This document supersedes the old N2 note that N3 was
not yet authorized; it does not rewrite or certify N2's pending final handoff.

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

The admitted v2 plan has 32 sequential jobs. It includes the complete frozen
prototype test suite; real smokes; A1 empty/silence/replay and stateful ONNX
attempt; A2/A3 CPU conformance and reference/native comparisons; one lower-buffer
contrast; 384 screen cells, 32 regression cells, paced cases, six actual GUI
cells; lexical, punctuation/ITN and route comparison reports. Nothing uses
prerecorded transcript substitution or evaluator truth inside inference.

Private root: `G:\Just_Peachy_N1\20260924_campaign\local\n3`.
Active plan: `plan-v2.json`. Frozen source: `..\releases\n3-common-v2\prototype`.
Live status: `numerical-v2\QUEUE_RESULT.json`, then `numerical-v2\RESULT.json`.
No v1 numerical run was launched. Its preparation files are preserved as
superseded evidence after the module-name and reference-import preflights.

`N3_METRICS.json` and PREPARATION_TESTS.json are preparation snapshots. Null
accuracy, CPU and VRAM measurements are intentional. Read the live private
results for later numerical changes; do not treat this checkpoint as acceptance.
EXECUTION_ADMISSION.json and GITHUB_BACKUP.json record admission/backup once
created. A source tag named integration/rc is not a validated backend release.

## Run, rollback and resume

README_QUEUE.md gives exact PowerShell and CMD/Anaconda commands for checking
and supervising the plan. README_RUN.md covers actual saved-audio inference;
README_GUI.md describes private-desktop tests. Every new executable/helper has
a README describing purpose, inputs, outputs and invocation.

The numerical queue uses the existing OS supervisor, disk reserves and campaign
deadline. It starts no LLM and changes no user desktop focus. The Pi stays off;
there is no SSH, device enumeration, recording, playback or new acoustic bank.
It writes an exact-task manual resume request on completion/failure. Automatic
guarded LLM continuation has not been verified, so no automatic final-review
promise is made. Existing owned scheduled probes remain active during the run.

Rollback: the original checkout, normal launcher, assets and personal data are
untouched. In a candidate Controller select Baseline and start a fresh session.
Do not terminate N2 or unrelated processes. A queue failure preserves evidence;
create a new reviewed run path for changed or failed cells.

Exact resume instruction for this existing task:

> Complete N3 in G:\Just_Peachy_N1\20260924_campaign\worktree. Inspect N2's
> numerical-v2 RESULT/CHAIN_RESULT and N3's numerical-v2 QUEUE_RESULT/RESULT plus
> live PID creation times. Do not duplicate either stage. If N3 finished,
> review every job, denominator and private GUI capture; diagnose failures;
> finish A1 portable frontend/predictor/EOU parity if feasible; publish actual
> lexical/PnC/ITN/resource and capability tables; update N3_HANDOFF, metrics,
> limitations and proposed workbook update; create a final small analysis ZIP
> and verify the scoped GitHub backup. Preserve failed evidence. N4 is not
> started or selected here. Keep the desktop available and the Pi offline.

Open acceptance items: actual model/GUI/file evidence and interpretation; native
reference comparisons; A1 portable qualification or documented tested failure;
final artifact/Git receipts. CPU/ARM64/CM5 2-GB qualification remains explicitly
separate. No model is declared the winner from the 48-scene screen.
