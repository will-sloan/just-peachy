# Native alternate projection kernel: mismatch remains

September30 03:09UTC. A fresh bounded Pi experiment used the existing NumPy2.2.6 FP32 matrix kernel for only the1024-to-512 preencoder projection, with exact original weights and four retained natural feature stacks. Build configuration reports scipy-openblas0.3.29. No installed sources, references, main graph or application mode changed; no checkpoint extraction or full-model rerun occurred.

| Retained case | Error versus original PyTorch | Error versus retained ORT | 1e-5 gate |
|---|---:|---:|---|
| 8-frame tail | 0.000076294 | 0.000147939 | Fail |
| 2120-frame first | 0.000236511 | 0.000213623 | Fail |
| 2128-frame middle | 0.000198841 | 0.000198364 | Fail |
| 253-frame final | 0.000146866 | 0.000099540 | Fail |

All repeats are exact, inputs/weights unchanged, and stack/length/output-shape checks pass. Different projection kernels produce different finite FP32 results; NumPy does not uniformly improve the mismatch and repairs none of the four cases. The original probability and state1e-5 gates are unchanged. This is independently reviewed negative evidence, not a qualified alternate runtime. No full-waveform parity or speedup follows from projection-only timings.

Numerical protocol0.187s, kernel protocol0.114s including output work; recorded multiplication calls0.000212–0.011369s. Peak RSS40.516MiB, sampled Threads1. Actual768MiB AS/1MiB stack,CPU2/3/200%,Tasks64,300s/10s Stop envelope, naturalexit0, exact owners and unchanged baseline/leases/capture closure pass. Exit0 means observation collection completed; numerical acceptance failed. Private21-file/9,070,909byte target backup verified, combined18,146,615bytes under32MiB admission.

ClosureV104: all222Pi/48isolatedhost owners closed, original app/config/install unchanged, captureclosed, bothleasesfree. Combined4,499,578,146/5GiB; actual fixed32GBPi free17,833,279,488bytes, RAM1,553,317,888bytes,52.35C/throttle0x0. No research compute remains active.

Do not substitute this candidate, rerun it unchanged or launch a kernel sweep. Any additional arithmetic experiment needs a distinct supported hypothesis. Next delivery priority is the actual sequential Sherpa-primary/A2-refinement controller/GUI cancel/failure/archive path. V50's complete B01 isolated saved-input pass remains intact; V48's physical DSP readback blocker is separate. Full alternate D1, real live B01, visible GUI/endurance and field-release acceptance remain open.

Run and reader commands, inputs, outputs and limits: README_D1_PROJECTION_NUMPY_V1.md. Private evidence: local/n5/research-extension-20260928/pi-native-20260928/d1-projection-numpy-v1-evidence. Preserve original kernel, all failed candidates and reference arrays.
