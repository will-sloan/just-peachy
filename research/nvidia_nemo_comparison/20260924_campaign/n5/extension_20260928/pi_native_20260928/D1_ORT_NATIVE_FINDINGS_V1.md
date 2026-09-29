# D1 ONNX Runtime: first native Pi component checks

September 29, 2026, 21:04 UTC. The exported FP32 diarizer now executes with ONNX Runtime 1.29.0 CPU on the actual CM5. Three constructed feature/cache cases and their resident repeats independently match the preserved PyTorch references at the unchanged maximum absolute tolerance of `1e-5`. This qualifies a graph component, not a complete audio diarizer or a speedup.

| Case | Feature/cache/FIFO frames | First / repeat seconds | Maximum probability error | Maximum embedding error |
| --- | --- | --- | --- | --- |
| Delayed warm | 2128 / 264 / 0 | 5.362 / 5.376 | 4.7341e-8 | 6.6758e-6 |
| Cold short | 32 / 0 / 0 | 0.054 / 0.046 | 1.6019e-7 | 3.8147e-6 |
| Odd tail | 17 / 8 / 3 | 0.120 / 0.117 | 7.8977e-7 | 4.7684e-6 |

All repeat arrays are exact; integer lengths and input hashes are unchanged. A separate standard-library NPY/ZIP reader checked every retained output against its reference, shape, finite values and probability bounds. Natural exit, session release, exact owner closure and the live systemd resource envelope passed. The transfer received its own independent byte/hash/envelope/closure review before model execution.

Load took 3.077 seconds. Kernel peak RSS was 521,168 KiB (508.953 MiB), sampled peak virtual size 611,888 KiB, with one model thread. The isolated admission allowed 1536 MiB virtual space, required 1408 MiB available before dispatch, and retained sampled resource stops. CPUs 2/3, total 200%, one thread, 1 MiB stack and GPU-off remain. This admission is not integrated B01/B02 memory qualification. The original app stayed active, so timings are conditional; these random feature cases have no audio RTF or accuracy interpretation.

Graph: 400,460,515 bytes, SHA256 `b4e32f5581339a6542a298fc58724b5b0f659978c8d958c53ec378d14a8c79d2`. The Pi reuses `d1-onnx-stage-v1/D1_fp32.onnx`; do not copy it again. Native test output was 4,033,128 bytes under its 32 MiB admission. Raw arrays and evidence remain private in `d1-ort-native-v1-evidence`; its `REVIEW.json` is `PASS_NATIVE_ORT_FP32_THREE_FEATURE_CASES_ONLY`. Earlier host tracing and tail failures remain preserved.

The current graph emits coarse state probabilities. The next fresh export must also retain learned high-resolution predictions: repeating coarse frames is not equivalent. A portable waveform frontend and the ordered cache/FIFO/update/EOF driver still need implementation and full-source parity. Native operator execution alone does not establish that complete runtime, integration, sustained behavior or acceleration. Bounded quiet PCM/journaling and GUI readiness remain parallel priorities.

Closure V43 found all 140 recorded Pi research identities and all isolated host export owners closed, original app/config/install unchanged, capture closed and leases free. No capture or playback occurred in these tests.

The preceding 3 GiB allowance had only 206,141,691 bytes remaining, insufficient for another approximately 400 MB host graph plus its Pi copy. Under the user's resource authority, fresh `WINDOW_V3.json` raises file output to 4 GiB without resetting usage, deleting evidence or changing CPU/RAM limits or the October 1 checkpoint. Closure V43 counted 3,015,145,354 bytes. Three new guard boundary tests pass; the fresh guard also checks isolated export identities. Earlier windows and admissions remain immutable.

Run/review instructions: [graph transfer](README_STAGE_D1_ONNX_V1.md), [transfer review](README_REVIEW_STAGE_D1_ONNX_V1.md), [native cases](README_D1_ORT_NATIVE_V1.md), [native independent review](README_REVIEW_D1_ORT_NATIVE_V1.md), [closure census](README_COLLECT_NATIVE_CLOSURE_V3.md), and [file allowance](../README_WINDOW_V3.md).

The fresh host census also exposed a separate constraint: including target bytes and retained 2.5 GiB reservations leaves only 276,619,748 bytes under the original 50 GiB total-payload ceiling. The combined 512 MiB request was correctly rejected before dispatch; HOST_CENSUS_V43 alone is not a target-inclusive admission. The 4 GiB window increase does not waive this check. Prepare the small frontend/state-driver source next; a further graph/export copy needs a fresh measured payload policy under the existing resource authority, preserving earlier limits and evidence. Private COMBINED_PAYLOAD_HEADROOM_V1.json records the rejection.
