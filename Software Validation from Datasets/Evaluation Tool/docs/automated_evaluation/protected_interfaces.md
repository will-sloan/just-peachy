# Protected Interfaces and Version Policy

This is the Stage 0 change boundary. Later phases may orchestrate these interfaces but must not replace, silently reinterpret, or bypass them.

## Existing protected behavior

| Boundary | Authoritative implementation | Invariant |
|---|---|---|
| Dataset registry, normalization, filtering, and path rebase | `app/datasets`, `app/metadata`, `app/utils/paths.py` | Use normalized metadata and deterministic filtering; do not create a duplicate dataset loader. |
| Augmentation and RIR convolution | `app/augmentation` | Only approved clean rows receive controlled augmentation; native-condition rows remain native-only unless a later public decision changes that rule. Never double-augment native noisy/reverberant audio. |
| Model execution bridge | `app/model_runner/base.py`, `app/model_runner/external_stub.py`, `app/model_runner/pipeline_runner.py` | Inference consumes `record["inference_audio_path"]`; `recording_id`, `utt_id`, and record bounds remain stable. |
| Pipeline contracts | `app/inference_pipeline/contracts.py` | Keep `EvaluationRecord`, `AudioSegment`, component output contracts, and `PipelineOutput.validate_identity` compatible. |
| Minimum prediction schema | `PipelineOutput.to_utterance_prediction_row()` | `predictions/utterances.jsonl` contains exactly `recording_id`, `utt_id`, `start_sec`, `end_sec`, `speaker_label`, and `text`. The literal unknown speaker label is preserved and scored, not omitted. |
| Scoring and grouped metrics | `app/scoring`, `app/metrics` | Reuse WER/grouping logic. New metrics may be additive optional artifacts; they must not silently alter existing metrics. |
| Plots and reports | `app/plotting`, `app/reporting` | Existing single-run output remains readable. Campaign comparison is additive. |
| Existing execution surfaces | `app/cli`, GUI modules, simulation runner, `ExternalStubRunner` | Ordinary CLI, GUI, simulation, and external-stub behavior remain operational. |
| Component model logic | `app/inference_pipeline/{vad,segmentation,asr,speaker_embedding,speaker_matching,diarization}` | Stage 0 inventories and qualifies implementations; it does not refactor model algorithms. |

## Audio boundary confirmed from code

`load_audio()` reads the record-bounded portion of `inference_audio_path` with SoundFile as float32, applies the configured channel policy (mono by default), and resamples to 16 kHz by default. The in-memory `LoadedAudio.waveform` is channel-first Torch audio. ASR and speaker adapters accept an `AudioSegment`, crop to the record/segment bounds, select a channel or downmix, and present mono float32 samples to the backend. File-only backends receive a temporary bounded PCM16 WAV where required. Diarization prefers the already cropped/processed waveform so that it cannot silently process audio outside the Evaluation Tool record bounds.

The framework supports both whole-file and bounded-record inputs. Active inference is offline per record/segment even when a backend model is internally streaming. Real-time scripts are separate execution surfaces and are not the automated benchmark contract.

## Output boundary confirmed from code

Component outputs are typed as speech regions, audio segments, ASR transcripts with optional words/timestamps/confidence, speaker embeddings with model/runtime metadata, speaker decisions, and diarization turns. `PipelineOutput` may retain detailed diagnostics and transcript items, but only the six protected fields are emitted to the minimum prediction JSONL. Future RTTM, embedding, confidence, word-timing, and resource files must be additive and versioned.

## Public-contract version policy

Existing artifacts remain readable. A reader must dispatch on a declared schema/hash version and reject unknown versions clearly; it must not guess. Additive optional fields may be introduced within a version only when old readers can safely ignore them. Any canonicalization or identity change is a breaking change and requires a new major contract identifier plus migration/read compatibility tests.

The Stage 0 identifiers below are now either released or retained as existing contracts:

| Contract ID | Current status |
|---|---|
| `benchmark-manifest.v1` | Released and frozen in Stage 2. Uncompressed Parquet is authoritative; committed byte-stable fixtures protect the wire form. |
| `manifest-canonicalization.v1` | Released and frozen in Stage 2 for deterministic manifest content, ordering, and metadata. |
| `manifest-hash.v1` | Released and frozen in Stage 2; full-file SHA-256 identifies the authoritative Parquet bytes. |
| `scenario-definition.v1` | Released and frozen in Stage 2 with JSON Schema and committed golden fixtures. |
| `scenario-canonicalization.v1` | Released and frozen in Stage 2; NFC UTF-8 canonical JSON defines identity bytes. |
| `scenario-hash.v1` | Released and frozen in Stage 2; global IDs are `scenario_` plus the first 12 lowercase hexadecimal characters of the full SHA-256. |
| `artifact-registry.v1` | Released and frozen in Stage 3; artifact paths, producers, formats, requirements, validators, checksums, privacy classes, and consumers are explicit. |
| `artifact-registry.v2` | Released additively in Stage 5. It inherits every v1 definition, upgrades only the resource sample schema, and registers component spans, resource summary, and availability artifacts. v1 remains unchanged and readable. |
| `resource-usage.v2` | Released in Stage 5 as typed scenario samples with explicit nullability, availability reasons, monotonic ordering, and no absolute/sensitive paths. |
| `component-spans.v1` | Released in Stage 5 for nested high-resolution component timing and optional synchronized CUDA-event duration. |
| `resource-summary.v1` | Released in Stage 5 for reconciled counts, peaks, percentiles, phase/component summaries, availability, and warnings. |
| `campaign-manifest.v1` | Released in Stage 3 with detached SHA-256; execution state is deliberately not part of this immutable definition. |
| `checksums.v1` | Released in Stage 3; every materialized scenario artifact using the SHA-256 policy is indexed, while the checksum manifest excludes itself. |
| `environment-fingerprint.v1` | Released in Stage 3; static software/hardware identity is audit data and never changes a Stage 2 scenario ID. |
| `scenario-status.v1` | Released in Stage 3; state and reconciled counts are mutable during execution and final only when atomically published as successful. |
| `campaign-database.v1` | Implemented in Stage 4 as transactional SQLite state. It records execution metadata only and never participates in global scenario identity. Schema migration requires a new explicit database version. |
| `campaign-execution-state.v1` | Implemented in Stage 4 with explicit transition, lease, heartbeat, retry, stop, and recovery semantics. Detailed executor state remains in SQLite; `scenario-status.v1` remains the Stage 3 artifact-completion summary. |
| `worker-assignment.v1` | Implemented in Stage 6. It binds global scenarios to one worker and exact campaign, benchmark, component, model, seed, Git, and environment-profile identities. |
| `worker-result-transfer.v1` | Implemented in Stage 6 with portable complete file inventories, tree hashes, assignment identity, and environment fingerprint. SQLite is excluded. |
| `merged-result-index.v1` | Implemented in Stage 6. Byte-identical duplicates may share one indexed result; conflicting bytes are rejected without overwrite. |
| `merge-validation-report.v1` | Implemented in Stage 6 for transfer errors, missing work, duplicates, conflicts, and machine/environment differences. |
| `analysis-input-index.v1` | Implemented in Stage 6 as the portable input handoff for later comparative analysis and final analysis-manifest generation. |
| `component-registry.v1` | Implemented and validated in Stage 0. |
| `evaluation-environment-profiles.v1` | Implemented and validated in Stage 0. |

Any change that alters manifest bytes or scenario identity semantics requires a new explicit contract version. Readers must continue to validate the declared version and must never silently recompute an old scenario under new rules. Stage 2 contract release does not authorize campaign execution behavior.

## Protected decision constants

- deterministic seed: `3800`;
- reference ASR: Whisper Base;
- smoke ASR: Whisper Tiny;
- required real candidate: Whisper Small;
- excluded ASR: Whisper Medium/Large/Turbo families;
- unknown speaker output: literal `Unknown`, preserved for scoring;
- controlled RIR scope: dining room, one unresolved bedroom file, and restaurant only;
- `h044_ParkingLot_4txts.wav`: Parking Lot, excluded, never a kitchen replacement;
- GPU default: one GPU-heavy scenario at a time until controlled concurrency qualification passes;
- CPU contract gate first; CUDA gate immediately next.
- Stage 5 execution remains one scenario subprocess at a time; telemetry does not authorize GPU concurrency.
