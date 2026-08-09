# Phase 1 Report - Component Catalog, Pipeline Resolver, and Configured Runner

## Objective

Implement Stage 1 only: make the Stage 0 runtime component inventory readable by execution code, resolve one explicit existing pipeline composition without mutating source YAML, and run that composition through the ordinary Evaluation Tool dataset, augmentation, inference, prediction, scoring, plotting, and reporting lifecycle. Campaign state, scenario generation, retries, resume, and distributed execution remain unimplemented.

## Baseline and preserved work

The implementation started from branch `handoff` at commit `e7e5516991b95f4e7c915e852fc0b4f5bae7cd11`. Existing staged `Resumes/` ignore/removal work, the user-modified planning DOCX, and existing speaker-protocol artifacts were preserved and not edited. Stage 0 files and qualification changes were treated as inherited prerequisites.

## Files added

- `app/inference_pipeline/catalog.py`: integrity-checked runtime catalog derived from `component_registry.v1.yaml`, the active Python registry, and existing component fragments.
- `app/inference_pipeline/resolver.py`: scenario-independent composition, compatibility/download validation, override provenance, warnings, and artifact writing.
- `app/model_runner/configured.py`: explicit `PipelineRunner` bridge and prediction/diagnostic/failure adaptation.
- `tests/automated_evaluation/test_stage1_configured_runner.py`: Stage 1 unit, contract, malformed-output, failure, and real-model smoke coverage.
- `docs/automated_evaluation/phase_1_report.md`: this report.

## Files modified

- `app/cli/main.py`: adds the opt-in `configured` runner and `--inference-config`, repeatable `--component`, and repeatable `--inference-override` arguments. Existing defaults are unchanged.
- `app/model_runner/base.py`: adds a default no-op per-item failure hook and calls it inside the existing protected per-item exception boundary.
- `app/model_runner/__init__.py`: exports the configured runner.
- `app/utils/paths.py`: recognizes every existing raw-dataset project anchor alias, including the repository's actual `Raw Datasets (Not formatted)` folder. This narrow fix was required for an ordinary CLI run from the current repository layout.
- `README.md` and `docs/automated_evaluation/README.md`: purpose, inputs, outputs, Anaconda/Command Prompt/PowerShell commands, and stage boundary.

## Interfaces added or modified

### Component catalog

`ComponentCatalog.load()` reads the Stage 0 registry and exposes the 27 executable runtime components across the six active families. It verifies registry/config hashes and active-registry identity, then exposes family, implementation class/path, source config path/hash, package/asset/credential/platform requirements, device/dtype, input/output contracts, compatibility rules, qualification status/evidence, model identity, and local model asset size/hash where practical. It does not introduce a competing component configuration format.

### Pipeline resolver

`resolve_pipeline()` starts from an existing higher-level inference YAML, uses the existing `PipelineConfig` composition behavior, optionally substitutes one existing catalog entry per family, applies only explicit supported dotted overrides, validates structural compatibility and download prohibition, and returns a `ResolvedPipeline`. It never writes to a source YAML. Every override records source presence/value/origin, requested value, and final value.

The resolver writes:

- `inference/selected_inference_config.json`;
- `inference/resolved_inference_config.yaml`;
- `inference/component_identity_summary.json`;
- `inference/configuration_warnings.json`;
- `inference/configured_runner_artifacts.json`.

The resolved YAML remains loadable by the existing `PipelineConfig` reader. Component identity records retain both the actual source fragment identity and the corresponding Stage 0 registry identity.

### Configured evaluator runner

`ConfiguredEvaluatorRunner` is opt-in. The existing default simulation runner and `ExternalStubRunner` remain unchanged. The new path is:

```text
existing deterministic dataset selection
-> existing runtime augmentation/materialized inference_audio_path
-> resolved existing PipelineConfig
-> existing PipelineRunner
-> PipelineOutput
-> configured prediction adapter
-> existing six-field utterances.jsonl
-> existing scoring
-> existing plots
-> existing report
```

The runner consumes `record["inference_audio_path"]` through the existing pipeline. It rejects changed `recording_id`, `utt_id`, `start_sec`, or `end_sec`; maps successful null text to an explicit empty string; rejects malformed/non-`PipelineOutput` responses; converts recognized alternate unknown labels to literal `Unknown` while recording the original token; and never uses reference text or reference speaker identity as fallback or prediction provenance.

The protected prediction row remains exactly six fields. `source_recording_id`, channel/stream/microphone/session identity, augmentation identity, component diagnostics, and normalization evidence are additive rows in `predictions/diagnostics.jsonl`. Per-item failures are isolated and written to `predictions/failures.jsonl`; missing packages/assets/credentials/platforms are classified as unavailable when identifiable. Errors from one record cannot discard successful unrelated records. Machine-specific roots are removed from failure messages.

No model logic, dataset reader, augmentation algorithm, scorer, plotter, reporter, GUI workflow, or source component YAML was replaced or refactored.

## Commands executed

Focused Stage 1 and lint checks:

```text
python -m pytest tests/automated_evaluation/test_stage1_configured_runner.py -q --basetemp artifacts/stage1_pytest_tmp_20260806_2140
python -m ruff check app/inference_pipeline/catalog.py app/inference_pipeline/resolver.py app/model_runner/configured.py app/model_runner/base.py app/model_runner/__init__.py app/cli/main.py app/utils/paths.py tests/automated_evaluation/test_stage1_configured_runner.py
```

Protected regression and GUI checks:

```text
python -m pytest tests/automated_evaluation tests/inference_pipeline tests/model_runner -q --basetemp artifacts/stage1_pytest_final_20260806
python -m app.gui.validation_harness
```

Ordinary Evaluation Tool real-model qualifications:

```text
python run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --augmentation none --runner configured --inference-config configs/inference/live_mic_whisper_tiny.yaml --runs-root artifacts/stage1_qualification_runs --run-name stage1_whisper_tiny
python run_evaluation.py full --dataset cmu_arctic --max-recordings 1 --augmentation none --runner configured --inference-config configs/inference/live_mic_whisper_base.yaml --runs-root artifacts/stage1_qualification_runs --run-name stage1_whisper_base
```

No package was installed, no asset was downloaded, no credential was supplied, and no source component YAML was modified.

## Tests and results

- focused Stage 1 suite: `21 passed`;
- full automated-evaluation/inference/model-runner regression selection: `350 passed, 2 warnings`;
- GUI validation harness: passed;
- Ruff on all Stage 1 Python changes: passed;
- real one-item Whisper Tiny direct smoke: passed;
- real one-item Whisper Base direct smoke: passed;
- ordinary full CLI Whisper Tiny qualification: one selected, one prediction, zero failures, zero missing, report complete;
- ordinary full CLI Whisper Base qualification: one selected, one prediction, zero failures, zero missing, report complete.

The two warnings are the existing Silero/Torch deprecations for `importlib.resources.path` and `torch.jit.load`. The one-item WER values (Tiny `0.0000`, Base `0.2500`) are contract-smoke observations only and are not model-selection evidence.

## Generated artifacts inspected

The following ordinary-run folders were inspected:

- `artifacts/stage1_qualification_runs/20260806_204414_cmu_arctic_full_stage1_whisper_tiny`;
- `artifacts/stage1_qualification_runs/20260806_204438_cmu_arctic_full_stage1_whisper_base`.

For both runs:

- prediction `recording_id`, `utt_id`, `start_sec`, and `end_sec` exactly match `dataset_selection_records.jsonl`;
- `source_recording_id` is retained in diagnostics;
- `predictions/failures.jsonl` contains zero rows;
- `runtime.allow_model_downloads` and component download flags remain false;
- the selected Whisper asset is present and its observed SHA-256 matches the Stage 0 identity;
- configuration warnings contain zero warnings;
- existing aggregate metrics report zero missing predictions;
- 11 existing plot PNGs and the Markdown/JSON report were produced;
- no likely Hugging Face/Picovoice credential value, `allow_model_downloads: true`, or `C:\Users\amiri` path occurs in the inspected artifacts.

## Implementation decisions

- The existing YAML composition system remains authoritative. The catalog is metadata/provenance over it, not a second configuration language.
- A higher-level YAML is mandatory for the configured runner; component substitutions are explicit deltas from that composition.
- No-op components are represented as disabled selections because active no-op implementations have no source component fragments.
- Unknown runtime override fields are rejected rather than silently ignored.
- The minimum prediction schema remains unchanged. Additional identity and diagnostic requirements use separate versioned-style artifacts so existing scoring remains compatible.
- A successful pipeline response with no text is a valid empty transcript; a thrown exception or an output carrying errors is an explicit failure and produces no prediction row.
- Reference speaker fields are excluded even from prediction-side provenance.
- Missing prerequisites are availability outcomes, not automatic installation or download requests.

## Assumptions

- Stage 0 registry/config hashes describe the intended component sources and should fail closed if those sources change without a registry update.
- Existing `PipelineRunner` output identity is authoritative only after exact comparison with the selected Evaluation Tool record.
- The six-field `utterances.jsonl` contract cannot carry channel/source identities without a breaking change, so diagnostics are the additive preservation boundary.
- Local Tiny/Base model caches are approved for internal smoke qualification but not for redistribution.

## Limitations and unresolved issues

- This Stage 1 implementation executes one ordinary run; it does not create campaign/scenario IDs, manifests, assignments, state databases, retries, resume, or result merging.
- CUDA remains unqualified in the current CPU-only Torch environment.
- Components marked unavailable/configured-but-unproven remain unavailable until their separate environment, package, asset, platform, terms, or credential prerequisites are satisfied.
- The exact bedroom RIR remains unresolved and is irrelevant to Stage 1 configured-runner qualification.
- Stage 1 records pipeline component diagnostics but does not add campaign-level resource telemetry or new diarization/speaker metrics.
- The GUI remains behaviorally compatible but does not expose the configured-runner selection controls; Stage 1 provides the explicit CLI path.

## Deferred work

- CUDA environment creation and contract qualification;
- immutable benchmark/scenario wire schemas and hashes;
- campaign state, expansion, retries, interruption/resume, stop requests, and distributed assignments;
- standard/large benchmarks and staged component/model selection;
- controlled dining room/bedroom/restaurant RIR scenarios;
- concurrency qualification and campaign resource monitoring;
- campaign merge, comparative analysis, and final campaign reporting.

## Readiness for the next phase

Stage 1 acceptance criteria pass on CPU: real selected Tiny and Base configurations run through the ordinary Evaluation Tool; IDs and timestamps remain unchanged; protected predictions validate; resolved component/source/model identities are saved; no implicit download occurs; failures are explicit and isolated; and existing CLI, simulation/external runner contracts, GUI validation, scoring, plots, and reports remain functional.

The next gate should be the separately pinned CUDA environment and real CUDA contract qualification, one GPU-heavy run at a time. Do not begin standard or large benchmarking, performance-based model selection, campaign execution, or GPU concurrency testing before that gate passes.
