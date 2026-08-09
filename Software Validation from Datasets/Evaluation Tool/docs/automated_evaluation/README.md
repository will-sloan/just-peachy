# Automated Evaluation Development Guide

This directory records the contracts, evidence, and operating instructions for extending the Evaluation Tool into an unattended campaign runner. Stage 0 froze readiness and protected interfaces. Stage 1 added a runtime component catalog, a scenario-independent pipeline resolver, and a configured evaluator runner. Stage 2 added immutable benchmark manifests, exact RIR/condition registries, canonical scenario expansion, and released versioned hash contracts. Stage 3 defines typed campaign/scenario artifacts, atomic publication, checksums, completion validation, and static environment fingerprints. Stage 4 adds persistent campaign state and restart-safe execution. Stage 5 adds scenario/component resource telemetry. Stage 6 adds deterministic worker assignments and conflict-safe merging. Stage 7 adds targeted core component qualification and screening contracts. Stage 8 adds isolated extended-backend environments, assets, and independent real qualification. Stage 9 integrates only those real-qualified backends into environment-aware staged screening, real smoke evidence, per-environment campaign catalogs, and separate model-quality/runtime analysis. Stage 10 adds privacy-safe speaker enrollment, calibration, verification, identification, and unknown rejection. Stage 11 adds reference-safe native diarization execution and scoring. Stage 12 adds standalone campaign analysis, statistical comparisons, eligibility-gated plots, coverage reconciliation, reports, and preregistered staged release gates. Shared database coordination and unqualified GPU concurrency remain intentionally excluded.

## Start here

- [System guide](system_guide.md): complete owner/operator manual.
- [Quick reference](quick_reference.md): concise verified command workflows.
- [Current architecture](current_evaluation_tool_architecture.md): implementation and integration map.
- [Final acceptance audit](final_acceptance_audit.md): requirements matrix, corrections, verdict, and limitations.
- [Phase 13 report](phase_13_report.md): final validation counts, corrections, and documentation consistency.
- [Analysis guide](analysis_guide.md): deeper analysis and release-gate interpretation.

## Inputs and outputs

The Stage 0 inputs are the repository at the frozen Git commit, component YAML files under `configs/inference/components`, higher-level inference YAML files, pinned requirements, local model caches, the MIT RIR filename inventory, repository tests, and real component-qualification artifacts.

The outputs are:

- `configs/automated_evaluation/component_registry.v1.yaml`: complete versioned component disposition and evidence;
- `configs/automated_evaluation/environment_profiles.v1.yaml`: mutually compatible installation and qualification profiles;
- `docs/automated_evaluation/protected_interfaces.md`: boundaries later phases must preserve;
- `docs/automated_evaluation/stage_0_readiness_freeze.md`: decisions, conflicts, current state, and gates;
- `docs/automated_evaluation/phase_0_report.md`: completion evidence and handoff.

Stage 1 adds:

- `app/inference_pipeline/catalog.py`: a runtime view of executable components derived from the Stage 0 registry and existing component YAML;
- `app/inference_pipeline/resolver.py`: immutable composition, compatibility validation, override provenance, and resolved configuration artifacts;
- `app/model_runner/configured.py`: the explicit bridge from ordinary Evaluation Tool records to `PipelineRunner` and back to protected predictions;
- `tests/automated_evaluation/test_stage1_configured_runner.py`: contract, error-path, and real Tiny/Base smoke coverage;
- `docs/automated_evaluation/phase_1_report.md`: Stage 1 evidence and handoff.

Stage 2 adds:

- `app/benchmark_contracts`: canonicalization, policy enforcement, deterministic selection, Parquet I/O, RIR audit, and scenario identity;
- `configs/automated_evaluation/benchmark_targets.v1.yaml`: tier eligibility and requested quotas;
- `configs/automated_evaluation/rir_registry.v1.yaml` and `condition_sets.v1.yaml`: exact approved, unresolved, and excluded RIR/condition identities;
- `configs/automated_evaluation/contracts.v1.yaml` and `schemas/`: frozen public contract rules and JSON Schemas;
- `benchmarks/v1`: authoritative manifests, audits, summaries, and scenario definitions;
- `tests/automated_evaluation/fixtures/stage2`: byte/hash golden fixtures;
- `docs/automated_evaluation/phase_2_report.md`: Stage 2 evidence and handoff.

Stage 3 adds:

- `configs/automated_evaluation/artifact_registry.v1.yaml`: producer, format, schema, requirement, checksum, privacy, and consumer definitions;
- `configs/automated_evaluation/table_schemas.v1.yaml` and additional JSON Schemas: typed exchange contracts;
- `app/artifact_contracts`: layout, atomic writes, schema validation, checksums, completion classification, and static environment fingerprinting;
- `scripts/validate_campaign_artifacts.py`: read-only registry/campaign/scenario validator;
- `tests/automated_evaluation/test_stage3_artifact_contracts.py`: interruption, truncation, corruption, conditional output, count, fingerprint, and portability tests;
- `docs/automated_evaluation/phase_3_report.md`: Stage 3 evidence and handoff.

Stage 4 adds:

- `app/campaign_executor/state.py`: transactional `campaign-database.v1` state, attempts, leases, heartbeats, stops, and events;
- `app/campaign_executor/planner.py`: deterministic scenario selection, immutable campaign creation, benchmark copying, and scenario registration;
- `app/campaign_executor/executor.py`: subprocess supervision, disk checks, timeout/stop/interrupt handling, failure classification, retries, and completion validation;
- `app/campaign_executor/runtime.py`: adapter from one frozen ASR scenario to the existing configured runner, scorer, plotter, and reporter;
- `app/campaign_executor/synthetic_worker.py`: GPU/model-free executor contract qualification only;
- `tests/automated_evaluation/test_stage4_campaign_executor.py`: persistent-state, process, lease, retry, resume, corruption, and overwrite protection tests;
- `docs/automated_evaluation/phase_4_report.md`: Stage 4 evidence and handoff.

Stage 5 adds `app/resource_telemetry`, additive `artifact-registry.v2` resource contracts, CPU/NVML sampling, component spans, and `phase_5_report.md`.

Stage 6 adds:

- `app/campaign_exchange`: assignments, independent copies, assignment-scoped execution, transfer packages, merge, and analysis indexing;
- five versioned exchange schemas under `configs/automated_evaluation/schemas/`;
- `tests/automated_evaluation/test_stage6_campaign_exchange.py`: deterministic and synthetic two-worker qualification;
- `docs/automated_evaluation/phase_6_report.md`: Stage 6 evidence and handoff.

Stage 7 adds `app/core_screening`, a Whisper Base reference protocol, deterministic one-family-at-a-time planning, repeated core qualification, declared advancement rules, and `phase_7_report.md`.

Stage 8 adds:

- `app/extended_backends`: profile/asset readers, secret-safe independent qualifiers, and evidence consolidation;
- `configs/automated_evaluation/environment_profiles.stage8.v1.yaml`, `extended_backends.v1.yaml`, and `model_asset_registry.v1.yaml`;
- isolated pinned requirements under `requirements/stage8` and profile installers under the repository `scripts` directory;
- `extended_backend_setup.md`, `environment_profiles.md`, `extended_backend_qualification.md`, and `phase_8_report.md`;
- checksummed machine evidence under `runs/extended_backend_qualification`.

Stage 9 adds:

- `app/extended_screening`: qualification gating, deterministic planning, real smoke, environment-aware analysis, and handoff reports;
- `extended_screening.v1.yaml` and a checksummed extended qualification registry;
- 228 released global scenarios plus four compatible environment catalogs under `benchmarks/stage9`;
- component comparison, advancement/exclusion, environment compatibility, benchmark coverage, and shortlist contracts;
- `extended_backend_screening.md` and `phase_9_report.md`.

Stage 10 adds:

- `app/speaker_protocol`: immutable split derivation, backend-bound enrollment, real extraction, calibration, scoring, confidence intervals, validation, and CLI integration;
- `speaker_protocol.v1.yaml`, an artifact registry, and JSON schemas for the public speaker contracts;
- small, standard, and large protocol manifests under `benchmarks/stage10`;
- real ECAPA, Resemblyzer, Sherpa-ONNX, and WeSpeaker smoke results under `runs/speaker_protocol_smoke`;
- `speaker_protocol.md` and `phase_10_report.md`.

Stage 11 adds `app/diarization_evaluation`, immutable native scoring views, RTTM/UEM and timebase validation, explicit segmentation provenance, qualified-backend execution, DER/JER suppression rules, grouped native analysis, and `phase_11_report.md`.

Stage 12 adds:

- `app/campaign_analysis`: exact result indexing, registry-driven metric reuse, paired cluster-bootstrap comparisons, plots, coverage, reports, release gates, and CLI integration;
- `metric_registry.v1.yaml`, `plot_report_registry.v1.yaml`, and `analysis_decision_policy.v1.yaml`;
- public analysis/result-index/coverage/release/plot schemas;
- `tests/automated_evaluation/test_stage12_campaign_analysis.py`;
- `analysis_guide.md` and `phase_12_report.md`.

No secrets are inputs or outputs. Credential-gated components use only the variable names `PYANNOTE_AUTH_TOKEN` and `PICOVOICE_ACCESS_KEY`; values must never be written to configuration, logs, reports, shell history, or transferred artifacts.

## Run a configured pipeline

Purpose: execute an explicitly selected existing inference YAML through dataset selection, runtime augmentation, `PipelineRunner`, standardized prediction writing, scoring, plotting, and reporting. Inputs are a dataset selection plus an existing higher-level inference YAML and optional explicit component/setting overrides. Outputs are the ordinary run folder plus `inference/` resolution artifacts and `predictions/diagnostics.jsonl` and `predictions/failures.jsonl`.

In Anaconda Prompt or Command Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python run_evaluation.py full ^
  --dataset cmu_arctic ^
  --max-recordings 1 ^
  --augmentation none ^
  --runner configured ^
  --inference-config configs\inference\live_mic_whisper_base.yaml ^
  --run-name configured_base_smoke
```

In PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python run_evaluation.py full `
  --dataset cmu_arctic `
  --max-recordings 1 `
  --augmentation none `
  --runner configured `
  --inference-config configs/inference/live_mic_whisper_base.yaml `
  --run-name configured_base_smoke
```

Optional selections are repeatable:

```text
--component asr=whisper_base
--component vad=silero_vad
--inference-override runtime.num_threads=2
--inference-override components.asr.params.beam_size=1
```

Only existing catalog component names and supported override paths are accepted. Source YAML is read-only. `allow_model_downloads=true` is rejected at both runtime and component levels. A missing prerequisite produces an explicit unavailable failure record.

Configured-runner additions under each run are:

```text
inference/
  selected_inference_config.json
  resolved_inference_config.yaml
  component_identity_summary.json
  configuration_warnings.json
  configured_runner_artifacts.json
predictions/
  utterances.jsonl
  diagnostics.jsonl
  failures.jsonl
  segments.rttm              # only when RTTM is emitted
```

The protected six-field `utterances.jsonl` schema is unchanged. `source_recording_id`, channel/stream identity, augmentation identity, component diagnostics, and unknown-token normalization evidence are stored in diagnostics. Reference text and reference speaker identity are never copied into prediction artifacts.

## Validate Stage 1

```bat
python -m pytest tests\automated_evaluation\test_stage1_configured_runner.py -q --basetemp artifacts\pytest_stage1
python -m pytest tests\automated_evaluation tests\inference_pipeline tests\model_runner -q --basetemp artifacts\pytest_stage1_regression
python -m app.gui.validation_harness
python -m ruff check app\inference_pipeline\catalog.py app\inference_pipeline\resolver.py app\model_runner\configured.py tests\automated_evaluation\test_stage1_configured_runner.py
```

The Tiny and Base smoke tests run only when their exact local assets are present. They never download a missing model.

## Build and validate Stage 2

Purpose: select stable source records from existing normalized metadata, enforce panel augmentation policy, audit exact RIR identities, and expand canonical scenario definitions. Inputs are normalized metadata, Stage 2 YAML contracts, the local RIR directory, and one or more existing inference YAMLs whose identities are frozen into scenarios. Outputs are Parquet manifests, audit/summary files, and scenario JSONL under `benchmarks/v1`. No audio is copied, no model is loaded, and no inference is run.

In Anaconda Prompt or Command Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\build_benchmark_contracts.py --output benchmarks\v1
python -m pytest tests\automated_evaluation\test_stage2_benchmark_contracts.py -q --basetemp artifacts\pytest_stage2
```

In PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/build_benchmark_contracts.py --output benchmarks/v1
python -m pytest tests/automated_evaluation/test_stage2_benchmark_contracts.py -q --basetemp artifacts/pytest_stage2
```

The default scenario identity uses the existing Whisper Base reference configuration. Additional `--pipeline-config` arguments are repeatable and resolve identities without loading models. Missing/unapproved bedroom and kitchen RIRs are not substituted and do not produce executable conditions.

## Validate Stage 3 artifacts

Purpose: verify future campaign handoffs before any executor trusts them. Inputs are a Stage 3 registry plus a campaign manifest pair or one materialized scenario directory. Output is a machine-readable `complete`, `incomplete`, `corrupt`, or `incompatible` report. Validation is read-only and does not run inference or collect telemetry.

In Anaconda Prompt or Command Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\validate_campaign_artifacts.py --registry-only
python scripts\validate_campaign_artifacts.py --scenario-dir automated_runs\<campaign_id>\scenarios\<scenario_id>
python -m pytest tests\automated_evaluation\test_stage3_artifact_contracts.py -q --basetemp artifacts\pytest_stage3
```

In PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/validate_campaign_artifacts.py --registry-only
python scripts/validate_campaign_artifacts.py --scenario-dir automated_runs/<campaign_id>/scenarios/<scenario_id>
```

See `app/artifact_contracts/README.md` for the full directory model, atomic commit sequence, scenario-type requirements, inputs/outputs, checksum recovery boundary, and environment-fingerprint privacy rules.

## Plan, run, and resume Stage 4 campaigns

Purpose: execute selected frozen scenarios without duplicating evaluator logic. Inputs are the Stage 2 scenario catalog/manifests, one short worker ID, the existing dataset checkout, and optional scenario/config filters. Outputs use the Stage 3 artifact layout plus `database/campaign.sqlite` and audit-preserved attempt work.

In Anaconda Prompt or Command Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python run_evaluation.py campaign plan --dry-run
python run_evaluation.py campaign plan --campaign-id campaign_example01 --scenario-id <scenario_id>
python run_evaluation.py campaign validate --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_example01 --worker-id amir
python run_evaluation.py campaign resume --campaign-root automated_runs\campaign_example01 --worker-id amir
python run_evaluation.py campaign status --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign validate-artifacts --campaign-root automated_runs\campaign_example01
```

Stop one active scenario without deleting partial output:

```bat
python run_evaluation.py campaign stop --campaign-root automated_runs\campaign_example01 --scenario-id <scenario_id> --reason "operator request"
```

See `app/campaign_executor/README.md` for ranges, component filters, all commands, state semantics, inputs/outputs, and PowerShell examples. Automated Stage 4 tests use synthetic subprocesses and require no model, GPU, credential, network access, or download.

## Collect Stage 5 telemetry

Purpose: measure a scenario subprocess and active pipeline components without changing predictions. Inputs are a planned campaign, worker ID, optional exact scenario selection, and an optional sample interval. Outputs are typed Parquet samples, JSONL component spans, summary JSON, availability flags, and checksums under each scenario's `resource_logs/` folder.

```bat
python run_evaluation.py campaign run --campaign-root automated_runs\campaign_example01 --worker-id amir --telemetry --telemetry-interval-sec 1.0
python -m pytest tests\automated_evaluation\test_stage5_resource_telemetry.py -q --basetemp artifacts\pytest_stage5
```

CPU/process telemetry is independent of NVIDIA tooling. NVML and CUDA fields are explicit when unavailable. Execution remains one scenario subprocess at a time; Stage 5 does not authorize GPU concurrency. See `app/resource_telemetry/README.md` and `phase_5_report.md`.

## Assign, transfer, and merge Stage 6 work

Purpose: divide one global campaign between complete repository clones without sharing a live database. Inputs are a pending campaign, worker selectors, expected Git/environment identity, and completed scenario folders. Outputs are assignment YAML, independent worker transfer packages, a merge-validation report, a merged result index, and `analysis/analysis_input_index.json`.

```bat
python run_evaluation.py campaign assign --campaign-root automated_runs\campaign_example01 --worker-id amir --environment-profile core-cpu --partition-index 0 --partition-count 2
python run_evaluation.py campaign validate-assignments --campaign-root automated_runs\campaign_example01
python run_evaluation.py campaign run-assignment --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml --environment-profile core-cpu
python run_evaluation.py campaign export-results --campaign-root automated_runs\campaign_example01 --assignment automated_runs\campaign_example01\worker_assignments\worker_amir.yaml --environment-profile core-cpu --destination C:\transfer\transfer_amir
python run_evaluation.py campaign merge-results --campaign-root automated_runs\campaign_example01 --transfer-root C:\transfer\transfer_amir --transfer-root C:\transfer\transfer_friend
```

Create Machine B's campaign copy before either worker starts, then place it on Machine B's local disk. Never run its SQLite file from a network share. See `app/campaign_exchange/README.md` for the complete Anaconda Prompt, command-line, PowerShell, input/output, selector, copy, validation, and recovery instructions.

## How to validate Stage 0

In Anaconda Prompt or Command Prompt:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python -m pytest tests\automated_evaluation tests\inference_pipeline\test_component_qualification.py -q --basetemp artifacts\pytest_stage0
```

To rerun real CPU component qualification using the approved Whisper Base composition reference:

```bat
python scripts\qualify_speech_components.py ^
  --audio "..\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_b0476.wav" ^
  --output runs\component_qualification\cpu_contract_20260807.json
```

In PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python -m pytest tests/automated_evaluation tests/inference_pipeline/test_component_qualification.py -q --basetemp artifacts/pytest_stage0
```

The tests read the two versioned YAML files and active component/config registries. They produce only temporary pytest files. Real qualification produces one machine-readable JSON report and model runtime caches; it does not score a benchmark.

## Analyze and release-qualify a completed campaign

Purpose: validate a Stage 6 merged handoff, preserve every planned failure/gap, reuse existing scientific metrics, run explicitly declared paired comparisons, create only eligible plots, reconcile coverage, and evaluate preregistered release gates. Stage 12 never reruns inference.

```bat
python run_evaluation.py campaign validate-merged --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis run --campaign-root automated_runs\<campaign_id> --prerequisite-evidence C:\results\previous_gate.json
python run_evaluation.py analysis coverage --campaign-root automated_runs\<campaign_id>
python run_evaluation.py analysis release-status --campaign-root automated_runs\<campaign_id> --prerequisite-evidence C:\results\previous_gate.json
python run_evaluation.py analysis qualify-synthetic --project-root . --output-root runs\stage12_release_qualification
```

See `app/campaign_analysis/README.md` for inputs, outputs, Anaconda Prompt, Command Prompt, PowerShell, comparison, and test commands. `analysis_guide.md` is the independent analyst handoff.

## Current stage boundary

Stage 12 completes the planned orchestration and analysis framework. It does not itself execute small, standard, or large speech inference campaigns, acquire credentials/models, authorize unsupported backends, or enable multiple simultaneous GPU scenarios. Release progression remains synthetic → small → standard → large, and GPU concurrency remains one until a separate sustained qualification passes.
