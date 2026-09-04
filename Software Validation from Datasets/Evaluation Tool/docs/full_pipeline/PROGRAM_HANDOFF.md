# Just-Peachy Complete Speech-Pipeline Program Handoff

## Canonical status

- Program: `just_peachy_full_pipeline_program_v1`
- Protocol: `full_pipeline_protocol.v1`
- Prompt: `2 of 8`
- Current status: `COMPLETE_COMMON_DEMO`
- Prompt-0 lock: `COMPLETE_FULL_PIPELINE_PROGRAM_LOCK` (preserved)
- Prompt-1 runtime: `COMPLETE_STREAMING_RUNTIME` (preserved)
- Logical matrix: `18` pipelines (`2 ASR × 3 anonymous diarization × 3 identity`)
- Long scientific campaign started: **no**
- Bounded Prompt-1 component/enrollment/file smokes: **passed**
- Bounded Prompt-2 AG-H5/AG-H2/AO-H4 application smoke: **passed**
- Physical microphone capture performed by Prompts 1–2: **no**
- Tier C production selection: **not selected**

Prompt 0 locked the program specification. Prompt 1 implemented the reusable
true-streaming runtime and qualified its components with bounded local smokes.
Prompt 2 built one matrix-driven Tk desktop/CLI demonstration application on
that runtime and qualified three required presets with bounded local inference.
This is not the 18-pipeline scientific campaign, a production-policy freeze, or
evidence from a physical Beaker/microphone recording.

## Read these files first

Later prompts must use this set as the authoritative context instead of
reconstructing the program from older chats:

1. `runs/full_pipeline_program/PROGRAM_STATE.json` — machine-readable current
   completion state and hashes of the canonical artifacts.
2. `configs/automated_evaluation/full_pipeline_matrix.v1.yaml` — exact axes,
   component and policy identities, all 18 rows, tiers, and selection rules.
3. `configs/automated_evaluation/schemas/full_pipeline_contracts.v1.schema.json`
   — additive common event, enrollment, session, and result contracts.
4. `docs/full_pipeline/PIPELINE_MATRIX.md` — human-readable matrix rationale,
   evidence anchors, and tier gates.
5. `docs/full_pipeline/LICENSE_AND_ASSET_MANIFEST.md` — code/checkpoint/data
   provenance, acquisition, attribution, redistribution, and deployment review.
6. `app/full_pipeline/README.md` — runtime architecture, inputs, outputs, exact
   PowerShell/Anaconda commands, caching, and operating boundaries.
7. `app/full_pipeline_demo/README.md` — common desktop/CLI application,
   enrollment flow, exports, privacy rules, and exact launch commands.
8. This file — execution boundaries, reusable code, qualification evidence,
   result roots, limitations, and continuation rules.

All paths in the canonical files are relative to the Evaluation Tool root unless
explicitly stated otherwise.

## Roots and output ownership

Repository root on the locking machine:

```text
C:\Users\amiri\Documents\GitHub\just-peachy
```

Evaluation Tool root:

```text
C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
```

Portable root names for future work:

| Purpose | Evaluation-Tool-relative root |
|---|---|
| Program definition and state | `runs/full_pipeline_program` |
| Full-pipeline scientific results | `JustPeachyResults/full_pipeline` |
| Full-pipeline research summaries | `JustPeachyResearchSummaries/full_pipeline` |
| Restart-safe campaign workspaces | `automated_runs` |
| Common schemas | `configs/automated_evaluation/schemas` |
| Program documentation | `docs/full_pipeline` |

Do not write future results to `C:\Users\amiri\JustPeachy*`. Existing project
policy places Evaluation Tool results below the repository-local
`JustPeachyResults`/`JustPeachyResearchSummaries` roots. Dataset assets remain
external according to the repository's portable resolver policy; no raw audio or
archive belongs in Git.

## Scope

The Prompt-1 product/evaluation runtime now supports:

- AO and AG incremental ASR;
- Pyannote Segmentation 3.0 speech segmentation;
- anonymous diarization and clustering with DW, DR, or DE;
- open-set enrolled identity with IW, IR, or IE;
- stable session-local anonymous identities and `Unknown_N` labels;
- incremental labelled transcript revisions;
- microphone capture and incrementally replayed audio-file simulation;
- enrollment recording and import;
- restart-safe status, telemetry, provenance, and complete results.

XVF3800 integration and model fine-tuning remain outside this program. Prompt 1
used bounded local inference only, did not run the long 18-pipeline campaign, and
did not change any frozen scientific result.

## Exact component aliases

### ASR

| Alias | Component ID | Environment | Current qualification boundary |
|---|---|---|---|
| AO | `sherpa_onnx` | `onnx` | Persistent native streaming is bound to the common runtime and passed the bounded Prompt-1 smoke. Prior large scientific evidence remains segment-contract evidence. |
| AG | `sherpa_onnx_libri_giga_zipformer_2023_06_21` | `onnx` | Persistent native streaming passed the bounded Prompt-1 smoke through a runtime policy overlay; the frozen large-study `native_streaming_replay=false` identity remains unchanged. |

Both consume mono 16 kHz audio. Neither component declares a scientific minimum
audio duration; the configured `0.66 s` value is tail padding, not a minimum.

### Anonymous diarization

| Alias | Pipeline ID | Segmentation environment | Embedding environment | Status |
|---|---|---|---|---|
| DW | `modular_pyannote_wespeaker` | `credential-diarization` | `wespeaker` | Held-out standalone primary |
| DR | `modular_pyannote_redimnet2` | `credential-diarization` | `redimnet2` | Held-out standalone efficiency fallback |
| DE | `modular_pyannote_speechbrain_ecapa` | `credential-diarization` | `core-cpu` | Development comparator; not held out |

These are generated cross-environment scientific pipelines implemented by
`CrossEnvironmentPyannoteEmbeddingClustering`, not ordinary single-environment
component-registry entries. All share the locked Pyannote Segmentation 3.0 asset
and current segmentation/window/clustering settings declared in the matrix.

### Enrolled identity

| Alias | Backend ID | Environment | Dimension | Minimum input |
|---|---|---:|---:|---:|
| IW | `wespeaker` | `wespeaker` | 256 | 0.75 s |
| IR | `redimnet2_b2_speaker_embedding` | `redimnet2` | 192 | 0.50 s |
| IE | `speechbrain_ecapa` | `core-cpu` | 192 | 0.75 s |

The matrix is the authority for config, backend, model, asset, requirements, and
current environment hashes. Do not substitute a friendly model name for those
identities.

## Hybrid mapping

The hybrid label is a shorthand for anonymous diarization plus identity; it is
not another matrix axis:

| Label | Pair | Program meaning |
|---|---|---|
| H1 | DW + IW | development comparator |
| H2 | DR + IR | frozen hybrid anchor |
| H3 | DR + IW | development comparator |
| H4 | DW + IR | frozen hybrid anchor |
| H5 | DR + IE | frozen hybrid anchor |
| H6 | DW + IE | development comparator |
| C7 | DE + IW | new challenger, uncalibrated |
| C8 | DE + IR | new challenger, uncalibrated |
| C9 | DE + IE | new challenger, uncalibrated |

The complete matrix combines each of AO/AG with each of these nine pairs. Frozen
H2/H4/H5 thresholds in the matrix are research anchors only; they are not Beaker
production thresholds and may not be transplanted into a new gallery or protocol.
C7–C9 have no frozen hybrid decision calibration and must not be assigned an
invented threshold.

## Policy identities

Each human pipeline ID is `fullpipe_v1_<asr>_<diarization>_<identity>`. The
`fullpipe_v1` namespace binds these result-affecting policies, and every row also
records them explicitly:

- protocol: `full_pipeline_protocol.v1`;
- streaming: `full_pipeline_incremental_stream.v1`;
- hybrid/open-set decision: `full_pipeline_open_set_decision.v1`;
- enrollment: the exact IW/IR/IE scientific policy ID and file hash in the
  matrix.

Any result-affecting change to chunking, endpointing, enrollment aggregation,
threshold/margin calibration, evidence accumulation, overlap treatment, label
hysteresis, or revision behavior requires a new policy identity and, when it
changes matrix semantics, a new protocol/pipeline identity.

Raw similarity scores are not probabilities. Production decisions require
development-only maximum-gallery calibration, a Top-1 threshold, a Top-1/Top-2
margin, minimum evidence, and frozen evaluation parameters. Pairwise EER is a
diagnostic and is not the production identity threshold.

## Evaluation tiers

- **Tier A:** all 18 receive adapter qualification, end-to-end smoke, controlled
  development, held-out controlled evaluation, common metrics, and the common
  result schema.
- **Tier B:** exactly AO/AG × H2/H4/H5 are mandatory (six pipelines). At most two
  additional challengers may advance, and only from development evidence showing
  a distinct non-dominated position.
- **Tier C:** at most three production candidates may be selected only after
  held-out and extended testing. Prompt 0 selects none.

Selection is constraint- and Pareto-based. There is no arbitrary weighted score.
The ordered twelve priorities and the separation between technical and
license/provenance deployment rankings are frozen in the matrix.

## Common contracts

`full_pipeline_contracts.v1.schema.json` defines these 15 public types:

```text
AudioFrame                 AsrPartialEvent            AsrFinalEvent
SpeechActivityEvent        SpeakerBoundaryEvent       AnonymousSpeakerEvent
IdentityEvidenceEvent      IdentityLabelEvent          TranscriptRevisionEvent
PipelineStatusEvent        ResourceTelemetryEvent      EnrollmentSample
EnrollmentProfile          SessionState                PipelineResult
```

They are additive contracts. Do not silently mutate or relabel older frozen
batch/case schemas. Adapters may map old artifacts into the new contracts while
preserving their original identity and checksum.

Important semantic rules:

- sample/capture and processing clocks must remain distinct and named;
- a raw cosine score is `raw_score` with `score_type=cosine_similarity`, never a
  probability unless a separate calibration method and identity exist;
- the session owns stable anonymous IDs and `Unknown_N` allocation;
- tentative and confirmed known identities are separate states;
- transcript and identity changes are explicit, causal revisions;
- biometric vectors belong in protected referenced artifacts with checksums, not
  duplicated into general event logs;
- completion artifacts retain failures, missing items, warnings, checksums, and
  reproducibility/provenance references.

## Cross-environment architecture boundary

The pipeline cannot safely import all inference stacks into a single Python
process. The current Prompt-1 coordinator preserves isolated environment profiles:

1. coordinator/control and contracts in the repository `.venv`;
2. AO/AG ASR in `onnx`;
3. Pyannote segmentation in `credential-diarization`;
4. anonymous/identity embeddings in `wespeaker`, `redimnet2`, or `core-cpu`;
5. stable artifact/event exchange across subprocess boundaries with exact
   config/model/environment identities.

Do not resolve incompatibility by modifying a frozen environment in place. A
runtime-specific environment change requires a new recorded freeze and
qualification.

## Reusable implementation anchors

Use these areas before inventing another controller or schema:

- `app/full_pipeline/` — current backend-neutral streaming coordinator, audio
  sources, persistent workers, caches, identity state, alignment, artifacts, and
  CLI;
- `configs/automated_evaluation/full_pipeline_runtime.v1.yaml` — runtime policy;
- `scripts/run_full_pipeline_runtime.ps1` — supported PowerShell entry point;

- `app/campaign_executor/` — strongest restart-safe campaign/controller base;
- `app/inference_pipeline/contracts.py` — existing batch pipeline result types;
- `app/inference_pipeline/asr/streaming.py` — AO streaming replay abstraction;
- `app/inference_pipeline/realtime/stitching.py` — transcript stitching and
  provisional/committed word behavior;
- `app/inference_pipeline/realtime/speaker_state.py` — unknown/tentative/confirmed
  evidence accumulation;
- `app/inference_pipeline/speaker_matching/base.py` — rich raw speaker scores,
  threshold, and margin decisions;
- `app/hybrid_speaker_attribution/attribution.py` — causal open-set attribution
  behavior and research `Unknown_N` allocation;
- `app/inference_pipeline/enrollment/schema.py` and
  `app/speaker_protocol/contracts.py` — enrollment and backend identity sources;
- `app/resource_telemetry/` — UTC/monotonic resource samples and component spans;
- `scripts/live_mic_realtime.py` — current microphone/incremental-WAV prototype,
  bounded queues, diagnostics, stitching, and delayed identity;
- `app/artifact_contracts/` and `app/prediction_io/` — protected legacy artifact
  validation/adaptation boundaries.

The current `app/gui/` is a batch dataset evaluator, not a live session and
enrollment GUI. The current live diagnostics JSONL has mixed unversioned row
types and must not be frozen as the common event contract.

## Canonical prior evidence

The matrix records hashes for frozen selections. These are the human-readable
result roots later prompts should consult:

| Research area | Canonical result/report root | Current conclusion carried forward |
|---|---|---|
| Matched Common Voice 60+ ASR | `JustPeachyResults/asr_commonvoice/commonvoice_60plus_asr_v1/campaign_commonvoice_60plus_asr_v1_10a3c45df81c` | AG technically outperformed AO on that panel; neither result proves live partial-event behavior. |
| Speaker deployment replay | `JustPeachyResults/speaker_embedding_deployment/speaker_embedding_deployment_v1_4779270a5bf0` | Open-set gallery calibration and margin are required. |
| Enrollment/live duration | `JustPeachyResults/speaker_enrollment/speaker_enrollment_live_v2_5107db9ab304` | Completed 624 configurations; useful design evidence, not a frozen Beaker threshold. |
| Standalone diarization final | `JustPeachyResults/diarization_finalists_final_evaluation` | DW primary and DR efficiency fallback survived held-out evaluation; DE was not held out. |
| Hybrid development | `JustPeachyResults/hybrid_speaker_attribution_product_v2_development` | Frozen H2/H4/H5 finalists. |
| Hybrid final | `JustPeachyResults/hybrid_speaker_attribution_product_v2_final_evaluation` | H5 primary, H2 fallback, H4 reference; more policy work and real Beaker data still required. |

Prior component-isolation results are evidence anchors, not substitutes for the
future end-to-end evaluation of ASR words, anonymous clusters, identity labels,
latency, revisions, reliability, and resource use together.

## Licensing and deployment gates

Technical ranking must remain separate from production eligibility. The detailed
manifest is authoritative; the most important current gates are:

- the repository has no top-level `LICENSE`, `COPYING`, or `NOTICE`, so repository
  redistribution permission is unresolved;
- AO runtime/model use is technically available, but exact upstream training
  provenance and archive redistribution review are incomplete;
- AG must not be called commercially cleared while its GigaSpeech training-data
  review remains unresolved;
- Pyannote Segmentation 3.0 requires gated credentialed acquisition and should not
  be bundled merely because a local cache exists;
- WeSpeaker checkpoint use requires CC BY 4.0 attribution;
- SpeechBrain code and checkpoint provenance are different questions, and its
  five-file runtime cache versus two-file frozen identity/naming discrepancy must
  be resolved before a production asset freeze.

## Known scientific and implementation limitations

1. AO/AG completed large evaluations used an offline/segment comparison contract.
   Prompt 1 proves bounded native partial/final/reset behavior, but scientific
   time-to-first-text, time-to-stability, and revision distributions are not yet
   established.
2. AG streaming uses a separately recorded runtime overlay and does not mutate the
   frozen large-study `native_streaming_replay=false` configuration. Scientific
   streaming qualification and GigaSpeech deployment-provenance review remain.
3. DE was development-only and showed a standalone speaker-confusion safeguard
   warning; it is not a held-out finalist.
4. C7–C9 are new program labels with no old registry entry, frozen hybrid
   threshold, or held-out evidence.
5. The old hybrid research replay remains causal over completed diarization and
   did not include ASR/cpWER. Prompt 1 adds a true incremental runtime, but its
   evidence is bounded functional qualification rather than a scientific result.
6. Common Voice is prompted/read, device-variable speech, not representative of
   far-field overlapping Beaker conversation.
7. CHiME and VOiCES evidence has bounded task-specific reference limitations and
   cannot be silently promoted to fully labelled end-to-end identity evidence.
8. Real Beaker recordings remain required before fine-tuning or a production
   threshold/policy freeze.
9. Tier C cannot be selected until end-to-end held-out and extended metrics exist.

## Prompt-1 true-streaming runtime status

The runtime owns one session clock and event sequence while keeping AO/AG,
Pyannote segmentation, and IW/IR/IE in persistent isolated workers. It provides
bounded capture/backpressure handling, native Sherpa stream state, rolling
diarization with explicit lookahead, stable `Unknown_N` allocation, frozen-anchor
H2/H4/H5 decision policy, conservative transcript relabelling, protected
enrollment profiles, eight content-addressed cache kinds, live atomic status,
resource telemetry, provenance, `SessionState`, and `PipelineResult` artifacts.

Canonical bounded qualification evidence:

| Evidence | Path | Result |
|---|---|---|
| Component coverage | `JustPeachyResults/full_pipeline/component_smoke/prompt1_streaming_runtime_final_20260823/component_smoke.json` | PASS; three runs collectively exercised 2 ASRs, 3 diarizers, and 3 identity backends; 511 contract-valid events, 3 results, 3 session states, and zero run errors. |
| Enrollment/profile smoke | `JustPeachyResults/full_pipeline/enrollment_smoke/prompt1_final_20260823/enrollment_smoke.json` | PASS for IW/IR/IE; 12 locked enrollment documents validated. Same-segment repetition intentionally makes this a mechanics/profile-integrity smoke, not diverse production enrollment evidence. |
| Functional H2 stream | `JustPeachyResults/full_pipeline/runtime_sessions/prompt1_h2_file_final_20260823/result.json` | COMPLETE; AO+DR+IR, 183 events, zero warnings/errors, delayed identity states, and transcript revisions. Enrollment and probe share source audio, so this is deliberately leaky functional evidence, not accuracy evidence. |
| Focused tests | `tests/full_pipeline` | 54 passed; no complete repository test suite was run. |

No physical microphone capture was performed. The microphone path is implemented
and its model-free capture/queue behavior is tested, but hardware/device behavior
requires an operator-controlled bounded smoke. No Tier A/B/C scientific campaign
was started.

Exact repo-root PowerShell commands:

```powershell
# Inspect the locked 18 IDs without inference.
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action MatrixStatus

# Bounded accelerated file smoke (default checked local WAV).
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action FileSmoke -PipelineId fullpipe_v1_ao_dr_ir -DurationSec 10

# Operator-controlled 10-second microphone smoke; this was not run by Prompt 1.
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action MicrophoneSmoke -PipelineId fullpipe_v1_ao_dr_ir -DurationSec 10

# Build protected smoke profiles for all three identity backends. Separate
# invocations are intentional so powershell.exe -File binds each backend exactly.
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action EnrollmentSmoke -Backend wespeaker
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action EnrollmentSmoke -Backend redimnet2_b2_speaker_embedding
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action EnrollmentSmoke -Backend speechbrain_ecapa

# Bounded 2-ASR/3-diarizer/3-identity component coverage.
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action ComponentSmoke -DurationSec 10

# Read the newest status, or add -OutputRoot with a specific session directory.
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action Status
```

## Prompt-2 common demonstration application

Prompt 2 adds one backend-neutral application in `app/full_pipeline_demo`. It
loads every preset through `FullPipelineMatrix`; it does not duplicate model
selection or inference logic in Tk. `DemoSessionManager` constructs the exact
Prompt-1 runtime in a background thread and exposes pause, resume, stop,
immutable between-session switching, durable event cursors, and post-join
exports. Tk work is restricted to view state and user controls.

Implemented application surfaces:

- live microphone device enumeration, selected device/rate/channels,
  start/pause/resume/stop, optional local recording, session time, queue and
  processing state;
- exact-live-path file replay at 1.0x or accelerated engineering pace, optional
  local playback, pause/resume, synchronized durable events, and export;
- local-only three-take enrollment by microphone or labelled WAV import, with
  duration/RMS/peak/clipping checks, embedding consistency, selective repeat,
  backend/checkpoint/profile identity, archive/restore, and immutable rebuild;
- a simple user view with transcript, `Unknown_N`/friendly name, and explicit
  tentative/confirmed state, plus a research view with raw score type, Top-1/
  Top-2 margin, evidence duration, threshold, ASR/segmentation/cluster state,
  RTF, CPU/RAM, queue latency, and events. Raw cosine is never presented as a
  probability;
- all 18 matrix rows, with AO/AG crossed with H2/H4/H5 highlighted as the six
  frozen research anchors. The other 12 remain structurally runnable but
  Unknown-only until their open-set decision calibration is resolved;
- checksum-bound local exports containing labelled JSONL/TXT/MD, the exact
  event log, split pipeline/component/profile identities, telemetry, failure
  diagnostics, provenance/state/result references, and optional explicitly
  authorized input audio. No network upload exists and biometric vectors are
  excluded from general exports.

Primary code and instructions:

| Purpose | Path |
|---|---|
| Desktop UI | `app/full_pipeline_demo/ui.py` |
| Session/thread/control layer | `app/full_pipeline_demo/session.py` |
| Matrix-derived preset catalog | `app/full_pipeline_demo/presets.py` |
| Local enrollment workflow | `app/full_pipeline_demo/enrollment.py` |
| Session export | `app/full_pipeline_demo/exports.py` |
| CLI and strict bounded smoke | `app/full_pipeline_demo/cli.py`, `app/full_pipeline_demo/smoke.py` |
| PowerShell entry point | `scripts/run_full_pipeline_demo.ps1` |
| User/developer runbook | `app/full_pipeline_demo/README.md` |
| Focused tests | `tests/full_pipeline_demo`, `tests/full_pipeline/test_demo_runtime_controls.py` |

Canonical Prompt-2 evidence:

```text
JustPeachyResults/full_pipeline/demo_smoke/
  prompt2_common_demo_strict_final_20260823/
    common_demo_smoke.json
    enrollment/
    sessions/
    exports/
```

The strict summary is `PASS` with input SHA-256
`c3ebf5bc3f4ecc92c99367e554c2bfae34e551655cc3415144bdc507566b0d36`.
It uses the portable external CMU Arctic `arctic_a0281.wav` asset and repeats
that one known-speaker clip for three mechanics-only enrollment takes. The raw
dataset remains outside Git.

| Preset | Pipeline | Events | Labelled interval | Label | Result |
|---|---|---:|---|---|---|
| AG-H5 | `fullpipe_v1_ag_dr_ie` | 85 | 0.000–3.995 s | `Local Smoke Speaker` / `anon_0001` | COMPLETE |
| AG-H2 | `fullpipe_v1_ag_dr_ir` | 85 | 0.000–3.995 s | `Local Smoke Speaker` / `anon_0001` | COMPLETE |
| AO-H4 | `fullpipe_v1_ao_dw_ir` | 85 | 0.000–3.995 s | `Local Smoke Speaker` / `anon_0001` | COMPLETE |

All three sessions recorded zero errors, exact pipeline/config/component/profile
identities, nonempty durable event logs, checksum-valid exports, and causal
accepted-audio-interval alignment without inventing backend word timestamps.
The second and third sessions prove immutable model switching with joined
predecessor IDs and distinct session/output roots.

This remains bounded functional qualification. It does not establish accuracy,
far-field/overlap behavior, production thresholds, device latency, or physical
microphone reliability. No scientific campaign or physical microphone capture
was run by Prompt 2.

Exact repository-root PowerShell launch commands are maintained in
`app/full_pipeline_demo/README.md`. The shortest entry points are:

```powershell
# Desktop demo.
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Demo

# Direct 30-second live CLI (physical capture; not run by Prompt 2).
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action Live -PipelineId "fullpipe_v1_ag_dr_ie" -DurationSec 30 -Device "0"

# Full real-time file simulation.
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action File -PipelineId "fullpipe_v1_ag_dr_ir" `
  -InputPath "C:\path\to\speech.wav" -Pace 1.0

# Three-WAV local enrollment. Scalar arguments are intentional for -File.
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_demo.ps1" `
  -Action EnrollImport -PipelineId "fullpipe_v1_ag_dr_ir" `
  -DisplayName "Alice" `
  -Wav1 "prompt_1=C:\enrollment\alice_1.wav" `
  -Wav2 "prompt_2=C:\enrollment\alice_2.wav" `
  -Wav3 "prompt_3=C:\enrollment\alice_3.wav"
```

## Prompt-3 reproducible full-pipeline evaluation infrastructure

Prompt 3 adds `app/full_pipeline_evaluation` without changing any frozen source
protocol. The package owns the additive protocol builder, exact metric catalog,
pure scorers, checksum-bound common result tree, restart-safe controller,
measured monitor, and Prompt-1 runtime adapter. Model logic remains in the
backend-neutral runtime and isolated workers.

Canonical prepared protocol:

| Field | Locked value |
|---|---|
| Protocol | `full_speech_pipeline_v1_b0c88389194b` |
| Development | 807 cases; identity `88eaacaf3e874b6c68db228b8e6d30392f5221bc12491c868a5fb321d9a62301` |
| Evaluation | 10,102 cases; identity `d3764bd6c897ca147ab5cf9caa5cea1a75d6e329cd6b398af0025085db878a92` |
| Total source cases | 10,909 |
| Matrix rows | 18 |
| Accuracy/resource jobs | 432 |
| Planned pipeline/mode case executions | 392,724 |
| Campaign identity | `full_speech_pipeline_v1_b55c7cd3d711` |
| Scorer/reuse policy | `full-pipeline-evaluation-scorers.v2`; exact evaluation/runtime source trees checksum-bound |
| Evaluation package SHA-256 | `03a432e92beb354de0b1089b7d835580320e15feeee9f917b535ae59b04cd566` |
| Streaming runtime package SHA-256 | `e99e4f09657f1534ce9ab8f57a13e1960a0b43ee52cb4804d85bbbeeb03cf963` |

Audit, Prepare, default Validate, deep `Validate -VerifyAudio`, and Plan all
passed. The protocol preserves exact transcripts, global speakers, sample
placement, known/unknown overlays, gallery size, scenarios, overlap, and source
hashes. Development/evaluation mixture speakers and enrollment-gallery speakers
are explicitly disjoint; enrollment clips are disjoint from evaluated mixtures.
Installed reference hydration is checked before campaign work. Native material
is separated into `ami_cpwer_and_diarization`, `ami_diarization_only`, and
`chime6_diarization_only` strata so unsupported references cannot contaminate a
supported score. VOiCES remains acoustic/ASR diagnostic only.

Frozen Stage-11 logical paths remain
`benchmarks/stage11/<protocol>/...`. The physical resolver additionally checks
`JustPeachyGeneratedData/<protocol>/...`, matching the already-consolidated local
layout without changing a logical path, content hash, or frozen identity.

Every completed result uses the same tree:

```text
run.json
pipeline_identity.json
model_assets.json
events.jsonl
predictions/transcript.jsonl
predictions/labelled_transcript.jsonl
predictions/diarization.rttm
references/
metrics/{summary,asr,diarization,identity,streaming,resources}.json
diagnostics/
checksums.json
```

Every catalogued metric is `computed`, `undefined`, or `unsupported` with a
reason. cpWER computes only with the frozen `lowercase_whitespace.v1`
normalization and `per_recording` permutation scope; it is never fabricated.
Diarization scores are per recording with exact UEM/collar/overlap policy, and
known/unknown galleries are built attempt-locally from frozen reserved clips.
The scientific worker never falls back to a user's demo/enrollment store.
Biometric vectors are excluded from the result tree.

The SQLite/WAL controller provides immutable job/reuse identities, leases and
heartbeats, partial attempt preservation, restart/retry, graceful in-case stop,
exact filters, development freeze binding, and result-tree/checksum validation
before Validate/Freeze/Analyze/Collect. One host-wide process lock prevents a
resource run from overlapping another invocation. A single accuracy invocation
may run at most two jobs, further reduced by measured memory; resources are
serial. ETA is based on selected-job completed audio versus observed wall time
and remains `calculating` when no active measured rate exists.

Canonical model-free Prompt-3 evidence:

```text
JustPeachyResults/full_pipeline/evaluation_infrastructure_smoke/
  prompt3_final_20260823/
    infrastructure_smoke.json
    perfect_result/
    failure_result/
    restart_state/
```

The smoke is PASS: the perfect tree is valid/reusable; the intentional failure
tree is valid/non-reusable; perfect WER and DER are zero; output failure and
retry semantics are exercised. It processed no dataset audio, loaded no model,
downloaded nothing, evaluated zero pipelines, and started no long campaign.

Exact repository-root management commands:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Audit
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Prepare
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Validate -VerifyAudio
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Plan
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\monitor_full_pipeline_evaluation.ps1" `
  -Follow -IntervalSeconds 30
```

`RunDevelopment`, `Freeze`, and `RunEvaluation` are implemented for later
prompts but were deliberately not invoked. Prompt 4 must start from the prepared
protocol/campaign identities above and must not treat the infrastructure smoke
as accuracy evidence.

## Continuation rules for Prompts 4–8

Prompts 4–8 remain `PENDING_UNSPECIFIED`, not failed or blocked. Each later prompt
must:

1. read `PROGRAM_STATE.json`, the matrix, contracts, and this handoff first;
2. validate the program lock before work;
3. preserve all frozen source results and hashes;
4. use the declared result roots and common contracts;
5. record result-affecting deviations under a new policy/protocol identity;
6. keep development calibration separate from held-out evaluation;
7. never infer production eligibility from technical performance alone;
8. update the machine-readable program state and relevant README when it adds
   code or changes completion state.

## Program-lock and focused runtime/demo validation

PowerShell, from the Evaluation Tool root:

```powershell
& "..\..\.venv\Scripts\python.exe" -m app.full_pipeline_program validate --json
& "..\..\.venv\Scripts\python.exe" -m app.full_pipeline_program validate --verify-assets --json
& "..\..\.venv\Scripts\python.exe" -m pytest tests\automated_evaluation\test_full_pipeline_program_lock.py -q
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline -q
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_demo -q
& "..\..\.venv\Scripts\python.exe" -m ruff check app\full_pipeline app\full_pipeline_demo tests\full_pipeline tests\full_pipeline_demo
```

Anaconda Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
call .venv\Scripts\activate.bat
cd "Software Validation from Datasets\Evaluation Tool"
python -m app.full_pipeline_program validate --json
python -m pytest tests\automated_evaluation\test_full_pipeline_program_lock.py -q
python -m pytest tests\full_pipeline -q
python -m pytest tests\full_pipeline_demo -q
```

The optional asset command reads and hashes local files. It does not load a model,
download an asset, process audio, or start a campaign. The focused runtime/demo
tests are model-free/fake-worker tests; bounded real-model evidence is retained
in the canonical result roots above.
