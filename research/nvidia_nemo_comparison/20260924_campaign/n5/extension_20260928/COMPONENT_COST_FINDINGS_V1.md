# Complete targeted Windows call-cost measurements

Both shortlisted Windows combinations passed the new cumulative accounting checks and retained exact full-file caption, source-time and native-activity parity with their respective reviewed references. The measurement gap from rotating journals is repaired in a fresh derivative. Nemotron 3 diarization remains the dominant processing cost on this saved-file sample.

Each run used the same 715,127 samples (44.6954375 seconds), original 1x pacing, CPUs4/14 total, one native thread per model and GPU off. Every sample ran through ASR and D1; shadow gates proposed skips but applied none. These are single Windows observations, with no native CM5 or independent real-world qualification.

| Measured boundary | B01: Sherpa + D1 + ReDimNet | B02: Nemotron English ASR + D1 + ReDimNet |
| --- | ---: | ---: |
| ASR accept/reset/finish calls | 3.021 s | 27.221 s |
| ASR call time / source duration | 0.068 | 0.609 |
| D1 push/finish calls | 82.393 s | 84.922 s |
| D1 call time / source duration | 1.843 | 1.900 |
| ReDimNet embedding calls | 0.566 s | 0.601 s |
| ReDimNet call time / source duration | 0.013 | 0.013 |
| ASR/E0 acquisition and stream setup | 1.996 s | 1.104 s |
| D1 acquisition | 0.148 s | 0.140 s |
| Observed session elapsed, including setup/pacing/drain | 91.706 s | 92.541 s |

RTF here is accumulated wall time at the named model-call boundaries divided by original audio duration. Adapter work and scheduling delays during those calls are included. Source waiting, event/UI publication, counter bookkeeping and other orchestration are outside them. Calling-thread CPU is retained separately in the JSON and excludes native worker CPU. Concurrent lane times must not be summed as session elapsed time. Setup measurements are not controlled cold disk-load benchmarks; operating-system caches were not cleared.

## What the differences mean

Nemotron ASR consumed about 9.01 times Sherpa's ASR call time on this file. Both ASR totals were below the file duration, while D1 alone needed about 1.84–1.90 seconds of call time per second of source. The nearly equal session elapsed times are consistent with the shared D1 lane dominating completion while ASR proceeds independently. The two D1 timings are single observations; their difference does not isolate a causal effect of ASR choice or establish a repeatable throughput difference.

ReDimNet's twenty calls took about six-tenths of a second per run, less than 1% of D1's call time. Removing this encoder would therefore save little of the measured work on this sample. Keeping E0 remains useful for model-compatible persistent identity, while D1 supplies anonymous activity tracks. Actual personal naming accuracy was not evaluated by these runs; their galleries were empty. On-demand embeddings and anonymous bypass remain useful controlled research options, with this result lowering their priority as a solution to D1 throughput.

The complete D1 activity fingerprint is identical across the two compositions, and both produced 4,470 activity frames. Each composition's captions and source timestamps matched its own earlier reference. This validates the instrumentation's preserved outputs; it is not a new WER/DER measurement or evidence that A0 and A2 transcriptions are identical.

The active native recipe is `low_latency`: nine chunk frames and four right-context frames, for a 1.04-second input buffer. It is already the largest of the three profiles currently exposed by this application adapter. Merely changing host push sizes does not change that internal recipe. Any larger supported delayed/offline recipe needs a new explicit adapter/configuration, state/EOF/timestamp validation, measured label delay and accuracy checks before it can be compared as a candidate.

The source is a retained synthetic-scene diagnostic and may contain substantially more silence than real conversation. No silence was removed. Existing shadow skip percentages remain conditional proposals, not speed gains or speech-loss validation. These results do not establish sustained real-time diarization, dense-speech performance, native Pi throughput, end-to-end caption/label latency or thermal behavior. The work still needed includes matched integrated panels, backlog/queue and drain measurements, endurance, and frozen held-out real conversations after the device is connected and the user is ready.

## Accounting and acceptance evidence

The eight fixed counters are persisted in the atomic session summary independently of rotating journals. A0 counted 701 D1 pushes, including 640 with no output frames; A2 counted 657, including 596 without frames. Both had 61 frame-producing pushes plus one finish. Host push grouping varies with arrival/scheduling; all 715,127 input samples and 4,470 emitted frames reconciled. Each ASR received 447 configured input quanta and one finish. E0 submitted twenty overlapping windows totalling 408,000 samples in both runs; that is window workload, not unique source duration. All calls completed without error or in-flight work.

Three model-free counter tests passed. Both actual runs passed independent review of counter conservation, persisted totals, full-file parity, Tk render/save/reopen/delete, unchanged inference/drain gates and exact process/job/thread/lock closure. No personal enrollment, capture, playback, downloads or target access occurred. The V1 launcher preflight failed on a README dependency path before numerical dispatch; its evidence remains preserved, and V2 repaired only the launcher binding.

`COST_CHECK_SUMMARY_V1.json` contains exact values and bindings to both private independent reviews, per-run COSTS.json and session summaries. The derivative receipt SHA256 is `98c63f2d56d2c91e84b42dc72a4ed08bb04790fdb1a483272e0c12bbc07f9f02`. It preserves the reviewed `ui-error-v1` parent, changes four source files and adds the bounded counter module plus README. Run instructions are in README_COMPONENT_COSTS_V1.md and README_COST_RUN_V2.md; the unchanged numerical protocol is documented in README_COST_RUN_V1.md. Full N4/N5 acceptance and native CM5 remain incomplete.
