# IMPLEMENTATION PLAN

This plan assumes you are integrating into the existing Evaluation Tool, not building a separate prototype forever.

## Assumptions

1. The Evaluation Tool already works end to end as a harness.
2. The missing piece is the real inference backend.
3. You want an ONNX-first runtime, not a PyTorch research stack.
4. Two people are working on the project.
5. Mono / record-level inference comes first.
6. Multi-microphone support is a later front-end concern.

---

## Milestone 0 — Lock the engineering decisions

Before Codex writes real code, decide and freeze these:

### A. Primary v1 model choices
Pick exactly one first-pass stack:
- VAD: Silero VAD
- ASR: sherpa-onnx Whisper backend
- speaker embeddings: WeSpeaker CAM++ ONNX
- punctuation: sherpa-onnx punctuation

Do **not** keep three ASR families active in the first commit.

### B. Pipeline contracts
Freeze:
- `InferenceRecord`
- `UtterancePredictionData`
- `EnrollmentStore` schema
- speaker threshold config format
- model config YAML format

### C. Repo location
Create the new code under:

`Evaluation Tool/app/onnx_pipeline/`

Do not scatter it through unrelated directories.

---

## Milestone 1 — Scaffolding only

### Goal
Create the skeleton without any real model calls yet.

### Files
- contracts
- config loader
- audio utilities
- matching utilities
- evaluation adapter
- pipeline orchestrator interface
- tests for non-model parts

### Expected result
You should be able to import the package and run tests without having any model files.

### Why this comes first
This is what lets two people work in parallel.

---

## Milestone 2 — Dummy integration with the Evaluation Tool

### Goal
Prove the external runner contract works.

### Work
- add a dummy pipeline
- wire it into an example `predict_one()`
- return placeholder text and `speaker_label=None`

### Test
Run a tiny Evaluation Tool job and make sure:
- `predictions/utterances.jsonl` is produced
- `(recording_id, utt_id)` are preserved
- scoring does not break
- report generation still works

### Why this matters
It isolates integration errors before model complexity is added.

---

## Milestone 3 — ASR only

### Goal
Get real transcripts flowing.

### Work
- implement sherpa-onnx Whisper backend
- cache model session / recognizer once
- run ASR on `inference_audio_path`
- support optional `start_sec` / `end_sec` cropping

### Test order
1. CMU Arctic tiny run
2. LibriSpeech tiny run
3. HiFiTTS tiny run
4. then AMI / VOiCES / CHiME-6 subset smoke tests

### Acceptance criteria
- real text output
- no per-record model reload
- no ID drift
- valid JSONL output

---

## Milestone 4 — Speaker enrollment and matching

### Goal
Attach names conservatively.

### Work
- implement WeSpeaker CAM++ ONNX backend
- implement enrollment store
- implement cosine similarity + thresholding
- add Unknown fallback

### Policy
Wrong name is worse than Unknown.

### Acceptance criteria
- one speaker can be enrolled
- a test utterance can be matched
- low-confidence results return Unknown
- store supports multiple embeddings per speaker

---

## Milestone 5 — Punctuation

### Goal
Improve transcript readability.

### Work
- add optional punctuation pass
- keep it config-driven
- make it easy to turn off during benchmarking

### Acceptance criteria
- punctuation can be applied after ASR
- the rest of the pipeline works if punctuation is disabled

---

## Milestone 6 — VAD trim

### Goal
Reduce silence without breaking record-level evaluation.

### Work
- implement Silero VAD backend or sherpa-onnx VAD wrapper
- trim leading / trailing silence first
- do not aggressively split until you have evidence it helps

### Acceptance criteria
- VAD can be enabled / disabled by config
- record-level WER does not obviously regress
- silence trimming works on clean and augmented samples

---

## Milestone 7 — Benchmark and choose defaults

### Goal
Stop guessing.

### Benchmarks to run
- Whisper backend vs Moonshine vs Parakeet
- WeSpeaker CAM++ vs exported ECAPA baseline
- with and without VAD trim
- with and without punctuation
- desktop vs Pi candidate models

### Output
A short benchmark table with:
- WER
- runtime
- memory
- speaker-match acceptance rate
- false known-speaker rate

---

## Milestone 8 — Olive optimization

### Goal
Get deployable CPU / Pi artifacts.

### Work
- quantize chosen models
- benchmark int8 vs fp32/fp16
- test ORT format if size reduction matters
- package candidate optimized models

### Rule
Do this **after** baseline correctness.

### Acceptance criteria
- optimized model loads successfully
- accuracy loss is acceptable
- latency or size improves enough to justify it

---

## Milestone 9 — Alternative backend branch

### Goal
Support portability without destabilizing v1.

### Work
Create alternative backends:
- `SherpaMoonshineBackend`
- `SherpaParakeetBackend`
- optional future diarization branch

### Rule
Do not modify the orchestration contract when adding these.

---

## Two-person split

## Person 1 — integration / orchestration
Own:
- config
- contracts
- evaluation adapter
- pipeline orchestration
- external stub integration
- tests
- benchmark harness glue

## Person 2 — model backends
Own:
- ASR backend
- speaker embedding backend
- enrollment store details
- threshold tuning
- VAD backend
- punctuation backend

### Shared rule
Freeze interfaces before both people start implementing internals.

---

## Branch strategy

Use:
- `main` — always stable
- `feature/onnx-pipeline-scaffold`
- `feature/onnx-asr-backend`
- `feature/onnx-speaker-backend`
- `feature/onnx-external-runner`
- `feature/onnx-olive-opt`

Do not let both people edit the same files unless the interfaces are already stable.

---

## First smoke-test sequence

Run this exact order:

1. dummy pipeline
2. real ASR only
3. real ASR + punctuation
4. real ASR + speaker matching
5. real ASR + speaker matching + VAD trim
6. optimized models
7. alternative backends

---

## What to delay

Delay all of this:
- full conversation diarization
- overlap-heavy source separation
- multi-microphone spatial logic
- UI redesign
- service-based deployment
- RPC / microservice split
- model fine-tuning

These are not first-mile tasks.

---

## Exit criteria for v1

v1 is done when:

1. the Evaluation Tool can call the real ONNX pipeline directly;
2. `predictions/utterances.jsonl` is valid and scoreable;
3. the ASR backend is real;
4. speaker enrollment and Unknown fallback are real;
5. at least one small benchmark run has been completed;
6. a clear desktop default and a clear Pi fallback model have been chosen.
