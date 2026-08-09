# Phase 2 Report: Immutable Benchmark and Scenario Contracts

## Objective and result

Stage 2 is complete. The Evaluation Tool can now select deterministic `small`, `standard`, and `large` benchmark tiers from the existing normalized metadata, freeze a disjoint speaker enrollment/probe protocol, audit exact RIR identities, resolve named acoustic condition sets, and expand validated canonical scenarios without running inference.

The public contracts `benchmark-manifest.v1`, `manifest-canonicalization.v1`, `manifest-hash.v1`, `scenario-definition.v1`, `scenario-canonicalization.v1`, and `scenario-hash.v1` are released and frozen. Breaking wire, canonicalization, or identity changes require a new explicit version. Existing IDs must never be silently recomputed under changed rules.

No source audio was copied. No model was loaded. No inference, scoring, campaign execution, retry/resume, worker assignment, distributed execution, or GPU qualification was performed.

## Implemented files

Runtime contract package:

- `app/benchmark_contracts/canonical.py`: NFC UTF-8 canonical JSON, finite float normalization, null/absent distinction, project-relative path normalization, SHA-256, and stable rank generation;
- `app/benchmark_contracts/policy.py`: panel/dataset/metadata augmentation policy and condition enforcement;
- `app/benchmark_contracts/manifest_io.py`: fixed Arrow schema, deterministic uncompressed Parquet, immutable identity, logical row conversion, and cross-field validation;
- `app/benchmark_contracts/manifest.py`: deterministic tier and speaker-protocol selection using actual normalized metadata and the existing loader;
- `app/benchmark_contracts/rir_registry.py`: exact RIR registry loading, hash/size audit, unresolved/excluded semantics, and condition resolution;
- `app/benchmark_contracts/scenario.py`: pipeline identity freezing, canonical expansion, public identity payload, validation, and global scenario IDs;
- `app/benchmark_contracts/versions.py` and `__init__.py`: frozen constants and public exports;
- `scripts/build_benchmark_contracts.py`: non-inference build entry point.

Versioned configuration and schemas:

- `configs/automated_evaluation/benchmark_targets.v1.yaml`;
- `configs/automated_evaluation/rir_registry.v1.yaml`;
- `configs/automated_evaluation/condition_sets.v1.yaml`;
- `configs/automated_evaluation/contracts.v1.yaml`;
- `configs/automated_evaluation/schemas/benchmark_manifest.v1.schema.json`;
- `configs/automated_evaluation/schemas/scenario_definition.v1.schema.json`.

Tests and frozen fixtures:

- `tests/automated_evaluation/test_stage2_benchmark_contracts.py`;
- `tests/automated_evaluation/fixtures/stage2/golden_manifest*`;
- `tests/automated_evaluation/fixtures/stage2/golden_scenario*`.

Documentation:

- `README.md`;
- `benchmarks/v1/README.md`;
- `docs/automated_evaluation/README.md`;
- `docs/automated_evaluation/protected_interfaces.md`;
- this report.

## Existing interfaces preserved

The builder does not replace or modify normalized metadata behavior. It uses normalized Parquet only to identify deterministic candidates, then calls `app.dataset_registry.loader.load_dataset_selection()` and `selection_records()` to obtain final records and portable paths. Existing dataset definitions, path rebasing, runtime augmentation, model logic, runners, scoring, plotting, reports, GUI, and CLI behavior remain protected.

The Stage 1 resolver is reused only to freeze selected/resolved Whisper Base configuration contents, component identities, model identities, and hashes. Resolution prohibits implicit downloads and does not instantiate a model.

## Manifest design and generated identities

Authoritative representation is deterministic uncompressed Parquet. Rows are sorted by declared canonical keys and written with a fixed Arrow schema and metadata. The full file bytes are hashed with SHA-256; IDs use `manifest_<first-12-hex>`.

Selection rank is the SHA-256 of a canonical mapping containing seed `3800`, dataset key, source recording ID, and utterance ID. Selection does not depend on dataframe order. Every row preserves project-relative source identity, bounds, reference metadata, speaker identity, explicit augmentation policy, rank, and a recomputable source-metadata hash.

| Artifact | Rows | Manifest ID | SHA-256 |
|---|---:|---|---|
| `small_source_manifest.parquet` | 405 | `manifest_0bd28359f11a` | `0BD28359F11AB283C349386BB5DFC78E52C3C1E8B4EDE271551F5029C9FC44F6` |
| `standard_source_manifest.parquet` | 2,083 | `manifest_55d9e81b041b` | `55D9E81B041BB589FAAB173E76BE89B59AAFAF3C6B02409201EA7A5F10AA01C0` |
| `large_source_manifest.parquet` | 8,258 | `manifest_bc207e61b820` | `BC207E61B82052F06CCB9FFFE038B6DFE7B1C65C21843D08905946114238DE88` |
| `speaker_protocol.parquet` | 1,488 | `manifest_a9b0b28f5c7f` | `A9B0B28F5C7FDEF51215069521215BB78598DB9497E40BDA6C893181F71288D4` |

The source-tier panel totals are:

| Tier | Controlled clean | Native robustness | Total duration |
|---|---:|---:|---:|
| small | 165 | 240 | 2,208.623880 seconds |
| standard | 760 | 1,323 | 10,843.437575 seconds |
| large | 1,960 | 6,298 | 38,897.208099 seconds |

Speaker protocol rows are 108 small, 420 standard, and 960 large. Enrollment source utterances do not overlap known or unknown probe source utterances. Clean and degraded probe rows intentionally refer to the same frozen probe source selection so acoustic-condition comparisons remain paired.

`manifest_summary.json` records requested/realized counts, durations, speakers, authorized gender/accent distributions, identities, and shortfalls. `selection_audit.csv` records a reason for every nonzero shortfall.

## Observed shortfalls

Shortfalls were not silently filled from unapproved splits or reclassified metadata:

- small: HiFiTTS clean 15/50 and HiFiTTS other 16/20;
- standard: HiFiTTS clean 60/200, AMI 518/576, HiFiTTS other 40/50, and VOiCES 120/640;
- large: HiFiTTS clean 300/1,000, LibriSpeech clean 760/2,000, AMI 3,168/3,600, HiFiTTS other 160/200, LibriSpeech other 330/1,000, and VOiCES 240/3,200.

The large LibriSpeech requests deliberately expose that normalized `dev-clean` and `dev-other` contain only 40 and 33 speakers. HiFiTTS retains the normalized clean/other reader labels. VOiCES eligibility and balanced source/condition requirements leave substantially fewer qualifying test speakers/source utterances than the nominal corpus speaker count. Exact explanations are in the audit rather than inferred by downstream code.

## Augmentation policy

Every manifest row contains `allow`, `native_only`, or `review`. Current emitted controlled-clean CMU Arctic, LibriSpeech clean, and HiFiTTS clean rows are `allow`. AMI, VOiCES, CHiME-6, approved LibriSpeech other, approved HiFiTTS other, and any metadata-marked native noisy/reverberant row are `native_only`.

Both scenario expansion and public validation reject synthetic noise/RIR requests for native-only rows. `none` requires null noise, SNR, and RIR. Noise requires exact white/pink identity and finite SNR. Reverberation requires a complete exact RIR identity. RIR-plus-noise requires both.

## RIR registry and condition sets

The actual flat RIR collection was inspected and hashed. The directory contains 270 WAV files, while the collection label implies 271; the discrepancy is explicit in `rir_registry_audit.json`.

- dining room `h025_Diningroom_8txts.wav`: approved and hash verified;
- restaurant `h093_Restaurant_2txts.wav`: approved and hash verified;
- bedroom: unresolved; 11 candidate filenames/hashes/sizes are recorded, but none is silently selected;
- historical kitchen request: unresolved;
- `h044_ParkingLot_4txts.wav`: accurately recorded as ParkingLot and excluded, never represented as kitchen.

Named sets are `smoke`, `core_controlled`, `all_approved_rir_environments`, `selected_rir_plus_noise_interactions`, `speaker_degraded`, and `native_only`. Bedroom emits no executable condition until an exact candidate is separately approved. No acoustic characterization or RT60 computation was added.

## Scenario contract

Every scenario includes schema/canonical/hash versions, exact manifest identity, panel/tier/slice, condition, pipeline component/config/model contents and hashes, seed, repetition, device, dtype, batch/runtime settings, timeout/resource/scoring/failure policy. The public identity excludes worker, machine, absolute/output paths, start time, retry/attempt number, and non-result references.

Canonical JSON uses sorted NFC-normalized mapping keys, preserves array order, keeps integers distinct from floats, preserves explicit null versus absent fields, normalizes portable paths to forward slashes, rejects absolute/traversing paths, forbids non-finite floats and timestamps, and emits UTF-8 without ASCII escaping. Scenario IDs are `scenario_<first-12-lowercase-hex>` from the full canonical SHA-256.

Cross-field validation verifies manifest ID/hash agreement, exact RIR filename/path agreement, selected/resolved/component hash shapes, resolved/component content hashes, model asset hash consistency, component/model family agreement, and runtime agreement with the resolved pipeline.

The generated catalog contains 108 unique validated scenarios using `live_mic_whisper_base`. Counts by tier/panel are in `scenario_catalog_summary.json`. These are definitions only, not completed runs.

## Commands and verification evidence

Pinned-environment rebuild:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
.venv\Scripts\activate
cd "Software Validation from Datasets\Evaluation Tool"
python scripts\build_benchmark_contracts.py --output benchmarks\v1
```

Result: completed in 391.4 seconds, emitted the four identities above and 108 scenarios, and printed `No inference was run.` Rebuilding under the pinned PyArrow 21.0 environment preserved every authoritative manifest hash.

Focused Stage 2 tests:

```bat
python -m pytest tests\automated_evaluation\test_stage2_benchmark_contracts.py -q --basetemp artifacts\stage2_pytest_pinned
```

Result: `35 passed`.

Protected regression selection:

```bat
python -m pytest tests\automated_evaluation tests\inference_pipeline tests\model_runner -q --basetemp artifacts\stage2_pytest_regression
```

Result: `385 passed, 2 warnings`. Both warnings are upstream deprecations from Silero/importlib resources and TorchScript loading; no test failed.

Additional verification:

- all four generated Parquet files re-read through the v1 validator and matched their stored SHA-256;
- all 108 scenarios passed cross-field/canonical identity validation and had 108 unique IDs;
- Ruff passed for the Stage 2 package, build script, and tests;
- GUI validation harness passed, including its existing scoring exercises;
- no model or inference process ran during Stage 2 generation.

## Acceptance criteria

| Criterion | Result |
|---|---|
| Identical pinned inputs create byte-stable canonical outputs | Pass; golden byte fixture and unchanged rebuilt manifest hashes. |
| Result-affecting changes create new scenario IDs | Pass; condition, runtime/config, resource, failure, and repetition tests. |
| Machine, worker, output path, start time, and retry do not affect IDs | Pass. |
| Manifests validate | Pass; schema, path, rank, source hash, bounds, role/panel, policy, and disjointness checks. |
| Augmentation restrictions are enforced | Pass. |
| RIR identities are accurate | Pass; dining/restaurant verified, kitchen/bedroom unresolved, ParkingLot excluded. |
| Golden hashes are present and reproducible | Pass. |
| Existing protected behavior remains functional | Pass; 385-test selection and GUI harness. |

## Decisions, assumptions, and limitations

- The pinned repository `.venv` and `requirements/core.txt` are authoritative for canonical Parquet generation. Cross-version PyArrow output is not claimed byte-identical; dependency changes that alter bytes require an explicit contract/version decision.
- Actual normalized metadata governs realizable counts. Shortfalls are preserved rather than backfilled from disallowed datasets or splits.
- The speaker protocol is CMU Arctic-only in v1, preserving the already qualified known/unknown boundary.
- Whisper Base is the default scenario identity reference. Other existing inference YAML identities can be added with repeatable `--pipeline-config` arguments without inference.
- Bedroom remains requested but unresolved. No bedroom, kitchen, or ParkingLot execution scenario exists in the released catalog.
- The schemas and validators define scenario inputs; Stage 2 does not create execution status or output directories.

## Deferred work and next gate

The following remain deliberately outside Stage 2:

- scenario execution, campaign manifests/databases, status, retry, timeout enforcement, resume, and stop requests;
- worker assignments, range/component selection, two-machine partitioning, transfer validation, and result merging;
- resource telemetry, disk/GPU monitoring, reporting, and analysis handoff manifests;
- benchmark scoring or model/component comparisons;
- standard/large inference and GPU concurrency qualification;
- approval of one exact bedroom RIR.

The next execution gate remains creation/verification of the separately pinned CUDA environment and real CUDA contract qualification, one GPU-heavy run at a time. Standard or large benchmark inference, performance-based model selection, and concurrency tests must not begin before that gate passes. A later campaign-execution stage may consume these frozen contracts but must not alter their identities.
