# Stage 2 Benchmark Contracts

## Purpose

This directory is the frozen Stage 2 source-selection and scenario-definition handoff. It contains deterministic benchmark rows selected from the existing normalized metadata, exact RIR identities, selection audits, and canonical scenario definitions. It does not contain copied source audio, predictions, metrics, campaign state, worker assignments, or inference results.

The authoritative benchmark representation is uncompressed Parquet under `benchmark-manifest.v1`. JSONL is authoritative only for the scenario catalog, whose rows use `scenario-definition.v1`, `scenario-canonicalization.v1`, and `scenario-hash.v1`.

## Inputs

- normalized metadata under `../Normalized Metadata`;
- existing dataset registry and metadata loader;
- seed `3800` and tier quotas in `configs/automated_evaluation/benchmark_targets.v1.yaml`;
- exact RIR records in `configs/automated_evaluation/rir_registry.v1.yaml`;
- named conditions in `configs/automated_evaluation/condition_sets.v1.yaml`;
- Whisper Base composition in `configs/inference/live_mic_whisper_base.yaml`, used only to freeze pipeline identity;
- locally available source audio and RIR files for path/hash validation.

No model is loaded and no inference is run by the build command.

## Outputs

| File | Purpose |
|---|---|
| `small_source_manifest.parquet` | 405 small-tier controlled/native rows; `manifest_0bd28359f11a`. |
| `standard_source_manifest.parquet` | 2,083 standard-tier controlled/native rows; `manifest_55d9e81b041b`. |
| `large_source_manifest.parquet` | 8,258 large-tier controlled/native rows; `manifest_bc207e61b820`. |
| `speaker_protocol.parquet` | 1,488 enrollment/probe rows across all three tiers; `manifest_a9b0b28f5c7f`. |
| `manifest_summary.json` | Counts, durations, speakers, authorized gender/accent distributions, hashes, and shortfalls. |
| `selection_audit.csv` | Requested/realized counts and a reason for every shortfall. |
| `rir_registry_audit.json` | Requested/resolved RIR paths, hashes, status, discrepancies, and bedroom candidates. |
| `resolved_scenarios.jsonl` | 108 validated, globally stable scenario definitions for the reference pipeline. |
| `scenario_catalog_summary.json` | Scenario totals by tier/panel and selected pipeline IDs. |

The RIR audit records 270 observed WAV files against the collection label’s expected count of 271. Dining room `h025` and restaurant `h093` are approved. Bedroom is unresolved and therefore emits no executable condition. The historical kitchen request is unresolved; `h044_ParkingLot_4txts.wav` remains ParkingLot and is excluded.

## Rebuild in Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\build_benchmark_contracts.py --output benchmarks\v1
```

To build manifests and the RIR audit without expanding scenarios:

```bat
python scripts\build_benchmark_contracts.py --output benchmarks\v1 --skip-scenarios
```

## Rebuild in PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
.\.venv\Scripts\Activate.ps1
Set-Location 'Software Validation from Datasets\Evaluation Tool'
python scripts/build_benchmark_contracts.py --output benchmarks/v1
```

The source metadata and configuration files must be identical to reproduce the listed bytes and SHA-256 values. Rebuilding with changed inputs intentionally creates new manifest/scenario identities.

## Validate

```bat
python -m pytest tests\automated_evaluation\test_stage2_benchmark_contracts.py -q --basetemp artifacts\pytest_stage2
python -m ruff check app\benchmark_contracts scripts\build_benchmark_contracts.py tests\automated_evaluation\test_stage2_benchmark_contracts.py
```

Golden fixtures under `tests/automated_evaluation/fixtures/stage2` protect byte-stable Parquet output, canonical scenario bytes, and full hashes. A breaking schema, canonicalization, or hash change must introduce a new public version; existing IDs must never be silently recomputed.
