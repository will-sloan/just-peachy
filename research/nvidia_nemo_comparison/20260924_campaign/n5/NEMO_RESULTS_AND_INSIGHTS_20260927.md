# NeMo results compared with the existing pipeline

The strongest transcription candidate is A2, Nemotron Speech Streaming English
0.6B. The strongest speaker-assignment improvement comes from D1, Nemotron
diarization. TitaNet has not demonstrated an additional benefit in the primary
comparison. These findings support prioritizing A2 and D1 while retaining the
existing baseline; they do not make N4/N5 complete.

## Transcription

The independently reviewed N4 main bank contains 7,680 composition/tap/scene
cases. Primary lexical WER uses only complete non-overlap references: 156 scenes
at two taps, 312 files and 9,120 reference words per ASR. Tap recordings share
scene dependencies. Lower WER is better; punctuation/case are normalized out.

| ASR | Errors / words | WER | Difference from baseline |
|---|---:|---:|---:|
| A0: existing Sherpa Giga | 1,361 / 9,120 | 14.92% | baseline |
| A1: Parakeet realtime EOU 120M | 1,536 / 9,120 | 16.84% | +1.92 percentage points |
| A2: Nemotron Speech Streaming English 0.6B | 1,217 / 9,120 | 13.34% | −1.58 points; 10.58% fewer errors |
| A3: Nemotron 3.5 ASR Streaming 0.6B | 1,600 / 9,120 | 17.54% | +2.62 points |

A2 improves both taps: O0 14.39% → 13.00%; O1 15.46% → 13.68%.
The smaller N3 screen also favored A2 (12.00% → 10.21%), but it is overlapping
engineering evidence, not an independent replication or unseen-room result.
The separate small N4 modes panel does not favor A2 in every condition.

## What the average hides

| Error type, same 9,120 words | Existing A0 | A1 | A2 | A3 |
|---|---:|---:|---:|---:|
| Substituted words | 880 | 790 | 571 | 965 |
| Omitted words | 354 | 612 | 565 | 508 |
| Extra words | 127 | 134 | 81 | 127 |

A2 makes 309 fewer substitutions and inserts 46 fewer extra words, but omits
211 more words. Its net improvement is 144 errors. This is a useful caption
tradeoff, not uniformly better recognition. The counts identify omissions as
a repair/investigation priority; they do not establish whether endpointing,
stream geometry, precision or the trained model caused them.

Scenes tagged as containing short turns show A0 at 243/1,806 words (13.46%)
and A2 at 249/1,806 (13.79%), over 78 files. A2 omissions rise from 48 to 130
there. These are all words in short-turn scenes, not isolated short-turn-word
scores. The other 234 files favor A2: 15.29% → 13.23%. Thus the aggregate gain
does not justify a claim that A2 handles brief interjections better.

Among the explicitly labelled approximately 0-dB SNR cases with primary
references, A0 has 271/600 errors (45.17%) and A2 205/600 (34.17%), over 18 files.
Tiny floating representations of zero are combined. At 10 dB the six-file
subset instead favors A0 (13.22% versus 20.69%); the eight-file 20-dB subset
also favors A0 (10.00% versus 13.46%). These are small dependent subsets.
Unlabelled SNR is unknown, not a clean-audio category. No statistical or general
noise-robustness claim follows from these descriptive figures.

## Speaker processing and names

On the supported main-bank speaker-reference population (406 files / 12,032
words), modeled speaker-attributed cpWER changes as follows:

| Composition | cpWER |
|---|---:|
| Existing ASR + Pyannote + ReDimNet (A0/D0/E0) | 99.73% |
| Existing ASR + Nemotron diarization + ReDimNet (A0/D1/E0) | 39.36% |
| A2 ASR + Nemotron diarization + ReDimNet (A2/D1/E0) | 34.23% |

cpWER measures the error in word streams assigned to speakers. It is a different
metric and population from lexical WER, can exceed 100%, and must not be called
personal-name recognition accuracy. The D1-only improvement with unchanged ASR
shows that speaker assignment, not a change in recognized words, accounts for
most of this modeled gain. N2's smaller actual integration evidence points in
the same direction: approximately 96–100% → 35.98% cpWER.

Replacing ReDimNet with TitaNet (E1) leaves these D1 main-bank totals unchanged.
With the baseline diarizer it worsens cpWER from 99.73% to 108.49%. TitaNet also
needs its own model-compatible gallery. It is a functioning comparator, not a
demonstrated recognition upgrade. N2 primary captions contained zero verified
named words; closed-roster displayed names were explicitly assumptions.

## Cost, streaming and Windows usability

N3's CPU component observations put A2 at compute RTF 0.569 and about 1,026 MiB
sampled process RSS; A3 at 0.552 and about 1,023 MiB. The baseline CPU screen
observed about 0.055 RTF / 351 MiB, and A1 about 0.56 / 613 MiB. RTF is compute
seconds per audio second. These are different component panels, not a matched
whole-application speed benchmark. They show a substantial resource concern;
they do not establish desktop live latency or fit on a 2-GB CM5. CUDA timings
must not be treated as CPU timings, and process RSS is not total-system RAM.

N3 already passed three actual Windows GUI cases each for A1 and A2. A3 passed
three with two CPU cores after a retained one-core ASR-drain failure. Its many
short caption fragments are a readability concern. A3 lexical route agreement
was also weaker: 3/4 CPU/CUDA and 1/4 native/FP32-reference files, versus 4/4 and
4/4 for A2. A3's result therefore describes this pinned native Q8 implementation;
it does not prove the original NVIDIA model is intrinsically less accurate.

The new A2 caption lifecycle test checks one complete saved file, rendering,
save, restart/reopen and test-session deletion in real private Windows GUIs.
Use `NEMOTRON_WINDOWS_CAPTION_CHECK_V1.json` for its verified result and
`README_NEMOTRON_WINDOWS_PREVIEW_V1.md` for the user-invoked launcher. This
caption-only check does not execute the diarization lane. A separate
anonymous-conversation/balanced lifecycle check also passed on the same file:
715,127 ASR samples and 715,127 identity samples, zero final speaker lag,
two observed anonymous model slots and 20 embedding calls. It rendered,
saved, reopened and deleted only the test session, with normal process closure.
See `NEMOTRON_WINDOWS_ANONYMOUS_CHECK_V1.json`. These counts do not prove speaker
label correctness or personal-name recognition.

N4's larger actual application panel remains partial: two collected cells need
review, two D1 cells failed, and 236 were unattempted. D1 exceeded the unchanged
60-second drain; one Controller then failed clean-closure checks. No new N4
release profile is accepted. The failure is integration/throughput evidence,
not evidence that all NeMo Windows prototypes are nonfunctional.

## Evidence and limits

Primary sources: `../n4/MAIN_MODELED_RESULTS_V1.md`,
`../n4/MAIN_MODELED_SCORING_ACCEPTANCE_V1.json`, `../n2/FINAL_REVIEW.md`,
`../n3/REPORT_N3.md`, and `../n3/N3_ACCEPTANCE.json`.
The source for error-type and condition counts is the acceptance-bound private
N4 `REPORT.json`, SHA-256
`e872670a9f9ca56c620184236ca3fb7ea6132499aaa8339da29e0fe09b656a2b`.
Counts sum the two `A*_D0_E0` cohorts' `word_metrics.primary_wer`; condition
counts use their matching `strata` entries. All four ASRs have matching word
and file denominators in the comparisons above. No alignments were rerun.

The bank is seen engineering data with repeated speakers/text/taps. These
descriptive comparisons do not establish generalization or statistical
significance. Incomplete ambient references stay target-only. Real personal
naming, all-mode GUI behavior, continuity, complete-stack resources and release
qualification remain separate. The Pi is off; installation and live CM5
checks remain deferred until reconnection.
