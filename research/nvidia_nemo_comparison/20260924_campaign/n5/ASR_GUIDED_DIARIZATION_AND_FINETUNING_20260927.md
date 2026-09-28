# ASR guidance, synthetic data and practical runtime

The user's current priority is D1 Nemotron 3 Diarization with the existing
ReDimNet encoder, paired with Sherpa Giga A0 or Nemotron English A2. TitaNet E1
is retired from further candidate development; its completed comparative
results, manifests, models and failed/successful evidence remain preserved.
English remains the target. The anonymous encoder-free derivative is an
optional mode; it does not remove E0 from automatic-name research.

## ASR can inform a separate decision layer

The released D1 model accepts mono 16 kHz audio and returns speaker activity.
There is no documented text/timestamp input in the current model interface.
Using ASR output therefore means a downstream fusion/postprocessing layer,
or a separately designed and trained architecture; passing text to the current
audio API is not a supported switch. [NVIDIA D1 model card](https://huggingface.co/nvidia/Nemotron-3-Diarization)

Existing application behavior already associates D1 activity with coarse ASR
revision spans. That determines speaker labels on captions. The proposed
additional step would challenge uncertain D1 activity when ASR has no supporting
speech, while preserving raw D1 probabilities and the original ASR text.

ASR support says that speech probably occurred; it does not identify which
speaker produced it. A phantom second D1 speaker during correctly transcribed
real speech could survive this filter. Overlap and speaker confusion therefore
need separate measurement, even if noise-only false alarms improve.

An initial offline diagnostic reuses the accepted component runs on all 11
empty-control scenes, both taps (22 files; 983.30 seconds). D1/E0 emits 27.75
false speaker-seconds at the unchanged 0.5 threshold. Intersecting that activity
with nonempty final ASR utterance intervals gives:

| ASR support | Padding either side | False speaker-seconds retained | Removed |
|---|---:|---:|---:|
| Sherpa A0 | 0 s | 2.52 | 90.92% |
| Sherpa A0 | 0.25 s | 3.02 | 89.12% |
| Sherpa A0 | 0.5 s | 3.54 | 87.24% |
| Sherpa A0 | 1.0 s | 4.95 | 82.16% |
| Nemotron English A2 | all four settings | 0 | 100% |

A0 produced nonempty final ASR on three empty-control files. A2 produced none,
so the A2 gate suppresses every frame in these files by construction. This is a
useful negative-control result, not evidence that it is safe to suppress speech.
All 44 ASR final-utterance and raw-word counts were independently joined back
to the accepted review. No new neural inference or threshold selection occurred.
See ASR_ACTIVITY_SUPPORT_EMPTY_CONTROLS_V1.json and its README/script.

The diagnostic uses completed utterances, hence future information. It is not
a causal streaming test, full-bank DER improvement, or a chosen production
threshold. Coarse utterance support includes pauses; it is not word alignment.
The full-bank English A2 comparison had 565 deleted reference words versus
354 for A0. A hard ASR gate can therefore erase actual speech and harm quiet
voices, brief replies and overlap even while looking perfect on silence.

The next bounded experiment should retain the raw baseline and test a separate
causal support score on all reference-complete speech/overlap files, short replies
and empty controls. Use only ASR evidence available at that source-time event;
allow bounded delayed revisions, retain high-confidence acoustic evidence and
measure the false-alarm/miss/confusion tradeoff, speaker-attributed WER, return
consistency and added delay. Freeze candidates before scoring; do not pick a
padding value from the empty-control result and call it validated. Fully
supervised metrics remain invalid for incomplete ambient references. This
postprocessing by itself saves no native model computation.

## Language support

A2 `nemotron-speech-streaming-en-0.6b`, the current English preview model,
is English-only. A3 `nemotron-3.5-asr-streaming-0.6b` is the separate multilingual
model. NVIDIA lists 40 language-locales, of which 32 transcribe out of the box
and eight need adaptation; that is not 40 equally qualified languages. It
supports language conditioning and optional detection. Our campaign evaluated
English only, and A3's English WER was 17.54% versus A2's 13.34% on the same
primary population, so multilingual capability is no reason to switch the
English default. [A2 model card](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b),
[A3 model card](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b)

## The current bank is useful but not training-ready

FINETUNING_DATA_ASSESSMENT_V1.json freshly verifies the accepted corpus and
transcript audit bindings and measures:

- 240 scenarios, 12 families with 20 scenes each, five room-response conditions.
- 10,893.905 seconds: 3.03 hours of scenario audio. O0/O1 provide two paired
  views, 6.05 file-hours, not twice as much independent conversational content.
- 43 speaker keys, 449 source clips and 381 unique transcript hashes across
  777 complete-clip utterance occurrences; 193 clips recur across scenes.
- 156 complete nonoverlap scenes, 47 complete overlap scenes, 26 incomplete
  ambient-reference scenes and 11 empty controls.
- All 777 utterances have estimated activity; none has exact word timing.
  Recorded provenance describes a 20 ms estimated activity grid, not phonetic gold.
- All 43 speaker keys recur across scenes. A speaker-linked connected group
  reaches 69 scenes; source-linked groups reach 53. Random scene/tap splitting
  would leak related content. The existing historical partitioning has zero
  source/speaker/text-hash crossings in this audit, but all partitions have now
  been used in campaign comparisons and are not an untouched blind test.

The useful families include overlap, rapid short replies, returning speakers,
long pauses, relative source levels, distance/outsiders, obstruction, nonspeech
transients, ambience and empty controls. These match the observed D1 problems.
The speech comes from existing Common Voice, HiFiTTS and CMU ARCTIC recordings
arranged into scenarios; a corpus name involving TTS does not establish that
the waveform itself was generated speech. Reuse, short scripts and simulated
room conditions limit claims about spontaneous real conversations.

NVIDIA trained D1 using simulated mixtures and real conversations, so synthetic
scenarios are compatible with its training approach. The official training
recipe expects audio with speaker-count and RTTM speaker-time labels. Our bank
could support a small domain-adaptation study after annotation and provenance
work, not a credible from-scratch replacement dataset.
[NVIDIA training description](https://huggingface.co/nvidia/Nemotron-3-Diarization),
[official training recipe](https://github.com/NVIDIA-NeMo/Speech/blob/main/examples/speaker_tasks/diarization/conf/neural_diarizer/sortformer_streaming_8spk.yaml)

Diarizer fine-tuning principally needs reliable speaker-time activity labels,
including simultaneous speakers. Exact word timestamps are not a prerequisite
for that task; their absence matters more for ASR alignment/fusion experiments.
The current estimated activity labels are the main annotation concern for D1.

Before training: validate speaker activity boundaries and overlap against the
recorded signal; exclude or fully annotate unknown ambient speech; group both
taps, repeated clips, speakers, text and matched room variants appropriately;
reserve a truly unseen future evaluation set; and verify source-level training
rights. Retain silence negatives without turning untranscribed real speech into
silence targets. Focus an initial adaptation on activity/overlap/short replies,
evaluate catastrophic forgetting on other recordings, and keep explicit
encoder/gallery calibration separate. No training, augmentation/new scene bank,
human enrollment or model download was started for this assessment.

## What the CPU processing factor means

In the accepted D1/E0 component collection, one pinned numerical CPU thread
with GPU off took 1.893 seconds per audio second; native calls alone accounted
for 1.880 and 99.31% of wall time. E0 embedding calls accounted for 0.52%.
These are measured component results, not the entire app or maximum workstation
throughput. Calls include scheduling/preemption. Full Windows A2+D1 GUI work
adds ASR and application cost; it is not guaranteed to sustain the component rate.

At a constant 1.893 processing factor, 10 minutes of stored audio requires
18.93 minutes of processing. During ten minutes of continuous 1x arrival, an
initially empty serial queue would process about 5.28 minutes and accumulate
about 4.72 minutes of unprocessed audio; after input stops, draining takes about
8.93 more minutes. This arithmetic excludes startup, buffering and other work.
It is serious for uninterrupted live diarization, acceptable for some offline
jobs, and is not merely a fixed two-second delay.

Real-time service needs sustained throughput below 1.0 with spare capacity for
bursts; an engineering target such as 0.7 is a target, not a current result.
Separating fast captions from delayed speaker/name annotations can improve
usability, but the delayed lane still falls further behind if it remains slower
than input. Pauses only help if processing can actually exploit them; the current
continuous diarizer still processes silence, so ordinary quiet periods are not
automatically free time. Dropping chunks or resetting at oracle speaker changes
would invalidate state and the comparison.

Plausible routes are a controlled two-core/native-thread trial within the
current CPU allowance, measured CPU build/runtime optimization, more efficient
streaming geometry, or GPU inference when separately enabled. Scaling is not
assumed linear. Already-Q8 weights mean another precision reduction is a new
accuracy/parity experiment. Smaller buffers increased work in existing tests.
Larger chunks may improve throughput but add waiting, especially the 30.4-second
offline-style profile. Fine-tuning the same architecture does not itself fix
compute throughput. Distillation/pruning would be a separate training project.

Previous standalone CUDA D1 screening measured approximately 0.03 processing
factor for the nominal profile, demonstrating a viable desktop acceleration
route in that scoped test. It is not current GPU authorization, combined-app
latency, or evidence that a CPU-only Pi will achieve that speed. GPU remains off.

Saved-file real-time simulation is possible without microphones: deliver the
existing WAV in source-clock-paced blocks, preserve continuous native state,
and record publication timestamps, queue growth, dropped samples and final
drain. Slowing playback to 0.5x to make a factor-two worker keep up must be
labelled slowed-source demonstration, not real-time performance. The existing
campaign's paced tests and failures remain the starting evidence.

## Pi and phase priorities

The new Windows pair passed independent review at this checkpoint. Both fresh
derivatives gather the configured 100 ms ASR journal quantum plus the exact EOF
tail, fixing 20-80 ms coarse timestamp differences caused by partial journal
reads. This is a delivery change and may add up to 100 ms of buffering. It does
not change model weights, native word offsets or relax timestamp tolerances.

With exactly two logical CPUs and one numerical thread per model, A2+D1+E0
consumed all 715,127 samples in both lanes and completed the 44.695-second
saved source in 91.95 session-wall seconds. The encoder-free anonymous arm
completed in 91.04 seconds, with zero external encoder loads/calls versus one
load and 20 calls for E0. Both retained all 4,470 activity frames and identical
thresholded activity, displayed captions and saved text/coarse timestamps.
Each saved four utterances, reopened them in a new process and deleted only
the test session. All four GUI processes closed normally on private desktops;
the user's input desktop stayed unchanged. Neither timing is a full-bank or
steady-state speed benchmark; roughly 2.04-2.06 session seconds per audio second
on this one file still does not demonstrate continuous real-time operation.

Thirteen lifecycle/refusal tests and three fragmentation/gain/failure tests
on each source passed. Earlier filesystem-race, one-CPU drain and timestamp
parity failures remain preserved in D1_ANONYMOUS_ATTEMPTS_V1.json. The exact
successful receipts are in D1_ANONYMOUS_WINDOWS_CHECK_V1.json. Read
README_D1_ANONYMOUS_PREVIEW_V1.md for Start-N5-NEMOTRON-REDIMNET.cmd and
Start-N5-NEMOTRON-ANONYMOUS.cmd. Both launch checks passed without opening a
visible GUI. These are saved-file engineering previews in anonymous mode;
they do not qualify personal-name recognition or replace N4/N5 acceptance.

Preserve the current baseline and N1-N3 scoped acceptance. Finish honest N4/N5
evidence and packaging for the functioning paths; do not relabel modeled results
as full application acceptance. Prioritize A0+D1+E0 and A2+D1+E0, plus the
anonymous bypass mode. New E1 work is out of scope per the user's latest choice.
The current full N4 app panel and ARM64 functional blockers remain unresolved.

The Pi stays off until the user reconnects it. Tomorrow's first work should be
read-only architecture/storage/dependency checks, scoped install into the
versioned release location, hash verification, and saved-file smoke/parity and
paced queue/resource measurement. Preserve personal data and rollback. Do not
assume 2 GB can fit the complete combination, extrapolate QEMU timing, or promise
native real-time diarization. Additional RAM addresses capacity, not CPU speed.
The existing packaging reserve and campaign deadline remain unchanged; later
hardware development must be recorded separately from offline campaign acceptance.
