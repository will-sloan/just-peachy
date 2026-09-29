# Whole native geometry candidates, inspected September29

The retained source at revision97a15afa5caa9bce5baaa86c1184103877af4101 defines named geometry presets in `src/asr/diar/aosc_state.h` and validates them in aosc_state.cpp. The current Python adapter explicitly overrides every geometry field; passing `v3-streaming` as its base preset does not mean it uses that preset's final values.

All geometry counts below are coarse80ms frames, while D1 public output remains10ms. Field order is made explicit to prevent mixing partial recipes.

| Whole recipe | Chunk | Right | Left | FIFO | Speaker cache | Cache refresh |
|---|---:|---:|---:|---:|---:|---:|
| Current accepted-component adapter low_latency |9|4|0|264|264|222|
| Pinned native v3_streaming() |13|1|0|80|264|40|
| Pinned native v3_offline() |264|1|1|0|264|188|

The native source explicitly states that its offline preset still uses the ordered streaming state machine with larger chunks/caches. These are credible bounded next candidates, not measured improvements. The large recipe may amortize repeated context computation while delaying speaker evidence by roughly one21-second center chunk plus right context and processing. It cannot make captions wait for those labels. The streaming preset also changes several context/cache fields, so it is not merely a larger Python push. The current adapter's roughly1.04-second input buffer and the native preset's roughly1.12-second center-plus-right buffer should not be conflated with actual end-to-end label latency.

After the repaired kernel's full-source/repeat gate and initial combined-memory check, create an isolated adapter derivative with two explicitly named whole recipes. Preserve all old profiles/results. Verify the exact native configuration handed across the C ABI, output frame/time mapping, empty/EOF, repeat/reset, finite probabilities and bound enforcement. Numerical equality between different geometries is not an expected gate; use the same geometry for generic-versus-optimized numerical parity and repeat checks. Do not reinterpret a geometry difference as an accuracy improvement or loosen the existing same-geometry1e-5 kernel gate.

Measure full-source and source-paced native runtime, load/RSS, native call durations, source backlog, drain, availability of labels and cache-history growth. Keep all audio and original source chronology; no silence skipping or ASR/WER/DER scoring on saved inputs. Return/overlap/quiet speech quality and30/60-minute sustained dense conversation remain later user-ready held-out tests. Smaller caches can affect returning-speaker behavior; no new recipe becomes a release default from a synthetic timing result.

This document records inspected source and proposed experiments, not executed recipes. Use the existing native README and fresh derivative-specific README/admission for execution. No downloads, training, capture, enrollment or resource increase is needed for this source inspection.
