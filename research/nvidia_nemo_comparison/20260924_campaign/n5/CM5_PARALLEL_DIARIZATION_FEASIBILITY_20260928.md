# CM5 caption-first processing and selective diarization

Checkpoint: 2026-09-28. Exploration requested by the user; N4/N5 remain partial.
The Pi was not contacted. No production gate, new model inference, training or
audio-device operation was performed. TitaNet remains out of further work.

The proposed separation is useful: publish ASR text promptly and revise speaker
labels later. The code already has independent ASR and speaker threads, plus
a research presentation path that publishes `Pending identity` before the
speaker-policy scheduler. This is not proof that every GUI configuration
activates that path or that real-time deadlines hold on a CM5. The remaining
problem is reducing sustained speaker work, not merely adding another queue.

## New saved-bank measurements

Two small analyses finished on logical CPU14 below normal priority in 20.17
and 21.16 seconds. They reused 480 verified saved files (240 scenarios with
paired O0/O1 taps), their A0/A2 observations and measured D1/E0 collection
times. Nine arithmetic/causality tests passed. All input hashes and detailed
rows stay under private `local/n5/d1-workload-v1` and `d1-causal-support-v1`.
Public results: `D1_WORKLOAD_ASSESSMENT_V1.json` and `D1_CAUSAL_SUPPORT_V1.json`.
Reproduction: `README_D1_WORKLOAD_V1.md`, `README_D1_CAUSAL_SUPPORT_V1.md`.

The energy cue is 20ms RMS, with 200ms pre-roll and 400ms hangover. It is NOT
a trained speech VAD. The fixed -55/-45/-35dBFS thresholds were declared
before measuring results. They are diagnostics, not selected production
thresholds. The ASR-assisted variants keep a frame if energy OR a nonempty
ASR observation supports it, with a strict deadline. Positive partial results
count; subsequent corrections cannot undo already retained computation.

| Method | Delay allowed for gate decision | Audio retained | Estimated speech excluded | Ideal desktop service RTF | Files with ideal RTF >1 |
|---|---:|---:|---:|---:|---:|
| All audio | none in actual collector | 100.00% | 0% | **1.893 measured collection RTF** | 480/480 |
| Energy -55dBFS | 0.22s | 31.16% | 0.125% | 0.587 modeled | 56/480 |
| Energy -45dBFS | 0.22s | 28.43% | 1.371% | 0.536 modeled | 46/480 |
| Energy -35dBFS | 0.22s | 22.65% | 15.660% | 0.427 modeled | 33/480 |
| Energy -45 OR Sherpa A0 partials | 0.22s | 35.35% | 0.229% | 0.667 modeled | 52/480 |
| Energy -45 OR Sherpa A0 partials | 1s | 39.21% | 0.118% | 0.740 modeled | 68/480 |
| Energy -45 OR Sherpa A0 partials | 2s | 41.06% | 0.054% | 0.775 modeled | 72/480 |
| Energy -45 OR Nemotron A2 partials | 0.22s | 33.23% | 0.455% | 0.627 modeled | 49/480 |
| Energy -45 OR Nemotron A2 partials | 1s | 35.04% | 0.276% | 0.661 modeled | 54/480 |
| Energy -45 OR Nemotron A2 partials | 2s | 38.93% | 0.175% | 0.734 modeled | 64/480 |
| Energy -45 OR Nemotron A2 partials | 4s | 44.76% | 0.151% | 0.845 modeled | 94/480 |

Speech-loss denominator: 3,289.877 seconds of estimated union speech across
428 complete-reference files. The other 52 files have incomplete ambient
references and are excluded from speech-loss percentages, but included in
workload totals. Estimated activity uses the existing 20ms reference labels;
these are not sample-perfect human boundaries. This is not DER, WER or a
speaker-assignment test. It counts what audio a proposed gate would exclude.

There were 138 paired short-turn occurrences with at most one second of
estimated activity. -35dBFS entirely lost 15; the other listed methods entirely
lost none. Partial speech loss still occurred. A0-assisted methods missed
0.0158% of estimated overlap time; A2 at 4s and the -55dB energy cue missed none
in these labels. Neither result proves preservation of quiet overlapping
speakers in actual model inference.

The ASR deadline replay uses `available_at_sec` from the recorded component
collector's modeled serial ASR clock. It never uses an observation before
that clock says it exists, and late words cannot rescue discarded frames.
However, it does not measure arrival while ASR and D1 compete for a CM5's
resources. Final-only ASR diagnostics are separately marked OFFLINE: for
example energy OR final A0 retained 41.36%, excluding 0.054% estimated speech;
energy OR final A2 retained 48.08%, excluding 0.128%. Those use future knowledge.

The modeled RTF is retained duration multiplied by each file's measured
ungated desktop D1/E0 RTF, divided by total source duration. It assumes linear
scaling and omits new gate cost, state restoration, context replay, native
chunk granularity and fusion overhead. It is a feasibility estimate, NOT an
observed speedup. No compressed/gapped waveform was sent to Nemotron.

## What the results mean

Combining inexpensive cues is worth an actual controlled model experiment.
At -45dBFS, Sherpa support with a 220ms decision delay cut excluded estimated
speech from 1.371% to 0.229%. Allowing two seconds reduced it to 0.054%, at the
cost of retaining more audio. Nemotron ASR support arrived less helpfully for
these short deadlines; its better aggregate transcription WER does not imply
that its speech-support evidence is available sooner.

The conservative -55dB energy result also warrants comparison, not automatic
adoption. This synthetic bank is sparse: even an oracle using all known
estimated speech retains only 17.00% of total file time. In incomplete ambient
files that oracle omits unannotated speech, so it is not a valid production
lower bound there. A meeting with continuous speech is a harder workload.

Background noise is a major limitation of simple energy gating. The -55dB
cue retained 75.52% in the noise/silence/speech-in-noise family and 55.34% in
the ambience/babble/music-proxy family. Of its 56 over-budget files, 52 came
from those two families. A speech classifier and measured hardware cues could
be better, but need their own accuracy and cost evaluation.

Average throughput also hides bursts. With energy OR A0 and a 220ms deadline,
the ideal queue still reached 34.81 seconds of pending compute in its worst
file and needed up to 31.99 seconds after EOF. Even the average 0.667 estimate
does not establish prompt labels throughout a conversation. The queue tests
also confirm that equal duty cycle can produce very different backlog when
speech arrives in one long burst rather than short separated turns.

## Architecture to carry into the next derivative

1. One authoritative audio timeline, expressed as source sample indices. ASR,
   gate cues, D1 frames and embeddings carry source intervals plus observation
   availability. Capture/source delivery never waits for speaker analysis.
2. Keep ASR publication independent: stable utterance/revision IDs, immediate
   text with Pending/Unknown, then speaker-only revisions. Do not delay text
   by the gate's 0.22-4s decision buffer. Existing worker separation is useful;
   deadline priority and CPU isolation still need integrated verification.
3. Start with ONE persistent D1 stream. Measure efficient internal chunking
   and native thread allocation before multiple independent diarizer models.
   Keep E0 ReDimNet on demand for identity-bearing clean speech windows.
4. Fuse evidence by matching source intervals and track/identity history.
   Diarizer probabilities, embedding similarity and ASR confidence are
   different quantities; do not average them as calibrated probabilities.
   An interval with multiple speakers remains overlap/uncertain. Do not invent
   word-level alignment from coarse ASR utterance timestamps.
5. Bound queued audio, queued computation and label revision age separately.
   Telemetry must expose source lag, outstanding work, oldest unlabelled text,
   dropped/unanalyzed intervals and deadline misses. The current 120s RAM
   journal explicitly raises AudioGap if a consumer falls behind; it does not
   provide unlimited background catch-up.
6. On overload, keep captions running and make speaker degradation explicit.
   Fall back to a qualified lighter speaker path or Unknown labels. If a new
   stream is deliberately started near current audio, record the discontinuity
   and new track epoch; use E0/context to reacquire identities. Do not silently
   treat unprocessed audio as silence or carry an uncertain name through it.

Multiple workers help independent stages overlap; they do not create CPU
capacity. The CM5 has four 2.4GHz Cortex-A76 cores, shared by all application
work. Desktop CPU4 in these results means one affinity index on a Ryzen
5700X3D, not four CPU cores and not a CM5 estimate.
[Raspberry Pi specifications](https://www.raspberrypi.com/products/compute-module-5/).
Current Windows admission remains two logical CPUs total with GPU off. Any
Pi thread-allocation experiment belongs after reconnection and admission.

At an ungated RTF of 1.893, the ideal break-even retained fraction is 52.8%
(47.2% removed). An illustrative effective-RTF target of 0.7 would require
retaining at most 37.0%, before new overhead. If the Pi measures an ungated
RTF of 3 instead, break-even would be 33.3%; at 4, 25%. Those last two values
are examples, not predictions. Actual Pi RTF, sustained clocks, thermals,
RAM pressure and ASR competition must be measured.

## State, chunks and XVF3800 caveats

Nemotron preserves identity with an arrival-order speaker cache and recent
FIFO context. Its slots are session-relative. Splitting one conversation among
independent models can produce different slot numbering; overlapping windows
and identity reconciliation add work. Keeping one ordered stateful stream is
the simplest first benchmark.
[NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3-Diarization).

The pinned wrapper serializes pushes and allows resets only between independent
sessions/scenes. Therefore a production gate cannot just delete silence from
the waveform and retain original timestamps. It needs an explicit source-to-
model timeline map and validation of what cache/context removal does to returning
speakers and overlap. Replacing skipped audio with zeros keeps model work and
does not achieve the modeled savings. Freezing state across silence also changes
normal cache ageing; it must be validated rather than assumed equivalent.

Larger host `push` calls alone may still execute the same number of internal
chunks. Change and validate the native profile if testing chunk efficiency.
NVIDIA lists 1.04/0.64/0.32s streaming buffers and a 30.4s offline-style buffer;
these exclude computation. The offline profile is useful as a throughput
contrast, but its wait is unsuitable for prompt speaker labels. Custom
intermediate profiles need supported geometry checks and a new source/profile
binding. [NVIDIA streaming settings](https://huggingface.co/nvidia/Nemotron-3-Diarization#setting-up-streaming-configuration).
Existing campaign evidence already warns against making chunks smaller:
the 0.32s profile cost about twice the nominal GPU work, and a historical
24s CPU overlap diagnostic rose from about 27s nominal to 77s ultra-low.
See `COMPONENT_PERFORMANCE_REPORT_20260927.md`; those are not new CM5 timings.

XVF3800 provides `AEC_SPENERGY_VALUES` for four beams and
`AUDIO_MGR_SELECTED_AZIMUTHS`, whose processed direction is NaN when no speech
is detected. These can supply timestamped positive cues once the actual
firmware/output mapping and telemetry timing are verified. Missing, stale or
uncertain telemetry must not veto speech. Beam energy is not a calibrated
probability or a personal identity. Hardware beam gating can mute the weaker
of two active beams, so do not enable it as a shortcut for overlap processing.
[XMOS commands](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/AA_control_command_appendix.html),
[XMOS host guide](https://www.xmos.com/documentation/XM-014888-PC/html/modules/fwk_xvf/doc/user_guide/03_using_the_host_application.html).
No XVF telemetry was synthesized or measured in these saved-WAV experiments.

## Evidence needed before claiming real-time CM5 operation

Preserve the working Windows sources and repair ARM64 correctness first. In a
fresh derivative, compare A0/D1/E0 and A2/D1/E0 with unchanged audio, models,
gains and scoring; add a supported larger native chunk and admitted thread
allocation one at a time. Next evaluate a shadow gate that records proposed
skips without changing native inference. Only then test discontinuous input
with explicit mapping/state handling against the ungated baseline.

The acceptance run must cover continuous speech, long pauses and returning
speakers, quiet/distant speech, short replies, overlap, music/noise and overload.
Report ASR latency, speaker first/committed label latency, correction frequency,
DER/cpWER/identity errors, missed short/overlap speech, native service RTF,
backlog slope/max, tail drain, CPU/RSS/temperature/clocks and all degraded spans.
Saved-file paced execution can simulate audio arriving in real time without
microphone access; it must run longer than the queue reserve, ideally a sustained
30-60 minute session after admission. File throughput alone is insufficient.

These analyses add useful feasibility evidence. They do not close the existing
N4 actual-application or N5 ARM64/release gates. Packaging reserve remains
2026-09-28 02:48:19 UTC and deadline 2026-09-28 14:48:19 UTC, unchanged.
