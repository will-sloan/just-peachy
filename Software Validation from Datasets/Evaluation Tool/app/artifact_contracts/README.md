# Campaign Artifact Contracts

## Purpose

This package defines the Stage 3 exchange boundary for future automated campaigns. It provides the versioned artifact registry, Windows-safe campaign/scenario layout, atomic publishers, checksum manifests, typed artifact validation, scenario-completeness classification, and static environment fingerprints.

It does not execute inference, schedule scenarios, assign workers, collect runtime telemetry, retry work, or alter the ordinary Evaluation Tool run format.

## Inputs

- `configs/automated_evaluation/artifact_registry.v1.yaml`;
- JSON Schemas under `configs/automated_evaluation/schemas`;
- Parquet column contracts in `configs/automated_evaluation/table_schemas.v1.yaml`;
- a Stage 2 `scenario-definition.v1` resolved scenario;
- future scenario artifacts rooted at `automated_runs/<campaign_id>/scenarios/<scenario_id>`;
- explicit model and component hashes when collecting an environment fingerprint.

No credentials are inputs. Credential values are rejected from run configuration, diagnostics, failures, event/error logs, runner logs, and environment fingerprints.

## Outputs

The package can create contract directories, atomically publish registered scenario artifacts, maintain `checksums.json`, publish `campaign_manifest.json` with `campaign_manifest.sha256`, collect one `environment-fingerprint.v1` mapping, and produce a `completion-validation.v1` report with one of four states:

- `complete`: all required/conditional artifacts, schemas, counts, and checksums reconcile;
- `incomplete`: required data or checksum entries are missing, status is unfinished, or a temporary file remains;
- `corrupt`: bytes, schemas, hashes, or stored counts contradict each other;
- `incompatible`: an unknown registry/schema/scenario type or unregistered artifact is present.

## Directory contract

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
          embeddings/                    # conditional NPZ + index
          similarity_scores.parquet      # conditional
          diarization_diagnostics.jsonl  # conditional
        metrics/
          item_metrics.parquet
          grouped_metrics.parquet
          summary.json
          failures.parquet
        resource_logs/                    # reserved; no Stage 3 collection
        logs/
          events.jsonl
          runner.log
          errors.jsonl
        report/
          scenario_report.json
          scenario_report.md
        checksums.json
    audit/
      environment_fingerprints/
    analysis/
```

The registry specifies producer, format, schema, mandatory/conditional status, validation rules, checksum policy, privacy classification, and downstream consumers for every material artifact. Pickle is forbidden as an exchange format.

## Atomic publication contract

`ScenarioArtifactStore` writes each artifact to a same-directory `.tmp-<uuid>` file, closes and fsyncs it, validates its schema, calculates SHA-256 and byte count, atomically replaces the destination, and atomically updates `checksums.json`. An interruption before replacement preserves the previous artifact. An interruption after replacement but before checksum-index update is safely detectable and can be repaired with `reconcile_checksum_manifest()` after all materialized artifacts revalidate.

`checksums.json` intentionally excludes itself to avoid recursive hashes. Campaign manifest bytes use the detached `campaign_manifest.sha256` sidecar.

## Validate in Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\validate_campaign_artifacts.py --registry-only
python scripts\validate_campaign_artifacts.py --scenario-dir automated_runs\<campaign_id>\scenarios\<scenario_id>
python scripts\validate_campaign_artifacts.py --campaign-dir automated_runs\<campaign_id>
python -m pytest tests\automated_evaluation\test_stage3_artifact_contracts.py -q --basetemp artifacts\pytest_stage3
```

The scenario validator exits `0` only for `complete`; it exits `2` for incomplete, corrupt, or incompatible results. Validation is read-only.

## Validate in PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/validate_campaign_artifacts.py --registry-only
python scripts/validate_campaign_artifacts.py --scenario-dir automated_runs/<campaign_id>/scenarios/<scenario_id>
python -m pytest tests/automated_evaluation/test_stage3_artifact_contracts.py -q --basetemp artifacts/pytest_stage3
```

## Environment fingerprint

`collect_environment_fingerprint()` records Git commit/dirty state, OS, Python executable/version, pinned profile and package freeze, CPU/RAM, static GPU identity/UUID/VRAM, driver, CUDA runtime, explicit model/component hashes, timezone, and clock implementations/resolutions. GPU lookup is a one-time static identity query, not telemetry sampling. Collection time is audit metadata and is excluded from the stable fingerprint hash.

Environment fingerprints may contain machine-specific executable paths and hardware identifiers and are therefore `restricted_system`. They are never part of the global Stage 2 scenario identity.
