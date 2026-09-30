# ARM confirms the alternate D1 projection mismatch

September30 01:49UTC. Independent result: **REVIEWED_NATIVE_PROJECTION_MISMATCH_ONLY**. The Pi ran the compact FP32 preencoder graph on the four retained natural feature chunks, each twice. Every ARM projection output is exactly equal to the host ONNX output; stack/padding/lengths and resident repeats are exact. The original PyTorch discrepancy is therefore reproduced on ARM. This rules out switching to ARM as a repair for these cases, not every possible downstream cause.

| Feature case | Frames | Pi versus original PyTorch max absolute error | Pi versus host ORT |
|---|---:|---:|---:|
| Tail | 8 | 0.0001639128 | 0 |
| First chunk | 2120 | 0.0002336502 | 0 |
| Middle chunk | 2128 | 0.0002346039 | 0 |
| Final chunk | 253 | 0.0001398325 | 0 |

All four still fail the unchanged0.00001 state limit. The prior full probability limit also remains0.00001. Exit0 means the diagnostic completed and preserved its observations; no full waveform, cache update, runtime repair, quality or speedup is accepted. No microphone, ASR, full model, UI or playback ran. The original graph/weights and prior failures are unchanged.

CPU-only ORT1.29 used BASIC optimization, sequential execution, one thread and the same enabled arena as the host diagnostic. Graph load0.0447s, protocol0.3178s, kernel peakRSS68.578MiB. Individual projections were0.36–9.96ms; those are component costs, not audio RTF. The active original app makes timings conditional. Actual live systemd properties confirm768MiB hard virtual/1MiB stack,CPU2/3,total200%,Tasks64,300s. Both owned processes closed naturally0; no memory/log/output stop fired. SampledRSS missed the kernel peak, so the kernel value is reported.

The2.1MB graph and exact fixtures were staged once. Target23files total20,017,999bytes fit32MiB; their verified host backup plus receipts and target were40,040,479bytes under64MiB combined reservation. No400MB graph copy/export or checkpoint extraction. Backup originals remain intact; raw features and vectors stay private.

ClosureV89 confirms197Pi and48isolatedhost owners closed, baseline app/config/install unchanged, capture closed and both leases free. Combined campaign output4,413,577,640/5GiB; fixed32GBPi available17,873,743,872bytes (about16.65GiB), availableRAM1,590,132,736bytes. Temperature52.9C, throttle0x0. Global swap3062in/35519out at16KiB pages is context only.

Next prioritize actual isolated-source/controller startup and sequential-ASR GUI integration, while preparing one evidence-based accumulation-order experiment using these retained arrays. Do not re-export the full graph, rerun unchanged cases or relax numerical gates. The separate passing frontend/state/constructed-graph cases remain scoped; N4/N5 and a field release remain incomplete.

Run instructions: [native diagnostic](README_D1_PROJECTION_NATIVE_V1.md), [independent reader and backup](README_REVIEW_D1_PROJECTION_NATIVE_V1.md). Private receipts are d1-projection-native-v1-evidence/REVIEW.json and BACKUP.json. Prior host diagnosis is [preserved here](D1_PROJECTION_FINDINGS_V1.md).
