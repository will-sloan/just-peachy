# H2 product architecture

## Purpose and status

H2 is the single fixed product architecture selected for the current program. The scientific campaign changes only declared runtime policies and product behavior; it does not reopen the earlier H1–H6/C7–C9 architecture comparison.

The immutable 18-pipeline matrix retains the historical AG field
`BLOCKED_BY_CURRENT_LARGE_STUDY_SEGMENT_CONTRACT_GUARD` because that field
describes the evidence boundary before the H2 pivot. It is provenance, not the
current H2 runtime gate. The H2 program subsequently completed the dedicated
36-case native-streaming qualification job
`h2p0_h2_true_streaming_qualification_f81cfadf81`, whose sealed result is bound
by SHA-256
`f834851e1ac1b70b0d463b254b753156dc9c85b7261edac04c1c3eeff664d068`.
Final H2 reporting must use that qualification result while continuing to
preserve the matrix's historical value unchanged.

The desktop reference stack is:

```text
16 kHz mono audio frames
        |
        +--> native Sherpa streaming ASR (Giga primary, Original reduced regression)
        |
        +--> rolling Pyannote Segmentation 3.0 (10 s window, 5 s model lookahead)
                    |
                    +--> ReDimNet2-B2 embeddings
                              |
                              +--> deterministic online anonymous clustering
                              |
                              +--> enrolled-profile maximum-gallery scoring
                                        |
                                        +--> score + Top-1/Top-2 margin
                                        +--> evidence/quality gate
                                        +--> causal hysteresis and expiry
                                                  |
                                                  +--> bounded session memory
                                                  +--> labelled transcript/events/UI
```

The anonymous diarization and enrolled-identity roles use the same ReDimNet2-B2 model identity. `R2_ONE_SHARED_MODEL` is the implemented shared-model path. R3/R4 embedding reuse is not treated as equivalent unless an exact vector, decision, and event parity gate passes.

## Runtime ownership

The common runtime owns inference, clocks, queues, state transitions, durable events, transcript construction, and exports. The GUI and CLIs only select a preset, provide audio/profile input, consume runtime events, and request safe lifecycle actions. No model or threshold logic lives in the UI.

Every H2 run binds:

- pipeline/model/config hashes;
- the strict runtime-tuning document and SHA-256 (`v4` for calibrated M4/M5;
  legacy v1-v3 identities remain readable only with their original fields);
- product mode;
- exact protocol/case membership;
- result-affecting source and worker-environment identities;
- a development/evaluation firewall receipt.

### Logical-interface implementation map

The steering specification names logical roles. They are implemented by the
existing backend-neutral protocols and concrete components below; a different
Python class name does not imply a missing component or a second inference
engine.

| Required logical role | Runtime contract and concrete implementation | Scientific boundary |
|---|---|---|
| `AudioSource` | `interfaces.AudioSource`; `FileAudioSource`, `MicrophoneAudioSource`, `PlaybackAudioSource`, `RecordingAudioSource`, and `DurationLimitedAudioSource` in `audio.py` | Live and file inputs yield the same source-native frame contract. |
| `AudioClock` | `RawAudioFrame` and `NormalizedAudioFrame.capture_contract()` in `models.py`, plus the session `EventFactory` source-clock envelope in `events.py` | This is an immutable timestamp/sample-index contract, not a second mutable clock engine. Source time drives evidence and expiry; monotonic wall time measures delivery and computation. |
| `AudioNormalizer` | `interfaces.AudioNormalizer`; `StreamingAudioNormalizer` in `audio.py` | Downmixing/resampling preserves source sample, channel, clock, discontinuity, and dropped-sample provenance. |
| `SherpaStreamingASR` | `interfaces.StreamingASRAdapter`; `SherpaStreamingASRAdapter` in `asr.py` | Owns persistent native decoder state, partial/final events, endpointing, finalize, and reset. |
| `PyannoteStreamingSegmenter` | `interfaces.StreamingSegmenter`; `WorkerStreamingSegmenter` in `runtime_components.py` composed with `RollingSegmentationPlanner` and `CausalSpeechRegionTracker` in `segmentation.py` | The isolated worker performs Pyannote inference; the host exposes causal updates and records lookahead separately from compute latency. |
| `ReDimNetEmbeddingService` | `interfaces.DiarizationEmbeddingAdapter` and `interfaces.IdentityEmbeddingAdapter`; one `WorkerEmbeddingAdapter` plus `H2EmbeddingReuseRouter` | One persistent ReDimNet model may serve both roles, but role/window/preprocessing identities remain separate and reuse is allowed only after parity checks. |
| `OnlineClusterManager` | `interfaces.OnlineClusterManager`; `OnlineClusterManager` in `clustering.py` | Deterministic, session-local anonymous clusters with bounded revisions and reconciliation provenance. |
| `EnrollmentStore` | `interfaces.EnrollmentStore`; `ProtectedEnrollmentStore` and `RuntimeEnrollmentProfile` in `enrollment.py` | Permanent identities originate only from deliberate local enrollment; backend/checkpoint identity is validated. |
| `OpenSetIdentityMatcher` | Full-gallery scoring in `StreamingPipelineCoordinator`, `IdentityPolicy.effective_gate()`, and `SessionIdentityManager.observe()` in `identity.py` | This is intentionally a composition, not a duplicate matcher. It requires complete-gallery scores, Top-1 threshold, Top-1/Top-2 margin, evidence/quality gates, and calibrated hysteresis. |
| `SessionIdentityManager` | `interfaces.SessionIdentityManager`; `SessionIdentityManager` in `identity.py` plus the selected bounded memory policy | Owns tentative/confirmed/unknown/released state, source-clock expiry, `Unknown_N`, and safe session reset. |
| `TranscriptSpeakerAligner` | `interfaces.TranscriptSpeakerAligner`; `TranscriptSpeakerAligner` in `alignment.py` | Preserves original assignments, bounded retroactive revisions, identity revisions, and explicit timestamp uncertainty. |
| `ParagraphManager` | Pure deterministic `build_paragraphs()` with `TranscriptParagraph` in `paragraphs.py`, invoked by the coordinator | Paragraph policy consumes emitted transcript spans and cannot alter ASR words or speaker decisions, so it remains cheaply replayable. |
| `SpatialEvidenceInterface` | `SpatialEvidenceInterface` and disabled `NoEffectXVFPlaceholder` in `h2_portability/spatial.py` | The interface is prepared for XVF3800, but current spatial evidence is provably inert and cannot affect campaign results. |
| `PipelineCoordinator` | `interfaces.PipelineCoordinator`; `StreamingPipelineCoordinator` in `coordinator.py` | Owns lifecycle, queues, component causation, failure propagation, deterministic events, and export. |
| `ResourceMonitor` | `interfaces.ResourceMonitor`; `RuntimeResourceMonitor` in `telemetry.py` | Samples existing providers without moving inference or policy logic into monitoring/UI code. |
| `EventSink` | `interfaces.EventSink`; `OrderedJsonlEventSink` (and bounded test `MemoryEventSink`) in `events.py` | Append-only sequencing rejects event/time regression and supplies the durable labelled-event record. |

Isolated model processes are additionally owned by `WorkerSupervisor` and
`PersistentWorker` in `workers.py`. This worker boundary supplies health,
startup identity, restart, failure propagation, and graceful shutdown without
mixing Sherpa, Pyannote, and ReDimNet dependencies in one interpreter.

## Clocks and incremental operation

Source/audio time is authoritative for speech evidence, expiry, correction windows, and long-session bounds. Wall time measures computation and UI delivery. The output separates speech evidence duration, model lookahead, compute latency, queue delay, and UI/event delay.

File simulation feeds frames through the same incremental path as live microphone mode. Engineering acceleration changes pacing only; it does not batch the recording through a different inference path. A seek is rejected unless it can safely reset causal model and session state.

The required timing points are retained as follows:

| Timing point | Authoritative record |
|---|---|
| Audio capture | Source sample interval, source audio interval, capture monotonic/UTC interval, clock identity, discontinuity, and dropped-source-sample count on `RawAudioFrame`. |
| Normalized frame | Normalized 16 kHz sample/audio interval plus the complete source and resampling provenance on `NormalizedAudioFrame`; the same fields enter every event capture envelope. |
| ASR partial/final | Ordered `AsrPartialEvent`/`AsrFinalEvent` with accepted-audio interval, emitted monotonic/UTC time, native decode latency, revision ancestry, and explicit word-timestamp provenance. |
| Speech onset/offset | `SpeechActivityEvent` with region start/end, committed causal state, Pyannote lookahead, and compute latency kept separate. |
| Speaker boundary | `SpeakerBoundaryEvent` at a source-audio instant, causally linked to the anonymous-cluster update that produced it. |
| Embedding request/completion | Role/window identity and source interval on the embedding request path; `EmbeddingResult.compute_latency_ms`, cache/reuse provenance, and the causal downstream event record completion. |
| Cluster update | Ordered `AnonymousSpeakerEvent` with source interval, stable cluster/`Unknown_N` identity, revision ancestry, re-entry reason, and overlap status. |
| Identity decision | `IdentityEvidenceEvent` and causally linked `IdentityLabelEvent` with evidence time, full-gallery scores, margin, threshold identity, quality gate, decision reason, hysteresis, and emitted wall time. |
| UI label event | The UI consumes the ordered `IdentityLabelEvent`/transcript-revision stream asynchronously. Runtime emitted time, queue telemetry, and demo delivery state support UI/event-lag measurement without placing policy logic in the UI. |

Thus accelerated replay changes wall-clock pacing but never source evidence
time. Expiry, hysteresis, correction, and transcript decisions remain identical
for deterministic file replay and scientifically equivalent live frames.

## Open-set identity safety

Pairwise verification EER is diagnostic only. Product identity decisions are calibrated on the maximum score over the enrolled gallery and require both a score threshold and a Top-1/Top-2 margin, plus evidence and quality gates. Policy selection uses development speakers only; held-out raw score vectors are not exported for retuning.

A generic or anonymous label is preferred to a wrong known name. Permanent known identities can only come from deliberate local enrollment profiles. Session memory never narrows the full enrollment gallery or converts an anonymous profile into a permanent identity.

For enhanced-memory candidates, M4 may order active-roster identities first,
but a set-equality gate requires complete full-gallery scoring before the
decision. Source-time confidence decay can only release a remembered identity.
M5 cluster reconciliation uses timing and full-gallery score-signature
similarity calibrated exclusively on development-calibration identities; it
does not use reference truth or future/spatial evidence at runtime.

## Product and runtime profiles

- `AG-H2`: Sherpa Giga + H2, primary scientific/product candidate.
- `AO-H2`: Original Sherpa + H2, reduced paired ASR regression/fallback.
- `H2_REFERENCE`: native framework Pyannote/ReDim implementations.
- `H2_PORTABLE_ONNX_FP32`: separately versioned portability candidate; it is not silently substituted for the reference.

The portable candidate remains distinct until all declared component and end-to-end parity gates pass. ARM64 Linux preparation is not Raspberry Pi hardware qualification.

## Data and privacy

Audio, profiles, events, and results remain local on drive C:. Anonymous session state is volatile and is removed on reset/end. Enrollment removal is recoverable archive by default. The compact research package excludes raw datasets, generated audio, credentials, model weights, biometric vectors, and large caches.

## Failure behavior

The runtime degrades or fails explicitly for missing models, invalid profiles, unsupported audio, worker failure, queue pressure, device loss, and stop requests. It never blocks the UI on inference. The scientific controller finishes the current atomic case before a graceful stop, preserves valid checksum-bound work, and resumes only missing or invalid work.

## Scientific lifecycle

Development search and policy replay precede one immutable freeze. The held-out queue is generated only from the freeze identity and cannot reuse baseline placeholder tuning. Final analysis does not select or recalibrate from held-out outcomes.
