# Reproducible full-pipeline evaluation

## Purpose

This package is the additive `full_speech_pipeline_v1` evaluation system for
the 18 pipeline rows locked in the authoritative full-pipeline matrix. It
prepares deterministic development/evaluation manifests, runs the Prompt-1
backend-neutral streaming runtime, scores every supported scientific view,
publishes one checksum-bound result layout, and maintains restart-safe campaign
state. It does not alter any earlier frozen ASR, diarization, speaker, or hybrid
protocol.

Prompt 3 qualifies only the infrastructure with model-free synthetic cases. It
does **not** start the development or evaluation campaign.

## Scientific boundaries

- Only already-installed data and frozen source protocols are accepted.
- Network download and implicit model acquisition are forbidden.
- Controlled development and evaluation speakers remain disjoint.
- Enrollment clips and evaluated mixtures are checked for disjointness.
- Evaluation material is never promoted into development.
- VOiCES is limited to the supported acoustic/ASR diagnostics.
- Native AMI/CHiME-6 metrics are emitted only when their frozen references
  satisfy the metric prerequisites.
- cpWER is explicitly `unsupported` unless complete per-speaker reference and
  hypothesis streams use the implemented `lowercase_whitespace.v1`
  normalization and `per_recording` permutation scope.
- Matched resource jobs are serial and are never compared as though concurrent
  accuracy telemetry were equivalent.
- One cross-process host lock covers each controller invocation. A single
  accuracy invocation may run two jobs internally, but a second invocation
  cannot overlap it or a serial resource run.
- No weighted composite score is created.

## Inputs

- Matrix:
  `configs/automated_evaluation/full_pipeline_matrix.v1.yaml`
- Runtime policy:
  `configs/automated_evaluation/full_pipeline_runtime.v1.yaml`
- Additive protocol declaration:
  `configs/automated_evaluation/full_speech_pipeline_v1.yaml`
- Installed frozen manifests and their exact SHA-256 identities listed in that
  protocol declaration
- Local model assets and isolated environments already qualified by Prompts 0-1
- Optional exact `-PipelineId` and `-ProtocolId` filters for campaign actions

The prepared protocol is written under:

```text
benchmarks/full_pipeline/full_speech_pipeline_v1/
  protocol_summary.json
  source_audit.json
  checksums.json
  development/
    case_manifest.jsonl
    references/speaker_attributed_transcript.jsonl
    identity/identity_overlays.jsonl
    enrollment/enrollment_registry.jsonl
  evaluation/
    ...same layout...
```

Raw audio is referenced by logical path and hash; it is not copied into Git.
Frozen Stage-11 logical paths remain
`benchmarks/stage11/<protocol>/...`; the portable resolver maps their generated
WAVs to `JustPeachyGeneratedData/<protocol>/...` when that is the installed
physical location. This alias does not change any logical path, source hash, or
scientific identity. `Validate -VerifyAudio` checks the resolved files and
their recorded SHA-256 values without running inference.

## Outputs

Controller state defaults to:

```text
automated_runs/full_speech_pipeline_v1/
  campaign_manifest.json
  campaign.sqlite3
  campaign_progress.json
  controller_state.json
  validation.json
  plan.json
  attempts/
  analysis/
```

Every completed pipeline/protocol result has the same checksum-bound layout:

```text
run.json
pipeline_identity.json
model_assets.json
events.jsonl
predictions/transcript.jsonl
predictions/labelled_transcript.jsonl
predictions/diarization.rttm
references/
metrics/summary.json
metrics/asr.json
metrics/diarization.json
metrics/identity.json
metrics/streaming.json
metrics/resources.json
diagnostics/
checksums.json
```

Prompt-3 and synthetic callers continue to use the immutable v1 layout above.
Prompt-4 development jobs opt in to additive result-tree v2, where the sole
layout difference is `events.jsonl.gz` in place of `events.jsonl`. The gzip
stream is deterministic (`mtime=0`), lossless, validated one NDJSON row at a
time, and checksum-bound as compressed bytes. The worker streams it while each
case runs, scores each recording before releasing its event objects, and removes
the completed case's transient runtime directory only after all public evidence
has been extracted. Failed case directories are retained for diagnosis. This
keeps memory and disk bounded without changing transcripts, metrics, event
ordering, scientific identities, or legacy v1 results. Readers must accept both
event paths and may use Python's `gzip.open(..., "rt", encoding="utf-8")` for
v2.

The compact diagnostic directory also includes
`diagnostics/per_case_metrics.jsonl`. Each row records the complete supported,
undefined, and unsupported metric reports for one atomic case, together with
its case/source identity, duration, and reference-speaker IDs. It deliberately
contains no embeddings. Campaign-level metric JSON remains authoritative for
point estimates; the per-case rows preserve dependence for case- and
speaker-level bootstrap intervals instead of treating clips from one speaker as
independent observations.

Raw maximum-gallery candidate vectors and predicted-overlap score diagnostics
are copied into the compact result tree only for development calibration. The
untouched evaluation split still computes the already-frozen identity metrics,
but its raw biometric score vectors are not exported and cannot be fed back
into threshold selection. This is an explicit held-out firewall, not missing
metric evidence.

Each real evaluation attempt also owns one deterministic worker-warmup WAV at
`attempts/<job>/attempt_<N>/shared_runtime_work/warmup/mono16k_10s.wav`.
Shared lazy workers and the frozen enrollment-gallery embedder both reference
that attempt-stable file. Completed per-case cleanup may therefore remove
`runtime_cases/<case>` without breaking a worker that starts only after a later
cache miss. A retry creates its own attempt-stable warmup file; it never relies
on a prior attempt or a deleted case directory.

Result documents use one same-directory atomic writer. On a transient Windows
sharing violation it retries the identical `os.replace` operation with bounded
exponential backoff; it does not delete or rewrite the destination between
attempts. Exhaustion re-raises the first permission error, and cleanup is
limited to the writer's exact UUID-named temporary file. This allows a graceful
stop to publish terminal `stopped` evidence instead of becoming `failed` solely
because an indexer briefly held `run.json`.
Its additive document schema is
`configs/automated_evaluation/schemas/full_pipeline_evaluation_result.v2.schema.json`;
the v1 schema and files are not modified.

The SQLite campaign queue uses the rollback journal with `synchronous=FULL`.
Journal mode and schema are created only while bootstrapping an absent or empty
database. A later process opening an existing queue performs `quick_check` and
read-only schema/journal verification; it does not rerun DDL or request a
journal transition on the live controller. One process-wide lock per resolved
database path serializes transactions across the controller, both job threads,
and their lease keepalives. The controller
polls the durable stop flag once every 0.5 seconds and publishes the result into
one in-memory event. The runtime's 0.1-second stop watcher reads only that event;
it does not open ten SQLite connections per second per active job. This keeps
graceful-stop latency bounded while removing high-churn connection and journal
reconfiguration traffic from the inference path.

SQLite `quick_check` must pass when a store first opens and again before a run
is finalized. A queue exception sets the same in-memory stop event, prevents
submission of every still-pending job, lets already-started runtimes stop, and
records a fail-closed controller error without treating queue damage as a model
failure. The controller never auto-repairs or overwrites a damaged database;
preserve that workspace for forensics and prepare a fresh additive campaign.
Checksum-bound result trees remain independent evidence, but source edits in
this package change the campaign's evaluation-package hash and therefore its
reuse identity.

Every catalogued metric is present as `computed`, `undefined`, or
`unsupported`; unsupported metrics contain a reason. Biometric vectors are
never placed in the public result tree.

Every job and campaign identity binds SHA-256 digests of the exact evaluation
package and Prompt-1 streaming-runtime source tree. A result-affecting source
edit therefore invalidates reuse even if a human-readable version label was not
changed.

## Metric views

The precise definitions, units, direction, and prerequisites are canonical in
`app/full_pipeline_evaluation/metrics.py`. The scorers cover:

- ASR: WER, CER, substitutions, deletions, insertions, output failures.
- Streaming: first non-empty/readable partial, stable prefix, endpoint-to-final,
  revisions, token/word churn, final WER, and long-stream stability.
- Anonymous diarization: DER/JER, miss, false alarm, confusion, boundaries,
  count error, fragmentation, merge contamination, short turns, and re-entry.
- Identity: named/wrong/false-known/generic/uncovered duration, Unknown_N
  consistency, split/merge, cold/warm behavior, stable-name latency, revisions,
  FPIR, and FNIR.
- Speaker-attributed transcription: cpWER (only behind its evidence gate),
  attributed WER, word-label accuracy, jointly correct word rate,
  wrong-speaker count/time, unlabeled rate, and retroactive corrections.
- UX: first/stable text, first anonymous label, tentative and confirmed names,
  wrong-name dwell, revisions, UI/event lag, dropped audio, and stall time.
  Stable-name latency and wrong-name dwell are derived from complete
  time-aligned identity decision intervals when no redundant precomputed UI
  annotation is supplied; censored episodes remain explicit.
  The runtime worker marks the first known reference turn per identity as cold
  and later turns as warm for scoring only, and derives non-contiguous
  reference-turn re-entry episodes without feeding reference information into
  inference.
- Resources: component/total RTF, CPU/GPU availability, peak RSS, startup,
  model/cache bytes, queue depth, throughput, failures, and retries.

## PowerShell commands (recommended)

Run from the repository root in Windows PowerShell or Anaconda Prompt:

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy"

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Audit

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Prepare

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Validate

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Plan

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Smoke `
  -OutputRoot ".\Software Validation from Datasets\Evaluation Tool\JustPeachyResults\full_pipeline\evaluation_infrastructure_smoke\prompt3_manual"

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Status
```

Read-only monitoring:

```powershell
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\monitor_full_pipeline_evaluation.ps1" `
  -Follow -IntervalSeconds 30
```

The monitor derives ETA from observed completed-audio/wall-time progress. It
shows `calculating` until enough work has completed; it never invents an ETA.

## Campaign commands (do not run for Prompt 3)

These commands are provided for the later campaign prompts. `Freeze` requires
all development jobs to have valid checksum-bound results. `RunEvaluation`
refuses to start without that immutable gate.

```powershell
# Accuracy jobs: at most two, further reduced by measured available memory.
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action RunDevelopment -MeasurementMode accuracy -ParallelJobs 2 `
  -PipelineId fullpipe_v1_ag_dr_ie

# Matched resources: always serial.
powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action RunDevelopment -MeasurementMode resources -ParallelJobs 1 `
  -PipelineId fullpipe_v1_ag_dr_ie

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Freeze

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action RunEvaluation -MeasurementMode accuracy -ParallelJobs 2

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Stop

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Analyze

powershell -ExecutionPolicy Bypass -File `
  ".\Software Validation from Datasets\Evaluation Tool\scripts\run_full_pipeline_evaluation.ps1" `
  -Action Collect
```

Repeat `-PipelineId` or `-ProtocolId` for exact multi-value filters. Unknown
identities fail instead of being interpreted as fuzzy matches.

## Direct Anaconda Prompt / command-line use

No Conda activation is required when calling the repository interpreter
directly:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.full_pipeline_evaluation audit
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.full_pipeline_evaluation prepare
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.full_pipeline_evaluation validate
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.full_pipeline_evaluation plan
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m app.full_pipeline_evaluation smoke --output-root "JustPeachyResults\full_pipeline\evaluation_infrastructure_smoke\prompt3_manual"
```

If using an activated Anaconda environment, first `conda activate <your-env>`,
then replace the absolute interpreter above with `python`. Management runs from
the repository `.venv`; model components remain isolated in their selected
Prompt-1 worker environments.

## Targeted development checks

These are model-free and do not download data or run the 18-pipeline campaign:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m pytest tests\full_pipeline_evaluation -q
"C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" -m ruff check app\full_pipeline_evaluation tests\full_pipeline_evaluation
```

The synthetic smoke publishes one perfect result and one intentional failure,
validates checksums/reuse semantics, and exercises retry-safe controller state.
