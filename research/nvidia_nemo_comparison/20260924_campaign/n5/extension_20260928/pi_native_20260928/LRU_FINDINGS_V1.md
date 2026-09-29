# Native D1 executable-graph cache repair

The earlier streaming recipe failed while flushing the end of the saved file: it produced 4,368 of the required 4,470 frames, then an 8 MiB metadata allocation failed under the 768 MiB virtual-address limit. The runtime had accumulated 42 executable graphs in a cache allowing 48 entries.

A fresh D1-only build changes that executable-graph cache capacity from 48 to 8. It preserves the existing eviction and placement-generation checks, model weights, numerical kernels, speaker history, FIFO history and recipe. The scheduler remains at the separately qualified 2,048-node capacity with its original 95% guard; metadata arenas retain the qualified 8 MiB bounds. These limits have not been qualified for Nemotron ASR.

The new library SHA256 is `fa8ecbb66124b62fced485d45dd2ec6018634a35d39dbc143e221b9f7230b622`. The build reader independently verified the one-line source change, retained input hashes and exact process closure. See README_D1_LRU_V1.md for build instructions and README_D1_LRU_CHECKS_V1.md for execution and review instructions.

## Reviewed results

All tests use the original 44.6954375-second saved source, one native thread, CPUs 2/3, GPU off and the unchanged hard 768 MiB virtual limit. The original rc5 app stays active. These are conditional native functional/resource measurements, not uncontended benchmarks or speech-quality scores.

| Recipe / CPU | First / repeat processing time | First / repeat RTF | Peak process RSS | Independent outcome |
|---|---:|---:|---:|---|
| Streaming 13-frame chunk, generic | 215.076 / 215.014 s | 4.812 / 4.811 | 192.59 MiB | Full source, repeat, reset, EOF and closure pass |
| Streaming 13-frame chunk, A76 | 162.412 / 162.677 s | 3.634 / 3.640 | 212.72 MiB | Same gates; exact generic and repeat arrays |
| Delayed 264-frame chunk, A76 | 18.128 / 18.108 s | 0.406 / 0.405 | 173.08 MiB | Same gates; exact original delayed generic arrays |

All three runs retain every one of the 715,127 samples and produce 4,470 × 8 finite probabilities. The declared same-geometry tolerance remains 1e-5; observed repeat and generic/A76 differences are zero. The delayed regression also preserves its earlier complete reference after the cache change. The old streaming run has no complete reference because it aborted, so this does **not** establish complete old-cache/new-cache array parity for that recipe.

The generic streaming log contains 86 graph-build observations over both sessions, never more than eight resident cache entries and never more than 870 graph nodes. A live repeat observation showed 356.20 MiB virtual size. This observation is not a comparison of whole-application memory. Frequent graph reconstruction can have a cost; a smaller cache is a correctness/resource repair, not an automatic throughput improvement.

The A76 streaming time is approximately 24.5% below the generic time for the same repaired recipe. It still cannot keep pace with continuous input on this test: RTF 3.64 means roughly 3.64 seconds of work for each second of audio. The delayed recipe's RTF below one has a different latency tradeoff. Its previously reviewed actual 1x producer test returned first probabilities after about 25.5 seconds and drained for about 11.4 seconds after source EOF. Unpaced first-output measurements must not be presented as live latency.

## Remaining scope

This closes the tested streaming component's EOF allocation failure. It does not clear B01 application startup, qualify an integrated ready-to-run mode, establish sustained dense-conversation performance, or validate speaker accuracy. ReDimNet identity, independent captions, UI control and complete shutdown remain application gates. The pending request for a short 1 GiB application virtual-address trial has not been approved or executed.

One intermediate 52-frame center-chunk candidate is prepared separately to investigate the workload/label-delay tradeoff. Different recipes may change diarization behavior; each needs its own generic/A76 reference and frozen real-life validation. No audio is skipped in these comparisons.
