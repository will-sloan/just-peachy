# N2 integration â€” validation in progress

N2 is not yet complete. The selectable Nemotron and TitaNet backends, real
model-specific galleries, native/reference parity and embedding comparisons
are implemented and executed. The full application comparison and final
analysis package must finish before this document becomes an accepted handoff.
N3 has not started.

## Current evidence

The native Q8 comparison completed all 288 cells: 96 identical prepared files
under each of the 1.04, 0.64 and 0.32 second buffer profiles. Low latency
(1.04 seconds) is the frozen nominal choice before the factorial study.
Shorter buffers used more processing time without a consistent quality gain.
See `evaluation/NOMINAL_PROFILE_DECISION_V1.md` and
`evaluation/native_profiles/NATIVE_PROFILE_SUMMARY.md` for denominators,
estimated-reference qualifications and the retained O1 noise failure.

Both embedding models processed the same 1,194 E/C/Q windows. TitaNet's CPU
ONNX export and original-model score parity were actually run. E0 and E1
profiles use separate model/preprocessing namespaces. Processed-XVF naming
calibration remains unavailable: open naming returns Unknown; closed roster
assignments are visibly marked assumptions. Component diagnostics favor E0,
but do not select an integrated model. See `evaluation/COMPONENT_RESULTS.md`.

All four first-cell Controller smokes completed with exact raw and formatted
ASR/source-sequence invariance and all 15 shadow naming conditions per run.
This validates the integration gate, not the full 384-cell comparison. Both
D0 variants fragmented the smoke's speaker into several tracks; both D1
variants retained one. No threshold was tuned on that query example.

An actual private 480Ã—800 GUI run exposed missing D1 embedding archive sample
indices. The fix uses the exact waveform slice supplied to the encoder;
tests verify bit-identical exported samples. The combined Tk test process also
hit a native Tcl assertion. Earlier failures remain preserved. Each real GUI
cell and each full-suite module now requires its own private process and a
successful exit, complete archive and joined workers.

The complete isolated prototype suite passed: 46 modules, 432 tests, 430 passed,
two Linux-only skips and no failures. All six isolated actual GUI cases also
completed with zero process exits and complete archive checks. The image-review
scope and private evidence hashes are in `GUI_VISUAL_REVIEW.json`.

## Frozen application and remaining execution

The current source is
`G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v6\prototype`.
Its runtime source SHA-256 is
`6b1c960e1f31955e6d9dc93716ade0315182ea3ea0f922e5b2ee4e976d4db0a7`.
The six common UI source files remain exactly the N1 version, hash
`54c0283b8058978eca87dc9b0461a15addf804200856e41d2c83b55bff590456`.
The source ZIP and every file are bound in the adjacent `SOURCE_RECEIPT.json`.
V5 restored the existing ARM64 installer requirements omitted by V4's source
allowlist; V6 includes the calibration test's explicit evaluator-code dependency.
Application/model code is unchanged from the successful V4 smokes.
The retained, hash-bound `SCREEN_SMOKE_READINESS_REVIEW_V1.md` still names V5;
its full-run source instruction is superseded by V6 above. V5 and V6 share the
same runtime hash; V6 adds the explicit evaluator auxiliary dependency.

The reviewed private plan is `local\n2\numerical-spec-v3.json`: 384 main cells,
32 supplemental cells and six GUI cells, all using the common frozen source.
Its hash is `eed4a7fd15e77d024f52e9807b049f60924710c72263ed0233b4362b2ddeb648`.
CPU4 runs the GUI and D0 variants; CPU14 owns the single CUDA diarization lane.
ASR, embeddings and punctuation stay on CPU. Each independent scene gets fresh
state, with immutable model weights reused within a batch.

The four main screens are source paced, with at least 2.38 hours of delivery
across two workers before loading, drainage and supplemental checks. The OS
coordinator completes/checkpoints without an active LLM. Existing 10/15/30
minute code-only probes remain in place. There is no verified automatic LLM
resume guard; final review must use this exact task and these artifacts.

The independently reviewed `execute_campaign.py --wait-for-existing` waiter
was attached on 2026-09-24 at 18:05 UTC. It observes the existing coordinator
without starting another numerical run. Once all 422 cells finish and the
coordinator exits successfully, it validates their evidence and runs the final
screen/regression analysis. Its current receipt is
`local\n2\numerical-v1\CHAIN_RESULT.json`; the final private analysis destination
is `local\n2\final-analysis-v1`. `READY_FOR_REVIEW` means analysis is available;
it does not mean this stage has been accepted or the final ZIP produced.

## Run, resume and rollback

`README.md` gives explicit PowerShell and CMD/Anaconda commands for runtime
configuration, plan construction and coordinator execution. `README_FINISH.md`
describes the fail-closed post-run analysis. `README_EXECUTE.md` documents the
running waiter and the exact commands for observing this run. Inspect the current coordinator
and supervisor ownership before any resume; do not start a duplicate job.
Changed contracts require new output directories, and failed attempts remain.

Select Baseline in the shared backend selector for runtime rollback. The
immutable N1 release and original personal-data root remain intact. Configure
an explicit separate data root before using an N2 backend; TitaNet profiles
need compatible reference vectors and never reuse ReDimNet vectors.

The Pi stays off and disconnected. No microphone enumeration, live enrollment,
USB, playback, desktop focus changes or hardware deployment occurred. Private
audio, full transcripts, voice vectors and model binaries remain outside Git.

Final completion requires all application results, complete isolated tests and
GUI receipts, final metrics/limitations, scoped Git backup verification and
the small analysis handoff ZIP. `LIMITATIONS.json` keeps capability gaps
separate from execution failures and untested hardware.
