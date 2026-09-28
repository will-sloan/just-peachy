# Nemotron 3 diarizer acceleration candidates

Purpose: answer the user's September 28 export/runtime question and retain a bounded research order. Inputs are the existing ARM audit, measured Windows component costs and the linked publishers' documentation inspected on September 28, 2026. Output is this research note and the queue entry in NEXT.md. This note adds no executable code; there are no PowerShell, CMD or Anaconda execution commands. No model was downloaded, exported or benchmarked for this note. No Pi was contacted. All candidates below remain unqualified in this campaign.

## Measured starting point

COMPONENT_COST_FINDINGS_V1.md records 82.39/84.92 seconds of D1 push/finish call wall time for 44.695 seconds of saved audio with Sherpa/Nemotron ASR respectively: D1 RTF 1.843/1.900. These are narrow Windows observations with one native thread per model, not Pi measurements or sustained performance. Reaching RTF 1 requires about 1.84–1.90 times the observed throughput, before allowing operational headroom.

ARM_OPTIMIZATION_FINDINGS_V1.md establishes that D1 already uses native NeMo-Speech.cpp and a 107,012,128-byte mixed-Q8_0 GGUF. The preserved ARM build targets generic armv8-a, disables KleidiAI and uses a one-thread graph helper. Python coordinates this backend; its core inference is already native. Changing the file container alone does not establish faster inference.

## Bounded research order

1. **Targeted native ARM build.** Following confirmed reconnection and H01, verify CPU features and emitted instructions, then compare the retained generic build with a fresh target-specific derivative. Investigate supported NEON/dot-product/FP16 kernels and compatible optimized kernel libraries. Do not assume newer I8MM, SVE or SME instructions exist. Thread-allocation experiments require a fresh admission and must share the total budget with ASR/E0; the current one-thread-per-model admission remains unchanged.
2. **Whole native chunk/cache recipe.** NVIDIA documents 1.04-second low-latency and 30.4-second offline-style input buffers, with different FIFO, chunk and cache-update settings. Larger steps might amortize repeated context work, with later speaker labels. This is a hypothesis, not measured savings. Preserve one ordered stream and implement the entire supported recipe; larger host pushes alone are insufficient. Keep captions independent. [NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3-Diarization#setting-up-streaming-configuration).
3. **ONNX Runtime CPU comparison.** Actual exports of this exact model exist, so export feasibility is more concrete than an unimplemented proposal. Establish graph, preprocessing and cache contracts first; compare a verified floating-point reference and an INT8 candidate under matched native recipes and resources. ONNX Runtime supports ARM builds, but that does not establish speed or model correctness on our target. [ARM build documentation](https://onnxruntime.ai/docs/build/inferencing.html#arm).
4. **Lower precision and GPU follow-ups.** Inspect Q4/mixed-precision graphs after the first comparison. Less storage does not guarantee less inference time: packing, dequantization and unsupported operators matter. ONNX Runtime documents hardware-dependent quantization gains and possible accuracy loss. NVIDIA's current upstream runtime also documents a Vulkan diarizer preset; this is only an exploratory route, not evidence for the preserved runtime or Pi GPU. [Quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html), [upstream build presets](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/build.md). No GPU dispatch is admitted now.

## Located ONNX candidates

| Publisher | Observed offering | Qualification gap |
|---|---|---|
| [NealCaren](https://huggingface.co/NealCaren/Nemotron-3-Diarization-ONNX) | FP32 and approximately 103-MB dynamic-INT8 neural step, separate feature projection and constants; export scripts listed | Front end and streaming speaker cache remain outside the graphs. Publisher's browser/Apple results are not Pi or our pipeline evidence. |
| [wannaphong](https://huggingface.co/wannaphong/Nemotron-3-Diarization-ONNX) | Approximately 103.7-MB INT8 step, FP32 reference, preprocessing and NumPy cache driver | Explicitly offline-only 30.4-second recipe; sub-second streaming is not qualified. The publisher reports cache tie-breaking differences and file-length-dependent memory. Its Intel results are not a comparison with our GGUF backend. |
| [onnx-community](https://huggingface.co/onnx-community/Nemotron-3-Diarization-ONNX/tree/main/onnx) | Tree lists FP32, FP16, quantized, Q4 and Q4F16 graph/data pairs; Q4 external data approximately 82.8 MB | File existence and names do not verify graph precision, streaming cache support, complete asset requirements or accuracy. Usage documentation currently says coming soon. Pin and audit before use. |

These are community conversions, not campaign-accepted replacements. Sizes are publisher-listed decimal MB and exclude runtime working memory. Main-branch pages are discovery references, not immutable run bindings: resolve exact commits, licenses, all graph/external-data hashes and dependencies before any admitted acquisition or run. Current no-download authorization remains in force. Prefer cached sources/artifacts where verified; record any acquisition need rather than downloading automatically.

## Comparison and acceptance

Hold input chronology, whole recipe, total CPU allocation, thread limits and component composition fixed when attributing differences to a runtime. Separately compare latency recipes; do not credit a 30.4-second offline versus 1.04-second streaming difference entirely to ONNX. Count preprocessing, neural execution, cache maintenance, fusion and memory, not only the encoder.

Verify complete-source/repeat/EOF/Stop behavior, output coverage and source timestamps before speed testing. Use probability/segment tolerances and ground-truth DER decomposition; quantify cache divergence rather than relaxing existing gates after a failure. Include returning speakers, quiet/short speech, overlap and dense continuous speech. Preserve ReDimNet naming and match thresholds independently. Then measure paired B01/B02 caption/speaker latency, corrections, RTF, backlog slope/max/drain, CPU/RSS and native thermals/clocks in paced endurance tests. Freeze settings before independent real-world validation. Sparse synthetic silence savings cannot qualify sustained conversation.

This adds candidates to the existing campaign; it changes no accepted stage, source binding, resource limit, deadline or N4/N5 completion claim.
