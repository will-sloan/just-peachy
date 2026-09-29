# One intermediate native CM5 diarizer recipe

The experimental `native_cm5_chunk52` profile changes the streaming center chunk from 13 to 52 coarse frames (1.04 to 4.16 seconds). The complete recipe is 52/1/0/80/264/40 for chunk/right/left/FIFO/speaker-cache/refresh, on the 80 ms grid. Context, speaker history, weights and refresh settings remain explicit. This is an inspected and executed candidate, not an official named NVIDIA preset or a quality-qualified replacement.

The private adapter is native-profiles-v3, SHA256 `6237997f05b45baf244c520e84d2a27a364906b24e0f02907e47cdcb31f435a5`. It preserves previous profiles and the delayed FIFO-zero binding repair. It uses the separately reviewed eight-entry executable-graph cache, not a shorter speaker-history cache. See README_CM5_CHUNK52_V1.md and README_CM5_CHUNK52_PACED_V1.md for purpose, inputs, outputs and exact commands.

## Full-file and repeat checks

| Kernel | First / repeat processing time | First / repeat RTF | Peak process RSS |
|---|---:|---:|---:|
| Generic | 64.091 / 64.154 s | 1.434 / 1.435 | 188.09 MiB |
| Cortex-A76, preserved integer lane grouping | 48.501 / 48.513 s | 1.085 / 1.085 | 187.09 MiB |

Both readers independently verify all 715,127 input samples and 4,470 × 8 finite output probabilities, actual C-ABI geometry, continuous source/frame mapping, full resident repeat, reset/empty input, EOF, rejection after finish and model/process closure. Repeat and same-geometry generic/A76 arrays match exactly under the unchanged 1e-5 gate. Different chunk recipes are not expected to produce identical speaker probabilities. No new ASR, WER or diarization accuracy score was calculated.

## Why the average is not a sustained-speed promise

The A76 first-file trace starts at about 0.79 seconds of model work for the first 4.16-second output block. As retained context fills, later full blocks at source times 33.4, 37.6 and 41.7 seconds each cost about 6.47 seconds. That is approximately **1.56 seconds of work per second of newly emitted audio** in those three blocks, despite the whole-file average RTF of 1.09. This is evidence that the short-file average benefits from startup with less context. It does not prove the later cost remains constant indefinitely.

For comparison, the repaired 13-frame recipe's late full blocks cost roughly five to six seconds for 1.04 seconds of new output. The delayed 264-frame recipe's second full block costs about nine seconds for 21.12 seconds of new output. Chunking changes how often expensive retained context is processed; it trades output delay against work. It is not silence removal: every sample passes through all these runs.

These conditional measurements use the original 44.6954375-second saved source, one native model thread, CPUs 2/3, GPU off and hard 768 MiB virtual space while the original rc5 app remains active. They are not uncontended matched capacity measurements, real speech quality, named-speaker latency or full application acceptance. Do not describe unpaced first emission (about 0.82 seconds) as live speaker latency; it required 4.3 seconds of source audio.

## Independently reviewed original-1x pacing

An independent producer supplies each 100 ms source interval at its original time. One ordered A76 D1 worker consumes it from a queue bounded to 200 entries. Overflow fails explicitly; audio is never silently dropped. Both full-file sessions passed exact reference/repeat arrays, complete source/frame coverage, EOF and producer/model/process closure.

| Observed quantity | First session | Resident repeat |
|---|---:|---:|
| First probability output after source start | 5.093 s | 5.091 s |
| Actual model-call work | 48.510 s | 48.472 s |
| Maximum queue wait | 13.479 s | 13.464 s |
| Maximum queue depth | 88 intervals | 88 intervals |
| Drain after original source EOF | 16.661 s | 16.647 s |
| Total paced elapsed time | 61.357 s | 61.342 s |
| Maximum source scheduling lateness | 3.445 ms | 2.667 ms |

Peak process RSS is 188.344 MiB. Maximum queue depth counts intervals; it is not the same measurement as maximum queue residence time. Total elapsed divided by source length is about 1.373, while model-call work divided by source length is about 1.085. The former includes original pacing and final drainage. Neither is a speech-accuracy score.

Relative to the separately reviewed delayed recipe, this candidate emits first probabilities much earlier (about 5.09 versus 25.5 seconds) but has more work and a larger measured final drain (about 16.66 versus 11.4 seconds). These are different whole recipes with potentially different speaker behavior. This one short saved file is insufficient to promise long-conversation stability. It demonstrates the workload/latency tradeoff and why captions must remain independent.

The candidate stays available for later frozen real-life evaluation. Longer admitted tests must report context growth and backlog, including dense speech and natural pauses. An integrated caption-first mode must keep captions independent and speaker labels Pending/Unknown until evidence is available. B01 startup and full N4/N5 acceptance remain open.
