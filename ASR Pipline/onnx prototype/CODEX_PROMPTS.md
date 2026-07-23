# CODEX_PROMPTS

This file concatenates all prompt files in execution order.


---

## 00_repo_audit.md

# Prompt 00 — repo audit

You are working in the existing Evaluation Tool repository.

## Task
Audit the repo and produce a short implementation note before writing any new model code.

## What to inspect
- `run_evaluation.py`
- `app/cli/main.py`
- `app/model_runner/base.py`
- `app/model_runner/external_stub.py`
- `app/prediction_io/schema.py`
- any code path that writes `predictions/utterances.jsonl`
- any code path that calls `predict_one()`
- any run-config field relevant to external runner setup

## What to produce
Create `docs/onnx_pipeline_audit.md` containing:
1. the current `external_stub.py` integration shape
2. what object `predict_one()` must return
3. where model config should be loaded from
4. whether runner instances are created once per run or per record
5. which fields from the record dict are guaranteed
6. exact file path recommendations for new ONNX pipeline code

## Constraints
- Do not change any existing behavior yet.
- Do not add model code yet.
- Do not redesign the harness.

## Acceptance criteria
- `docs/onnx_pipeline_audit.md` exists
- the note explicitly confirms the prediction key contract `(recording_id, utt_id)`
- the note explicitly confirms that inference must use `record["inference_audio_path"]`
- the note explicitly confirms how `start_sec` / `end_sec` should be handled

---

## 01_scaffold_package.md

# Prompt 01 — scaffold ONNX pipeline package

You are working in the existing Evaluation Tool repository.

## Goal
Create a new package for the ONNX-first inference pipeline without changing the current scoring/reporting logic.

## Create this structure
- `app/onnx_pipeline/__init__.py`
- `app/onnx_pipeline/contracts.py`
- `app/onnx_pipeline/config.py`
- `app/onnx_pipeline/interfaces.py`
- `app/onnx_pipeline/audio.py`
- `app/onnx_pipeline/matching.py`
- `app/onnx_pipeline/pipeline.py`
- `app/onnx_pipeline/factory.py`
- `app/onnx_pipeline/adapters/__init__.py`
- `app/onnx_pipeline/adapters/evaluation_tool.py`
- `app/onnx_pipeline/asr/__init__.py`
- `app/onnx_pipeline/asr/backends/__init__.py`
- `app/onnx_pipeline/asr/backends/sherpa_whisper.py`
- `app/onnx_pipeline/asr/backends/sherpa_moonshine.py`
- `app/onnx_pipeline/speaker/__init__.py`
- `app/onnx_pipeline/speaker/store.py`
- `app/onnx_pipeline/speaker/backends/__init__.py`
- `app/onnx_pipeline/speaker/backends/wespeaker_campplus_onnx.py`
- `app/onnx_pipeline/vad/__init__.py`
- `app/onnx_pipeline/vad/silero_onnx.py`
- `app/onnx_pipeline/text/__init__.py`
- `app/onnx_pipeline/text/sherpa_punctuation.py`
- `configs/onnx_pipeline.desktop.example.yaml`
- `configs/onnx_pipeline.pi.example.yaml`
- `tests/test_contracts.py`
- `tests/test_matching.py`
- `tests/test_evaluation_adapter.py`

## Requirements
- Add module docstrings explaining the intended role of each file.
- Backend files may contain TODO placeholders, but the interfaces and imports must be coherent.
- Use type hints everywhere reasonable.
- Keep imports lightweight.

## Constraints
- Do not wire into `external_stub.py` yet.
- Do not add real model-loading code yet unless it is trivial.
- Do not modify scoring / report code.

## Acceptance criteria
- `pytest -q tests/test_contracts.py tests/test_matching.py tests/test_evaluation_adapter.py` passes
- importing `app.onnx_pipeline` does not raise errors
- the example YAML configs exist

---

## 02_contracts_and_config.md

# Prompt 02 — implement contracts and config

You are working in the existing Evaluation Tool repository.

## Goal
Implement the stable internal data contracts and YAML config loading for the ONNX pipeline.

## Implement in `app/onnx_pipeline/contracts.py`
Define typed dataclasses for:
- `InferenceRecord`
- `SpeechSegment`
- `SpeakerMatch`
- `UtterancePredictionData`

Requirements:
- `InferenceRecord` must be able to represent:
  - `recording_id`
  - `utt_id`
  - `inference_audio_path`
  - `start_sec`
  - `end_sec`
  - optional reference text / speaker label
  - free-form metadata
- `UtterancePredictionData` must map cleanly to the Evaluation Tool JSONL contract
- include small helper methods if useful, but keep it simple

## Implement in `app/onnx_pipeline/config.py`
Define dataclasses for:
- runtime config
- VAD config
- ASR config
- speaker config
- punctuation config
- enrollment config
- thresholds
- root pipeline config

Add:
- `load_pipeline_config(path: str | Path) -> PipelineConfig`

## Update tests
Add tests that:
- instantiate config objects
- load example YAML
- serialize / validate prediction contract fields

## Constraints
- No model code yet
- No hard-coded Windows-only paths
- Keep the config schema explicit and readable

## Acceptance criteria
- tests pass
- the YAML example files round-trip through `load_pipeline_config`
- prediction dataclass contains exactly the fields needed to emit `utterances.jsonl`

---

## 03_audio_and_adapter.md

# Prompt 03 — implement audio utilities and Evaluation Tool adapter

You are working in the existing Evaluation Tool repository.

## Goal
Implement the non-model plumbing that turns Evaluation Tool records into internal inference requests.

## Implement in `app/onnx_pipeline/audio.py`
Create utilities to:
- load mono audio from a file path
- preserve float32 output
- crop by `start_sec` / `end_sec`
- resample to a target sample rate
- optionally concatenate kept speech segments later

Implementation guidance:
- use `soundfile`
- use `scipy.signal.resample_poly`
- be explicit about shapes and dtypes
- handle stereo or multi-channel input by deterministic mono reduction

## Implement in `app/onnx_pipeline/adapters/evaluation_tool.py`
Add functions to:
- convert an Evaluation Tool record dict into `InferenceRecord`
- convert `UtterancePredictionData` into the dict / object shape needed by the existing runner layer

Requirements:
- preserve `recording_id`
- preserve `utt_id`
- keep `start_sec` / `end_sec`
- keep `speaker_label` nullable
- do not guess new IDs

## Tests
Add / update tests for:
- cropping behavior
- resampling behavior
- adapter conversion
- round-trip output formatting

## Constraints
- Do not touch `external_stub.py` yet
- Do not touch scoring / report code
- Do not load any model here

## Acceptance criteria
- tests pass
- adapter explicitly uses `inference_audio_path`
- adapter output can be serialized to the expected JSONL fields

---

## 04_dummy_pipeline_integration.md

# Prompt 04 — wire a dummy ONNX pipeline into the external runner

You are working in the existing Evaluation Tool repository.

## Goal
Prove that the new ONNX pipeline package can be called through the existing external runner hook before real model code is added.

## Implement in `app/onnx_pipeline/pipeline.py`
Create an `OnnxSpeechPipeline` class that can be constructed with pluggable components:
- ASR engine
- optional VAD engine
- optional speaker embedder
- optional punctuator
- optional enrollment store

For now:
- allow the pipeline to operate with missing components
- if no ASR engine is provided, return placeholder text like `"TODO_ASR"`
- if no speaker embedder / store is provided, return `speaker_label=None`

## Implement in `app/onnx_pipeline/factory.py`
Add a placeholder `build_pipeline_from_config()` that returns a pipeline with no real model backends yet.

## Add example integration file
Create:
- `app/model_runner/external_stub_example.py`

This file should show:
- a cached singleton or `lru_cache` pattern for pipeline construction
- conversion from Evaluation Tool record dict -> `InferenceRecord`
- conversion from `UtterancePredictionData` -> existing prediction schema shape

## Optional
If the repo structure makes it easy, update `external_stub.py` behind a feature flag or clearly marked TODO branch. If not, leave `external_stub.py` unchanged and document the exact patch.

## Constraints
- Do not add real ASR yet
- Do not load any real model yet
- Do not change scoring/reporting

## Acceptance criteria
- a tiny run can execute through the dummy pipeline
- valid `predictions/utterances.jsonl` can still be produced
- the pipeline object is constructed once, not once per record

---

## 05_sherpa_whisper_backend.md

# Prompt 05 — implement the sherpa-onnx Whisper backend

You are working in the existing Evaluation Tool repository.

## Goal
Add the first real ASR backend using sherpa-onnx and a Whisper ONNX model family.

## Implement
In:
- `app/onnx_pipeline/asr/backends/sherpa_whisper.py`

Create a backend class that:
- reads its config from `AsrConfig`
- validates required model paths
- constructs the sherpa-onnx recognizer once
- exposes `transcribe(audio: np.ndarray, sample_rate: int) -> str`

## Requirements
- handle the model session / recognizer lifecycle once
- keep the backend isolated from Evaluation Tool details
- make configuration explicit for model paths and decoding options
- include clear errors when model files are missing

## Also update
- `app/onnx_pipeline/factory.py` to build this backend when configured
- `tests/` with at least one non-heavy unit test that validates configuration / failure behavior

## Constraints
- Do not implement alternative ASR backends yet
- Do not change the prediction contract
- Do not add model download logic inside production code

## Acceptance criteria
- pipeline can be constructed with `SherpaWhisperBackend`
- missing-model error messages are clear
- backend is reusable across multiple records
- code is ready for the next prompt to wire into `external_stub.py`

---

## 06_external_stub_real_asr.md

# Prompt 06 — connect real ASR into `external_stub.py`

You are working in the existing Evaluation Tool repository.

## Goal
Replace the dummy path with real transcription through the ONNX pipeline.

## Task
Update:
- `app/model_runner/external_stub.py`

so that:
- it constructs or retrieves a cached ONNX pipeline instance
- converts the incoming record dict to `InferenceRecord`
- runs the pipeline
- returns the correct prediction object / dict for the existing runner flow

## Required behavior
- use `record["inference_audio_path"]`
- preserve `recording_id`
- preserve `utt_id`
- preserve `start_sec`
- preserve `end_sec`
- return `speaker_label=None` for now unless already implemented
- emit real transcript text

## Important
If `start_sec` / `end_sec` exist:
- crop correctly before transcription
- do not ignore them for segment-based datasets

## Constraints
- Do not touch scoring/reporting code
- Do not touch dataset registry logic
- Do not change JSONL schema fields

## Acceptance criteria
- a tiny `cmu_arctic` run with `external-stub` produces real ASR text
- scoring still works
- model is not loaded per record
- there is no ID drift

---

## 07_wespeaker_backend.md

# Prompt 07 — implement the WeSpeaker CAM++ ONNX speaker embedding backend

You are working in the existing Evaluation Tool repository.

## Goal
Add a real ONNX speaker embedding backend for enrollment and matching.

## Implement
In:
- `app/onnx_pipeline/speaker/backends/wespeaker_campplus_onnx.py`

Create a backend class that:
- loads a WeSpeaker CAM++ ONNX model with ONNX Runtime
- validates input/output signatures defensively
- exposes `embed(audio: np.ndarray, sample_rate: int) -> np.ndarray`

## Requirements
- keep model loading separate from matching logic
- isolate preprocessing assumptions
- document any expected sample rate or feature frontend assumptions
- raise clear errors if the ONNX model shape does not match expectations

## Also update
- `app/onnx_pipeline/factory.py`
- tests for configuration / failure behavior

## Constraints
- do not implement enrollment storage here
- do not hard-code thresholds here
- do not couple this backend to Evaluation Tool record dicts

## Acceptance criteria
- backend can be instantiated independently
- backend exposes a clear embedding method
- pipeline can be constructed with the backend, even if the enrollment store is still empty

---

## 08_enrollment_and_matching.md

# Prompt 08 — implement enrollment storage and speaker matching

You are working in the existing Evaluation Tool repository.

## Goal
Make the pipeline capable of known-speaker assignment with Unknown fallback.

## Implement in `app/onnx_pipeline/speaker/store.py`
Create an enrollment store that can:
- add one embedding for a speaker
- add multiple embeddings for a speaker
- persist to disk
- load from disk
- return a gallery of speaker -> embeddings

Use a simple, transparent format. Favor clarity over cleverness.

## Implement in `app/onnx_pipeline/matching.py`
Add:
- cosine similarity
- best-match selection
- second-best score tracking
- threshold + margin-based acceptance logic
- Unknown fallback logic

## Update `app/onnx_pipeline/pipeline.py`
When a speaker backend and enrollment store are configured:
- compute the embedding for the current record
- match it against enrolled speakers
- set `speaker_label` to the accepted speaker
- otherwise set `speaker_label` to the configured Unknown label

## Constraints
- wrong known-speaker label is worse than Unknown
- keep the threshold config-driven
- do not add diarization here

## Acceptance criteria
- tests cover:
  - exact match
  - below-threshold rejection
  - close-second-best rejection
- pipeline can emit known speaker labels and Unknown

---

## 09_punctuation_backend.md

# Prompt 09 — add optional punctuation post-processing

You are working in the existing Evaluation Tool repository.

## Goal
Improve transcript readability without changing the prediction contract.

## Implement
In:
- `app/onnx_pipeline/text/sherpa_punctuation.py`

Create a punctuation backend wrapper that:
- can be enabled / disabled by config
- accepts raw ASR text
- returns punctuated text

## Update
- `app/onnx_pipeline/factory.py`
- `app/onnx_pipeline/pipeline.py`

Pipeline behavior:
- ASR text first
- punctuation only if enabled
- if punctuation backend fails, fail clearly or optionally allow a strict config switch to bypass it

## Constraints
- do not block the whole architecture on punctuation
- do not change JSONL fields
- do not alter speaker logic here

## Acceptance criteria
- punctuation can be toggled by config
- pipeline still works with punctuation disabled
- text is punctuated only after ASR

---

## 10_vad_trim.md

# Prompt 10 — add conservative VAD trimming

You are working in the existing Evaluation Tool repository.

## Goal
Use VAD to trim silence and optionally define subsegments, but without destabilizing record-level evaluation.

## Implement
In:
- `app/onnx_pipeline/vad/silero_onnx.py`

Create a VAD backend wrapper that:
- loads the configured Silero model / runtime path
- returns speech timestamps or a trimmed audio region
- can operate conservatively for record-level processing

## Update
- `app/onnx_pipeline/pipeline.py`

Recommended v1 behavior:
- trim leading / trailing silence
- do not aggressively fragment utterance-level input unless explicitly configured

## Constraints
- VAD is optional by config
- do not turn VAD into generic diarization
- do not break existing record-level processing assumptions

## Acceptance criteria
- VAD can be enabled / disabled
- pipeline still works with VAD off
- with VAD on, silence trimming is applied before ASR

---

## 11_tests_and_smoke_runs.md

# Prompt 11 — add tests and smoke-run instructions

You are working in the existing Evaluation Tool repository.

## Goal
Make the new ONNX pipeline patch testable and safe to iterate.

## Add / update tests
Cover:
- contracts
- config loading
- adapter round-trip
- audio crop / resample
- matching thresholds
- pipeline behavior with dummy components
- failure behavior when model paths are missing

## Add docs
Create:
- `docs/onnx_pipeline_smoke_tests.md`

Include:
1. exact command to run a tiny dummy test
2. exact command to run a tiny real ASR test on `cmu_arctic`
3. what files to inspect in the run folder
4. what indicates success
5. what common failures mean

## Constraints
- do not add giant benchmark suites yet
- focus on fast smoke tests
- keep commands copy-pasteable

## Acceptance criteria
- tests pass
- smoke-test doc exists
- first-time integrator can follow the steps without guessing

---

## 12_olive_optimization.md

# Prompt 12 — add Olive optimization workflow after baseline correctness

You are working in the existing Evaluation Tool repository.

## Goal
Add a documented Olive optimization path for the chosen ONNX models without destabilizing the baseline code path.

## Create
- `docs/olive_workflow.md`
- an `olive/` folder with template configs or placeholders for:
  - ASR model optimization
  - optional speaker model optimization

## Workflow requirements
Document:
- baseline benchmark first
- quantization second
- compare accuracy drop vs latency / size gain
- when ORT format is worth using
- when not to optimize further

## If you add code
It should be helper scripts only, for example:
- validating model paths
- invoking Olive CLI with config files
- recording before/after benchmark artifacts

## Constraints
- do not replace the baseline model artifacts automatically
- do not change runtime code to require optimized models
- keep optimized artifacts opt-in

## Acceptance criteria
- Olive workflow is documented
- optimized artifacts can coexist with baseline artifacts
- no existing test path is broken

---

## 13_alt_backends_benchmark.md

# Prompt 13 — add alternative backend branch and benchmark hooks

You are working in the existing Evaluation Tool repository.

## Goal
Make the architecture capable of comparing desktop and edge ASR backends without rewriting orchestration.

## Implement
- finish `SherpaMoonshineBackend`
- add any config hooks needed for a Parakeet-style backend if practical
- keep the same `AsrEngine` interface

## Add docs
Create:
- `docs/backend_benchmark_plan.md`

It should define:
- which datasets to benchmark first
- what metrics to compare
- how to decide the desktop default
- how to decide the Raspberry Pi fallback

## Constraints
- do not change the pipeline contract
- do not duplicate orchestration logic
- keep backends swappable by config only

## Acceptance criteria
- at least two ASR backends can be selected by config
- benchmark plan doc exists
- existing pipeline tests still pass

---

## 14_docs_cleanup.md

# Prompt 14 — documentation cleanup and handoff polish

You are working in the existing Evaluation Tool repository.

## Goal
Make the ONNX pipeline maintainable for the next engineer.

## Produce / update
- `docs/onnx_pipeline_overview.md`
- `docs/onnx_pipeline_model_inventory.md`
- `docs/onnx_pipeline_known_risks.md`

## Required content
### Overview
- architecture diagram in text form
- module boundaries
- config files
- integration point with `external_stub.py`

### Model inventory
- ASR model family in use
- VAD model in use
- speaker model in use
- punctuation model in use
- where each artifact lives on disk
- who owns updating them

### Known risks
- diarization is not solved
- Raspberry Pi model may differ from desktop model
- thresholds require calibration
- model licenses must be rechecked per artifact
- per-record model loads are forbidden

## Constraints
- do not rewrite previous docs unless necessary
- avoid fluff
- keep docs operational and specific

## Acceptance criteria
- docs exist
- a new engineer could resume the ONNX pipeline work with minimal oral context
