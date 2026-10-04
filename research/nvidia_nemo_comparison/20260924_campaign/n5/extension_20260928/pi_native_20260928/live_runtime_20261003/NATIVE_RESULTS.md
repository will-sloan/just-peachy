# Native CM5 results for the new runtime iteration

Current hardware: 2 GB CM5, boot `69330ffb-62e8-43e9-aeb2-2198db93840d`.
The component results below are separate from later combined application checks.
Production16 is activated through the consolidated desktop launcher. v27/v28,
existing recordings and galleries remain preserved. Its 247 permitted selections
are not 247 native measurements; earlier evidence retains its actual build ID.

## Changed source and GUI checks

Build07 raw07 passed five seconds after one conditional recovery of an actual
XVF control fault. All 80,000 processed samples and 80,000 four-channel physical
microphone samples were read back with their shared sample clocks. The raw
format is four-channel 16 kHz signed PCM32; the firmware transports its packed
data over 48 kHz stereo S32LE. Maximum source lag was 0.03428 s, with zero dropped
frames. Every changed route was restored and the stream, source process and
leases closed before the complete independent PC mirror.

The preceding raw06 failed before accepting samples because AEC_MIC_ARRAY_TYPE
returned255 after the stream opened. The first recovery wrapper failed before
any device command because its prepared package dependency was absent. A new
independently pinned wrapper rechecked the fault, sent TEST_CORE_BURN0 exactly
once, and verified unchanged firmware/configuration plus readable AEC state.
Neither a periodic-reset policy nor the underlying cause is established.
Raw06 and both recovery receipts are preserved; only the subsequent raw07
establishes the new source's audio result.

GUI07 verified its full-screen geometry and normal Exit but its programmatic
driver failed before Start on a mismatched settings label. It started zero model
sessions. This is a locator/integration failure, not a failed speech-model run;
the later build08 check below exercises the repaired locator and full workflow.

Build08 `gui-qualification-02` then passed the programmatic workflow: 43 Tk
controls, stable fullscreen geometry, a policy-driven 300-second live capture
with no injected Stop, Save raw + processed, natural full saved replay, discard
of that replay and Exit. Both streams contained exactly 4,800,000 samples.
Physical capture, routes, nested process/cgroup ownership and leases closed,
and the complete regular-file PC mirror passed. This verifies programmatic
controls; physical touch and visual quality were not qualified.

Live source lag peaked at 0.32697 s with zero dropped frames. Worker peak
sampled RSS/PSS were 500,858,880/490,336,256 B live and
498,057,216/488,992,768 B replay. Available RAM stayed above 1,148,338,176 B
in the live worker trace. Both backlogs peaked around 21.2 s with Delayed's
input context, and final cursors reached 300 s. The trace does not show an
ever-growing five-minute queue. It does not establish hour-long stability.
The quiet live input produced zero embedding and punctuation inference calls;
there is no representative speech/identity quality result for this capture.
The external trace started late and measured the replay unit, not the earlier
live/source/GUI peak: aggregate sampled RSS/PSS reached
539,049,984/518,532,096 B. Owned-process swap was zero; system-wide swap was
94,371,840–119,537,664 B. The live SQLite ledger used 12,407,558 of 24,903,680 B;
replay used 846,014 B before its discard. Evidence is
`gui-qualification-02-monitor-01` and
`audit-preparation/gui-resource-review-0aaa7708b56e489da324a1c23ad6a286/REVIEW.json`.

Private evidence: `raw-qualification-06-monitor-01`,
`operation-xvf-recovery-01`, `xvf-recovery-02-monitor-01`,
`raw-qualification-07-monitor-01`, and `gui-qualification-01-monitor-01` under
the evidence root below. The raw07 source proof SHA256 is
`e4cfb4ce68c26f6e70a380592970e7921bdee5182f7b0868b0e2347da93825d4`.

## Selected recording export checks

`recording-export-01` failed while importing storage in the existing supervisor
under the128 MiB address-space policy. It produced no completed export. This
is not proof that physical RAM was exhausted. `recording-export-02` used the
fresh child but failed on the read-only store's exclusive session-lease request.
Both failed jobs closed and their full output mirrors remain preserved.

`recording-export-03` passed after the narrow shared-lease adapter repair. The
fresh child kept query-only storage, retained the original recording, used
128 MiB AS and an exact156,186,885-byte file limit, and exited naturally0.
Its terminal VmHWM/RSS were24,672 KiB, virtual size33,296 KiB and VmPeak33,440 KiB,
with zero process swap. These are child observations, not a continuous
whole-unit peak. Direct child reap, exact owner/cgroup closure and lease release
passed. No capture or models were started by this export.

The selected GUI02 recording yielded a142,926,668-byte ZIP, SHA256
`923edafd8513ef39d82ee08aefb1bc7204a106eb72a9cbadb2650920720f5b4a`.
Independent PC verification read all112 regular members and their CRCs,
142,904,468 uncompressed bytes, without extraction or source deletion. Audio
quality was not evaluated. This proves the fresh child and Store.export path;
it does not exercise the ordinary History widget. That targeted UI check
remains separate. Evidence: `recording-export-01-monitor-01`,
`recording-export-02-monitor-01`, `recording-export-03-monitor-01` and
`recording-export-03-pc-readback-01/VERIFY.json`.

recording-export-04 then passed the actual build13 Tk History Export control
path against the existing kept08 recording: one History Export invocation,
one normal Exit, ten stable480x800 fullscreen geometry samples and unchanged
270-degree orientation. The source store stayed read-only and its original
metadata hash was unchanged. No capture or model loading occurred. The file
chooser destination was injected; physical touch and visual quality remain
unqualified. Exact owner/cgroup closure, natural0 and the complete30-file
143,048,229-byte mirror passed.

The new ZIP was142,926,668 bytes, SHA256
5a63f1fa3cc698df3563ba41fa09bf861c8b167e470a9da877fa1b2fc7c2a347.
Independent PC verification read all112 regular members/CRCs and142,904,468
uncompressed bytes without extraction or deletion. Its different ZIP digest
does not replace export03's receipt. The frontend snapshot reported
RSS/VmHWM29,456 KiB, VM46,896 KiB, VMpeak47,184 KiB and zero process swap;
these are not simultaneous whole-unit peak measurements.
Evidence: recording-export-04-monitor-01 and
recording-export-04-pc-readback-01/VERIFY.json.

## Complete combined saved-input run

Build07 `pipeline-qualification-04` completed all 715,127 source samples
(44.6954375 s) through the existing Sherpa ASR/punctuation, ReDimNet and current
Nemotron Delayed path. All 3,550 event records drained; the processed recording
was kept, exact process/cgroup closure verified and every regular output file
copied/read back on the PC. Earlier failed attempts remain failed.

Measured calls used 6.00101 s for ASR accept plus 0.08238 s finish, 13.95082 s
for diarizer pushes plus 4.61064 s finish, and 1.97332 s for 19 embedding calls.
These component durations overlap with other work and must not be added into
a claimed critical-path RTF. Model setup was 2.97318 s. Peak sampled worker
RSS was 556,761,088 B, virtual size 730,234,880 B, and minimum system available
RAM 1,124,483,072 B. The unchanged 768 MiB AS limit held. Temperature ranged
57.3–61.7 degrees C; source backlog peaked at 21.2 s, including this geometry's
intentional large input context. This short saved-input result is not a live
or sustained-real-time qualification.

On the existing single-speaker, 38-word reference for this exact input, final
ASR had 12 substitutions, 2 deletions and 2 insertions: **42.1053% WER**.
Both reference and hypothesis contained 38 words after lowercase, removal of
ASCII punctuation and whitespace collapse; numbers/contractions were not
expanded. This is one short matched clip, not a dataset-wide accuracy claim,
speaker-recognition measurement or DER. No transcript text is published here.
Evidence: `audit-preparation/pipeline-allocation-review-5d6a078ff14d4f4085f6dd0868096878/REVIEW.json`
and `pipeline-qualification-04-monitor-01`.

Build08 `pipeline-qualification-05` also completed the same full 715,127-sample
saved input through Pyannote/TitaNet and Sherpa/PnC. Natural EOF, logical cleanup,
worker reaping, empty cgroup and the complete PC mirror passed. Its 45 worker
health samples reached RSS 468,762,624 B, PSS 459,514,880 B, virtual size
626,655,232 B and virtual high-water 634,437,632 B, under the unchanged 768 MiB
AS ceiling. Available RAM stayed above 1,253,867,520 B; backlog peaked at
0.23 s. ASR accept/finish used 6.50404/0.07655 s; model setup was 2.70793 s.
PnC handled three utterances with zero inference failures and two terminal
fallbacks. These timing components are not an end-to-end compute RTF.
The partial external unit trace sampled aggregate RSS/PSS up to
492,240,896/474,051,584 B, owned swap zero and system swap 118,489,088 B.
SQLite ledger use was 304,296/8,192,000 B. This short saved-input result does
not qualify optional parallel diarization or sustained live TitaNet quality.
Evidence: `pipeline-qualification-05-monitor-01` and
`audit-preparation/gui-resource-review-ee00881493764163879c58cc5b96b77b/REVIEW.json`.

Build10 `optional-first-01` completed the primary's 715,127 samples, with
44.87743 s paced source-to-EOF time and physical closure, but the optional child
failed after 2,880 samples and returned zero frames. Empty activity
acknowledgements filled the eight-batch consumer queue during native warmup.
The primary fallback result is preserved; it is not a successful optional
qualification. The activity-only build11 repair queues only nonempty masks
after the unchanged protocol and watermark checks, retaining the eight-real-
batch bound. The later build13 First02 result below evaluates that repair alongside the intervening authorization and saved-source changes.

Only three child-active resource samples were recorded: aggregate RSS/PSS
427,720,704/406,160,384 B and minimum available RAM 1,343,094,784 B. The child
startup maxima were RSS 145,883,136 B and VM 262,012,928 B. It processed only
0.18 s of input, so these observations do not establish mature combined memory
fit or throughput. Evidence: `optional-first-01-monitor-01` and
`presets-preparation-optional-first01-review-9abbf38fad32401c928dfab2f4a278ef/REVIEW.json`.

Build13 optional-first-02 passed short combined feasibility on the same
44.6954375-second saved input: primary and optional child both consumed715,127
samples with identical source hashes, and the child returned4,470 frames.
Primary/refiner EOF, all model closures, dead owners, empty cgroup and the
70-file/11,139,889-byte independent mirror were verified. Source/diagnostic
drops and owned swap were zero. This is not production eligibility, live300,
sustained operation or a speaker-label accuracy/DER result.

Across60 whole-unit samples (52 combined-resource samples), maximum sampled
RSS/PSS were637,370,368/615,421,952 B and minimum available system RAM was
1,211,170,816 B. Maximum primary/child virtual sizes were689,324,032/284,901,376 B;
these are separate process envelopes, not a physical-memory sum. Temperature
reached61.15 degrees C. Paced required-consumer wall time was56.236s; child
compute was18.290s. The paced duration is not a model-compute RTF.

The new saved-source path committed the complete input using447 append calls
of at most1,600 samples, with no append failure. Source wall time was44.707s,
maximum source-wall lag0.223s and terminal lag0.012s. Total append wall time
was5.268s, including lock, durability and observer work. This validates the
changed short intake path, not a repaired application-hour result.
Evidence: presets-preparation-first02-review-ea863b07ba804b90bf422003f60fc556/REVIEW.json.
The earlier first01 failure remains preserved.

Build13 optional-followup-01 completed the primary Pyannote/TitaNet live300
path with exactly 4,800,000 processed samples and 4,800,000 four-channel raw
samples. Primary paced EOF took 300.436 s, maximum primary backlog was 0.25 s,
and primary/source drops were zero. Raw routes and source closed. Natural0,
all owner/cgroup closure and the full155-file/144,793,183-byte mirror passed.

The optional CurrentDelayed child did not complete: its 30-second label-lag
guard stopped it after676,800 processed samples and2,112 returned frames.
The supervisor reaped it with return-15. This is successful bounded primary
fallback, not optional full EOF, a correction-quality result or production
eligibility. No physical-RAM failure was recorded. The worker continued
primary processing after the secondary stopped; late displayed child backlog
therefore is not a measurement of an active child's queue growth.

Across298 whole-unit memory samples, observed peak RSS/PSS were
696,287,232/651,709,440 B, minimum available RAM1,189,969,920 B, owned swap zero,
and maximum temperature63.35 degrees C. These are sampled observations, not
guaranteed continuous peaks. The same run logged43.604 s of ASR accept and
0.082 s finish; paced source-to-EOF wall time is not a compute-only RTF.
Evidence: optional-followup-01-monitor-01 and
presets-preparation-followup01-final-review-b4e28b6b9c9949419b4fde83448163d7/REVIEW.json.

Research06 exposed a separate single-D1 late-label presentation defect:
legitimate existing anonymous track evidence was treated as unresolved because
the current name was Unknown. The late-only build14 adds a strict same-token,
same-revision/event/track/source helper while retaining unsupported Unknown
retractions. The host replay of102 actual closed rows produced30 supported
publications instead of zero, with184 anonymous evidence publications and
negative/expiry/retraction checks. This is a host behavioral check, not new
native or speaker-quality evidence. Admitted14 was staged with exact source
verification; its changed native behavior is evaluated by the subsequent Research07 result below.
All optional/source/model/profile/storage/UI bytes remain unchanged from13.

Build14 Research07 then completed the changed sparse-embedding/single-D1
late-label path on the same715,127-sample input, with natural0, worker/owner
closure and the full58-file/8,542,245-byte mirror. All4,470 x8 ordered float32
native probability values exactly matched baseline04:35,760 compared values,
zero changed values and maximum absolute difference0. Final ASR was the same
three utterances and38-word sequence with matching source-window hashes.
Frame/column metadata provenance hashes differed; exact numerical agreement
must not be represented as identical full metadata or a quality evaluation.

The repaired late-label view published30 supported updates (two fully and28
partly attributed). Its final38 spans were31 attributed, one expired-supported
and six pending. This verifies the anonymous-evidence consumption path without
inventing support for the remaining spans. The archive lacks per-record
publication times, so actual Unknown duration/deadline compliance cannot be
reconstructed from it. No identity accuracy, DER, word-alignment, sustained
realtime or production approval is claimed.

Sparse embedding evaluated seven of19 considered runs, versus19 baseline
embedding calls:0.491s versus1.973s recorded embedding compute. Other runtime
and scheduling changes are present, so this is a matched observed comparison,
not causal isolation of sparse scheduling. Worker sampled RSS/PSS reached
550,502,400/541,426,688 B; VMpeak729,858,048 B under the805,306,368 B AS guard,
minimum available RAM1,258,323,968 B and owned swap zero. Whole-unit memory
was not recorded in this comparison. Text/first-supported-label latency was
5.675/26.452s and maximum backlog21.2s, including CurrentDelayed context.
Evidence: presets-preparation-research-comparison-b6ef55e4512a47c5ac6c77a139e44db7/COMPARISON.json,
SHA256 a8f729307181d57d477eb181820832434c5aa943f5a144da52bad288d6c3c95c.
Production16 reuses these actual14 facts through explicit reviewed GUI and
path-only changes; the later idle check did not rerun models.

## Short isolated component cohort

All rows below use the same 715,127-sample / 44.6954375-second mono PCM16
16 kHz input. WAV SHA256:
`0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8`.
No new capture or playback occurred. Weights and retained dependencies were
reused; the explicit thread2 run uses the separately compiled, pinned core.

| Run | Geometry chunk/right/FIFO/cache/update | Nominal buffer | Component RTF including EOF | First output on paced source clock | Result |
|---|---|---:|---:|---:|---|
| chunk52-02 | 52/1/80/264/40 | 4.24 s | 1.08129 | 5.12488 s | 4,470 frames, complete EOF and closure |
| chunk52-threads2-01 | 52/1/80/264/40, two graph threads | 4.24 s | 0.55433 | 4.73908 s | Full EOF/closure; all4,470×8 probabilities exactly match retained reference |
| candidate55-01 | 55/1/80/264/40 | 4.48 s | 1.10906 | 5.36967 s | 4,470 frames, complete EOF and closure |
| candidate2-01 | 24/1/80/264/40 | 2.00 s | 2.12330 | 2.46177 s | 4,470 frames, complete EOF and closure; changed geometry, quality unmeasured |
| official-low-01 | 9/4/264/264/222 | 1.04 s | 4.81915 on accepted prefix only | 1.28671 s | Failed safely at processing drain deadline; 558,400/715,127 input samples and 3,456 output frames preserved |
| official-very-low-01 | 6/2/264/264/222 | 0.64 s | 5.79081 on accepted prefix only | 0.81646 s | Failed safely at processing drain deadline; 456,000/715,127 input samples and 2,832 output frames preserved; no EOF |
| official-ultra-low-01 | 3/1/264/264/222 | 0.32 s | 8.11915 on accepted prefix only | 0.46020 s | Failed safely at processing drain deadline; 328,000/715,127 input samples and 2,040 frames preserved; no EOF |
| compact3-02 | 37/1/40/128/40 | 3.04 s | 0.85681 | 3.68575 s | 4,470 frames, complete EOF and closure; changed context, quality unmeasured |

Chunk52's 4,470×8 probabilities are exactly identical (maximum absolute
difference zero) to the preserved same-geometry A76 reference. This is numerical
agreement, not ground-truth accuracy. Candidate55 uses changed geometry; it has
no numerical-equivalence or labeled-quality claim. Its short-file result did
not improve throughput. Both still require whole-pipeline/long-run evidence.

The compact-context candidate completed the same full source in frozen build02.
Push work totaled 35.79451 seconds and final flush 2.50100 seconds; paced
source-phase wall time was 50.15250 seconds including pacing and bookkeeping.
The last regular output calls took approximately 2.6252, 2.5832, 2.5408, 2.4982
and 3.1459 seconds each for 2.96 seconds of new audio. Its component average
improved, but one of those calls exceeded its new-input duration. This short
component result does not establish sustained or whole-pipeline real-time
behavior. Cache128/FIFO40 changes context from Chunk52; no numerical-equivalence
or diarization-quality claim is made.

The Chunk52 average hides cache warmup. Its last three regular output calls
took approximately 6.44–6.46 seconds each for 416 frames / 4.16 seconds of
source audio, about 1.55 RTF. The 437 non-output pushes together took only
0.2364 seconds. Simulated input backlog peaked at 8.84675 seconds. These
observations point to full-context native computation; a Python copy reduction
does not resolve this measured bottleneck. No mode is labeled sustained real-time.

The separately compiled two-thread core reduced Chunk52 push work to21.69915 s
and final flush to3.07674 s on the complete matched file. Component RTF was
0.554327206 versus1.081286854, approximately1.95× throughput. Source-phase wall
time was48.09485 s including pacing/bookkeeping. Only the verified graph-helper
thread request changed; cache/geometry/model are unchanged and all output values
match. Two compute threads can compete with ASR and embeddings in the shared200%
CPU unit, so this short result does not qualify integrated performance.

## Continuous one-hour two-thread Chunk52 result

The separate full-application attempt `full-app-hour-02` did **not** complete
an hour. Its supervisor stopped after about319 seconds with the generic
`Output membership bound` failure. The final mirror contained100 files and
60,732,517 bytes, below the2048-file/2,306,682,336-byte allocations. A transient
atomic-publication link is a plausible cause, but the original failure did not
record path/link count and therefore does not establish that cause. Changed09
adds exact diagnostics and permits only the verified two-name publication
transaction; unknown aliases remain refused.

The failed prefix has314 complete whole-unit samples over318.193 seconds:
aggregate maximum RSS590,315,520 B/PSS573,756,416 B, minimum available RAM
1,143,275,520 B, maximum temperature66.65 degrees C, owned swap0. This was an
output-guard failure, with no measured RAM exhaustion. The supervisor failed
naturally with return1 after its SIGTERM path; the whole cgroup and exact owner
were verified closed and every output file mirrored. There is no worker RESULT
or HOST_CLOSURE receipt, so logical/model cleanup and full source EOF are not
claimed. Evidence: `full-app-hour-02-monitor-01`. The following completed hour
is the earlier **component-only** experiment, separate from this failed attempt.

`chunk52-threads2-hour-01` completed naturally with the same continuous native
state, repeating the pinned input to exactly 57,600,000 samples (3,600 s), with
360,001 output frames and EOF. Component RTF including final drain was
**0.8844478644**; push work was 3,180.45685 s and final flush 3.55546 s.
The first output arrived at 4.82294 s. No source samples were dropped. This
was a diarizer-only paced replay, without ASR, embeddings, microphone or GUI.

| Source interval | Component RTF including EOF where applicable | Mean input backlog | Last sampled RSS |
|---|---:|---:|---:|
| 0–10 min | 0.78065 | 1.358 s | 170,786,816 B |
| 10–20 min | 0.81727 | 1.472 s | 174,620,672 B |
| 20–30 min | 0.89804 | 1.768 s | 174,620,672 B |
| 30–40 min | 0.92574 | 1.875 s | 174,637,056 B |
| 40–50 min | 0.94055 | 1.911 s | 174,637,056 B |
| 50–60 min | 0.94448 | 1.923 s | 175,210,496 B at EOF |

Temperature peaked at 85.35 degrees C, swap stayed zero and available system
RAM never fell below 1,481,637,888 B. RSS settled near 166.5 MiB for most later
bins. Backlog remained bounded below four seconds but increased across bins;
late rolling RTF briefly exceeded one. The preferred 0.8–0.85 safety margin
was not sustained. This is evidence of one-hour completion and its limitations,
not a whole-application real-time or accuracy qualification.

Post-run `get_throttled` was `0xe0000`: historical frequency-cap, throttling
and soft-temperature bits, no current bits. This is a boot-history snapshot,
not continuous flags or proof of exactly when throttling occurred. Definitions:
[Raspberry Pi documentation](https://www.raspberrypi.com/documentation/computers/os.html#get_throttled).
The thermal/timing trend points to CPU/cooling headroom, with no demonstrated
physical-memory shortage. Model pointers, owner, cgroup and leases closed;
every regular output file was independently copied and hash/readback verified.
Evidence: `chunk52-threads2-hour-01-monitor-02`,
`chunk52-threads2-hour-01-review-01/SOAK_REVIEW.json`, and
`operation-post-soak-baseline-02/dispatch/RESULT.json`. Empty directories are
outside the regular-file mirror claim. There is no labeled quality result for
the repeated one-hour audio.

Candidate2 completed the same full file with component RTF 2.123295243 and first
output at 2.461766 s. Peak sampled RSS was 206,602,240 bytes and maximum simulated
input backlog 17.6954375 s. It is a complete bounded component run, but the
measured throughput is below the incoming audio rate. There is no ground-truth
or same-geometry numerical comparison claim. Exact review:
`candidate2-01-review-01/REVIEW.json`; model/cgroup closure and full mirror passed.

Official Low Latency produced an early result, but could not finish the matched
source within the admitted processing drain time. At its last logged graph,
native compute took 6,988.73 ms; allocation took0.52 ms, input copy0.18 ms and
output copy0.05 ms. Its 9-frame chunk corresponds to720 ms of source input, so
the mature graph cost was roughly9.7 times that source duration. Feature
extraction was approximately0.5 ms per small push. This is direct phase-timing
evidence that graph computation dominates; its early first output is not proof
of sustainable low latency. The process closed the model, cleared its pointers,
released leases and exited naturally with failure; all regular output files
were copied and verified. It is not counted as a complete functional run.

## RAM interpretation

Chunk52's maximum sampled `/proc` RSS was 190,349,312 bytes (about 181.5 MiB).
The separate `ru_maxrss` result was 188,710,912 bytes; these observations are
retained separately, rather than pretending sampled and kernel metrics match.
Minimum sampled system available RAM was 1,480,802,304 bytes (about 1.38 GiB).
The current process had a 768 MiB address-space limit and thread environment
variables set to one in a shared two-core/200% unit. The exact native graph
thread count is not established by those environment variables. The subsequent
pinned source audit reproduced retained metadata source SHA `679ce2e01202723e7f94233df362ad38751f5380882a6e0964db63270dac4726`,
which explicitly requests one graph thread. The selected A76 backend's actual
build flags use the pthread implementation, with no OpenMP flag. The upstream
checkout's helper argument4 does not describe that retained build. The immutable
benchmark envelope's `model_threads=1` still is not a measurement of active
workers. Subsequent instrumentation records task counts/affinities separately;
see [the exact source audit](README_NATIVE_OPTIMIZATION.md). Peak observed
temperature was 56.75°C.

For chunk52-threads2-01, maximum sampled RSS was190,808,064 bytes, cached PSS
184,850,432 bytes and virtual size361,807,872 bytes. Swap remained zero, minimum
available RAM was1,470,562,304 bytes and peak temperature59.5°C. Boundary task
counts can miss workers that exist only inside graph calls; near200% CPU on heavy
calls and the exact source request2 are recorded separately. These are measured
current2GB component results, not4GB/8GB benchmarks.

This component did not approach physical RAM exhaustion. A 4 GB or 8 GB device
would offer more capacity for the complete ASR/embedding/GUI pipeline and
possibly another resident model, but it is not expected to cure this single
diarizer's measured compute-per-audio-second deficit. That is an inference,
not a benchmark of larger devices. The OS availability floor, process address
space, RSS, shared pages, model residency, CPU demand and queue growth must be
reported separately. More installed RAM does not change an unchanged software
address-space ceiling.

The short combined and five-minute GUI measurements above include worker
memory and partial aggregate samples. A complete continuously observed live
unit peak, hour-long application growth and 4/8 GB concurrency benefits remain
unqualified. Telemetry records virtual size, peak virtual size, swap and cached
1 Hz PSS to distinguish physical pressure from the process envelope.

For compact3-02, maximum sampled RSS was 169,885,696 bytes, maximum cached PSS
164,120,576 bytes, and maximum sampled virtual size 344,391,680 bytes. Swap
remained zero and minimum sampled available system RAM was 1,500,643,328 bytes.
These component measurements support CPU/context work as the useful next
optimization target; they do not benchmark larger RAM devices. PSS/task samples
are cached at most 1 Hz with recorded ages. All observed boundary task counts
were one; samples at call boundaries can miss short-lived workers and are not a
continuous active-thread trace.

## Private receipts and preserved failures

Evidence root:
`G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003`.

* `chunk52-01`: missing experimental opt-in failed before model loading. Its
  actual process exited, leases released, cgroup emptied and all regular output
  files were copied/read back. No measurement credit.
* `chunk52-02-monitor-01` and `chunk52-02-review-01`: natural0, exact actual
  owner dead, cgroup empty, complete source membership/hash plus PC readback,
  all numerical rows compared.
* `candidate55-01-monitor-01` and `candidate55-01-review-01`: separate natural0,
  exact closure and complete regular-file mirror. No reused native run root.
* `chunk52-threads2-01-monitor-01` and `chunk52-threads2-01-review-01`: separate
  two-thread core; complete source/EOF, all values compared, model/pointers closed,
  exact owner/cgroup closure and full independent mirror.
* `official-low-01-monitor-01` and `official-low-01-review-01`: the incomplete
  prefix, exact native phase log and failed result remain intact. Native owner
  PID2583/start576157 is dead and its cgroup is empty.
* `compact3-02-monitor-01` and `compact3-02-review-01`: build02, complete matched
  source/EOF, model closed and native pointers empty; exact owner/cgroup closure
  and complete regular-file mirror. Geometry is `candidate_3_compact`; no labeled
  quality or same-geometry reference comparison was performed.

The mirror receipts cover every regular output file; empty directories are
explicitly excluded. Files, raw failures and old results remain immutable.

Official Very Low failed safely after 28.5 seconds of accepted source, with
prefix RTF 5.790805235 and first output at 0.816459 seconds. Model closure was
confirmed; the partial 2,832-frame output is not a full-file pass. Maximum sampled
RSS was 195,231,744 bytes and minimum available RAM 1,476,575,232 bytes, consistent
with a compute/backlog limit rather than physical RAM exhaustion in this run.
Exact evidence: `official-very-low-01-review-01/REVIEW.json` and its independent
monitor mirror. Official Ultra Low also failed safely at its processing drain
limit after 328,000 accepted samples (20.5 s), with 2,040 frames and no EOF.
Prefix RTF was 8.119146, first output 0.460199 s, maximum sampled RSS 193,511,424
bytes. Model/cgroup closure and the complete independent file mirror were
confirmed (`official-ultra-low-01-review-01/REVIEW.json`). All three official
settings therefore have actual bounded failure-prefix measurements on this CPU;
their early-response differences are separate from throughput and full-input
completion. None has a full-input numerical or labeled-quality pass. Any cohort must state
its exact source prefix and EOF/completion status rather than imply a full-file
or sustained pass.


## Build14 optional live300 with the explicit 60-second label window

Actual `optional-followup-02` completed all 4,800,000 samples in the primary, four-channel raw stream and continuous anonymous CurrentDelayed child. The child returned all 30,001 frames, matched the complete processed float32 hash, closed its model and exited0. Primary/source/child owners, routes, leases and the complete unit closed; all156 regular files /145,186,426 bytes were independently mirrored and rehashed. This is a bounded live300 functional/compute/closure result, not a sustained whole-application qualification.

The exact selection was Pyannote/TitaNet, continuous embeddings, retained presentation, optional D1, window60; policy was source300, load120, drain60, backlog30 and cleanup60 seconds. Maximum observed primary backlog was0.4999375s, label lag30.9799375s and primary drops0. Child compute-wall time was132.0036166s. The paced source-origin through required-consumer EOF was310.0341363s, including tail drain. Whole-cgroup CPU increased322.957342s during the explicit312.536701s resource-trace interval; this is neither a full-lifetime total nor a sum of two audio RTFs.

Sampled whole-unit RSS/PSS reached760,020,992 /700,768,256 bytes; minimum available RAM was1,178,828,800 bytes on actual MemTotal2,108,473,344. Child RSS high-water was171,606,016 bytes and recorded virtual peak287,916,032 bytes, below its unchanged805,306,368-byte AS guard. Owned swap was0 and maximum sampled temperature68.3C. Memory samples can miss peaks; physical, virtual, CPU and thermal limits remain distinct. No4/8GB measurement is claimed.

There were **zero optional-prefixed label-revision events and zero optional speaker-history observations**. Full child processing is not evidence that optional corrections improved labels. Primary labels and the separate functional Research07 late-label path must not be credited as optional corrections. The exact actual14 experimental admission is accepted in production16 through reviewed GUI-policy and path-only reuse. Its idle GUI verified the exact option and policy summaries with zero Start/model/capture; it is not a new model or quality measurement. Default capture and optional selection remain off.

Private measurement review SHA `8a82cd7b8c0bf113ce96fe0e02bb46d08d64abe4e5bd6e59af5c273df2a84430`; accepted actual14 admission SHA `dba6e37b531bf73076174ec929047866cb1aa5152eaae767680ad09df53cf366`. Actual Followup01/window30 remains a failed child-EOF run with successful primary fallback. The legacy admission field `primary_matched_baseline_seconds` stores actual primary08 saved44.84308986s with explicit different-source/duration metadata; it is checked only for a finite positive value and is not a matched-live speed comparison. The normal receipt makes no quality or sustained-performance claim.

## Production16 idle GUI and evidence reuse

Production16 was staged, activated and consolidated to one launcher. The actual
`production-idle-01` check enabled the experimental Pyannote/TitaNet/live option
at revision window60. Checked, it displayed source300/load120/drain60/backlog30/
cleanup60; unchecked, it restored ordinary300/120/120/120/60. All267 Start-disabled
checks passed with zero Start invocations, worker construction, models or capture.
Ten480x800 geometry samples were stable, normal Exit passed, and the exact owner,
cgroup and leases closed with the full37-file mirror. These are actual GUI and
closure observations, not physical-touch or new model-performance evidence.

The package uses content
`97709f98f34abb13b8e91658ed6822ff9e085f5b515ebaa45c686df7a64d32c3`
and manifest
`a88217b7dcdf0360309b4bea28baa376e6a55d64090fe64e2ba3cfeaa2cb2a73`.
Its accepted optional receipt preserves every actual14 measurement, policy, owner
and selected asset while recording the reviewed GUI14-to15 and path15-to16 reuse.
Evidence: `production-idle-01-monitor-01/closed-output/OPTIONAL_POLICY_GUI_CHECK.json`;
full mirror manifest SHA256
`ea89fca0ee6cf3a1b7a5a388a453658ca7acda348ae25723f0bb0fab23433615`.
