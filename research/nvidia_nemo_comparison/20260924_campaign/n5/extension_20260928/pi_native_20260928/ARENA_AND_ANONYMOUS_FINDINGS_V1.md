# Native allocator and anonymous-mode investigation

This follow-up preserves the pending1GiB cap decision and keeps the hard768MiB virtual-address limit. No new recording, playback, ASR/WER scoring, enrollment, downloads or original-install changes occurred. The original rc5 app remained active, so resource timings are conditional.

## ReDimNet CPU arena

A fresh standalone derivative disabled only ONNX Runtime's CPU memory arena, retaining graph optimization, memory-pattern defaults, threads and the same0.5/2/12-second original saved prefixes. All six normalized192-dimensional outputs equal the arena-enabled reference exactly; repeat/input/session/process closure checks passed. This is numerical/function evidence, not identity accuracy.

| Observation | Arena enabled | Arena disabled |
|---|---:|---:|
| Peak process RSS across all lengths |323.922MiB|341.719MiB|
| First2-second inference |153.75ms|162.11ms|
| First12-second inference |1.160s|1.216s|
| Repeat12-second inference |1.150s|1.149s|

The new reader observed some allocations released: after the12-second repeat, virtual size was166.38MiB and RSS91.44MiB. However, peak RSS increased and the old run lacks equivalent per-stage memory snapshots. No general memory or speed improvement is claimed. [ONNX Runtime's documented CPU arena option](https://onnxruntime.ai/docs/api/python/api_summary) provides a mechanism to test, not a promised gain.

The combined B01 derivative disabled the arena only for N2 ReDimNet. All other model/session defaults stayed unchanged and the composition policy was explicitly rebound. It still aborted on a39.45MB native D1 compute allocation. Exact owner is closed, with no RESULT or clean application finalization. This does not fix the combined memory blocker. See README_ORT_E0_NOARENA_V1.md and README_B01_E0_NOARENA_V1.md.

## Explicit anonymous composition B05

A fresh source derivative reapplies the previously tested anonymous-mode bypass to the current shared-controller source: keep one ordered D1 stream and Sherpa/PnC, avoid E0 loading/calls only in anonymous conversation without research observers. Newer controller, journal and failed-start cleanup remain intact. Catalog label and manifest explicitly say no personal naming. Other named/research modes retain their encoder behavior; they remain unqualified on this Pi. This is a separate control, not automatic fallback from B01.

The original1x-paced12-second constructed prefix passes independently reviewed application passage and closure:

- 192000samples each through source, ASR and D1; zero dropped audio, zero encoder loads/calls.
- 1201native probability frames in one EOF window, finite eight-channel values, plus actual captions and learned punctuation. One explicit terminal-period heuristic is recorded; zero punctuation inference failures.
- First text5.646seconds after source start; this includes the source's initial quiet interval and is not per-word latency. First D1 output14.340seconds, after EOF; delayed labels are expected for this shorter-than-chunk input.
- Source EOF to completed session2.493seconds; ASR accept work1.570s, ASR finish0.089s, D1 push work0.233s and finish2.336s. Concurrent call times must not be summed as elapsed time.
- PeakRSS476.719MiB; sampled peak virtual747.328MiB, close to the768MiB limit. All application/consumer/archive queues and handles closed; natural process exit was zero and exact owner closed.

The short run records actual frame count and passage, without claiming full-file probability parity. It does not qualify personal names, GUI, Stop/restart, release packaging, dense long conversations or real-life accuracy. Short success must not hide later full-file failures. See README_B05_ANONYMOUS_V1.md and README_B05_REVIEW_V1.md.

## Full44.6954375-second application result

The full original1x-paced file also passes native functional passage and natural closure. All715127samples reach ASR and D1, with no skipped audio or encoder calls. All4470x8 probabilities across three updates match the standalone delayed reference exactly (unchanged1e-5 gate). Actual caption output and learned punctuation are present; two explicitly recorded terminal punctuation heuristics, zero inference failures. Application, consumer, archive and exact process closure pass independently.

| Measurement | Observed full-file value |
|---|---:|
| First text after original source start |5.644s (includes initial source silence)|
| First D1 probability output |25.477s|
| Source EOF to completed session |11.612s|
| D1 push + finish work |18.877s (workRTF0.422)|
| ASR accept + finish work |6.117s (workRTF0.137)|
| Peak process RSS |499.453MiB|
| Sampled process peak virtual size |767.656MiB|
| Virtual-limit headroom at that peak |0.344MiB|

Paced source plus session drain is56.308s, not a56-second neural inference cost. Concurrent model-call times are not additive pipeline elapsed time. The extremely small virtual headroom is a practical blocker to calling this robust: Stop/restart, additional contexts, GUI, longer conversations and current app contention can change memory demand. No30/60minute stability, complete release, personal naming or independent speech accuracy is established. D1 is intentionally delayed; immediate text is separate from speaker evidence. This is the first scoped native anonymous combined passage evidence, not N4/N5 completion.

Next: qualify early Stop/drain and full-file restart on this exact anonymous source; investigate remaining virtual reservations before exposing a ready-to-run GUI mode. Preserve B01 retained-E0 as a separate failing candidate. Its short1GiB virtual-cap question remains unanswered, and no higher cap was used. Further unchanged allocator failures should not be repeated. All49 owned target identities are closed at06:01UTC, original rc5/current and application identities unchanged. Private NATIVE_CLOSURE_V7/NATIVE_RESOURCES_V7 record543119776combined bytes of1GiB, target54.55C/throttle0x0. Swap counters47in/26194out are global, not per-job attribution.

Reproduction/review: README_B05_ANONYMOUS_FULL_V1.md and README_B05_REVIEW_V1.md. Every previous failed allocation and immutable source remains preserved.
