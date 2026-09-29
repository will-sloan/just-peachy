# Whole native recipes on the connected CM5

September29,2026. Saved-audio functionality/resource evidence only. The original rc5 app remained active, so these timings are conditional. No audio was removed, gated, recorded or played. No new ASR/WER/DER accuracy metric was computed. Component passes do not qualify an integrated application mode or independent real-life performance.

## Verified delayed recipe

The exact native `v3-offline` recipe runs as one ordered AOSC stream: chunk264/right1/left1/FIFO0/cache264/refresh188, in80ms coarse frames, with10ms output. The input is the unchanged44.6954375-second saved file (715127samples). Native metadata/scheduler bounds, weights and other runtime libraries were held fixed between generic and A76 runs.

| CPU implementation | First pass | Resident repeat | Model call sequence RTF | Peak process RSS |
|---|---:|---:|---:|---:|
| Generic ARM kernel |23.675s|23.669s|0.530 /0.530|177.016MiB|
| Lane-preserving Cortex-A76 kernel |18.118s|18.122s|0.405 /0.405|172.984MiB|

Both independently pass all715127samples/4470x8 finite probabilities, continuous frames, repeat/reset/empty/EOF/post-finish rejection and model/owner closure. A76 output is exactly equal to the same-geometry generic array (max absolute error0, declared gate1e-5). Repeat arrays are also exact. This is software conformance; it does not establish speaker accuracy.

The A76 observation takes about23.5% less wall time than the matched generic run. The earlier low_latency A76 full-file diagnostic took269.603s (RTF6.032), about14.9times the new delayed recipe's18.118s. That larger change trades a different full chunk/cache recipe and speaker-label delay for reduced repeated work; old and new recipe probabilities are not required or claimed to match. Real speech and overlap/returning-speaker quality must be validated separately after freezing settings.

This candidate is useful for delayed speaker labels or post-session work. It needs21.3seconds of source input before the first emission in the100ms-push harness; the first native compute then takes roughly4.3seconds on A76. The unpaced4.336second first-output wall measurement excludes waiting for incoming audio. It is not a live label latency. ASR captions must remain independent, with Pending/Unknown labels while the speaker lane waits. A44.7second file/repeat is not30/60minute endurance.

## Binding repair

The earlier native-profiles-v1 preparation passed FIFO0 with a hardcoded streaming preset. The pinned C API only applies a FIFO override when it is positive, so zero would have inherited FIFO80. Before any delayed inference, native-profiles-v2 was created to select `v3-offline` specifically for the delayed recipe. Existing profiles and earlier source remain unchanged. The harness captures the actual C-ABI creation fields; the pinned C-API/header sources establish preset resolution. See README_GEOMETRY_V2.md.

Adapter SHA256: `2537162df8ac8ccdd89c45c3f26fa12ef48519867a0474bf4be39e4667d75e37`.
Generic result SHA256: `194b702bd31742d3a876fc7968b30c4688faa4fc980c8f64f88357c576048037`.
A76 result SHA256: `a47fe55478c952b407016298b6175c9881b2d799b5eba3af50c36d3bc5717352`.
Raw arrays/traces/receipts remain private in the matching d1-geometry directories.

## Streaming recipe failure and next repair

Native streaming13/1/0/80/264/40 was actually attempted with the generic kernel and the qualified2048-node/8MiB runtime. It accepted all447 source pushes, but aborted on an8MiB TensorContainer allocation during EOF. Only4368 of4470required frames were emitted; no complete output, resident repeat or clean application/model finalization exists. Exact process closure and all input hashes were independently checked. Preserve this as a failed recipe, not a faster working stream.

Source inspection found Sortformer explicitly permits48 cached compute graphs. The failed run accumulated42 graph entries before EOF. These executable graph caches are separate from the diarizer's speaker/FIFO caches. A fresh derivative with a smaller compute-graph LRU is a justified next memory investigation; retain native eviction/state guards and qualify numerical parity, returning state and rebuild cost. This reduction is not implemented or tested here. Do not change speaker cache/history to simulate it. Do not rerun the unchanged failed recipe or relax the768MiB cap.

The first dispatcher attempt failed locally at Windows command-line length before remote staging. V2 transmits preparation over strict SSH stdin; numerical code and resource limits were unchanged. Both attempts remain preserved.

## Paced follow-up and application gates

The independent1x producer/ordered-model check now passes full source and resident repeat, with exact generic-reference output and both producer/model closed. It retained every sample, with no FIFO overflow or skipped audio. Read README_GEOMETRY_PACED_V1.md for reproduction.

| Paced observation | First pass | Repeat |
|---|---:|---:|
| Full elapsed, including original source pacing and drain |56.096s|56.084s|
| Summed native/adapter call work |18.178s|18.141s|
| First speaker-probability output after source start |25.539s|25.507s|
| Maximum FIFO residence before processing |8.937s|8.924s|
| Maximum queue entries (100ms each) |42|42|
| EOF drain after original44.695s source end |11.400s|11.389s|
| Maximum source scheduling lateness |2.129ms|0.684ms|

Peak process RSS was173.359MiB; process CPU18.268/18.235seconds. Model-call work/audio was approximately0.407/0.406; total elapsed/audio was1.255 because it includes source pacing and drainage. First output is an anonymous probability array, not committed personal identity or caption latency. This short test does not measure sustained backlog slope or30/60minute behavior. Paced result SHA256: `cf3b5fb715eb9c2d1376d1720527644c770ee1ccac8da9bca96efdfdf8f305a7`. No integrated caption/E0/UI claim follows from this component check.

B01 integrated startup remains blocked under the current virtual-address admission. The1GiB short integrated trial remains pending the user's explicit answer, with its proposed1.25GiB available-RAM floor. No cap increase is inferred from these component results. B02/ONNX D1, complete shared GUI/mode/storage/lifecycle coverage, sustained native behavior and real spoken/noisy-location validation remain open. See STATUS.md and PI_MODE_PLAN.md. N4/N5 acceptance is unchanged.
