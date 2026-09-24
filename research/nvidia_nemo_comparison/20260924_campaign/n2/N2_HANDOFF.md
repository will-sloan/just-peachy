# N2 accepted offline integration and comparison

N2's implementation, numerical comparison and evidence review are complete.
All 422 final evaluations finished: 384 matched screen cells, 32 supplemental
regression cells and six actual isolated Windows GUI cells. Final checks passed
with zero failures. N3 is authorized and running its separate recovery plan.
The analysis package and verified final backup are recorded separately in
HANDOFF_PACKAGE.json and GIT_BACKUP.json; preparation reports in this package
are historical snapshots, superseded by FINAL_REVIEW.md for stage status.

## Findings and candidate disposition

The nominal D1 Nemotron native Q8 profile remains 1.04 seconds, selected before
the four-way application comparison after 288 paired profile cells. Native/
reference and CPU/CUDA checks are retained with their precision qualifications.
D1 is an eight-slot activity model, not an enrollment encoder. E1 is TitaNet
with CPU ONNX export/reference checks and an actual model-specific personal
save/reload/scoring path. E0 and E1 each processed the same 1,194 E/C/Q windows.
No query-based threshold tuning or mixing of embedding spaces occurred.

Exact raw ASR/final-word and source-sequence invariance passed for every matched
screen and regression comparison. Observed caption/formatting conditions also
passed. Names never gated those words. The shared six UI files still match N1.

D1/E0 and D1/E1 latest attributed cpWER was 35.98% on each tap, compared with
96.42%/100.26% for D0/E0 and 105.46%/104.60% for D0/E1. Each tap denominator is
1,173 complete-reference words. Unknown remains in the attributed streams;
these values are not ASR lexical WER or a personal-naming success rate.
The actual primary captions have zero verified named words because processed
C calibration is insufficient. Closed-roster/shadow labels are assumptions.

D1 estimated-activity zero-collar DER is 23.80% O0 and 32.32% O1. D0 full activity
is unavailable, so no D0-versus-D1 DER ranking is justified. The O1 noise-control
failure and all collar/denominator sensitivity remain in FINAL_REVIEW.json.
Each tap/composition retains one empty-control inserted word from fixed ASR.

Retain the immutable baseline and nominal D1/E0 hybrid for N4. E1 configurations
remain functioning controlled comparators; this screen does not establish an
E1 naming advantage. N4 must run the full bank and isolated resource comparisons
before choosing release configurations. Do not promote the large CUDA result
as a CPU/CM5 winner. Sampled process memory is not total-system memory.

## Verification and preserved failures

The v7 suite passed 434 of 436 discovered tests across 46 isolated modules,
with two explicit Linux-only skips and no failures/errors. All six actual GUI
cells passed archive integrity and clean shutdown. All 16 saved images were
previously inspected; the bound GUI_VISUAL_REVIEW.json retains that review.
The final checker independently validated this source/test/GUI evidence.

The original full run failed when a valid caption exceeded the old 128 KiB
archive record guard. Its failed/interrupted results remain preserved. V7
allows complete records within the existing 4 MiB queue, 512-item and 64 MiB
metadata bounds; it does not truncate captions or relax archive acceptance.
The exact failed scene passed fresh repair checks, then the entire 422-cell
comparison completed. Earlier cache/coordinator/Tcl failures are separately
retained in LIMITATIONS.json. None is erased by this acceptance.

## Reproducibility, run and rollback

Frozen source: G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\prototype.
Runtime SHA-256: 774ad5254c52a7e7644ae815140130d124c3f036517061179c8a5ef4399679ec.
Shared UI SHA-256: 54c0283b8058978eca87dc9b0461a15addf804200856e41d2c83b55bff590456.
The adjacent SOURCE_RECEIPT.json binds 364 source files plus test support.
The original implementation is backed up at commit
9924e687af76e218b17124ffa4ce04ddcfdec293 and tag n2-integration-20260924-rc2.
Final report/continuation backup refs are recorded in GIT_BACKUP.json.

Authoritative numerical outputs are local/n2/numerical-v2/RESULT.json and
CHAIN_RESULT.json; passing checks and complete private evidence are in
local/n2/final-analysis-v2. SCREEN_SUMMARY.json and REGRESSION_SUMMARY.json are
redacted detailed reports; their hashes and compact aggregates are included in
FINAL_REVIEW.json. Do not duplicate the completed run.

README.md, README_EXECUTE.md, README_FINISH.md and README_IO.md give explicit
PowerShell and CMD/Anaconda commands with inputs/outputs. README_PACKAGE.md
explains the allowlisted analysis ZIP. Select Baseline to roll back; the original
personal data and N1 release are untouched. Candidate data roots stay separate,
and TitaNet requires its own compatible reference vectors.

Pi/ARM64 throughput, physical latency, microphones, USB/GPIO/IMU/camera and
2 GB total-system suitability remain NOT_TESTED. No live device or desktop
focus control was used. No profiles, voice vectors, full transcripts, audio or
model weights belong in Git or the analysis ZIP. N4's D0 observability,
calibration and full-bank requirements are future work, not N2 measurements.
