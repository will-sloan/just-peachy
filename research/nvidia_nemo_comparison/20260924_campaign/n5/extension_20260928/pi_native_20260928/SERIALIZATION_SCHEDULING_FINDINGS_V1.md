# Native serialization and scheduling diagnostic

September30 2026. Independent review: `PASS_NATIVE_RETAINED_PACKET_EXACT_TIMING_DIAGNOSTIC_ONLY`, private `serialization-probe-v1-evidence/REVIEW.json`. No microphone, model, playback or GUI ran. The installed app and bound research sources were unchanged.

The actual application engine writer and archive writer replayed the first retained 2112-by-8 probability packet three times per variant. Both journals reconstructed every field exactly. Repetition is diagnostic load, not new chronological audio. The original path serializes a packet at the producer and again in the journal/archive consumers.

| Phase | Largest Python timing-thread interval | Largest separate-process interval | Cgroup throttle events | Phase elapsed |
|---|---:|---:|---:|---:|
| Idle | 1.08ms | 1.64ms | 0 | 1s |
| Original writers | 41.25ms | 6.34ms | 0 | 515.61ms |
| Unintegrated iterencode candidate | 30.46ms | 6.72ms | 0 | 639.89ms |

Both timing probes targeted1ms intervals. Phase elapsed includes three50ms pauses and closure; it is not pure serialization time. Original cgroup CPU work was319,954us versus442,608us for the candidate. Original producer serialization was15.3–19.9ms per packet; candidate26.5–27.3ms. The candidate reduced the observed maximum thread delay but increased total work. It is not accepted as a live fix.

The difference between same-process and separate-process timing is consistent with process-local contention, but these probes do not directly identify GIL ownership, scheduling cause, or the cause of the earlier live overflow. No replay interval exceeded90ms and no cgroup CPU throttling occurred in this short diagnostic. This does not establish that the original live capture had no throttling. Baseline rc5 remained active; probe overhead and concurrent activity limit timing comparisons.

The whole protocol took2.788s, peakRSS50.5625MiB. Both writer queues drained and both timing probes closed naturally. The actual service envelope retained768MiB hard virtual memory,1MiB stacks,CPU2/3,total200%,Tasks64 and300s. Exact main/gate/probe identities closed; no model or stream remained active.

Next: prepare a separate-process capture/source-buffer candidate or remove redundant packet encoding in a fresh derivative, then check bounded IPC, exact source offsets, backpressure/fault propagation, Stop/drain and restoration before a changed quiet trial. This result does not justify repeating the unchanged failed capture or treating480 rejected callback frames as upstream loss.

Execution and independent-reader commands, inputs and outputs: [protocol README](README_SERIALIZATION_PROBE_V1.md), [reader README](README_REVIEW_SERIALIZATION_PROBE_V1.md). Raw timing traces, source packet and journals remain private.
