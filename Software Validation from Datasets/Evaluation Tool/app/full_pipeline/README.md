# Just-Peachy true-streaming full-pipeline runtime

## Exact-duration sample quantization

Runtime audio windows are materialized by quantizing the requested duration
once and adding it to the quantized start sample. This prevents binary
floating-point endpoint drift from shortening an exact 0.50-second, 16 kHz
window from 8,000 to 7,999 samples. Cache and embedding-reuse provenance records
derive the end sample from the materialized PCM length. The runtime does not
pad audio and does not relax any embedding backend's minimum-duration rule.

## Purpose and scope

This package is the backend-neutral runtime for one live or incrementally read
audio source flowing through ASR, anonymous diarization, enrolled-speaker
identity, and speaker-attributed transcript revision. It implements the locked
`full_pipeline_protocol.v1` contracts and resolves one of the 18 pipelines in
`configs/automated_evaluation/full_pipeline_matrix.v1.yaml`.

The commands in this README are bounded operational smokes. They do **not** run
the 18-pipeline scientific campaign, calibrate a challenger, select a Tier-C
pipeline, or establish production/Beaker readiness. Model downloads are
disabled; all required checkpoints and isolated environments must already be
present locally.

## Runtime architecture and interfaces

```text
AudioSource -> AudioNormalizer -> StreamingPipelineCoordinator
                                      |
                                      +-> persistent AO/AG ASR -> partial/final text
                                      |
                                      +-> rolling segmentation -> diarization windows
                                                                  |
                                                                  +-> embedding
                                                                  +-> online clustering
                                                                  +-> open-set identity
                                      |
                                      +-> transcript/speaker aligner
                                      +-> ordered events, status, telemetry, artifacts
```

The coordinator runs in the repository `.venv`. Model-specific objects stay in
persistent JSONL-RPC workers in their locked environments: `onnx` for AO/AG,
`credential-diarization` for Pyannote Segmentation 3.0, and `wespeaker`,
`redimnet2`, or `core-cpu` for embeddings. Do not import these incompatible
model stacks into the coordinator or modify a frozen environment in place.

The public structural contracts are in `app/full_pipeline/interfaces.py`:

| Interface | Main input | Main output/responsibility |
|---|---|---|
| `AudioSource` | File or microphone capture | Ordered `RawAudioFrame` records plus source clock |
| `AudioNormalizer` | `RawAudioFrame` | Mono 16 kHz `NormalizedAudioFrame` with provenance |
| `StreamingASRAdapter` | Normalized frames | Ordered ASR partial, final, and reset records |
| `StreamingSegmenter` | Normalized frames | Causal `SpeechRegionUpdate` records |
| `DiarizationEmbeddingAdapter` | `EmbeddingWindow` | Anonymous-diarization `EmbeddingResult` |
| `OnlineClusterManager` | Embedding and its window | Stable session-local anonymous cluster updates |
| `IdentityEmbeddingAdapter` | `EmbeddingWindow` | Enrolled-identity `EmbeddingResult` |
| `EnrollmentStore` | Backend ID/profile ID | Checksum-bound protected enrollment profiles |
| `OpenSetIdentityPolicy` / `SessionIdentityManager` | Cluster evidence and gallery scores | Unknown, tentative, or confirmed identity state |
| `TranscriptSpeakerAligner` | ASR, anonymous-region, and identity events | Explicit transcript/speaker revisions and snapshot |
| `EventSink` | Common-contract event | Ordered append-only JSONL |
| `ResourceMonitor` | Runtime process/session | UTC/monotonic CPU, RAM, disk, and available GPU telemetry |
| `WorkerSupervisor` | Typed JSONL-RPC request | Start, health, restart, and close of an isolated worker |
| `PipelineCoordinator` | All adapters plus a source | Complete `PipelineResult` and restart-readable status |

The implementation entry points are `factory.py` (`build_file_runtime` and
`build_microphone_runtime`), `coordinator.py`, and `cli.py`. `python -m
app.full_pipeline` is the supported CLI surface. The PowerShell wrapper is
`scripts/run_full_pipeline_runtime.ps1`.

File-source shutdown is thread-safe and idempotent: a user/coordinator stop may
race the producer cleanup without closing the same libsndfile handle twice.
An in-flight bounded file read completes its native read section before the
handle is closed, while realtime pacing is interrupted immediately.

## Inputs

- `PipelineId`: one exact ID returned by `MatrixStatus`. The wrapper default is
  `fullpipe_v1_ao_dr_ir` (AO + DR + IR, the H2 anchor).
- File input: the wrapper default is
  `artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav`. Audio is
  frame-read, downmixed, and resampled to the internal mono 16 kHz contract.
- Microphone input: an optional `Device` name/index and a required bounded
  duration. File queues block; microphone queues drop the oldest frame when the
  bounded queue is full. Drops remain visible in status and metrics.
- Enrollment input: a protected enrollment-store root whose profiles match the
  selected backend config and model hashes. With no override, runtime profiles
  live below `JustPeachyResults/full_pipeline/enrollment_profiles`.
- Output override: `OutputRoot` selects one explicit run directory. If omitted,
  file and microphone sessions receive a UTC/UUID session directory under the
  default runtime-results root.

## AO/AG native-state semantics

`SherpaStreamingASRAdapter` in `asr.py` wraps the native session implemented by
`app/inference_pipeline/asr/sherpa_onnx_adapter.py`.

- One worker loads one recognizer and opens one mutable Sherpa stream for the
  session. Successive 100 ms mono 16 kHz frames advance that same decoder state;
  they are not transcribed as independent files or utterances.
- A changed hypothesis emits a partial. The stable prefix is the longest common
  normalized word-token prefix between consecutive changed hypotheses. Finals
  mark the full normalized hypothesis stable. Source offsets, decode latency,
  endpoint state, revision number, and finalization reason are retained.
- Endpoint detection is an explicit runtime overlay with provenance policy
  `full_pipeline_sherpa_endpoint_backend_defaults.v1`. It does not rewrite the
  frozen AO or AG YAML. An endpoint emits a final and automatically creates or
  resets the decoder stream for the next utterance while leaving the model
  loaded.
- End-of-input finalization adds the component's configured tail padding, calls
  `input_finished`, drains ready decoder steps, and closes that session. Manual
  reset discards only decoder state and starts a fresh stream on the same loaded
  recognizer.
- A per-chunk decode-step guard fails loudly instead of allowing a recognizer to
  spin forever.
- AG's frozen segment-study setting `native_streaming_replay=false` remains
  unchanged. The new `open_stream` surface is separate from `transcribe`; it
  enables a native runtime smoke but does not retroactively turn AG's prior
  segment evaluation into native-streaming evidence. AG's GigaSpeech commercial
  provenance review also remains unresolved.

## Incremental diarization: 10 seconds / 5 seconds

Pyannote Segmentation 3.0 is not represented as a zero-lookahead model. The
runtime uses a symmetric 10-second rolling analysis window and commits only its
first half. It therefore records 5 seconds of history context and a conservative
5-second **algorithmic lookahead**. Compute latency is measured separately from
that lookahead. The rolling step is 0.75 seconds and the last partial window is
flushed at end of input.

Speech regions are converted to 1.5-second embedding windows at a 0.75-second
step, with a 0.75-second minimum. Online cosine-centroid clustering uses the
locked 0.35 threshold, stable session-local IDs, and a 0.5-second short-turn
attachment gap. These streaming policies are additive runtime policies; they do
not relabel frozen batch diarization results as true-streaming results.

## Shared cache coverage

`cache.py` declares exactly the eight Prompt-1 cache products. Every key binds
the source content/range, windowing, preprocessing, producer/model,
configuration, role, and typed upstream dependencies; entries are atomic and
payload-checksummed. The current runtime wiring is:

| Cache product | Current use |
|---|---|
| Decoded/resampled audio | File replay loads/publishes normalized frames; microphone audio is not cached by default. |
| Pyannote segmentation | Cross-session load/publish for exact rolling chunks. |
| Diarization windows | Load/publish of causal window plans including prior planner state. |
| Diarization embeddings | Cross-session load/publish with role `anonymous_diarization`. |
| Identity embeddings | Cross-session load/publish with role `identity_matching`; it cannot alias diarization embeddings. |
| Enrollment embeddings | Enrollment smoke uses the shared cache with role `enrollment_embedding`. |
| ASR finalized results | Final-only results are published for reuse; partial timing is never replayed from this cache. |
| Score matrices | Open-set raw cosine score maps load/publish with probe, gallery, profile aggregation, policy, and embedding dependencies. |

Decoded live-microphone audio requires an explicit cache-key opt-in and the
production microphone factory does not opt in. Native ASR still runs for a
streaming session even when a finalized result exists, because reusing a final
cannot reproduce partial-event timing, endpoint timing, or revision behavior.

## Frozen identity anchors and unresolved rows

Only these hybrid labels have frozen runtime identity calibration:

| Label | Anonymous diarization + identity | Score threshold | Runtime status |
|---|---|---:|---|
| H2 | DR + IR | `0.5265351286789879` | Frozen anchor |
| H4 | DW + IR | `0.5331755752703802` | Frozen anchor |
| H5 | DR + IE | `0.4572960706169966` | Frozen anchor |

They also require a 0.03 Top-1/Top-2 margin, at least 2.0 seconds of evidence,
minimum embedding consistency 0.35, and two consecutive passes before a known
identity is confirmed. These historical research thresholds are not universal
or production Beaker thresholds.

H1, H3, and H6 remain development comparators; C7, C8, and C9 are new
challengers. All six are unresolved in this runtime. They emit raw cosine scores
and safe `Unknown_N` labels but cannot emit a known-speaker decision until a
development-only calibration is registered and frozen. Never invent or borrow a
threshold for them.

## H2 product modes and executable tuning

The H2 factories accept the optional keywords `product_mode` and
`runtime_tuning`. Omitting both preserves the legacy 18-pipeline behavior. The
three exact product modes are:

| Mode | Unenrolled-speaker display | Volatile session behavior |
|---|---|---|
| `H2_KNOWN_ONLY` | Generic `Unknown` | No anonymous voice profile survives a turn; permanent enrolled profiles remain available. |
| `H2_SESSION_ANONYMOUS` | Session-local `Speaker_N` | Anonymous continuity is session-only and is deleted on reset/end. Confirmed enrolled names still use fresh identity evidence. |
| `H2_SESSION_MEMORY_ENHANCED` | Session-local `Speaker_N` | Adds bounded active-roster ordering, source-time confidence release, causal calibrated fragment reconciliation, and safe confirmed-name carryover for attached short turns; full-gallery scoring remains mandatory. |

`H2RuntimeTuning` is an immutable, JSON-serializable, SHA-256-bound contract.
Mappings are validated fail-closed: an unsupported key or mismatched serialized
hash raises an error before workers start. Executable controls cover the rolling
segmentation hop and thresholds, ReDim windowing, online clustering, R1/R2 model
worker sharing, checksum-qualified R3/R4 embedding reuse, include/exclude
overlap policy, recent/accumulated identity evidence, open-set decision
parameters, 0–1000 ms bounded boundary correction, T1–T4 paragraph
construction, expiry, and hard memory limits. Current capability gates still
reject shorter/zero Pyannote lookahead, deferred overlap identity,
ambiguous-overlap display, and XVF/spatial result effects.

### H2 ReDim R3/R4 execution semantics

`embedding_reuse.py` keeps the anonymous-diarization and identity request
interfaces separate. R3 can reuse a diarization vector only when the two
role-specific requests have one identical scientific-equivalence fingerprint:
normalized float32 PCM SHA-256, source/assignment sample bounds, duration,
preprocessing, normalization, backend, model, checkpoint, and backend config.
R4 applies the same exact gate plus identity-specific duration, finite-sample,
level, voicing, and clipping checks. Any mismatch, missing candidate, or R4
quality rejection explicitly falls back to a fresh identity embedding.

R4 does not replace identity scoring: accepted segment vectors still enter the
existing duration-weighted, bounded recent/accumulated cluster aggregation and
then the frozen open-set policy. Per-window private observations record exact
input/fingerprint hashes, vector hashes, cosine/max-absolute agreement,
reuse/fallback reasons, quality scalars, and call counters without serializing
the vectors. Telemetry reports diarization/identity calls, reuse hits, embedded
and reused audio seconds, initialization/startup, model instances/bytes, RTF,
RSS at the evaluation layer, and synchronous queue-delay status. An unavailable
quantity is labelled unsupported rather than estimated.

R3/R4 are rejected by ordinary H2 execution unless
`embedding_reuse_qualification_sha256` binds the completed development parity
and combined selection. R1/R2 keep their historical v2 tuning serialization
and hashes. Raw full-gallery score diagnostics are disabled by default and are
accepted only through an explicitly checksum-bound development execution;
held-out/evaluation use rejects the flag before inference.

The application/controller normally supplies this mapping. For a bounded local
Python integration, use the same environment as the runtime:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "..\..\.venv\Scripts\python.exe" -c `
  "from pathlib import Path; from app.full_pipeline.factory import build_file_runtime; r=build_file_runtime(pipeline_id='fullpipe_v1_ag_dr_ir', input_path=Path(r'artifacts\realtime_test_audio\aew_rxr_eey_arctic_a0301_concat.wav'), duration_sec=10, product_mode='H2_SESSION_MEMORY_ENHANCED', runtime_tuning={'segmentation_hop_sec':0.75,'boundary_correction_ms':0}); print(r.runtime_tuning.identity_sha256)"
```

This command constructs the runtime and prints its tuning identity; calling
`r.run()` would load local models and run inference. Interactive file/live use
is documented in `app/full_pipeline_demo/README.md` and keeps inference outside
the UI.

### H2 ONNX runtime profile

`H2_REFERENCE` remains the factory default. The separately versioned
`H2_PORTABLE_ONNX_FP32` profile replaces only Pyannote Segmentation 3.0 and the
shared ReDimNet2-B2 embedding execution with checksum-verified FP32 ONNX
graphs. ASR, preprocessing, clustering, enrollment, open-set policy, alignment,
and event contracts remain the common runtime code. Both graph paths and both
expected SHA-256 values are mandatory; no model is downloaded and a mismatch
fails before inference.

Use `python -m app.h2_portability runtime-file` or `runtime-live` for the
supported explicit command surface. Full commands, inputs, outputs, the frozen
desktop parity result, and ARM64 limitations are in
`app/h2_portability/README.md`. The portable profile has bounded Windows/x86-64
component and end-to-end parity evidence. It is not yet ARM64 hardware
qualified.

While a session is paused, `reset_session(preserve_transcript=True)` resets
decoder and anonymous state, and
`clear_anonymous_memory(preserve_transcript=True)` deletes only volatile
clusters/mappings. Passing `False` deletes the current transcript too. Both
operations preserve deliberate enrollment profiles and loaded model workers.
The reset is synchronized at a source-frame boundary; event logs remain an
append-only audit and are never reused as biometric profiles.

H2-specific outputs add:

- `transcript/paragraphs.json`, containing the selected T1–T4 paragraph policy;
- `diagnostics/boundary_corrections.jsonl`, containing original and corrected
  assignments;
- `diagnostics/embedding_reuse_observations.jsonl` and
  `diagnostics/embedding_reuse_telemetry.json`, containing private
  hashes/scalars and measured execution counters, never raw vectors;
- `diagnostics/identity_score_diagnostics.jsonl`, empty in ordinary live/file
  sessions and populated only for an authorized private development run;
- `metrics/runtime_metrics.json` → `bounded_session_state`;
- `manifests/provenance.json` → `h2_runtime_tuning` and its identity hash;
- live `status.json` fields `h2_product_mode`, `runtime_tuning_sha256`, and,
  for enhanced mode, `session_memory`.

## PowerShell wrapper commands (run from the repository root)

First enter the repository root:

```powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy"
```

`MatrixStatus` is inference-free and prints the locked 18 IDs and config hashes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action MatrixStatus
```

`FileSmoke` runs the default AO-H2 pipeline on at most 10 seconds of the bounded
repository smoke WAV:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action FileSmoke `
  -PipelineId fullpipe_v1_ao_dr_ir `
  -DurationSec 10
```

`MicrophoneSmoke` captures and processes exactly 10 seconds. Use `-Device
"<device name>"` when the default input device is not correct:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action MicrophoneSmoke `
  -PipelineId fullpipe_v1_ao_dr_ir `
  -DurationSec 10
```

`EnrollmentSmoke` creates three checksum-bound **smoke-only** IR templates from
the same bounded segment of the WAV. Repetition prevents the concatenated
three-speaker fixture from becoming an invalid mixed-speaker profile, but it is
not diverse or production-quality enrollment. With no `-Backend`, it uses
`redimnet2_b2_speaker_embedding`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action EnrollmentSmoke
```

To smoke another supported enrollment backend, run the action separately with
`-Backend wespeaker` or `-Backend speechbrain_ecapa`.

`ComponentSmoke` runs three bounded pipeline selections that collectively touch
both ASR components, all three diarization components, and all three identity
components. It is coverage smoke, not all 18 pipelines:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action ComponentSmoke `
  -DurationSec 10
```

`Status` is inference-free and returns the most recently updated default runtime
session:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
  -Action Status
```

To query one explicit run, append `-OutputRoot "<absolute session directory>"`
to `Status`. The same option on a smoke action fixes its output directory.

## Anaconda Prompt / direct CLI equivalents

The controller must use the repository `.venv`, even when the shell is an
Anaconda Prompt. These commands call that interpreter directly, so the active
Conda environment cannot silently change the controller dependencies:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"

"..\..\.venv\Scripts\python.exe" -m app.full_pipeline matrix-status

"..\..\.venv\Scripts\python.exe" -m app.full_pipeline file-smoke --pipeline-id fullpipe_v1_ao_dr_ir --input "artifacts\realtime_test_audio\aew_rxr_eey_arctic_a0301_concat.wav" --duration-sec 10

"..\..\.venv\Scripts\python.exe" -m app.full_pipeline microphone-smoke --pipeline-id fullpipe_v1_ao_dr_ir --duration-sec 10

"..\..\.venv\Scripts\python.exe" -m app.full_pipeline enrollment-smoke --input "artifacts\realtime_test_audio\aew_rxr_eey_arctic_a0301_concat.wav"

"..\..\.venv\Scripts\python.exe" -m app.full_pipeline component-smoke --input "artifacts\realtime_test_audio\aew_rxr_eey_arctic_a0301_concat.wav" --duration-sec 10

"..\..\.venv\Scripts\python.exe" -m app.full_pipeline status
```

CLI option names use hyphens; wrapper parameter names use PowerShell casing.
Use `--output-root "<absolute path>"`, `--enrollment-root "<absolute path>"`,
or `--device "<device name or index>"` on the applicable CLI command.

## Bounded-smoke warning

`FileSmoke`, `MicrophoneSmoke`, `EnrollmentSmoke`, and `ComponentSmoke` load real
local models and may use substantial CPU, RAM, and time. Run only one smoke set
at a time unless the machine has been explicitly qualified for concurrent model
workers. The default wrapper duration is 10 seconds. Do not pass
`-DurationSec 0` to file or component smoke: the wrapper then omits the duration
limit and the full input file is consumed. Smoke profiles and microphone audio
are test/private data, not production enrollment.

`MatrixStatus` and `Status` do not import or run model adapters and are safe for
frequent monitoring.

## Results and monitoring

All paths below are relative to the Evaluation Tool root:

| Action/data | Default location |
|---|---|
| File/microphone session | `JustPeachyResults/full_pipeline/runtime_sessions/<session_id>` |
| Protected enrollment profiles | `JustPeachyResults/full_pipeline/enrollment_profiles` |
| Enrollment smoke | `JustPeachyResults/full_pipeline/enrollment_smoke/<UTC stamp>` |
| Component smoke | `JustPeachyResults/full_pipeline/component_smoke/<UTC stamp>` |
| Cross-session content cache | `JustPeachyResults/full_pipeline/_shared_cache` |

The run directory is printed as `output_root`. During a run, `status.json` is
atomically refreshed and `events/events.jsonl` is append-only and flushed after
each ordered event. After successful finalization, the important artifacts are:

- `result.json` — checksum-bound `PipelineResult`, completion state, counts,
  warnings, errors, and references;
- `session_state.json` — locked `SessionState` with event/revision pointers,
  stable `Unknown_N` allocation, identity state, profile hashes, and queue/drop
  counters;
- `transcript/final_transcript.json` and `transcript/revisions.jsonl`;
- `speakers/anonymous.jsonl`, `speakers/identity_evidence.jsonl`, and
  `speakers/identity_labels.jsonl`;
- `metrics/runtime_metrics.json` and `telemetry/resource_samples.jsonl`;
- `diagnostics/asr_native_events.jsonl` and
  `diagnostics/unresolved_identity_scores.jsonl`;
- `manifests/provenance.json`, `manifests/license_reference.json`, and
  `manifests/checksums.json`.

Identity evidence and enrollment data are biometric-sensitive; do not upload or
copy them as ordinary logs.

To monitor the latest default session every two seconds from PowerShell, run
this from the repository root and stop it with `Ctrl+C`:

```powershell
while ($true) {
  Clear-Host
  powershell -NoProfile -ExecutionPolicy Bypass -File `
    ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_runtime.ps1" `
    -Action Status
  Start-Sleep -Seconds 2
}
```

For a known output directory, set `$runRoot` and monitor its ordered event log:

```powershell
$runRoot = "C:\absolute\path\to\the\session"
Get-Content -LiteralPath (Join-Path $runRoot "events\events.jsonl") -Tail 20 -Wait
```

`Status` reports progress and component health; presence of `result.json` with
`completion_state: complete` is the completion condition. A smoke PASS is not a
scientific result and must not be promoted into the frozen campaign evidence.

## Prompt-1 qualification evidence and targeted tests

The current-tree bounded component package is
`JustPeachyResults/full_pipeline/component_smoke/prompt1_streaming_runtime_final_20260823`.
Its three complete selections collectively exercised 2 ASRs, 3 diarizers, and
3 identity backends. All 511 events, 3 `SessionState` documents, and 3
`PipelineResult` documents validated against the locked contract schema.

The all-backend profile smoke is
`JustPeachyResults/full_pipeline/enrollment_smoke/prompt1_final_20260823`;
all 12 public enrollment documents validated. The H2 functional file smoke is
`JustPeachyResults/full_pipeline/runtime_sessions/prompt1_h2_file_final_20260823`.
It used the same source for enrollment and probing, so its identity labels prove
only runtime wiring—not accuracy or generalization. No microphone capture was
performed automatically; use the bounded command above when the operator has
selected and authorized an input device.

Run only the focused model-free runtime tests from the Evaluation Tool root:

```powershell
& "..\..\.venv\Scripts\python.exe" -m pytest tests\full_pipeline -q
& "..\..\.venv\Scripts\python.exe" -m pytest tests\test_h2_embedding_reuse.py tests\full_pipeline_evaluation\test_h2_worker_firewalls.py tests\full_pipeline_evaluation\test_worker_integration.py -q
& "..\..\.venv\Scripts\python.exe" -m ruff check app\full_pipeline tests\full_pipeline
```

The H2 mode/reset/expiry/boundary regression subset can also be run in an
Anaconda Prompt without neural inference:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
C:\Users\amiri\anaconda3\envs\moca-reg\python.exe -m pytest tests\full_pipeline\test_h2_product_modes.py tests\full_pipeline\test_identity_alignment.py tests\full_pipeline\test_event_adapters.py -q
C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe -m pytest tests\test_h2_embedding_reuse.py tests\full_pipeline_evaluation\test_h2_worker_firewalls.py tests\full_pipeline_evaluation\test_worker_integration.py -q
```

To run only the source-control and concurrent-stop regression coverage:

```powershell
& "..\..\.venv\Scripts\python.exe" -m pytest `
  tests\full_pipeline\test_demo_runtime_controls.py `
  tests\full_pipeline\test_runtime_core.py -q
```
