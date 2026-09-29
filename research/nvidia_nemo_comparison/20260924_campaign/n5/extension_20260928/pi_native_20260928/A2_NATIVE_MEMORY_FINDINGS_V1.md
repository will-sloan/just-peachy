# Native A2 memory findings, September 29

Nemotron English ASR now has two actual CM5 ABI/creation attempts. Neither opened a usable stream or processed audio. Both failed cleanly, with independently checked source/asset bindings, live systemd properties and owner closure.

| Trial | Hard virtual cap | Required available RAM | Outcome |
|---|---:|---:|---|
| a2-native-probe-v1 | 1024 MiB | 1280 MiB | Recognizer created; stream buffer allocation failed |
| a2-native-probe-v2 | 1280 MiB | 1408 MiB | Same failure; memory watchdog did not fire |

Both requested 930,624,512 bytes (887.51 MiB) for a CPU backend buffer. Recognizer creation took 0.589/0.587 seconds; neither is ASR inference speed. Each result records zero completed sessions, explicit recognizer destruction and natural exit1. Kernel peak RSS was83.92MiB in both because the large allocation was rejected. This cannot establish working RSS or justify integrated fit. Sampled virtual peaks may miss brief allocations.

V2's isolated cap change used the user's resource-adjustment authority. B01/B05 envelopes and original rc5/OS/swap/configuration remained unchanged. Its supervisor stops the owned service below192MiB available RAM or above1152MiB sampled modelRSS; sampling is not hard RSS enforcement. Both live unit receipts verify CPU2/3, quota200%, Tasks64,1MiB stacks,180s and their exact address-space limits. Unlike the earlier asset transfer, these receipts were retained before unit collection. Original app concurrency makes future timings conditional.

## Runtime and next repair

The candidate reuses immutable scheduler-native-v1 with8192nodes and the95% guard, original generic CPU kernels,64MiB metadata defaults and original executable cache. It does **not** use D1's2048/2MiB/LRU1 settings. No A2 graph was qualified. Session source calls graph compute with one thread; BLAS/OMP settings are also1.

Read-only source inspection found separate model/state TensorContainers and64MiB default temporary and per-buffer metadata reservations. The recognizer initially reports9.37MiB model-container storage; the lazy stream allocation then fails. This motivates reservation inspection but does not identify the entire887.51MiB buffer or prove a safe reduction. Do not attribute it all to metadata, weights, cache or duplicated file mapping.

Next inspect A2 tensor/reservation sizes and prepare a fresh conservative A2 metadata candidate, retaining allocation assertions and scheduler guards. Preserve original source/build hashes; qualify load, graph size, full-source/repeat/reset/forced-endpoint/EOF before B02 integration. Do not repeat unchanged cap trials or remove guards. ONNX Sortformer still needs its feature/cache/FIFO driver and same-precision checks; quiet PCM/logging and N5 GUI/rollback remain priorities.

## Evidence and reproduction

Private reviews: a2-native-probe-v1-evidence/REVIEW.json and a2-native-probe-v2-evidence/REVIEW.json. Each derivative retains about7.73MiB, below its32MiB admission; weights were reused. ClosureV36 confirms126research owners closed, no active research units, captureclosed, leasesfree and baselineunchanged. Combined output1,762,057,872/3,221,225,472bytes. No new capture, full-source, speech quality, endurance or release acceptance.

Purpose, inputs, outputs and PowerShell/CMD/Anaconda commands: [probe V1](README_A2_NATIVE_PROBE_V1.md), [probe V2](README_A2_NATIVE_PROBE_V2.md), [independent review](README_REVIEW_A2_NATIVE_PROBE_V1.md). Bound probes/admissions remain immutable. Future numerical work needs a new version and fresh admission.
