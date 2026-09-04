# H2 conservative 2 GiB memory budget

## Status

This is a design budget for Raspberry Pi OS/ARM64, not measured Raspberry Pi
evidence. Desktop RAM/RTF cannot prove the 2 GiB target fits. The candidate
remains `PORT_REQUIRES_WORK` until serial hardware measurement passes.

## Nominal allocation

| Area | MiB |
|---|---:|
| OS and background services | 384 |
| Sherpa Giga ASR graph and working memory | 620 |
| Pyannote segmentation ONNX and working memory | 160 |
| one shared ReDimNet2 ONNX session | 240 |
| Python control, optional GUI, telemetry | 180 |
| bounded audio queues and session cache | 128 |
| safety headroom | 336 |
| **Total** | **2048** |

The systemd candidate uses `MemoryHigh=1650M` and `MemoryMax=1850M`. These are
guardrails, not evidence. An out-of-memory restart is a failed qualification,
not acceptable steady-state behavior.

## Runtime rules

- run `H2_PORTABLE_ONNX_FP32`; do not co-load native Torch/Pyannote;
- keep the frozen R2 one-shared-ReDim execution strategy when that final
  selected snapshot is used;
- keep frame, model-request, event, and UI queues bounded;
- retain only bounded session embeddings/transcript history and expire volatile
  speaker memory at session end;
- keep model graphs outside result ZIPs and exclude large caches from compact
  exports;
- run accuracy jobs separately from standardized serial resource measurement;
- do not infer power consumption from desktop telemetry.

## Arduino UNO Q 2 GB interpretation

The UNO Q 2 GB / 16 GB eMMC variant is not presumed to satisfy this budget.
For the complete evaluated native pipeline its pre-hardware classification is
`PLATFORM_BLOCKER`. Only the lean `H2_PORTABLE_ONNX_FP32` service remains a
`PORT_REQUIRES_WORK` experiment, and only if the final serial desktop evidence
does not already reject the 2 GiB envelope.

That experiment must be headless, use one shared ReDimNet worker, avoid native
Torch and duplicate model processes, bound every queue and log, and demonstrate
startup plus sustained operation without swap. The 16 GB eMMC image must retain
measured room for Debian, exact wheels, checksum-bound model assets, logs, and a
safe update/rollback reserve. Evaluation datasets and reusable research caches
are reproducibility references and are not copied to the device.

The UNO Q Cortex-A53 CPU is also an independent real-time risk; a memory fit
does not imply that deadlines are met. No Qualcomm accelerator relief is
assumed for the Debian target. The final hardware assessment binds measured
serial RSS, RTF, model bytes, and run-cache bytes, but only an exact-board run
can change the classification.

## Hardware acceptance procedure

1. Boot the exact 64-bit image on the exact 2 GiB board and record kernel,
   firmware, package, wheel, model, and code hashes.
2. Start from a cold boot; measure OS baseline RSS and available memory.
3. Measure startup, warmup, and steady-state component/total RSS one pipeline at
   a time using both process-tree RSS and cgroup memory.
4. Exercise silence, speech, overlap, queue pressure, 30–60 minute streaming,
   repeated sessions, worker restart, and device reconnect.
5. Record RTF, CPU, peak RSS, dropped frames, deadline misses, swap, OOM events,
   temperature, throttling, and drift.
6. Require no OOM, no unbounded growth, no dropped audio under supported load,
   and sufficient headroom for the selected audio/UI/service configuration.
7. Repeat numerical and semantic parity; resource success cannot substitute for
   correct transcript, speaker, identity, and event behavior.

Commands for installation, service launch, audio diagnostics, and asset
validation are in `deployment/h2_arm64/README.md` and
`docs/full_pipeline/H2_ARM64_LINUX_HANDOFF.md`.
