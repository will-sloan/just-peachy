# Phase 0 Report — Readiness Freeze and Component Inventory

## Objective

Complete Stage 0 only: inspect the inherited Evaluation Tool and its in-repository speech pipeline, freeze approved decisions, create complete versioned component and environment-profile records, document protected interfaces, correct readiness-harness inconsistencies, and validate the package without implementing campaign execution or changing inference/model behavior.

## Files changed

Stage 0 files added:

- `configs/automated_evaluation/component_registry.v1.yaml`;
- `configs/automated_evaluation/environment_profiles.v1.yaml`;
- `docs/automated_evaluation/README.md`;
- `docs/automated_evaluation/protected_interfaces.md`;
- `docs/automated_evaluation/stage_0_readiness_freeze.md`;
- `docs/automated_evaluation/phase_0_report.md`;
- `tests/automated_evaluation/test_stage0_readiness.py`.

Small supporting changes:

- `scripts/qualify_speech_components.py`: the composition reference is now explicitly Whisper Base instead of opportunistically selecting Vosk/Sherpa/Tiny;
- `tests/inference_pipeline/test_component_qualification.py`: asserts the Whisper Base decision;
- `tests/inference_pipeline/test_faster_whisper_adapter.py`: makes a missing-model unit test simulate package presence so it reaches the intended asset-error branch in the core environment where the optional package is absent.

Existing unrelated/user-owned changes were not edited: the staged `Resumes/` removal/ignore work, the modified planning DOCX, and the previously generated untracked speaker-protocol artifacts.

## Interfaces added or modified

Added documentation/configuration contracts:

- `component-registry.v1` with 37 entries: every one of the 27 runtime-registered components, enrollment generation, temporal speaker evidence, and fixed/dummy test implementations;
- `evaluation-environment-profiles.v1` with seven mutually separated profiles;
- reserved future identifiers `benchmark-manifest.v1`, `scenario-definition.v1`, `scenario-canonicalization.v1`, and `scenario-hash.v1`, without implementing their wire formats;
- a written protected-interface boundary for metadata, augmentation, runners, pipeline contracts, minimum predictions, scoring, reporting, GUI, and CLI.

Modified only one operational support interface: the component qualification harness now uses the approved Whisper Base fragment for combination qualification. This changes readiness evidence, not `PipelineRunner`, component model logic, ordinary inference configuration, predictions, scoring, or user-facing execution.

## Commands executed

Read-only inspection included Git branch/commit/divergence/status/history, repository and Evaluation Tool documentation, prior milestone/phase reports, requirements/install/bootstrap/verifier/qualifier scripts, component and higher-level YAML, runtime adapter classes, model caches, GPU state, dataset directories, RIR filenames, file hashes, and tests.

Important executable checks:

```text
python -m pip check
python scripts/verify_install.py --profile dev --device cpu --cache-root models/cache --whisper tiny,base,small --require-models
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
python scripts/qualify_speech_components.py --audio <CMU arctic_b0476.wav> --output runs/component_qualification/cpu_contract_20260807.json
python -m pytest tests/automated_evaluation/test_stage0_readiness.py tests/inference_pipeline/test_component_qualification.py -q
python -m pytest <protected-interface regression selection> -q
python -m pytest tests/inference_pipeline tests/automated_evaluation -q
python -m ruff check <changed tests>
python -m ruff check --ignore E402 scripts/qualify_speech_components.py
```

No dependency was installed, no model was downloaded, no account/terms acceptance occurred, and no system-wide environment variable was changed during Stage 0.

## Tests executed

1. Stage 0 schema/completeness/decision/profile tests plus qualification-harness tests.
2. Protected prediction/identity/runner/config/install/optional-backend regression selection.
3. Entire `tests/inference_pipeline` plus Stage 0 tests.
4. Ruff on changed Python tests; Ruff on the existing qualifier with its pre-existing path-bootstrap `E402` pattern explicitly ignored.
5. Real CPU component qualification on a local CMU Arctic WAV.
6. Development environment verifier and `pip check`.

## Test results

- focused Stage 0 and qualification-harness suite: `17 passed` after the final higher-level-reference completeness test was added;
- protected regression selection: `87 passed`;
- first full inference run: `322 passed, 1 failed, 2 warnings`; the failure was an environment-dependent Faster-Whisper test that expected a missing-model error before accounting for the intentionally missing optional package;
- after making that test branch explicit and adding the final reference-completeness check: `324 passed, 2 warnings`;
- Ruff: passed for changed tests and passed for the qualifier with existing `E402` path-bootstrap exceptions ignored;
- `pip check`: passed (`No broken requirements found`);
- development verifier: 25 of 26 checks non-failing; FFmpeg was not visible on this process PATH;
- real component qualification: 19 total, 6 qualified, 13 unavailable, 0 failed.

The two full-suite warnings are upstream deprecations from Silero's use of `importlib.resources.path` and Torch's `torch.jit.load`; they do not indicate Stage 0 failures.

## Generated artifacts inspected

### CPU qualification report

`runs/component_qualification/cpu_contract_20260807.json` was parsed and manually inspected. It records schema `speech-component-qualification.v1`, relative source-audio identity and SHA-256, Python/Torch/CUDA/credential-presence booleans, per-component duration/evidence, and a summary. Qualified paths are:

- Energy VAD + VAD chunks + Whisper Base;
- Silero VAD + VAD chunks + Whisper Base;
- Whisper Tiny;
- Whisper Base;
- Whisper Small;
- SpeechBrain ECAPA + cosine threshold + Whisper Base.

All optional unavailable results carry explicit reasons and none are counted as code failures. Credential values are absent. One NeMo unavailable reason contains absolute search paths; this is diagnostic leakage of machine location, not a credential. A later artifact-normalization phase should replace such candidate paths with root-relative/log-safe forms.

### Speaker protocol

The previously created `artifacts/speaker_protocol/cmu_arctic_seed3800_v1` was inspected instead of regenerated. Its manifest freezes seed 3800, 18 speakers, 12 known/6 held out, 60 enrollment utterances, 120 known probes, 60 unknown probes, disjoint roles, source hashes, and literal `Unknown` scoring. The SpeechBrain enrollment database has 12 speakers, 60 exemplars, one model ID, and 192-dimensional embeddings.

The protocol manifest and items use relative paths, but the 12 generated per-speaker enrollment Markdown reports contain absolute source paths in replay commands. Those user-owned artifacts were preserved. They should be sanitized or regenerated portably before cross-machine handoff.

### Model and RIR inventory

Whisper Tiny/Base/Small and SpeechBrain ECAPA cache files were size/hash checked against `environment_profiles.v1.yaml`. The MIT RIR source was confirmed to be a flat WAV directory. Dining room and restaurant identities/hashes were recorded; all bedroom candidates were listed; `h044_ParkingLot_4txts.wav` was confirmed and excluded.

### Credential/path scan

Stage 0 configs/docs, the qualification report, and the speaker-protocol artifacts were scanned for likely Hugging Face/Picovoice secret values; none were found. Only approved credential variable names and false presence flags appear. Expected local setup examples and the previously noted diagnostic/replay paths are the absolute paths present.

## Implementation decisions

- Code and disk contents override stale documentation for actual interfaces and RIR identity.
- Latest explicit user instructions override the older kitchen/15-environment requirement: current RIR scope is dining room, bedroom, restaurant; no kitchen and no Parking Lot substitute.
- Current readiness is based on this environment's real qualification artifact. Historical success on another machine is evidence history, not current readiness.
- Core components remain in the qualified CPU profile; optional local, ONNX, credential-gated, and Linux/CUDA NeMo dependencies are isolated.
- A missing prerequisite is a readiness status/blocker, not an implementation failure.
- No-op/fixed/dummy implementations are contract-only and cannot support model performance claims.
- Model caches with no colocated license metadata may be used for internal qualification, but the registry does not authorize redistribution.
- Public benchmark/scenario contract identifiers are reserved; their absent wire implementations were not invented in Stage 0.

## Assumptions

- The checked-out `handoff` branch and commit `e7e5516991b95f4e7c915e852fc0b4f5bae7cd11` are the handoff baseline even though the working tree contains preserved user changes.
- The user's local possession of the six raw datasets supports internal evaluation; redistribution rights are outside this repository and were not inferred.
- FFmpeg 8.1.2 remains correctly installed by WinGet and only needs a refreshed/fixed process PATH.
- Existing model hashes identify the intended local assets; upstream terms still govern use and redistribution.
- The exact bedroom RIR requires user approval because multiple real bedroom responses exist and no technical rule was authorized to choose one silently.

## Limitations

- Current Torch is CPU-only; no CUDA component is qualified in this environment.
- No real diarization backend is qualified on this machine.
- Optional local/ONNX packages and assets are absent.
- Pyannote and Falcon require user-controlled terms/credentials.
- NeMo requires a separate Linux/CUDA profile and assets.
- The current verifier cannot discover FFmpeg until PATH is refreshed/fixed.
- Stage 0 records component contracts/readiness but does not compare accuracy, calibrate speaker thresholds, execute scenarios, merge workers, or generate campaign reports.
- Benchmark/scenario schema/hash wire contracts do not yet exist.

## Unresolved issues

1. Select one exact bedroom RIR filename from the recorded candidates before scenario generation.
2. Choose and pin the official Python-3.12-compatible CUDA Torch 2.11.0 build/index, then build a separate CUDA environment.
3. Refresh/fix FFmpeg PATH and rerun the verifier to reach 26/26.
4. Decide whether/when to provision each optional package, asset, account, term acceptance, and credential.
5. Record upstream license/model-card provenance if model or dataset artifacts will be redistributed rather than used internally.
6. Sanitize machine-specific paths in future generated qualification/enrollment reports.
7. Implement and validate benchmark/scenario canonicalization and hashing in their assigned later phase before calling those wire shapes frozen public releases.

## Deferred work

- campaign/manifest/scenario execution, persistence, resume, retry, partitioning, merge, and analysis manifests;
- CUDA performance/resource qualification and GPU concurrency qualification;
- staged model screening and targeted combination tests;
- controlled noise/RIR benchmark generation;
- standard/large benchmark execution;
- optional diarization/backend setup and qualification;
- new metric, plot, comparison, and campaign-report implementation.

## Readiness for the next phase

Stage 0 acceptance criteria pass: every discovered runtime component has a disposition, protected interfaces and decisions are explicit, environment profiles are versioned, missing prerequisites/terms/platform issues are explicit, and protected inference/model behavior was not changed. The core CPU path is qualified for contract work.

The next phase may begin only with environment cleanup and CUDA qualification: refresh FFmpeg PATH, preserve the CPU environment, select/pin the exact CUDA Torch build in a separate environment, and run real CUDA contract qualification one GPU-heavy scenario at a time. Do not begin standard/large benchmarks, model selection, or concurrency testing yet. Bedroom-RIR selection is not required for CUDA contract qualification but remains a hard gate before scenario manifest generation.
