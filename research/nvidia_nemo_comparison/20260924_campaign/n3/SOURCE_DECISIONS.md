# N3 source and capability decisions

Status: accepted offline N3 component evidence, 25 September 2026.
REPORT_N3.md and N3_FINAL_METRICS.json record actual model/GUI results.
Pinned source/model terms remain separate from measured efficacy.

| Component | Exact source / terms | Decision |
|---|---|---|
| A0 | Existing selected Sherpa Giga and its fine-tuned artifacts | Retain exact weights, final-only P0 and baseline identity |
| A1 | [NVIDIA Parakeet Realtime EOU 120M](https://huggingface.co/nvidia/parakeet_realtime_eou_120m-v1), revision a7e2b4629593dce0ec19f600e00e9904353fda2d | Actual NeMo recurrent reference and qualified full-service ONNX CPU route; three actual Controller/GUI cases passed; native GGUF route unavailable |
| A2 | [NVIDIA English Nemotron Streaming](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b), revision ebe59e5a817142986528bbbee5dba8db7b38ed50 | Exact official Q8_0 native CPU/CUDA artifacts plus FP32 NeMo reference, explicit English |
| A3 | [NVIDIA Nemotron 3.5](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b), revision ea30d66debe3740a08b573244286791d423d6b3e | Exact official Q8_0 native CPU/CUDA plus FP32 reference, explicit en-US |
| Native code | [NeMo-Speech.cpp supported models](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/97a15afa5caa9bce5baaa86c1184103877af4101/docs/asr/models.md), Apache-2.0 | A2/A3 supported. No evidence that this runtime accepts A1 EOU; offline TDT is not substituted |
| P0 | Existing 7,490,500-byte Sherpa int8 punctuation model | Apply final-only to A0/A1; compare on identical lexical inputs separately |
| P1 | Native A2/A3 punctuation/casing | Preserve output; no redundant P0 production pass |
| P2 | `P2_DISCOVERY.json` records official NVIDIA HF searches | No exact licensed standalone weight verified; retain explicit gap |
| ITN | [NeMo text processing](https://github.com/NVIDIA/NeMo-text-processing/tree/ddadfb2a38d2bc6b8cc6232c4f915eb60f500688), Apache-2.0 | Verified finite subset; 110 numeric and 16 unit forms; independently toggled |

A1/A2 weights use the [NVIDIA Open Model License](https://www.nvidia.com/en-us/agreements/enterprise-software/nvidia-open-model-license/).
A3 weights use [OpenMDW 1.1](https://openmdw.ai/license/1-1/). Model terms are
separate from runtime/tokenizer/grammar code. Existing terms receipts are in
`../assets/terms_receipts.json`; native/transitive notices are indexed in
`../assets/runtime_license_index.json`. No model weights ship in this checkpoint.
Exact asset hashes, sizes and card hashes are in `MODEL_REGISTRY.json`.

Nominal A1 is its published trained [70,1] setting. Nominal A2/A3 native right
context 1 is the supported native default: A2 left context 70, A3 56. The sole
lower-buffer contrast is right context 0 on four fixed manifest rows. Reference
routes use FP32 CPU, greedy decoding and an additional held final-frame buffer;
their performance cannot be labeled native or Pi performance.

The three inspected targets are RNNT classes. A2/A3 configurations retain
auxiliary CTC keys, but their RNNT model classes do not establish a usable CTC
decoder; A1 includes inter-CTC configuration metadata. `MODEL_HEADS.json` keeps
that distinction. [NeMo Forced Aligner](https://docs.nvidia.com/nemo-framework/user-guide/latest/nemotoolkit/tools/nemo_forced_aligner.html)
requires a compatible CTC model/head. No such runtime head has been verified in
these available candidates. E-only script/quality selection is deferred, with
existing disjoint E/C/Q metadata preserved. No Q text selects enrollment windows.

Conversational reconstruction decision: evaluate observed lexical alternatives,
native punctuation and conservative traceable normalization. Defer unconstrained
missing-word, grammar and large-LLM rewriting. No expected transcript becomes a
decoder bias list. Similar names require explicit contextual approval; no real
personal mapping or enrollment is created. Optional multitalker comparison is
deferred to preserve the essential A1/A2 work and portable baseline.
