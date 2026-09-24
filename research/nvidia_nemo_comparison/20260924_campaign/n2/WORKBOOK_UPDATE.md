# Proposed workbook insertion — N2 accepted offline comparison

The master workbook has not been rewritten. N2 implemented real selectable
D1/E0, D0/E1 and D1/E1 backends alongside immutable D0/E0 in the shared 480×800
frontend. D1 is Nemotron native Q8 with eight persistent activity slots;
E1 is TitaNet CPU ONNX with a separate compatible gallery namespace. ASR and
final punctuation remained fixed; adaptation stayed disabled.

Completed: 288 native profile cells, native/reference and CPU/CUDA checks,
2×1,194 matched embedding windows, personal save/reload/scoring, and all 422
final application evaluations (384 screen, 32 regression, six actual GUI).
The 46-module suite passed 434 tests with two skips; all 16 GUI images were
reviewed. Final evidence checks passed without failures. Exact ASR invariance
holds across every matched screen/regression comparison. Caption checks are
qualified as observed-only rather than independent execution of all galleries.

Nominal D1 buffering remains 1.04 seconds. Latest attributed cpWER on O0/O1 is
96.42/100.26% for D0/E0, 105.46/104.60% for D0/E1, and 35.98/35.98% for either
D1 combination (1,173 complete-reference words per tap, Unknown retained).
Actual verified named words remain zero under insufficient processed-domain
calibration. Closed labels are assumptions. These figures do not establish
lexical WER, safe open naming, or superiority of TitaNet.

D1 estimated zero-collar activity DER is 23.80/32.32% O0/O1; D0 DER remains
unavailable. Keep the O1 false-activity and fixed-ASR control insertion failures.
The earlier archive failure was repaired without truncation and the complete
v7 run passed; all original failed evidence remains preserved.

Retain baseline and the nominal D1/E0 hybrid for N4, with E1 as a controlled
comparator. Full-bank selection, isolated resources, D0 observability and
calibration remain N4 work. Pi execution, physical latency and total-system
2 GB suitability remain NOT_TESTED. No hardware contact occurred.

FINAL_REVIEW.json binds compact final aggregates to the detailed reports.
GIT_BACKUP.json records verified implementation/final report refs;
HANDOFF_PACKAGE.json records the final analysis ZIP and SHA-256. Earlier
preparation/smoke reports are historical and must not override these final
receipts. N3 is already authorized and has its own supervised execution.
