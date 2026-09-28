# Existing ARM optimization baseline

The cached Nemotron artifacts are already quantized. The preserved ARM64 build recipe uses generic `armv8-a`, disables host-native tuning, CUDA, Vulkan, OpenMP and KleidiAI, and changes the runtime's graph-compute helper to one thread. This is a conservative build baseline, not evidence of optimal CM5 execution. The original build receipt and later functional checks keep their original scopes.

The September 28 audit verified the pinned ggml source archive and these three content-addressed model hashes, then parsed their GGUF v3 headers without loading tensor data:

| Component | File bytes | MiB on disk | Tensors | Q8_0 tensors | Other tensor types |
|---|---:|---:|---:|---:|---|
| D1 Nemotron 3 diarizer | 107,012,128 | 102.055 | 360 | 126 | 233 type-0, 1 type-1 |
| A2 Nemotron English ASR | 699,872,960 | 667.451 | 653 | 272 | 351 type-0, 30 type-1 |
| A3 Nemotron 3.5 ASR | 742,090,464 | 707.713 | 657 | 272 | 355 type-0, 30 type-1 |

All three declare `general.file_type = 7`. The pinned ggml enum calls this `MOSTLY_Q8_0`; tensor type 8 is Q8_0. The files are mixed precision. Tensor counts are not byte proportions. These file sizes do not measure resident memory: model state, activations, working buffers, ASR/D1/E0 concurrency, Python/Tk, operating system and file mappings must be measured separately. A3 remains a secondary candidate under the user's English/A0/A2 priorities.

The exact archived CMake code appends `-march=${GGML_CPU_ARM_ARCH}` for an explicit architecture. Its ARM quantized kernels include compile-time guards for `__ARM_FEATURE_DOTPROD` and `__ARM_FEATURE_MATMUL_INT8`; the CPU code also checks FP16 vector arithmetic. This establishes an actionable build investigation. It does **not** establish that a particular instruction was emitted into the preserved binary, that a future target supports every feature, or that enabling an available feature will accelerate this workload. This audit performed no disassembly, WSL launch, rebuild or benchmark.

After H01 confirms the actual target and a fresh resource admission, retain the generic build as the control. Inspect compiler predefines, actual compile commands and emitted instructions; create a fresh target-specific derivative enabling only verified CPU features. Keep model hashes, native chunk/cache settings, one-thread baseline and source inputs fixed. First repeat full-source/repeat/EOF/timestamp/state conformance. Then compare per-component inference, integrated B01/B02 at original pacing, peak/steady RSS, caption and label latency, backlog/drain and thermals. Do not enable I8MM, SVE or other features merely because the source contains kernels for them.

A later lower-bit conversion would be a distinct accuracy/parity experiment, not reuse of these Q8_0 results. No suitable lower-bit replacement is established by this selected-file audit; it is not an exhaustive artifact search. No download or conversion was performed. On-demand E0, supported complete D1 chunk/cache recipes and process scheduling remain separate candidates; their savings cannot be inferred from these file sizes. Keep dense-speech and returning-speaker/overlap cases, not only silence-heavy synthetic averages.

Reproducibility: `README_ARM_CANDIDATES_V1.md` contains PowerShell/CMD/Anaconda commands. Private receipt: `local/n5/research-extension-20260928/ARM_CANDIDATES_AUDIT_V1.json`, with build/source/model/code hashes and exact source lines. Status: STATIC_CONFIG_AND_GGUF_HEADER_AUDIT_ONLY. Existing short-clip ARM64 passes do not resolve the full-source A2 timeout, unattempted full A3 protocol or Python/Tk/E0/punctuation/GUI qualification. No native Pi performance or full N4/N5 acceptance is claimed.
