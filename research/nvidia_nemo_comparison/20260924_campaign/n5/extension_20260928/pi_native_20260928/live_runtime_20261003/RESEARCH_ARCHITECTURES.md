# Streaming speech architectures for the current edge runtime

Primary links and current implementation/evidence cross-checked **2026-10-04**. This note uses primary papers, author archives and official
hardware/model documentation. It proposes adaptations of the existing Sherpa ASR,
Pyannote segmentation, Nemotron 3 diarization, ReDimNet and TitaNet assets. It does
not reproduce any paper's complete system. No new model was downloaded or trained.
All proposed native comparisons target the existing **2 GB CM5**; there are no
4 GB or 8 GB runtime measurements here. A configuration or synthetic test pass
does not prove native quality, memory fit or sustained real-time operation.

## Evidence that affects the design

| Primary source and date | What the source supports | Boundary for this project |
|---|---|---|
| [Streaming Sortformer](https://arxiv.org/abs/2507.18446), 2025-07-24, Interspeech 2025 | Arrival-Order Speaker Cache stores selected frame embeddings ordered by speaker arrival. High-score frame selection and dynamic allocation preserve past speaker information across chunks. | Retain continuous context and explicit slot provenance. Arrival ordering inside one stream does not align two independent model runs or prove a physical identity. No CM5 performance result is supplied. |
| [Online EEND with Speaker-Tracing Buffer](https://arxiv.org/abs/2006.02616), 2020-06-04, revised 2021-03-07 | Representative buffered frames and correlation resolve speaker permutations between chunks; variable chunk training addresses the streaming mismatch. | Supports explicit mapping across independently ordered results. Its reported latency is for its own model/setup, not a Nemotron geometry on ARM. |
| [FLEX-STB](https://arxiv.org/abs/2101.08473), 2021-01-21, revised 2021-04-07 | Extends speaker tracing to changing speaker counts and overlapping speech using padding and buffer strategies. | A conceptual reference for abstaining and mapping variable slots; swapping this trained EEND into the current runtime is outside scope. |
| [UIS-RNN: Fully Supervised Speaker Diarization](https://arxiv.org/abs/1810.04719), 2018-10-10, ICASSP 2019 | Learns interleaved speaker-specific recurrent states over extracted embeddings and supports online decoding with an unknown speaker count. | It is a trained clustering model, not a free replacement for the existing name resolver. Our ReDimNet/TitaNet embedding distributions and namespaces would need compatible training/calibration. |
| [Bayesian HMM x-vector clustering / VBx](https://www.isca-archive.org/interspeech_2019/diez19_interspeech.html), Interspeech 2019 | Variational Bayesian HMM inference clusters x-vectors and can initialize a further frame-level refinement stage. | Temporal smoothing is useful, but this paper does not establish our bounded streaming implementation. A compatible embedding/backend model and explicit revision horizon would be needed. |
| [Overlap-aware online diarization / DIART](https://arxiv.org/abs/2109.06483), 2021-09-14 | Combines local segmentation with incremental clustering on a buffer updated every 500 ms; downweights overlap in embedding pooling and applies cannot-link constraints. Its latency tradeoff is evaluated from 0.5 to 5 seconds. | We reuse only the principle of querying cleaner intervals. Our sparse schedule does not implement their pooling layer or cannot-link clustering, and their reported results are not ours. |
| [Streaming end-to-end ASR for mobile devices](https://research.google/pubs/streaming-end-to-end-speech-recognition-for-mobile-devices/), ICASSP 2019 | Demonstrates an on-device streaming RNN-T design and evaluates latency/accuracy against a CTC baseline. | Supports retaining a streaming recognizer as an independent primary text path. It gives no RAM or throughput guarantee for our Sherpa model on CM5. |
| [Streaming multi-speaker ASR architecture tradeoffs](https://arxiv.org/html/2609.10265v1), 2026-09-09 | Compares timestamp-based cascading, speaker-masked parallel ASR, word-level serialized output training and diarization-conditioned multiple instances. It examines memory, training and recognition tradeoffs. | The paper uses Nemotron Speech ASR and Sortformer 2.1, unlike our Sherpa/Nemotron 3 combination. A single ASR plus late timestamp association is the practical adaptation; duplicated ASR or retraining is not justified by current resources. |
| [ReDimNet2](https://arxiv.org/abs/2603.11841), 2026-03-12 | Time pooling changes compute/accuracy scaling for utterance-level speaker embeddings; the paper evaluates a family of sizes. | Retain the existing pinned B2 asset and namespace. A new smaller model would require new assets, enrollment/calibration and evidence. Less frequent queries can be evaluated without claiming a different encoder's published accuracy. |
| [TitaNet](https://arxiv.org/abs/2110.04410), 2021-10-08 | Depth-wise convolutions, global context and pooling produce fixed-size speaker representations from variable utterances. | Existing TitaNet remains a selectable embedding backend. Verification results do not make an overlapped, very short or skipped interval reliable identity evidence. |

The official [Nemotron 3 model card](https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/README.md),
released 2026-09-23 and model-card geometry checked 2026-10-03, documents eight speakers, AOSC/FIFO state
and selectable input buffering. Its low/very-low/ultra-low recipes are
cache/FIFO/chunk/right/update = `264/264/9/4/222`, `264/264/6/2/222`,
`264/264/3/1/222`, respectively: 1.04, 0.64 and 0.32 seconds of nominal input
buffer. These figures exclude native compute and application queues. Our retained
CurrentDelayed geometry is a different retained recipe, not the card's offline
recipe. The actual pinned model position limit and native C ABI are validated in
`profiles.py`. Actual bounded native results are now recorded separately in
[NATIVE_RESULTS](NATIVE_RESULTS.md), including failed official-profile prefixes.

## Three concrete architectures

**1. Existing Pyannote plus one embedding backend for the responsive baseline.**
Use current Sherpa ASR and the existing Pyannote path, selecting ReDimNet, TitaNet
or anonymous independently of live/saved input. This is the baseline to compare
against, with its real first-text and speaker-event timing. The new sparse helper
is intentionally D1-only because the audited clean-window hook belongs to D1;
do not silently apply it to a different Pyannote selection policy. Fast activity
or an ASR endpoint can suggest a boundary, but cannot prove a speaker change or
identity. Where evidence is insufficient, the fast result is Unknown.

**2. One persistent D1 plus ASR-first text and late labels: preferred low-memory
development path.** Keep one ASR instance and one continuous D1 context, with
optional ReDimNet/TitaNet. Emit text immediately with pending/Unknown speaker;
revise the same caption IDs when genuine D1 and name evidence arrives. Existing
`n2_pipeline.py:_revise_supported_spans` already emits interval-supported
`transcript_label_revision` events without altering words. It labels timing as
coarse ASR revision windows, not phonetic word alignment. A presentation adapter
now bounds the revision period and exposes pending/attributed/expired states without
adding another model. This is asynchronous attribution, not fast-speaker versus
slow-speaker model correction.

The prepared implementation is `SingleD1LateLabels` in
[late_labels.py](late_labels.py), documented with its integration API and host
commands in [README_LATE_LABELS.md](README_LATE_LABELS.md). It preserves ASR words,
accepts only genuine upstream interval-supported native speaker history, and
retains the last valid fallback after expiry. Unknown remains necessary where no
actual evidence is available. The installed-engine selection/UI path is wired;
native application validation remains separate from synthetic contracts. It does
not require a parallel-worker admission and does not allocate a second diarizer.

For this architecture, `sparse_embedding.py` now provides explicit experimental
`sparse_clean_turn`: the first eligible exclusive window of each observed turn,
then a configurable refresh (default 2 seconds), using the installed exact
contiguous windows. It preserves the existing thresholds/resolver and all
ASR/D1 samples. Considered and evaluated cursors are separate. Six focused host contracts passed. Actual Research07 later reduced embedding calls19 to7 and sampled input416,000 to104,000 against the retained matched baseline; changed source batching is also part of the comparison, so this is not an isolated total-runtime speedup measurement. Thirty supported/partial late-label publications were observed, while six final spans remained pending; quality remains unmeasured. It can
save only the optional embedding portion of work, not the D1 encoder cost.
The default `continuous` schedule is unchanged. See its
[API and commands](README_SPARSE_EMBEDDING.md).

**3. Pyannote/embedding primary plus one optional continuous anonymous D1 child:
implemented with exact bounded native evidence and separate release admission.** The new
`optional_refiner.py` supervisor and private D1-only worker read every committed
source sample through one bounded parent-owned journal RPC. They keep a single
continuous CurrentDelayed context without resets or skipped gaps. ASR and the
identity encoder remain solely in the primary process. This supersedes the
earlier independent-window sketch; `RefinementCoordinator` remains a separate
injected-worker component, not the implementation of this native child.

Exact sample-clock provenance, primary-track/D1-slot permutation mapping,
overlap abstention, bounded history/revision age, stable caption IDs and current
text-revision targets support optional corrections without holding primary text.
Failures or unusable lag disable only refinement and preserve primary fallback.
The child has a registered owner, inherited shared CPU2/3/200% unit, finite
memory/output/deadline limits, parent-death handling and bounded kill/reap.
See [README_OPTIONAL_REFINER](README_OPTIONAL_REFINER.md) for the actual API/tests.

The explicit `optional_d1_refiner` selection defaults false. Normal GUI use still requires an exact reviewed measured admission. A separate finite first-qualification permit now admits supervised measurement without inventing a prior pass: actual unit/boot/owners, source and asset pins, per-process address-space limits, whole-unit RSS/available-RAM guards, independent output allocation and complete Stop/closure remain mandatory. Address-space ceilings are not added together as a physical RAM requirement.

Actual build10 `optional-first-01` completed primary output but its child stopped at2,880 samples/zero frames on empty-activity queue capacity. The repair retained all acknowledgements and the eight-real-batch bound. Actual build13 First02 and build14 First03 subsequently completed the matched saved clip in both processes. Build13 Followup01/window30 preserved full primary/raw300 but disabled the child at its label-lag limit; this is real fallback evidence. Actual build14 First03 completed matched saved45 child/primary EOF; Followup02 then completed all4.8M primary/raw/child live300 samples and30,001 child frames with window60, source300/drain60/backlog30. Full owner/model closure and sampled aggregateRSS760,020,992B/minimumavailable1,178,828,800B/owned swap0 support that bounded experimental scope. Zero optional corrections were observed. The exact measured receipt is accepted for production16 through reviewed GUI-policy and path-only reuse. Its actual idle GUI verified the controls without starting models or capture; the model measurements remain build14 facts. The actual build13 window30 child timeout remains a preserved fallback result, not full child EOF. Pyannote and D1 retain two diarization working sets, with ASR/embedding solely in the primary; the existing one-D1 late-label mode uses fewer model contexts. See [the optional contract](README_OPTIONAL_REFINER.md).

## What 2, 4 and 8 GB change

Official [CM5 specifications](https://www.raspberrypi.com/products/compute-module-5/)
list the same BCM2712 four-core Cortex-A76 at 2.4 GHz with 2, 4, 8 or 16 GB memory
options. More capacity does not supply additional cores or make a compute-bound
model real-time. The entries below are engineering expectations, not measurements.

| RAM | Expected benefit | What remains constrained |
|---|---|---|
| 2 GB, current target | Bounded audio/history and one ASR; the exact measured Pyannote/TitaNet plus anonymous D1 live300 pair fits its observed envelope. One diarizer uses fewer model contexts. | Measure peak resident/virtual allocation and OS headroom for every selected combination. More aggressive chunk frequency can still overload the admitted CPU2/3 envelope. |
| 4 GB, unmeasured | More room for simultaneous model weights, native workspaces, file cache and application services; less risk of capacity pressure if 2 GB is near its limit. | Same CPU architecture and current CPU allocation. A second worker may increase latency/backlog even if it fits memory. Memory headroom alone cannot admit dual inference. |
| 8 GB, unmeasured | More capacity for larger models, multiple resident options or extra services; useful if measured working sets exceed 4 GB. | No evidence of lower per-chunk compute time or better accuracy merely from RAM. For the same bounded model set, idle extra RAM may provide little runtime benefit. |

Avoid storing an hour of copied audio in RAM. At mono 16 kHz, PCM16 is 32,000
bytes/second (115.2 MB/hour); float32 is 64,000 (230.4 MB/hour). A 30-second
float32 ring is 1.92 MB. Eight float32 probabilities at 100 frames/second are
3,200 bytes/second (11.52 MB/hour), excluding containers, native state and other
copies. These are arithmetic storage sizes, not process RSS forecasts. Model
file size likewise cannot substitute for native peak-memory measurement.

## Completed focused set and current follow-up

Use the retained 715,127-sample mono 16 kHz source WAV, SHA256
`0ee26e8aa6f815d8b202419aafb71ff5bc25093d193e95e972036f488c5040b8`, from
`d1-geometry-delayed-a76-v1/source.wav`. Keep sample count, gain, model/library
pins and CPU2/3 admission fixed; the retained source requests one native graph
thread. A separately pinned two-thread experiment must be labeled explicitly.
Use a fresh process per
geometry. The focused [benchmark CLI](README_NATIVE_BENCHMARK.md) records init,
push and finish timing, all probability rows, exact EOF, rolling push RTF,
source backlog and available RSS/CPU/thermal observations.

1. The focused component cohort is sufficient for the next integration decision:
   all three official recipes were attempted and failed safely at bounded drain
   limits; 2.00 s, compact3.04 s and4.48 s candidates completed the matched file.
   Their RTFs were2.1233,0.8568 and1.1091, respectively. No additional1.2-second
   sweep is prescribed. The separately compiled two-thread Chunk52 core then
   completed at RTF0.5543 versus1.0813 for one thread, with all4,470 x 8 values
   exactly matching the reference. It supersedes the one-thread throughput
   bottleneck for that explicit component option, without proving integrated
   headroom or accuracy. The official modes' early output remains distinct from
   their failed-prefix throughput. See [NATIVE_RESULTS](NATIVE_RESULTS.md).
2. The one matched integration comparison is complete: Research07 on build14 used the same715,127 samples as pipeline04, CurrentDelayed/ReDimNet, `sparse_clean_turn` at2s and `single_d1_late_labels` at30s. All4,470 x8 native float values and the final three-utterance/38-word ASR sequence matched exactly. Embedding calls fell19 to7;30 supported/partial late-label publications demonstrate actual existing anonymous evidence consumption, not identity accuracy. Source batching and the reviewed late-label repair are explicit differences, so whole-runtime timing changes are not assigned solely to sparse scheduling. No extra baseline or parameter sweep is prescribed.
3. The continuous one-hour two-thread Chunk52 component replay completed all
   57,600,000 samples and360,001 frames at RTF0.88445, with exact closure and
   complete regular-file mirror. Later RSS plateaued near166.5MiB, but temperature
   reached85.35C and late RTF approached0.94. This is a component result, separate
   from the first full-application hour attempt that failed an output guard
   after319s. The later build10 hour04 committed57,359,280 samples (3584.955s), did not reach the3600s EOF target, and ended at its watchdog. D1 rolling push RTF averaged about0.45 while the source fell behind wall time. Minimum available physical RAM remained1,210,351,616B; worker virtual peak797,163,520B approached the805,306,368B address-space guard. No failed allocation establishes that either RAM limit caused the source drift. The selected build13/14 saved-input derivative changes durable append grouping from20ms to100ms and records aggregate append time/source-wall lag; its changed path completed the matched short runs. External5Hz output-tree scans and1Hz fsynced resource sampling are additional unquantified overhead candidates; those guards remain unchanged. This is a new observable source-path experiment, not a proven hour fix. See NATIVE_RESULTS; never infer whole-application qualification from the completed component hour.

This note and benchmark authorize no broad campaign or4/8GB performance claim. Earlier failures remain failures. Current actual14 evidence includes the changed single-D1 late-label clip, exact saved primary/window60 prerequisite, short child feasibility and full live300/window60 child processing. Production16 now binds the exact reviewed parallel selection/policy through explicit GUI/path reuse, and its actual idle GUI verified the controls without Start/model/capture. These GUI observations do not extend the actual14 model measurements. Single-D1 late labels and sparse scheduling remain independently selectable without a second diarizer.

The [read-only comparison reviewer](README_RESEARCH_COMPARISON.md) verified both closed mirrors, exact processed float32/sample clocks, embedding costs, final ASR counts/hashes and all4,470 native probability frames. The [optional followup reviewer](README_OPTIONAL_FOLLOWUP_REVIEW.md) separately verifies full primary/raw/child clocks and closure, counts child-provenance revisions and scopes aggregate resources. Neither publishes transcript text or claims DER/identity accuracy. Paper-derived concepts are adaptations, not reproductions of those models or their reported benchmarks.
