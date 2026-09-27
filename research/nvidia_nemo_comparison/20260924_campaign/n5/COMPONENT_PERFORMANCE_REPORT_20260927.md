# Just Peachy component performance report — 27 September 2026

Nemotron-3 diarization provides the largest measured improvement in assigning
words to consistent anonymous speakers. Nemotron Speech Streaming English 0.6B
(A2) provides the best aggregate transcription result. Combining A2 with the
Nemotron diarizer is the strongest accuracy candidate tested, but the CPU
diarization path is too slow in the full-bank one-core measurement. TitaNet has
not demonstrated a benefit over ReDimNet in this pipeline.

This report distinguishes observed component measurements, actual Windows
integration checks, and modeled combinations. N1–N3 have scoped offline
acceptance; N4/N5 remain incomplete. No new neural inference was needed for this
report. The new processing summary reverified 960 existing results and their
compressed event files against the accepted component review.

## Components and populations

| Code | Component | Function |
|---|---|---|
| A0 | Existing Sherpa Giga | Baseline speech recognition |
| A1 | Parakeet realtime EOU 120M | Alternative speech recognition |
| A2 | Nemotron Speech Streaming English 0.6B | Alternative speech recognition |
| A3 | Nemotron 3.5 ASR Streaming 0.6B | Alternative speech recognition |
| D0 | Existing Pyannote-based activity/tracking pipeline | Baseline speaker assignment |
| D1 | Nemotron-3 Diarization, pinned official Q8 native runtime | Persistent anonymous speaker activity |
| E0 | ReDimNet | Baseline speaker embedding |
| E1 | TitaNet | Alternative speaker embedding |

The diarizer D1 and recognizer A2 are different models. Diarization answers
“which anonymous speaker spoke when”; recognition supplies the words; embeddings
can support identity matching if a compatible, calibrated gallery exists.

O0 and O1 are the two saved audio taps for the same scenes, not independent test
sets. The larger bank has 240 scenes × two taps × 16 combinations = 7,680 modeled
cases. Primary lexical WER uses 312 complete non-overlap files / 9,120 reference
words per recognizer. Speaker-attributed cpWER uses a different supported
population: 406 files / 12,032 reference words per combination. Incomplete
ambient references remain target-only. Repeated speakers, text and taps limit
independence; these are descriptive engineering results, not claims of
statistical significance or unseen-room performance.

## All sixteen combinations

Lower is better in every column. WER measures recognized words without speaker
labels. cpWER measures errors after matching predicted anonymous speaker word
streams to reference speakers; Unknown is retained. It can exceed 100% when
fragmented streams generate deletions and insertions. It is not the percentage
of people correctly named, and 99.73% cpWER does not mean 99.73% lexical WER.

| Recognizer | Lexical WER | D0 + E0 cpWER | D0 + E1 cpWER | D1 + E0 cpWER | D1 + E1 cpWER |
|---|---:|---:|---:|---:|---:|
| A0 existing | 14.92% | 99.73% | 108.49% | 39.36% | 39.36% |
| A1 Parakeet | 16.84% | 97.25% | 101.42% | 40.30% | 40.30% |
| A2 Nemotron Speech | **13.34%** | 91.65% | 104.28% | **34.23%** | **34.23%** |
| A3 Nemotron 3.5 | 17.54% | 93.62% | 107.55% | 39.40% | 39.40% |

Changing only D0 to D1 with the existing recognizer and E0 changes cpWER from
12,000/12,032 to 4,736/12,032: **60.37 percentage points lower, or 60.53% fewer
speaker-attributed edits**. Adding A2 reduces it further to 4,118/12,032,
**65.68% fewer edits than the original combination**. Keeping D0 and changing
only ASR to A2 produces a much smaller speaker-attribution gain. This identifies
speaker continuity as a major weakness of the existing combination.

These are application-method replays of actual component outputs, not 7,680
live GUI runs. The smaller N2 actual Controller evaluation supports the same
direction: D0/E0 cpWER 96.42% O0 / 100.26% O1, versus **35.98% on both taps** for
D1/E0 and D1/E1, over 1,173 reference words per tap. N2 verified that all
diarizer/embedding combinations preserved identical raw ASR words.

## Nemotron diarizer: what improved and what still fails

In the N2 screen, the nominal D1 profile gives the following results. Turn
coverage is an estimated-activity diagnostic: a turn is resolved by its largest
activity intersection with a track, not by every word being correctly labelled.
D0 uses recorded embedding/decision windows because its full activity timeline
was unavailable; D1 uses native activity. These coverage diagnostics therefore
have different observation support, while cpWER above compares actual captions.

| Diagnostic | Existing D0/E0 O0 / O1 | Nemotron D1 O0 / O1 |
|---|---:|---:|
| Resolved reference turns | 152/161 / 148/161 | **161/161 / 161/161** |
| Resolved short turns (≤1.5 s estimated activity) | 22/28 / 19/28 | **28/28 / 28/28** |
| Returning speaker keeps the same track | 18/59 / 17/59 | **57/59 / 54/59** |
| Same-person track-split incidences, summed across scenes | 38 / 35 | **3 / 5** |
| Track-merge incidences, summed across scenes | 3 / 3 | 5 / 6 |

D1 retains a returning speaker's track in **96.61% / 91.53%** of these cases,
versus 30.51% / 28.81% for the baseline diagnostic. The tradeoff is not zero
confusion: some different speakers are still merged. Resolving a short turn's
anonymous slot also does not ensure a clean embedding window long enough to
identify that person.

The direct activity error measures use complete references, include overlap,
and have approximate 20-ms activity labels rather than phonetic ground truth:

| Nominal D1 metric, N2 zero-collar primary | O0 | O1 |
|---|---:|---:|
| Diarization error rate (DER) | **23.80%** | **32.32%** |
| Macro scene Jaccard error rate (JER) | 21.24% | 21.61% |
| Missed speaker activity | 5.28 s | 6.84 s |
| False speaker activity | **61.12 s** | **89.82 s** |
| Speaker confusion | 12.20 s | 10.08 s |
| Reference speaker-time denominator | 330.28 s | 330.28 s |

DER adds missed, false and confused speaker-time and divides by reference
speaker-time. JER compares each matched speaker's activity intersection and
union; here it is averaged over 41 nonempty scenes. DER includes 42 eligible
scenes, including the empty control. Six ambient scenes are excluded from these
all-speaker metrics because their references are incomplete.

**False activity is about 78% / 84% of the nominal DER error numerator.** In the
single O1 empty/noise control, D1 produced 19.16 seconds of false speaker activity
within 44.70 seconds of audio; O0 produced none. This is an important retained
failure. A speaker can be tracked consistently while speech/silence boundaries
remain wrong. The percentages are activity-time errors, not word errors.

The larger N4 modeled bank separately records D1 DER **5.62% / 10.45%** and JER
**5.99% / 7.61%**, over 214 eligible files per tap. Its scorer uses a 0.25-second
Pyannote collar parameter (±0.125 seconds around boundaries), with overlap
included and JER aggregated by reference-speaker count. These are different
populations, collar conventions and JER aggregation from the N2 primary table;
the smaller percentages must not be described as an improvement from a repair.
N2's separate ±0.25-second collar sensitivity removes about 78.5% of reference
speaker-time, illustrating why a collar can hide much of the boundary error.
There is no comparable full-timeline D0 DER available in this campaign.

D1 preserves eight model slots. This bank observed at most three simultaneously
active slots; it does not establish eight-person conversational capacity or
reliable detection of a ninth person. Slots are anonymous. The primary N2
captions contained **zero verified personally named words**; open naming remains
uncalibrated and rejects names. Closed-roster names are explicit assumptions.

## Diarizer profile tradeoff: faster response versus more work

The 288-cell native-only CUDA panel completed all three profiles on the same
96 files. It excludes model load, ASR, embeddings and GUI. “RTF” here is measured
native cell wall time divided by audio duration, not caption latency.

| D1 profile | Input buffer / right context | Minimum audio before first emission | Zero-collar DER O0 / O1 | CUDA wall RTF O0 / O1 | Matched work relative to nominal |
|---|---:|---:|---:|---:|---:|
| Low latency, nominal | 1.04 / 0.32 s | 1.046 s | 23.80 / 32.32% | 0.0303 / 0.0303 | 1.00× |
| Very low latency | 0.64 / 0.16 s | 0.646 s | 23.83 / 31.59% | 0.0397 / 0.0396 | 1.31× |
| Ultra low latency | 0.32 / 0.08 s | 0.326 s | 24.40 / 31.71% | 0.0608 / 0.0610 | 2.01× |

The right context is part of the input-buffer geometry, not an extra amount to
add to that buffer. Minimum first-emission audio is a measured frontend/stream
boundary; actual visible results additionally wait for computation, scheduling
and presentation. The nominal CUDA result corresponds to about **1.82 seconds
of native wall time per minute of audio**. It does not imply 30-ms live latency.

Reducing the buffer makes the first result possible earlier, but performs more
frequent model work, with little consistent accuracy gain in this panel. O1
empty-control false activity remains at 19.16 / 16.86 / 16.42 seconds across the
three profiles. An earlier one-thread CPU test makes the cost particularly
clear: a 24-second overlap file took **26.89–27.14 seconds** nominal, but
**76.85–77.32 seconds** ultra-low latency. On an earlier 12-second file, nominal,
very-low and ultra-low took 7.01, 10.41 and 19.60 seconds. These short tests are
historical diagnostics, not substitutes for the full-bank CPU result below.

## Full-bank CPU processing: the central limitation

These measurements are from the accepted N4 D1 component bank: 480 files and
21,787.81 seconds (**6.052 hours**) of saved audio per embedding choice. Both
use the nominal Q8 diarizer, one native thread, CPU4 affinity, GPU off. The
collector runs the application's actual speaker-loop/window methods; it does
not run the recognizer or GUI. All result and compressed event hashes were
reverified for this report.

The campaign host is an AMD Ryzen 7 5700X3D (8 cores / 16 logical processors)
with an NVIDIA GeForce RTX 3080. CPU4 denotes a single logical processor's
affinity index, not four cores. The CUDA receipt also identifies the RTX 3080.
These are desktop measurements, not Raspberry Pi measurements.

| Measured quantity | D1 + ReDimNet E0 | D1 + TitaNet E1 |
|---|---:|---:|
| Collection wall time | 41,252.53 s (11.459 h) | 41,980.84 s (11.661 h) |
| Collection wall seconds / audio second | **1.893** | **1.927** |
| Files slower than their audio duration | **480/480** | **480/480** |
| Time inside actual native push/finish calls | 40,967.15 s | 41,474.54 s |
| Native call wall seconds / audio second | **1.880** | **1.904** |
| Actual embedding calls | 7,412 | 7,412 |
| Embedding wall time | 216.04 s | 433.38 s |
| Mean embedding call | **29.15 ms** | **58.47 ms** |
| Largest recorded embedding call | 80.87 ms | 149.90 ms |
| Remaining collection time outside those calls | 69.33 s | 72.91 s |
| Largest recorded post-cell process RSS | 698.0 MiB | 502.7 MiB |

For D1/E0, the native calls account for **99.31%** of measured collection time,
embedding calls 0.52%, and the remainder 0.17%. Thus logging/collection overhead
does not explain the component throughput deficit. One minute of audio needed
about **114 seconds** for this speaker lane. A real-time stream would accumulate
backlog under equivalent conditions. The standalone model-call bottleneck
exists before adding ASR or GUI work.

These are elapsed call durations, which include any OS preemption, not isolated
CPU instruction time. The sequential E0/E1 runs were not randomized, so the
small difference in native time cannot be attributed to the embedding model.
There are 218,380 native dispatches per encoder, including cheap pushes without
emitted frames; averaging these is not a model-chunk latency estimate. The
largest recorded individual native call was 4.18 s / 3.97 s. The residual
collection time includes initial native load and instrumentation outside the
timed calls. Embedding construction occurs before cell timing.

RSS above is the largest **post-cell sample**, not peak memory or total-system
RAM. ReDimNet/TitaNet RSS differences vary across harnesses and resident model
sets. The CUDA panel's host process RSS excludes GPU VRAM; no isolated GPU
allocation peak or 2-GB CM5 qualification is available. Do not divide the
one-core CPU and CUDA RTFs to claim a controlled hardware speedup.

The earlier N2 full Controller observations provide a separate resource view:

| Composition, existing A0 | Diarizer execution | CPU seconds per minute of audio O0 / O1 | Maximum sampled process RSS O0 / O1 |
|---|---|---:|---:|
| D0/E0 | CPU | 15.65 / 15.61 | 513.1 / 511.0 MiB |
| D0/E1 | CPU | 16.67 / 16.58 | 567.2 / 567.4 MiB |
| D1/E0 | CUDA | 21.75 / 21.80 | 1082.5 / 1082.5 MiB |
| D1/E1 | CUDA | 21.89 / 21.81 | 1159.5 / 1159.7 MiB |

Each row/tap covers 48 files / 2,145.381 seconds. This CPU-time column includes
the process's work supporting CUDA; it does not measure GPU compute time.
Observers and concurrent campaign lanes were present. These are actual host
observations, not isolated hardware comparisons or live caption latency.

## Recognition and embeddings: accuracy and processing

| Recognizer | Errors / 9,120 words | Substitutions / deletions / insertions | Earlier CPU component compute RTF | Sampled process RSS |
|---|---:|---:|---:|---:|
| A0 existing | 1,361 | 880 / 354 / 127 | ~0.055 | ~351 MiB |
| A1 Parakeet | 1,536 | 790 / 612 / 134 | ~0.56 | ~613 MiB |
| A2 Nemotron Speech | **1,217** | **571 / 565 / 81** | 0.569 | 1025.7 MiB |
| A3 Nemotron 3.5 | 1,600 | 965 / 508 / 127 | 0.552 | 1022.9 MiB |

The accuracy column is the larger modeled bank; processing columns are the
earlier N3 CPU panels, not simultaneous whole-stack measurements. They must not
be summed with the D1 wall-time column as an exact prediction of GUI latency.

A2 has **10.58% fewer lexical errors** than A0: 309 fewer substitutions and 46
fewer extra words, offset by **211 more omissions**. It is not uniformly better.
Scenes containing short turns favor A0 slightly (13.46% versus 13.79% WER), and
A2's omissions there rise from 48 to 130. These are scene-wide word scores, not
isolated short-turn transcription scores. On the labelled approximately 0-dB
SNR subset, A2 improves WER from 45.17% to 34.17% (18 dependent files / 600 words);
tiny 10-/20-dB subsets instead favor A0. See the linked insights report for
the denominators and additional breakdowns.

A1 is a functioning portable ONNX alternative but loses aggregate accuracy.
A3 also loses accuracy in this pinned native Q8 route. A2's four-file CPU/CUDA
and native/FP32-reference lexical comparisons agree 4/4 each; A3 agrees 3/4 and
1/4. These are lexical route checks, not complete tensor parity. A3's poorer
score therefore does not establish that NVIDIA's original full-precision model
is intrinsically worse.

The matched embedding-only benchmark processed the same 1,194 saved windows
with one CPU thread per encoder. E0 took **183.2 s**; E1 **288.9 s**, about 58%
longer. On the clean-enrollment query diagnostic, E0 identified the correct
known-gallery candidate in **182/192 (94.79%)**, versus E1 **174/192 (90.63%)**.
Using saved processed enrollment, E0 reached **184/192 (95.83%)**; E1 reached
**179–180/192 (93.23–93.75%)**, depending on position/stream. Query pair EER was
4.17% for E0 and 4.23–6.21% for E1 across these conditions; lower is better.
These whole-source-support query diagnostics do not calibrate short runtime
windows, stranger rejection or personal-name display.

E1 doubles measured runtime embedding-call time on D1-selected windows and
leaves every D1 cpWER total unchanged. With D0 it worsens cpWER for all four
recognizers. There is currently no measured reason to replace E0 with E1 as
the default. That is a conclusion about this integration, not all possible
TitaNet training/enrollment conditions. Separately, the isolated punctuation
reference panel measured F1 0.7273 on 110 eligible clips and zero normalized
lexical changes over 1,289 inputs; it is not a conversational punctuation score.

## Working Windows state and remaining work

There are functioning Windows NeMo engineering previews. N3 passed three actual
private GUI cases each for A1 and A2; A3 passed three with two CPU cores after a
retained one-core drain failure. New A2 caption-only and anonymous-conversation
lifecycle checks each processed a complete 44.695-second saved file, rendered,
saved, reopened identically in a second GUI process, deleted only the test
session, and closed normally. The anonymous case consumed all 715,127 samples
in both lanes, observed two model slots and 20 embedding calls, and ended with
zero speaker lag. This proves a working lifecycle, not live throughput or
correct labels on every file.

The broader actual N4 panel is still partial: two collected cells await review,
two D1 cells failed, and 236 were unattempted. D1 exceeded the unchanged
60-second final-drain limit, with a subsequent clean-closure failure in one
Controller. **No new N4 deployment profile is accepted.** The component accuracy
gains and passing smaller Windows cases do not erase these failures.

The next implementation priorities supported by this evidence are to improve
or appropriately provision the native CPU diarization path, retest bounded
full-application drain/closure behavior, investigate D1's O1 false activity and
A2's omissions, and then complete the missing resource/GUI/release checks. A
smaller buffer is not an automatic throughput fix. CUDA is a promising desktop
route from the component measurements, but is outside the current GPU-off
execution allowance. The existing baseline remains available. ARM64 software
validation and release packaging remain partial; installation/live CM5 checks
require the Pi to be reconnected later. It remains powered off now.

## Evidence and reproduction

- [N2 final review](../n2/FINAL_REVIEW.md) and `FINAL_REVIEW.json`: actual
  Controller/caption comparisons, activity, turns and host resources.
- [Native profile summary](../n2/evaluation/native_profiles/NATIVE_PROFILE_SUMMARY.md)
  and its JSON: all 288 native-only CUDA profile cases, zero-collar metrics,
  sensitivity, capacity, resources and matched ratios.
- N2 `diarization/NATIVE_PANEL_RECEIPT.json`, `NATIVE_OVERLAP_O0_RECEIPT.json`,
  `NATIVE_OVERLAP_O1_RECEIPT.json`, `NATIVE_BOUNDARY_RECEIPT.json`: historical
  CPU diagnostics and actual first-emission boundaries.
- [Embedding component results](../n2/evaluation/COMPONENT_RESULTS.md): matched
  windows, resource observations, EER/top-1 and calibration restrictions.
- [N3 final report](../n3/REPORT_N3.md): CPU ASR costs, lexical route parity,
  punctuation and actual GUI checks.
- [Main modeled results](../n4/MAIN_MODELED_RESULTS_V1.md) and
  `MAIN_MODELED_SCORING_ACCEPTANCE_V1.json`: 7,680 cases and metric denominators.
  Private main report SHA256:
  `e872670a9f9ca56c620184236ca3fb7ea6132499aaa8339da29e0fe09b656a2b`.
  Two-tap totals sum counts, never average unequal denominators. D1 activity
  reads the `A0_D1_E0` cohorts once; identical repetitions under other ASRs and
  encoders are not additional activity evidence.
- [D1 processing summary](D1_PROCESSING_SUMMARY_V1.json): new aggregate of all
  960 hash-verified existing cells/events, bound to `D1_FULL_BANK_REVIEW_V3.json`.
  [Reproduction README](README_COMPONENT_PERFORMANCE_V1.md) gives purpose,
  inputs, outputs and PowerShell/CMD/Anaconda commands. It reruns no models.
- [Additional ASR insights](NEMO_RESULTS_AND_INSIGHTS_20260927.md),
  `NEMOTRON_WINDOWS_CAPTION_CHECK_V1.json`,
  `NEMOTRON_WINDOWS_ANONYMOUS_CHECK_V1.json`, and `N5_STATUS_20260927_V16.json`:
  current Windows scope and unresolved release gates.

Prepared from preserved evidence on 2026-09-27; report changes no model, source
release, score, acceptance decision or failed attempt. Private recordings,
profiles, vectors and weights remain outside Git.
