# N3 final component report

The four ASR alternatives are implemented and evaluated for N4 composition. This
is offline component acceptance with explicit performance and portability limits.
No default is promoted. Live CM5 checks remain deferred, and N4/N5 are not complete.

## Lexical accuracy on the paired screen

All four variants completed the same 48 scenes / 96 mono files. Each tap has
32 complete nonoverlap, nine overlap, six incomplete-ambient and one empty-control
case. The primary table uses only the 32 complete nonoverlap cases per tap.
It sums edit counts and word counts, lowercases and deletes ASCII punctuation;
this is lexical WER, not case/punctuation-sensitive verbatim WER. Both taps use
896 reference words. Raw private hypotheses and every missed reference word remain.

| Variant | Runtime used for screen | O0 errors / 896 | O0 WER | O1 errors / 896 | O1 WER | Both taps |
|---|---|---:|---:|---:|---:|---:|
| A0 | CPU | 102 | 11.38% | 113 | 12.61% | 12.00% |
| A1 | CPU | 126 | 14.06% | 141 | 15.74% | 14.90% |
| A2 | native CUDA | 83 | 9.26% | 100 | 11.16% | 10.21% |
| A3 | native CUDA | 135 | 15.07% | 145 | 16.18% | 15.62% |

A2 has the lowest measured error in this screen. A1 and A3 are worse than the
unchanged baseline on the primary totals; A1 remains a compact portable-route
candidate. This small, dependent, seen bank screen does not establish a winner
or a significant generalization improvement. N4 must assess all 240 scenes,
identity, usability, paired conditions and complete-stack resources.

Overlap uses a single unassigned mono hypothesis against speaker references;
the reported cpWER is an explicitly limited diagnostic, not diarized-system
accuracy. Ordinary chronological overlap WER is not promoted to the primary
metric. Ambient references are target-only and incomplete. In the two empty
screen files A0 emitted one false word per file; A1/A2/A3 emitted zero. One
control scene at two taps cannot establish general hallucination immunity.

## Streaming, portability and resources

A1 now runs through ONNX Runtime/NumPy/SciPy without Torch or NeMo in the
application service. Six dynamic encoder/cache cases and four saved-audio cases
plus exact replay passed the full frontend/encoder/predictor/cache/token/EOU
comparison: 2,875 steps. Floating comparisons use combined rtol/atol 2e-4,
with exact integer lengths and text/control events. The trained [70,1] service
uses valid_out_len=1/cache_drop=1; export setup must not reset that geometry.
Decoder target types are INT32. A separately constructed reference feature
processor previously used training dither; the accepted nominal uses eval/no
dither and the screen was actually rerun. Failed export attempts remain intact.

A2/A3 run the exact pinned Q8 native CPU/CUDA artifacts with explicit English
settings. On four fixed files, A2 CPU/CUDA and native/FP32-reference lexical
outputs agree 4/4. A3 agrees 3/4 and 1/4 respectively. These are lexical route
checks, not complete floating tensor parity. Lower-buffer right-context-zero
contrasts remain separate from the frozen right-context-one nominal.

| Native CPU component panel | Compute RTF | Peak sampled process RSS |
|---|---:|---:|
| A2 | 0.569 | 1025.7 MiB |
| A3 | 0.552 | 1022.9 MiB |

A1 CPU screen compute RTF is about 0.56 with about 613 MiB sampled ASR-process
RSS; A0 is about 0.055 with about 351 MiB. Native CUDA screen RTF around 0.036
must not be compared as CPU performance, and CUDA process RSS excludes device
memory. Cold loads are process-local host observations; sampled RSS is neither
total committed memory nor complete GUI/identity/system RAM. No 2-GB CM5 tier
is qualified here. N5 still needs ARM64 software/model execution.

All variants completed eight regressions each (32 total). Paced evidence is
four files each for A0/A2/A3 and eight for A1 (20 total). A1 completed about
0.79–0.91 seconds after audio duration; its negative last-final-event offsets
mean EOU preceded trailing audio, not negative completion/flush latency. First
text includes initial silence. Word-time support remains approximate without
exact phonetic gold. Accelerated screen timing is not live latency.

The A1 paced queue expected four cells but its frozen command/manifest specified
eight. The runner exited zero and completed all eight. The final reviewer
independently rehashed every result/event and the original manifest, matched all
IDs, waveform hashes, samples, gain/reset and paced delivery. It accepts that
eight-file evidence in a separate census receipt; the original FAILED queue
record remains. No failure was erased and no numerical rerun was invented.

## Actual application and GUI checks

The final A1-capable source suite ran 454 tests across 48 modules: 452 passed,
two platform skips, zero failures/errors. All six common UI/presentation files
and the 480x800 layout retain their N1 hashes. A1/D0/E0/P0 passed three actual
private-desktop GUI cases; A2/D1/E0/P1 also passed three. A3/D1/E0/P1 failed the
latest one-core boundary attempt because its ASR lane could not finish within
the unchanged 60-second join. The failure retained almost eight seconds of
unprocessed audio, and its earlier passing run also had substantial backlog.

One bounded resource contrast then used CPU affinity [4,14], within the existing
two-core allowance. It changed no model, application, audio, GUI rule or timeout.
All three A3 cases passed with verified [4,14] in each actual private process
and complete archive closure. A3 whole-cell durations were approximately 91–94
seconds for 44.7 seconds of source audio, including setup and test work. This
is functional host qualification at two cores, not real-time success; retain
the single-core failure and measure equal complete-stack budgets in N4.

Final A1 and A3 portrait captures were visually inspected: text, backend banner
and controls fit the 480x800 client. A3 showed many very short caption fragments;
functional assertions do not establish good readability. N4 must retain that
usability issue when evaluating the shared renderer and native event policy.
No screenshot was taken from the user desktop, and no mouse/keyboard/focus or
microphone was accessed. Generic UI status wording is not evidence of capture.

## Punctuation, normalization and capability decisions

P0 changed zero normalized lexical sequences across 1,289 diagnostic inputs:
1,151 ASR utterances, 132 unique original clips and six preservation fixtures.
P0/P1 complete stacks remain distinct; A2/A3 do not receive a second production
P0 pass. On 110 eligible isolated-reference clips, P0 punctuation F1 was 0.7273.
This is not conversational reconstruction F1, which remains unavailable.

The licensed finite ITN subset remains independently callable/toggleable and
default off, with 110 numeric forms and explicit traces. WSL compilation and
Windows parity/disabled-layer/WD-40 contextual fixtures passed. It changed no
screen hypothesis in this diagnostic and made two traced fixture edits. No
personal-name mapping or enrollment was created. Unsupported broad grammars,
unconstrained missing-word/grammar rewriting and LLM captions remain deferred.

No exact licensed official standalone P2 checkpoint was verified. Optional
known-script E-window alignment is deferred because a usable CTC runtime head
was not verified; retained auxiliary CTC metadata is not proof of such support.
Optional multitalker work is deferred. Exact models, terms and lineage remain
in MODEL_REGISTRY.json and SOURCE_DECISIONS.md; these gaps are separate from
measured ASR quality.

## Evidence and next stage

N3_FINAL_METRICS.json binds the source numerical plans, result/cell counts,
text/route reports, GUI processes and test suite. README_REVIEW.md documents
the reproducible review and narrow census correction. Original failed exports,
bad expected-label assertions, missing final-state observations, the one-core
A3 failure and all superseded plans are preserved. Earlier N3_METRICS.json and
admission JSONs are immutable preparation snapshots; this report and the final
acceptance/configuration receipts are current.

N4 must derive its source from the accepted A1-capable source receipt, validate
all 16 compositions, finish D0 activity and D0/E1 calibration, connect cache/
archive-aware execution, then run the integrated full bank, paced panels and
continuity/resource checks. No N4 cell is credited by these component tests.
N5 packages only configurations actually supported by that evidence.
