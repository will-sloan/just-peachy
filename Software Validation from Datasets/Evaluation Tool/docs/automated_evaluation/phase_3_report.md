# Phase 3 Report: Artifact Schemas, Atomic Writes, Checksums, and Validation

## Objective and result

Stage 3 is complete. The repository now has a stable, versioned contract for future campaign and scenario artifacts before a campaign executor exists. The implementation defines artifact ownership and schemas, creates the required Windows-safe directory model, atomically publishes scenario artifacts, maintains checksums, validates detached campaign-manifest checksums, classifies scenario completeness, and records static environment identity.

No inference, campaign scheduling, campaign state database, retry/resume loop, worker assignment, result merging, or runtime telemetry collection was added. Stage 2 scenario IDs and manifest identities are unchanged.

## Implemented files

Registry and public schemas:

- `configs/automated_evaluation/artifact_registry.v1.yaml`;
- `configs/automated_evaluation/table_schemas.v1.yaml`;
- `configs/automated_evaluation/schemas/artifact_registry.v1.schema.json`;
- `configs/automated_evaluation/schemas/campaign_manifest.v1.schema.json`;
- `configs/automated_evaluation/schemas/checksums.v1.schema.json`;
- `configs/automated_evaluation/schemas/environment_fingerprint.v1.schema.json`;
- `configs/automated_evaluation/schemas/metrics_summary.v1.schema.json`;
- `configs/automated_evaluation/schemas/run_config.v1.schema.json`;
- `configs/automated_evaluation/schemas/scenario_event.v1.schema.json`;
- `configs/automated_evaluation/schemas/scenario_report.v1.schema.json`;
- `configs/automated_evaluation/schemas/scenario_status.v1.schema.json`.

Runtime contract package:

- `app/artifact_contracts/registry.py`: validates the registry, resolves path patterns, derives scenario type/capabilities, and calculates required artifacts from the resolved scenario;
- `app/artifact_contracts/layout.py`: validates short campaign/scenario IDs and creates directory structure only;
- `app/artifact_contracts/schemas.py`: validates JSON, JSONL, YAML, Parquet, NPZ, RTTM, text, SQLite, and detached SHA-256 artifacts without adding dependencies;
- `app/artifact_contracts/atomic.py`: same-directory temporary writes, flush/fsync, validation, SHA-256, atomic replace, checksum-index updates, detached campaign-manifest checksum, and repair after an interrupted checksum update;
- `app/artifact_contracts/completion.py`: registry-driven required-artifact, schema, checksum, count, status, temporary-file, and transfer validation;
- `app/artifact_contracts/environment.py`: static host/software fingerprint and resolved-scenario model/component hash extraction;
- `app/artifact_contracts/README.md`: purpose, inputs, outputs, directory model, commands, and recovery semantics.

Read-only command and tests:

- `scripts/validate_campaign_artifacts.py`;
- `tests/automated_evaluation/test_stage3_artifact_contracts.py`.

Updated documentation:

- `README.md`;
- `docs/automated_evaluation/README.md`;
- `docs/automated_evaluation/protected_interfaces.md`;
- this report.

## Artifact registry

`artifact-registry.v1` currently defines 30 artifacts. Every definition contains:

- scope and portable path/pattern;
- producer;
- exchange format;
- schema version;
- mandatory or conditional status plus condition;
- validation rules;
- checksum policy;
- privacy classification;
- downstream consumers.

Allowed typed formats are JSON, JSONL, YAML, Parquet, RTTM, NPZ, UTF-8 text, SQLite, and detached SHA-256 text. Pickle is not allowed. Parquet artifacts declare `artifact_schema_version` metadata and required typed columns. Embedding NPZ files are opened with `allow_pickle=False`, require `speaker-embedding.v1`, and contain a finite nonempty one-dimensional numeric `embedding` array.

Privacy classes are `public_contract`, `internal`, `sensitive_transcript`, `biometric_sensitive`, and `restricted_system`. Run configuration, diagnostic/failure/event/error/runner logs, and environment fingerprints reject credential-like values. Embeddings and similarity scores are explicitly biometric-sensitive. Environment fingerprints are restricted-system artifacts.

## Directory model

`CampaignLayout` creates directories only:

```text
automated_runs/
  <campaign_id>/
    campaign_manifest.json
    campaign_manifest.sha256
    benchmark_manifests/
    worker_assignments/
    database/
    scenarios/
      <scenario_id>/
        resolved_scenario.json
        run_config.yaml
        status.json
        predictions/
          utterances.jsonl
          diagnostics.jsonl
          words.jsonl                    # conditional
          vad_regions.jsonl              # conditional
          segments.rttm                  # conditional
          embeddings/*.npz               # conditional
          embeddings/index.parquet       # conditional
          similarity_scores.parquet      # conditional
          diarization_diagnostics.jsonl  # conditional
        metrics/
          item_metrics.parquet
          grouped_metrics.parquet
          summary.json
          failures.parquet
        resource_logs/
        logs/events.jsonl
        logs/runner.log
        logs/errors.jsonl
        report/scenario_report.json
        report/scenario_report.md
        checksums.json
    audit/environment_fingerprints/
    analysis/
```

IDs are short and Windows-safe. Artifact paths are scope-relative POSIX strings in exchange data. Drive-qualified, rooted, parent-traversing, and backslash-persisted paths are rejected where portability is required. Machine-specific Python executable paths are allowed only inside the restricted environment fingerprint and never affect Stage 2 scenario identity.

## Scenario requirements

The validator determines requirements from `resolved_scenario.json`. An optional additive `artifact_contract` declares an explicit scenario type and supported capabilities; otherwise the type is deterministically inferred from enabled Stage 2 pipeline components.

| Scenario type | Task-specific required artifacts |
|---|---|
| ASR | `utterances.jsonl`, item/grouped metrics, summary, failures, diagnostics, logs, reports, and checksums. |
| VAD-only qualification | `vad_regions.jsonl` instead of utterance predictions, plus metrics and common artifacts. |
| Embedding extraction | embedding NPZ files and typed index, plus metrics and common artifacts. |
| Speaker verification | embeddings/index and typed similarity scores, plus metrics and common artifacts. |
| Diarization | RTTM and diarization diagnostics, plus metrics and common artifacts. |
| Synthetic executor test | common status, diagnostics, summary, failures, events/errors/log, reports, and checksums; no task metric tables required. |

Enabled ASR, speaker embedding, speaker matching, or diarization families add their own required artifacts even when part of a larger combination. `words.jsonl` is required only when the resolved scenario explicitly declares `word_timestamps`. `resource_usage.parquet` is required only when a future scenario explicitly declares telemetry; Stage 3 does not collect it. Optional artifacts are not fabricated when the real pipeline cannot emit them.

## Atomic publication contract

`ScenarioArtifactStore` performs this ordered sequence:

1. create a same-directory `.tmp-<uuid>` artifact;
2. write, close, and fsync it;
3. validate format, schema, identity, paths, and privacy rules;
4. calculate uppercase SHA-256 and byte count;
5. atomically replace the destination with `os.replace`;
6. atomically update `checksums.json`.

An error before replacement removes the temporary file and preserves an existing destination. A real process termination can leave a temporary file; completion validation reports it as incomplete. The filesystem cannot atomically replace both the artifact and checksum index in one operation. Therefore, interruption after artifact replacement but before checksum-index replacement creates a valid but intentionally untrusted state. The validator detects the mismatch, and `reconcile_checksum_manifest()` repairs it only after every materialized registered artifact passes validation again.

`checksums.json` excludes itself to avoid recursion. `campaign_manifest.json` uses `campaign_manifest.sha256`. Pickle is never written or read.

## Completion classification

Completion reports use `completion-validation.v1` and exactly one state:

- `complete`: scenario hash matches, status is successful, all required and declared conditional artifacts exist, schemas validate, expected/stored/observed counts reconcile, checksums and byte counts match, and no temporary file remains;
- `incomplete`: required output or checksum entry is missing, a transfer target is absent, status is not successful, or a stale temporary file exists;
- `corrupt`: an artifact is truncated/malformed, bytes differ from stored SHA-256/size, content hashes disagree, or internally stored counts contradict materialized data;
- `incompatible`: registry/schema/scenario type is unsupported, artifact identity conflicts with the registry, or an unregistered exchange artifact is present.

Classification precedence is incompatible, corrupt, incomplete, complete. This prevents an incompatible artifact from being mistaken for a merely unfinished run.

For a successful ASR scenario, selected items equal the resolved Stage 2 slice row count; successful plus failed items equal selected items; diagnostics and utterance predictions equal successful items; failures equal failed items; item metrics equal selected items; grouped/error/optional counts match their materialized files; and `metrics/summary.json` counts exactly equal `status.json` counts. Equivalent task-specific checks apply to embeddings, similarity scores, VAD regions, and diarization artifacts.

## Environment fingerprint

`environment-fingerprint.v1` contains:

- Git commit, dirty indicator, and changed-path count without persisting path names;
- OS system/release/version/machine;
- Python executable, version, and implementation;
- environment profile identity, sorted package freeze, and freeze SHA-256;
- CPU identity/logical count and physical RAM;
- static GPU index/name/UUID/VRAM, driver, and CUDA runtime where available;
- explicit model-asset and component-config hashes extracted from the resolved scenario;
- timezone, UTC offset, and wall/monotonic clock implementation and resolution.

GPU collection is a one-time static `nvidia-smi` identity query, not utilization telemetry. Collection timestamp is audit metadata excluded from the stable fingerprint identity, while timezone/clock characteristics remain part of it. The complete fingerprint content hash and `environment_<first-12-hex>` ID are validated. No credentials or environment-variable values are recorded.

## Commands and verification evidence

Registry validator:

```bat
python scripts\validate_campaign_artifacts.py --registry-only
```

Result: `artifact-registry.v1`, 30 artifacts, and all six scenario profiles loaded successfully.

Focused Stage 3 tests:

```bat
python -m pytest tests\automated_evaluation\test_stage3_artifact_contracts.py -q --basetemp artifacts\stage3_pytest_pinned_focus
```

Result: `26 passed`.

Protected regression selection:

```bat
python -m pytest tests\automated_evaluation tests\inference_pipeline tests\model_runner -q --basetemp artifacts\stage3_pytest_pinned_regression
```

Result: `411 passed, 2 warnings`. The warnings are existing upstream deprecations from Silero/importlib resources and TorchScript loading.

Ruff:

```bat
python -m ruff check app\artifact_contracts scripts\validate_campaign_artifacts.py tests\automated_evaluation\test_stage3_artifact_contracts.py
```

Result: passed.

Additional validation:

```bat
python -m app.gui.validation_harness
python scripts\validate_campaign_artifacts.py --registry-only
python -m compileall -q app\artifact_contracts scripts\validate_campaign_artifacts.py tests\automated_evaluation\test_stage3_artifact_contracts.py
```

Results: GUI validation passed; the registry loaded 30 artifacts and all six scenario profiles; all 11 JSON schemas and two YAML contracts parsed; bytecode compilation passed; and `git diff --check` passed.

All commands above were run from the repository's pinned root `.venv`. A deliberately discarded check with the system Anaconda interpreter reproduced two environment-precondition failures: its PyArrow 16.1 bytes differ from the committed Stage 2 fixture, and it does not contain Whisper. The pinned environment has PyArrow 21.0 and Whisper and passes the protected suite. No source change was made to hide either environment mismatch.

The focused suite covers pre/post-rename interruption, truncated JSONL/Parquet, checksum modification, incomplete transfer, wrong schema/type, missing and conditional artifacts, typed embedding/index/similarity output, object-array NPZ rejection, RTTM/diarization diagnostics, count reconciliation, stale temporary files, all four completion states, campaign detached checksums, environment identity/hash behavior, credential rejection, and Windows/Linux path handling.

## Acceptance criteria

| Criterion | Result |
|---|---|
| Artifact requirements are unambiguous | Pass: 30 definitions and six explicit scenario profiles. |
| Complete/incomplete/corrupt/incompatible are distinct | Pass: classified machine-readable reports and tests. |
| Atomic writes survive simulated interruption | Pass: pre-replace preservation and post-replace detection/reconciliation tests. |
| Checksums detect modification and incomplete transfer | Pass: SHA-256/byte reconciliation and missing-target tests. |
| Schemas and counts validate | Pass: JSON/JSONL/YAML/Parquet/NPZ/RTTM/static environment contracts. |
| Future executor has a stable completion contract | Pass: registry-driven required outputs and final status/count/checksum rules. |
| Existing Evaluation Tool behavior remains functional | Pass: 411-test protected selection and GUI validation harness. |

## Limits and deferred work

- Stage 3 provides no executor or scheduling logic and does not create real `automated_runs` output outside tests.
- Atomic checksum updates are protected by an in-process lock. Future executors must retain one writer per scenario; cross-process locking is unnecessary while workers have non-overlapping scenario assignments, but must be designed if that rule changes.
- `database/campaign.sqlite`, worker assignments, resource telemetry, analysis manifests, and optional model outputs are registered contracts only. Their producers remain future stages.
- Existing ordinary single-run writers are unchanged. The future campaign executor must adapt their completed outputs through `ScenarioArtifactStore` rather than silently replacing protected runner/scorer behavior.
- Stage 3 does not approve a bedroom RIR or change any benchmark selection/condition.

The next execution gate remains the separately pinned CUDA environment and real CUDA contract qualification. Campaign scheduling/execution should be implemented only in its assigned later stage and must consume these contracts without changing Stage 2 identities or Stage 3 artifact semantics.
