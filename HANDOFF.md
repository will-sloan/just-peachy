# Just-Peachy Combined Evaluation Tool — Codex Handoff

Read this file first when a new Codex session takes over Evaluation Tool work.
It describes the complete combined evaluator, the boundaries between its
subsystems, the paths that carry scientific identity, and the safe operator
entrypoints.

## 1. Repository snapshot and worktree safety

At the time this handoff was authored:

```text
REPOSITORY = C:\Users\amiri\Documents\GitHub\just-peachy
BRANCH = codex/edge-component-expansion
BASELINE_HEAD = 4a170baf5d2a2236650508f6e582f1eb85557a78
UPSTREAM = origin/codex/edge-component-expansion
BASELINE_ORIGIN_RELATIONSHIP = 0 ahead / 0 behind
```

The handoff edit itself may be uncommitted. The following Evaluation Tool files
were already operator-owned worktree changes and must be preserved, inspected,
and excluded from unrelated staging:

```text
Software Validation from Datasets/Evaluation Tool/runs/edge_backend_qualification/edge-cpu.json
Software Validation from Datasets/Evaluation Tool/runs/edge_backend_qualification/moonshine-edge.json
Software Validation from Datasets/Evaluation Tool/runs/edge_backend_qualification/onnx-edge.json
Software Validation from Datasets/Evaluation Tool/runs/extended_backend_qualification/extended-local.json
Software Validation from Datasets/Evaluation Tool/runs/extended_backend_qualification/model_asset_inventory.json
Software Validation from Datasets/Evaluation Tool/runs/extended_backend_qualification/onnx.json
Software Validation from Datasets/Evaluation Tool/runs/extended_backend_qualification/wespeaker.json
Software Validation from Datasets/Evaluation Tool/artifacts/research_queue_logs/
```

Always begin with:

```powershell
git status --short
git branch --show-current
git rev-parse HEAD
git status -sb
```

Never use `git reset --hard`, `git clean`, `git restore .`, `git checkout -- .`,
or `git add .`. Do not rewrite or delete completed campaigns to make the tree
look clean.

## 2. What “combined Evaluation Tool” means

There is one Evaluation Tool with several layers. They share the same dataset,
pipeline, prediction, scoring, artifact, and reporting contracts.

```text
Normalized metadata + external raw audio
  -> deterministic selection or frozen benchmark manifest
  -> optional runtime-only augmentation/native condition
  -> resolved component pipeline
  -> VAD -> diarization -> segmentation -> ASR -> embedding -> matching
  -> standardized predictions and explicit failures
  -> scoring, plots, reports, and resource telemetry
  -> typed/checksummed scenario artifacts
  -> campaign merge, analysis, and release evidence
```

The layers are:

1. **Legacy/ordinary evaluator** — per-dataset selection, GUI/CLI, simulation,
   external stub, configured inference, augmentation, scoring, plots, reports.
2. **Configured speech pipeline** — composes qualified VAD, segmentation, ASR,
   speaker embedding, speaker matching, and diarization adapters.
3. **Automated campaign framework** — frozen manifests/scenarios, deterministic
   identities, persistent state, retries, stop/resume, telemetry, validation,
   exchange, merge, analysis, and release gates.
4. **Edge research layer** — generates deterministic screen, streaming, combo,
   and large catalogs, then delegates execution to the campaign framework.
5. **Specialized protocols** — leakage-safe Stage 10 speaker evaluation and
   Stage 11 diarization evaluation using their own typed artifact registries.

Do not build a second evaluator for a new model. Add/qualify the component,
register its assets/profile, resolve it through the existing pipeline, and use
the existing campaign executor and reporting paths.

## 3. Highest-priority paths for Codex

Read these in order for most Evaluation Tool tasks:

| Priority | Path | Why it matters |
|---:|---|---|
| 1 | `HANDOFF.md` | Current combined map, safety rules, and path index |
| 2 | `Software Validation from Datasets/Evaluation Tool/README.md` | Ordinary evaluator inputs, outputs, GUI, CLI, datasets, and prediction contract |
| 3 | `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/current_evaluation_tool_architecture.md` | Compact source-level runtime and package map |
| 4 | `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/system_guide.md` | Full owner/operator manual |
| 5 | `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/final_acceptance_audit.md` | Accepted contracts, evidence boundaries, and limitations |
| 6 | `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation/launch_control_sheet.md` | Current production/distributed launch verdict and exact worker commands |
| 7 | `Software Validation from Datasets/PORTABILITY.md` | Root-variable semantics and relocation rules |
| 8 | `Software Validation from Datasets/Evaluation Tool/run_evaluation.py` | Public Python launcher |
| 9 | `Software Validation from Datasets/Evaluation Tool/app/cli/main.py` | Ordinary and automated CLI dispatcher |
| 10 | `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/component_registry.v1.yaml` | Canonical component identities, packages, assets, profiles, and qualification status |
| 11 | `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/model_asset_registry.v1.yaml` | Model source, version, hashes, storage, licensing, and acquisition method |
| 12 | `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/environment_profiles.stage8.v1.yaml` | Isolated interpreter/profile contracts |
| 13 | `Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/artifact_registry.v3.yaml` | Required/conditional scenario artifacts and completion contract |
| 14 | `Software Validation from Datasets/Evaluation Tool/benchmarks/v1/` | Frozen Small/Standard/Large benchmark manifests |
| 15 | `Software Validation from Datasets/Evaluation Tool/benchmarks/edge_research/edge_research_queue.json` | Exact edge/combo/large catalog paths, hashes, profiles, counts, and default enablement |
| 16 | `Software Validation from Datasets/Evaluation Tool/app/edge_research/plan.py` | Deterministic edge/combo catalog construction |
| 17 | `scripts/run_edge_research.ps1` | Safe edge plan/run/status/stop/resume front door |
| 18 | `Software Validation from Datasets/Training Tool/handoff/HANDOFF_INPUT_FOR_CHATGPT.md` | Separate training-system handoff; training is not part of evaluation execution |

## 4. Portable roots and physical storage

Active code must not depend on a Windows username or drive. The shared roots
are:

| Variable | Default | Purpose |
|---|---|---|
| `JP_REPO_ROOT` | repository checkout | Source/config root |
| `JP_DATA_ROOT` | `<repo>/Software Validation from Datasets` | Normalized metadata and external raw datasets |
| `JP_MODEL_ROOT` | `<repo>/models` | Model cache replacing the configured `models` prefix |
| `JP_RUN_ROOT` | `Evaluation Tool/runs` for ordinary runs | Ordinary `run`/`full` outputs unless `--runs-root` is supplied |
| `JP_TRAINING_ROOT` | `<repo>/training` | Separate generated training workspace |

Important caveat: automated campaign roots use their declared
`Evaluation Tool/automated_runs/<campaign_id>` locations. `JP_RUN_ROOT` does not
silently relocate existing campaign contracts.

Run the non-mutating root diagnostic from the Evaluation Tool directory:

```powershell
..\..\.venv\Scripts\python.exe -m app.utils.paths
```

The preferred external dataset layout is:

```text
JP_DATA_ROOT/
├── Normalized Metadata/
│   ├── AMI/
│   ├── CHiME_6/
│   ├── CMU_Arctic/
│   ├── HiFiTTS/
│   ├── LibriSpeech/
│   └── VOiCES/
└── Raw Datasets (Not formatted)/
    ├── AMI Meeting Corpus/
    ├── CHiME 6/
    ├── CMU Arctic/
    ├── Common Voice.gz
    ├── Common Voice/cv-corpus-26.0-2026-06-12/prepared/en/
    ├── Hi Fi TTS/
    ├── LibreSpeech/
    ├── MIT 271 RIRs/Audio/
    └── VOiCES/
```

Raw audio and model binaries are external/ignored assets. Never add them to Git
or assume a shared folder grants redistribution rights.

## 5. Source-code ownership map

| Path | Responsibility |
|---|---|
| `app/dataset_registry/` | Dataset definitions, normalized metadata loading, filters, selection records |
| `app/augmentation/` | Runtime noise/RIR planning and processing; no full persistent augmented corpus |
| `app/inference_pipeline/` | Component interfaces/adapters, catalog, resolver, pipeline execution |
| `app/model_runner/configured.py` | Bridge from selected EvaluationRecords to the resolved pipeline and prediction contract |
| `app/model_runner/simulated.py` | Protected deterministic fake runner |
| `app/model_runner/external_stub.py` | Protected external integration hook |
| `app/scoring/` | Existing ASR and speaker-attributed scoring |
| `app/plotting/` and `app/reporting/` | Ordinary-run plots and reports |
| `app/benchmark_contracts/` | Frozen manifest selection, scenarios, canonical hashes, conditions, RIR registry |
| `app/artifact_contracts/` | Schemas, atomic publication, checksums, completion validation |
| `app/campaign_executor/` | Planning, SQLite state, leases, heartbeat, retries, stop/resume, subprocesses |
| `app/resource_telemetry/` | Process/system/GPU sampling and resource summaries |
| `app/campaign_exchange/` | Worker assignments, transfers, validation, conflict-safe merge |
| `app/campaign_analysis/` | Result index, registered metrics/statistics/plots, reports, release status |
| `app/core_screening/` | Core qualification/screening |
| `app/extended_backends/` and `app/extended_screening/` | Optional backend qualification and targeted screening |
| `app/edge_research/` | Edge/combo catalog generation and global preflight only |
| `app/speaker_protocol/` | Stage 10 enrollment/calibration/known/unknown speaker protocol |
| `app/diarization_evaluation/` | Stage 11 native diarization manifests and RTTM/UEM scoring |
| `app/launch_readiness/` | Operational launch probes and release binding checks |

## 6. Runtime pipeline and protected semantics

The actual configured pipeline order is:

```text
load/bound audio -> mono/resample 16 kHz -> VAD -> diarization
-> segmentation -> ASR -> speaker embedding -> cosine matching
-> apply valid diarization labels -> PipelineOutput -> prediction adapter
```

If a diarizer emits turns, those turns can become the effective segmentation
source. Reports must accurately state whether segmentation came from full
record, VAD/VADChunker, or diarization.

Preserve these behaviors:

- source IDs and timestamps;
- explicit empty prediction text;
- per-item failure/diagnostic records;
- literal `Unknown` speaker decisions and anonymous diarization labels;
- no copying reference transcripts or speakers into predictions;
- original simulation, external-stub, GUI, scoring, plotting, and reporting
  behavior.

## 7. Public execution surfaces

Run Python commands from:

```text
Software Validation from Datasets/Evaluation Tool/
```

### Ordinary evaluator

```powershell
..\..\.venv\Scripts\python.exe run_evaluation.py list-datasets
..\..\.venv\Scripts\python.exe run_evaluation.py gui
..\..\.venv\Scripts\python.exe run_evaluation.py run --dataset cmu_arctic --runner simulation --max-recordings 1
..\..\.venv\Scripts\python.exe run_evaluation.py full --dataset cmu_arctic --runner configured --inference-config configs\inference\desktop_cpu.yaml --max-recordings 1
..\..\.venv\Scripts\python.exe run_evaluation.py score --run-dir <run-folder>
..\..\.venv\Scripts\python.exe run_evaluation.py report --run-dir <run-folder>
```

`run` performs inference only. `full` performs inference, scoring, plots, and
reporting. Models must already exist; inference never downloads them.

### Automated campaign framework

The `run_evaluation.py campaign` command owns plan, validation, execution,
status, stop, resume, artifact validation, and related state operations. The
`analysis` command owns indexing, validation, analysis, coverage, and release
status. Consult `system_guide.md` before constructing commands manually.

A conservative one-scenario shape is:

```powershell
..\..\.venv\Scripts\python.exe run_evaluation.py campaign plan --catalog <catalog.jsonl> --campaign-id <new-id> --dry-run
..\..\.venv\Scripts\python.exe run_evaluation.py campaign plan --catalog <catalog.jsonl> --campaign-id <new-id>
..\..\.venv\Scripts\python.exe run_evaluation.py campaign validate --campaign-root automated_runs\<new-id>
..\..\.venv\Scripts\python.exe run_evaluation.py campaign run --campaign-root automated_runs\<new-id> --worker-id local --max-scenarios 1 --telemetry
..\..\.venv\Scripts\python.exe run_evaluation.py campaign status --campaign-root automated_runs\<new-id>
..\..\.venv\Scripts\python.exe run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\<new-id>
```

Never infer success from a directory’s existence. Validate campaign state,
scenario artifacts, schemas, counts, and checksums.

## 8. Edge and combo research

Use the repository-root PowerShell controls so each campaign runs under its
declared isolated interpreter:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\prepare_edge_research.ps1
powershell -ExecutionPolicy Bypass -File scripts\verify_edge_research.ps1
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 -Action Plan
```

`prepare` installs/reuses explicit profiles and approved assets. `verify`
regenerates/verifies catalogs and, unless `-SkipSmoke` is supplied, rewrites
qualification evidence. `Plan` dry-plans and starts no inference.

The queue contract currently declares:

| Campaign | Profile | Scenarios | Default |
|---|---|---:|---|
| `campaign_edge_screen_v1` | `edge-cpu` | 36 | enabled |
| `campaign_edge_stream_moon_v1` | `moonshine-edge` | 36 | enabled |
| `campaign_edge_stream_onnx_v1` | `onnx` | 12 | enabled |
| `campaign_edge_combo_moon_v1` | `moonshine-edge` | 216 | disabled |
| `campaign_edge_combo_onnx_v1` | `onnx` | 72 | disabled |

The Moonshine combo is three streaming ASRs crossed with Energy, Silero, and
WebRTC VAD in observe/chunk modes. The ONNX combo is Sherpa 20M crossed with
Energy, Silero, and Sherpa-ONNX VAD in observe/chunk modes. Both use the frozen
small controlled-clean benchmark and immutable component/pipeline identities.

The combined union catalogs are analysis/design inputs only. Do not execute a
union catalog in one process because its rows require different environment
profiles.

Plan one optional combo explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Plan -CampaignId campaign_edge_combo_moon_v1
```

Only after review and explicit authorization, start one bounded scenario:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_edge_research.ps1 `
  -Action Run -CampaignId campaign_edge_combo_moon_v1 -MaxScenarios 1
```

Use `-Action Status`, `Stop`, or `Resume` with the same campaign ID. Default
execution is sequential. Do not use `-IncludeOptional` casually.

Large edge catalogs are also optional and contain 32 scenarios per model. Their
exact names/hashes live in `edge_research_queue.json`. Whisper Large is not an
approved model; Whisper Base is the reference control.

## 9. Environments and model assets

| Profile | Interpreter | Main use |
|---|---|---|
| `core-cpu` | `<repo>/.venv/Scripts/python.exe` | Core Whisper/VAD/ECAPA, campaign control, analysis |
| `core-cuda` | `<repo>/.stage8-envs/core-cuda/Scripts/python.exe` | Qualified single-GPU core execution |
| `extended-local` | `<repo>/.stage8-envs/extended-local/Scripts/python.exe` | Faster-Whisper, Vosk, WebRTC, Resemblyzer |
| `onnx` | `<repo>/.stage8-envs/onnx/Scripts/python.exe` | Sherpa ASR/VAD/embedding/diarization |
| `edge-cpu` | `<repo>/.stage8-envs/edge-cpu/Scripts/python.exe` | FSMN-VAD edge screen |
| `moonshine-edge` | `<repo>/.stage8-envs/moonshine-edge/Scripts/python.exe` | Moonshine streaming models |
| `wenet` | `<repo>/.stage8-envs/wenet/Scripts/python.exe` | WeNet candidate; asset limitations apply |
| `wespeaker` | `<repo>/.stage8-envs/wespeaker/Scripts/python.exe` | WeSpeaker with recorded warnings |

Do not combine incompatible profiles in one Python process. Component YAML and
the registries select the required profile. Explicit model bootstrap lives at:

```text
scripts/bootstrap_models.py
models/cache/                         # default physical cache, ignored by Git
Evaluation Tool/configs/automated_evaluation/model_asset_registry.v1.yaml
```

Do not silently use a newer asset or download during inference. Verify hashes
and licensing/provenance, especially GigaSpeech-derived models and credential-
gated diarization backends.

## 10. Scientific identity and configuration contracts

Treat these as versioned contracts:

- benchmark manifests and `manifest_summary.json` under `benchmarks/v1/`;
- scenario schema/canonicalization/hash under `app/benchmark_contracts/`;
- component and model identities in the automated-evaluation registries;
- source component fragments under `configs/inference/components/`;
- condition/RIR registries;
- artifact registries and schemas;
- edge catalog JSONL files and their queue-recorded SHA-256 hashes;
- completed campaign manifests, scenario IDs, checksums, assignments, transfer
  packages, and analysis manifests.

Physical root changes do not change scientific identity. Result-affecting model,
data, component, condition, seed, device/dtype/runtime, timeout, resource,
scoring, or failure-policy changes require a new scenario identity. Never edit
an old result to make a new configuration appear compatible.

## 11. Output path atlas

Ordinary Evaluation Tool runs:

```text
Evaluation Tool/runs/<timestamp>_<dataset>_<mode>_<name>/
├── config/
├── predictions/utterances.jsonl
├── diagnostics/
├── metrics/
├── plots/
├── report/
├── previews/ or preview_audio/
└── logs/
```

Automated campaign results:

```text
Evaluation Tool/automated_runs/<campaign_id>/
├── campaign_manifest.json
├── campaign_state.sqlite
├── scenarios/<scenario_id>/
│   ├── resolved_scenario.json
│   ├── status.json
│   ├── predictions/utterances.jsonl
│   ├── predictions/streaming_diagnostics.jsonl   # when required
│   ├── diagnostics/ and failures/
│   ├── metrics/
│   ├── resource_logs/
│   ├── logs/
│   ├── report/
│   └── checksums.json
└── analysis/
    ├── result_index.parquet
    ├── analysis_manifest.json
    ├── tables/ and plots/
    └── report/campaign_report.md
```

Other important evidence/output roots:

```text
Evaluation Tool/runs/component_qualification/
Evaluation Tool/runs/edge_backend_qualification/
Evaluation Tool/runs/extended_backend_qualification/
Evaluation Tool/runs/edge_speaker_protocol_smoke/
Evaluation Tool/benchmarks/stage10/
Evaluation Tool/benchmarks/stage11/
transfer_packages/<campaign_id>/<machine_id>/
```

Qualification evidence is not equivalent to scientific model-selection
evidence. Smoke results prove contracts and runtime composition only.

## 12. Specialized protocols and distributed release

- Stage 10 speaker work: `app/speaker_protocol/`,
  `configs/automated_evaluation/speaker_protocol.v1.yaml`,
  `benchmarks/stage10/`.
- Stage 11 diarization: `app/diarization_evaluation/`,
  `configs/automated_evaluation/diarization_evaluation.v1.yaml`,
  `benchmarks/stage11/`.
- Distributed campaign exchange: `app/campaign_exchange/`, assignments,
  `scripts/setup_worker.ps1`, `verify_worker.ps1`, `launch_worker.ps1`,
  `worker_control.ps1`, `export_worker.ps1`, and `coordinator.ps1`.

The current launch control sheet says the product framework is
`PRODUCTION_READY`, while the distributed CUDA campaign remains
`WAITING_FOR_MACHINE_B` until the physical second machine passes setup,
verification, real inference, and full assigned preflight. Treat that launch
sheet—not older narrative text—as the operational source of truth.

## 13. Guardrails and deferred work

- Do not evaluate Whisper Large.
- Do not download models during inference or qualification.
- Do not run optional combo/large campaigns without explicit selection and a
  reviewed count/profile/output/stop plan.
- Keep one GPU-heavy scenario at a time unless concurrency is separately
  qualified.
- Do not run training alongside GPU Large evaluation on the same GPU.
- Dining Room and Restaurant are the approved exact RIRs. Bedroom remains
  unresolved; never substitute ParkingLot, Kitchen, or another file.
- Preserve `Unknown`, failure rows, timestamps, identities, checksums, and
  warnings.
- Credential-gated pyannote/Picovoice and platform-limited NeMo remain blocked
  until the operator supplies and approves prerequisites.
- Never treat a one-item smoke, synthetic Stage 12 trace, or qualification run
  as proof of the best production pipeline.
- Validate existing artifacts before rerunning expensive work.

## 14. Safe first actions for a new Codex session

1. Run the four Git checks in section 1 and preserve every unrelated change.
2. Read this handoff, `current_evaluation_tool_architecture.md`, the relevant
   runbook, and the final acceptance/launch-control evidence.
3. Run the portable-root diagnostic and verify the expected interpreter/model/
   data paths without downloading or executing inference.
4. Inspect the exact component, asset, profile, benchmark, catalog, and artifact
   contracts involved in the requested task.
5. Prefer a dry plan or tiny fixture test. Do not launch a campaign merely to
   understand it.
6. If execution is requested, state the campaign ID, profile, scenario count,
   input catalog/hash, output root, expected duration/storage, and exact
   status/stop/resume commands before starting.
7. Stage exact owned files only. Never stage operator qualification JSON/log
   changes accidentally.

## 15. Training boundary

The Training Tool is a sibling system that consumes external datasets and
produces adapter/full-fine-tune checkpoints. It does not run inside the
Evaluation Tool. Evaluation consumes exported immutable models later.

Start training-related work with:

```text
Software Validation from Datasets/Training Tool/handoff/HANDOFF_INPUT_FOR_CHATGPT.md
Software Validation from Datasets/Training Tool/handoff/training_handoff_state.json
Software Validation from Datasets/Training Tool/handoff/training_handoff_commands.md
```

Do not change frozen training identities because an Evaluation Tool path moved,
and do not change frozen evaluation identities because a model was trained.
Connect the two systems through explicit checkpoint/export IDs, SHA-256 values,
model lineage, and new registered Evaluation Tool assets/components.

## 16. Minimum context block for the next Codex prompt

```text
Repository: C:\Users\amiri\Documents\GitHub\just-peachy
Branch: codex/edge-component-expansion
Read first: HANDOFF.md
Evaluation root: Software Validation from Datasets/Evaluation Tool
Public launcher: Software Validation from Datasets/Evaluation Tool/run_evaluation.py
Component registry: Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/component_registry.v1.yaml
Model registry: Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/model_asset_registry.v1.yaml
Artifact registry: Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/artifact_registry.v3.yaml
Frozen benchmarks: Software Validation from Datasets/Evaluation Tool/benchmarks/v1
Edge/combo queue: Software Validation from Datasets/Evaluation Tool/benchmarks/edge_research/edge_research_queue.json
Ordinary outputs: Software Validation from Datasets/Evaluation Tool/runs
Campaign outputs: Software Validation from Datasets/Evaluation Tool/automated_runs
Portable roots: JP_REPO_ROOT, JP_DATA_ROOT, JP_MODEL_ROOT, JP_RUN_ROOT, JP_TRAINING_ROOT
Preserve current operator-owned qualification JSON and research_queue_logs changes.
Do not run optional/large work, download models, or mutate frozen identities unless explicitly authorized.
```
