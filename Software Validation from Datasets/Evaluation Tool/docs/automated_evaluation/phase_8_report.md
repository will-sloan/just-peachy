# Phase 8 — Extended Backend Setup and Environment Qualification

## Outcome

Stage 8 is implemented without beginning scientific screening. Thirteen configured extended backends now have versioned profiles, pinned setup inputs, registered assets, an independent offline qualification path, one explicit status each, and consolidated machine evidence. Nine backends produced real repeated valid outputs. Four remain correctly blocked: WeNet by an incompatible/missing runtime asset, pyannote and Falcon by personal licence actions, and NeMo by Linux/CUDA platform and unresolved checkpoint requirements.

The separately isolated CUDA prerequisite also passed real single-job qualification for Whisper Tiny, Base, Small, and SpeechBrain ECAPA. The Stage 0–7 CPU environment was not upgraded and the core regression suite remained functional.

## Implemented contracts and tooling

- `environment_profiles.stage8.v1.yaml` defines eight reproducible profiles.
- `extended_backends.v1.yaml` gives every scoped adapter one family, profile, packages, assets, platforms, and gated requirements.
- `model_asset_registry.v1.yaml` records source, licence, artifact, expected hash where known, acquisition method, portable storage, profile, credential requirement, and required files.
- `scripts/install_stage8_profile.ps1` builds Windows environments one family at a time, checks dependencies, optionally bootstraps only declared models, and freezes packages.
- `scripts/install_stage8_nemo_linux.sh` defines the isolated Linux/CUDA candidate setup without claiming qualification.
- `scripts/qualify_extended_backends.py` runs real repeated adapter and composition checks with downloads disabled.
- `scripts/inventory_stage8_assets.py` writes observed per-file and aggregate model identities.
- `scripts/consolidate_stage8_qualification.py` rejects incomplete/duplicate catalog coverage and writes a checksummed summary.

## Safety and compatibility decisions

No account, licence acceptance, credential, or token was created or saved. Credential values are never serialized; only environment-variable presence is recorded. The user actions are listed in `extended_backend_setup.md`.

WeNet's downloaded `final.pt` was not renamed or represented as the required TorchScript `final.zip`. WeSpeaker's unavoidable metadata mismatch is confined to its isolated environment and explicitly recorded. NeMo is not forced into Windows. Model acquisition is separate from scenario execution, and every qualifier forces local-only loading.

## Evidence and validation

Machine evidence lives under `runs/extended_backend_qualification/`. `qualification_summary.json` is the canonical index for this machine and references all source evidence and the model inventory by SHA-256. Environment freezes live under `.stage8-envs/<profile>/environment.freeze.txt` and are represented by hashes and package counts in profile evidence.

The Stage 8 unit/contract suite covers profile schemas, package/asset distinctions, credential-presence handling, status classification, adapter/output contracts, model identity, explicit devices, no-download behavior, pipeline composition, and consolidated coverage. Real backend qualifications are intentionally run with each profile's interpreter, never emulated by the core test environment.

Final completed checks were:

- Stage 8 contracts: 13 passed, 1 expected skip because WebRTC is isolated from the core interpreter;
- changed ASR/config/bootstrap regressions: 26 passed;
- model-runner regressions: 5 passed;
- Ruff on all Stage 8 Python and the adjusted WeNet adapter: passed;
- secret audit: 9 qualification JSON files inspected, 0 prohibited secret-value fields;
- consolidated catalog coverage: 13/13 unique backends, 0 missing, 0 unexpected.

The core 501-test regression scope passed after the installed backend families were added (501 passed, 2 skipped). A final combined rerun after documentation/evidence consolidation reached 73% with no failures before the five-minute command cap; changed-code and Stage 8 subsets then completed separately as listed above. An unrestricted repository discovery run also timed out in older slow dataset/integration tests without reporting a failure and is not represented as a completed pass.

## Deferred to later stages

Stage 8 does not add candidates to controlled or native benchmark matrices, rank models, choose a production pipeline, run diarization science metrics, or test GPU concurrency. Stage 9 may screen only the backends that remain qualified after environment reproduction on the execution machine.
