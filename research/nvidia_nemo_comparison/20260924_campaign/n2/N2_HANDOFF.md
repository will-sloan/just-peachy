# N2 integration - full comparison in progress

N2 is not complete. Nemotron diarization, TitaNet embeddings and real
model-specific galleries are implemented. The corrected common release is
running the complete application comparison; final interpretation and the
analysis handoff ZIP remain pending. N3 has not started.

## Implemented and actually run

The native Q8 profile comparison completed 288 cells: the same 96 prepared
files under 1.04, 0.64 and 0.32 second input buffers. Low latency (1.04 seconds)
was frozen as the nominal profile before the application factorial. Shorter
buffers cost more computation without consistent quality improvement. See
`evaluation/NOMINAL_PROFILE_DECISION_V1.md` and the native profile summary for
estimated-reference qualifications and the retained O1 noise failure.

E0/ReDimNet and E1/TitaNet processed identical sets of 1,194 E/C/Q windows each.
TitaNet CPU ONNX export, reference score parity and actual personal save/reload/
scoring passed. Embedding spaces remain separate. Processed-XVF C calibration
is insufficient for operational open naming: Unknown remains the fallback.
Closed-roster labels are visibly assumptions. Component diagnostics favor E0;
they do not select an integrated backend.

All four matched first-cell Controller smokes passed 18 exact ASR/source
signature comparisons and 60 caption-condition comparisons. Those checks are
integration evidence, not whole-screen quality or invariance results. D0
speaker fragmentation and the noise-control caption remain reported failures.

The current v7 isolated suite passed all 46 modules: 436 discovered tests,
434 passed, two explicit Linux-only skips, zero failures or errors. It includes
20 archive tests and all 44 N2 integration tests, with actual saved-audio E1
execution. Every private test process exited. The v7 actual GUI panel also
completed all six cases with clean exits and full archive integrity. All 16
saved images were inspected, with no archive warning. Closed labels remain
assumed, open labels Unknown, noise has one caption and silence has none.
`GUI_VISUAL_REVIEW.json` binds this review and preserves the earlier v6 review.

## Preserved archive failure and correction

The first full run stopped after a valid caption record exceeded the old
128 KiB archive item guard. Live captions continued, but the archive correctly
failed acceptance. Twenty D1/E0 and fourteen D0/E0 completed checkpoints,
one failed D1/E0 case and the interrupted D0 attempt remain preserved in the
v1 output directories. The old coordinator's RUNNING file is stale after its
interruption; terminal supervisor/waiter receipts record failure. See
`ARCHIVE_LIMIT_FAILURE_V1.json` and its recovery evidence.

V7 permits complete records within the existing 4 MiB aggregate queue budget,
retains the 512-item and 64 MiB metadata limits, and distinguishes an oversized
record from backlog. No payload truncation, model/ASR change, association change,
threshold tuning or relaxed archive acceptance was used. The metadata replay
preserved all available records exactly, with duplicate and missing-sequence
limitations explicitly reported.

The exact failed scene then passed a fresh source-paced D1/E0 run: all 715,127
samples arrived, 4,454 archive items were accepted and completed, no archive
error/loss remained, and all six ASR/formatting signatures matched v6. This is
a one-scene repair check. See `ARCHIVE_REPAIR_RECEIPT.json`.

## Current source and background run

Frozen application:
`G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\prototype`.
Runtime SHA-256:
`774ad5254c52a7e7644ae815140130d124c3f036517061179c8a5ef4399679ec`.
The six shared UI source files still match N1, hash
`54c0283b8058978eca87dc9b0461a15addf804200856e41d2c83b55bff590456`.
The adjacent `SOURCE_RECEIPT.json` binds all 364 files, explicit evaluator test
support and the source ZIP. Historical v4/v5/v6 and smoke-review instructions
remain preserved; v7 is the current run source.

The reviewed `local/n2/numerical-spec-v4.json` binds 384 main cells, 32 separate
regression cells and six actual GUI cells. Its SHA-256 is
`ea49c3dd76a815a4be9db97498ffd8cd05aa7e62288bf7c662dee1c8afca83db`.
CPU4 runs GUI/D0; CPU14 owns the sole CUDA diarization lane. ASR, embeddings
and punctuation use CPU. Independent scenes reset state while retaining
immutable resident weights within each batch. Old result caches are excluded.

The replacement coordinator started at 18:24:56 UTC on 2026-09-24, using
`local/n2/numerical-v2`. The reviewed waiter attached at 18:25:23 UTC. It only
observes that coordinator and runs final checks after successful exit and
exact 422-cell evidence validation. See `numerical-v2/CHAIN_RESULT.json`;
the future private analysis directory is `local/n2/final-analysis-v2`.
`READY_FOR_REVIEW` is an analysis handoff, not stage acceptance or a final ZIP.

Main source delivery alone takes at least 2.38 hours across two workers, before
loading, drainage and supplemental work. The coordinator/checker run without
an active LLM; code-only OS probes remain registered. Automatic LLM resume has
not been verified, so final interpretation and packaging require continuation
in this exact task. Source/profile Git mappings are in `GIT_BACKUP.json`.

## Run, resume and rollback

`README.md`, `README_EXECUTE.md` and `README_FINISH.md` give exact PowerShell
and CMD/Anaconda commands, inputs, outputs and checks. Do not launch a duplicate
coordinator or waiter. Inspect their exact PID/creation identities before a
resume. New source/contracts require fresh output directories; preserve failed
and interrupted attempts.

To continue in Codex: inspect `numerical-v2/RESULT.json` and `CHAIN_RESULT.json`.
If READY_FOR_REVIEW, inspect the full main/regression/GUI evidence, finalize
`N2_METRICS.json`, limitations and the proposed workbook update, verify final
Git backup, then create and verify the analysis ZIP with `README_PACKAGE.md`.
Do not start N3.

Select Baseline for backend rollback; the immutable N1 release and original
personal-data root remain intact. Configure an explicit separate N2 data root.
TitaNet requires compatible reference vectors; ReDimNet vectors are not reused.

The Pi stays off and disconnected. No microphone enumeration, live enrollment,
USB, playback, desktop focus changes or hardware deployment occurred. Pi/ARM64
throughput, physical latency and total-system 2 GB suitability remain untested.
Private audio, full transcripts, voice vectors and weights stay outside Git.
