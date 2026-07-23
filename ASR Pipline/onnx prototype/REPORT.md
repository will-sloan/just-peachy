# REPORT — ONNX-first speech pipeline for the Evaluation Tool

## 1. Executive position

An ONNX-first implementation is viable for this project, but only if you are disciplined about **where ONNX belongs**.

### Correct interpretation
ONNX should be treated as:
- the **model interchange format**,
- the **runtime and optimization stack**,
- and the **deployment layer**.

### Incorrect interpretation
ONNX should **not** be treated as:
- a requirement to hand-code every speech task directly against raw graph tensors,
- a guarantee of state-of-the-art quality,
- or a reason to avoid higher-level ONNX-native tooling that already solves the hard parts.

For this project, the best ONNX-first strategy is:

1. **Use ONNX Runtime as the base runtime**
2. **Use sherpa-onnx for speech tasks that are already packaged well**
3. **Use direct ORT / ONNX for the smaller pieces you control**
4. **Use Olive only after the pipeline is correct**
5. **Use Optimum only when you need export / conversion**
6. **Keep Python orchestration initially**
7. **Preserve the Evaluation Tool contract exactly**

---

## 2. What the system actually needs to do

You are not building a generic diarization research stack first.

You are building a product-oriented pipeline that eventually must support:

- speaker enrollment
- speaker recognition for known speakers
- Unknown fallback
- transcription
- ordered transcript assembly
- later, possibly multi-microphone support

For the current Evaluation Tool integration, the minimum useful record-level pipeline is:

`audio -> optional silence trimming -> ASR -> speaker embedding -> name match / Unknown -> utterances.jsonl`

That is enough to start generating valid predictions for the existing harness.

---

## 3. Recommended ONNX stack by layer

## 3.1 Core ONNX infrastructure

### A. ONNX
**Role**
- file format
- graph validation
- graph inspection
- shape inference / sanity checks
- CI-time model validation

**Why you should use it**
- it is the canonical validation layer before runtime
- it lets you reject broken exports early
- it gives you model graph visibility when debugging

**How to use it in this project**
- add a model validation script that runs `onnx.checker`
- inspect model inputs/outputs before writing wrappers
- use it in CI for every model bundle you decide to ship

**Do not**
- use raw ONNX APIs as your primary speech programming interface

---

### B. ONNX Runtime
**Role**
- main inference engine
- execution provider abstraction
- CPU / CUDA / hardware EP execution
- ORT format support for reduced deployments

**Why you should use it**
- it is the runtime foundation under almost everything else in this plan
- it is cross-platform
- it is the path to Windows, macOS, and Raspberry Pi deployment

**How to use it in this project**
- use it directly for custom, simple modules where you need control
- rely on it indirectly through sherpa-onnx for complex speech tasks
- benchmark CPU first, then CUDA if available
- later convert stable models to ORT format for smaller deployments

**What matters operationally**
- instantiate sessions once, not per record
- choose execution providers by config, not hard-coded logic
- keep model paths externalized in YAML

---

### C. ONNX Runtime Extensions
**Role**
- custom operators
- packaged pre/post-processing
- graph generation for some transformer-style pre/post pipelines

**Why it matters**
- it is the right tool if you later want to move parts of preprocessing/postprocessing into an ONNX graph
- it reduces glue code when packaging a deployable artifact

**Why it is not a day-1 requirement**
- your first milestone is correctness inside the Evaluation Tool
- Python-side audio I/O and post-processing are simpler to debug
- ORT Extensions adds complexity before you have a stable pipeline

**Recommendation**
- keep it out of the first smoke test
- bring it in only when you want to:
  - remove Python pre/post dependencies,
  - embed more pipeline logic inside ONNX,
  - or package cleaner deployment artifacts

---

### D. Olive
**Role**
- quantization
- optimization
- packaging
- ORT-focused deployment preparation

**Why it matters**
- this is the right optimization tool once you know which models you are keeping
- it is more defensible than doing ad hoc quantization scripts too early

**What it should be used for here**
- int8 optimization for CPU / Pi targets
- packaging candidate models
- generating optimized artifacts for benchmarking

**What it should not be used for**
- choosing the first working model
- solving model quality problems
- replacing basic engineering judgment

**Correct timing**
1. get the pipeline correct
2. benchmark baseline accuracy and latency
3. then run Olive

---

### E. Hugging Face Optimum
**Role**
- exporting HF-compatible models to ONNX / ORT
- loading ORT-backed HF model wrappers in some cases

**Why it matters**
- useful when you choose a Hugging Face model family and want a faster export path
- useful if you later need alternative ASR or punctuation models not already packaged by sherpa-onnx

**Why it is not the runtime center**
- your runtime center should still be ORT / sherpa-onnx
- Optimum is more valuable for export and conversion than for your final architecture

**Recommendation**
- keep it in the toolchain
- do not make it the primary orchestration layer

---

## 3.2 Speech-task runtime

### F. sherpa-onnx
**Role**
- high-level ONNX-native speech runtime
- ASR
- VAD
- speaker identification
- speaker diarization
- punctuation
- speech enhancement
- source separation
- more

**This is the key engineering shortcut.**

If you try to write raw-ORT wrappers for everything that sherpa-onnx already solves, you will waste time.

**Why sherpa-onnx is central**
- it already solves a large part of deployment logic for speech tasks
- it supports local/offline execution
- it targets Windows, macOS, Linux, Android, iOS, embedded, and Raspberry Pi
- it already wraps many ONNX-exported speech model families

**Where to use sherpa-onnx first**
- ASR backend
- punctuation backend
- possibly VAD backend if you want a unified API
- possibly speaker identification / diarization later

**Where not to overuse it**
- enrollment storage and identity-threshold logic should remain your own code
- prediction contract formatting should remain your own code
- Evaluation Tool adaptation should remain your own code

---

## 3.3 Task-specific recommendations

### G. VAD — Silero VAD
**Recommendation: use Silero VAD first**

**Why**
- strong practical quality
- ONNX-friendly
- lightweight
- fast on CPU
- common choice for production VAD

**How to use it**
- use it for silence trimming and optional sub-segmentation
- for the Evaluation Tool integration, keep it conservative:
  - trim silence first
  - do not over-fragment utterance-level inputs

**Important nuance**
For the Evaluation Tool, many inputs are already record-like units. That means VAD is useful first as:
- speech trimming,
- optional fallback segmentation,
not as the main diarization strategy.

---

### H. ASR — sherpa-onnx + Whisper first
**Recommendation: use Whisper via sherpa-onnx for desktop evaluation first**

**Why**
- mature
- strong general ASR
- exported ONNX models already exist in sherpa-onnx docs
- good starting point for English / multilingual desktop evaluation

**Model strategy**
Use a backend abstraction with at least two ASR options:

1. **Accuracy-first desktop backend**
   - Whisper large-v3 / turbo / distil-large-v3 via sherpa-onnx

2. **Edge-first fallback backend**
   - Moonshine or NeMo Parakeet int8 via sherpa-onnx

**Why two backends**
Because the desktop winner is not automatically the Raspberry Pi winner.

**Practical choice**
- start with Whisper on Windows/macOS
- add Moonshine or Parakeet int8 only after the pipeline is correct

---

### I. Speaker embeddings — WeSpeaker CAM++ ONNX first
**Recommendation: use WeSpeaker CAM++ ONNX as the first enrollment / matching backend**

**Why**
- direct ONNX model availability
- Apache-2.0 model card
- production-oriented toolkit
- ONNX/C++ deployment is already part of WeSpeaker’s positioning

**How to use it**
- extract one embedding per enrolled utterance
- store multiple exemplars per speaker
- use cosine similarity for initial matching
- apply a strict acceptance threshold
- use Unknown when uncertain

**Why not start with full speaker diarization**
Because your product value comes first from:
- known speaker enrollment
- known speaker matching
- conservative fallback

That is easier to implement and aligns better with your actual goal.

---

### J. Punctuation — sherpa-onnx punctuation
**Recommendation: add punctuation after ASR is stable**

**Why**
- improves transcript readability
- already supported in sherpa-onnx
- low engineering cost compared to building your own text post-processor

**Do not**
- block the first end-to-end milestone on punctuation

---

### K. Diarization — later, and with caution
**Recommendation**
- do not make generic diarization a day-1 deliverable
- keep it as a later branch

**Why**
- an all-ONNX path is weakest here
- the strongest public baseline remains pyannote, which is not ONNX-native
- this is the part most likely to pull you away from product needs into research complexity

**What to do instead**
- v1: record-level or VAD-trimmed enrolled-speaker attribution
- later: evaluate sherpa-onnx diarization
- benchmark that against pyannote to understand the gap

---

## 4. Recommended system architecture

## 4.1 Record-level architecture for the existing Evaluation Tool

This is the architecture you should build first:

1. Evaluation Tool record dict arrives
2. Convert to internal `InferenceRecord`
3. Load `inference_audio_path`
4. If `start_sec` / `end_sec` exist, crop correctly
5. Optionally run VAD trim
6. Run ASR
7. Run speaker embedding extraction
8. Match against enrolled speaker gallery
9. Punctuate text
10. Return `UtterancePrediction`
11. Preserve original `recording_id` and `utt_id`

**Critical engineering rule**
The pipeline object must be created once and reused.  
Do not load models inside `predict_one()` for each record.

---

## 4.2 Module boundaries

Recommended package inside the Evaluation Tool repo:

- `app/onnx_pipeline/contracts.py`
- `app/onnx_pipeline/config.py`
- `app/onnx_pipeline/audio.py`
- `app/onnx_pipeline/interfaces.py`
- `app/onnx_pipeline/matching.py`
- `app/onnx_pipeline/pipeline.py`
- `app/onnx_pipeline/factory.py`
- `app/onnx_pipeline/adapters/evaluation_tool.py`
- `app/onnx_pipeline/speaker/store.py`
- `app/onnx_pipeline/vad/...`
- `app/onnx_pipeline/asr/...`
- `app/onnx_pipeline/speaker/backends/...`
- `app/onnx_pipeline/text/...`

**Design rule**
Own the orchestration yourself.  
Do not let one library own your whole product architecture.

---

## 4.3 Data contracts

Freeze these early:

### `InferenceRecord`
Input to the pipeline:
- `recording_id`
- `utt_id`
- `inference_audio_path`
- `start_sec`
- `end_sec`
- `reference_text` optional
- `reference_speaker_label` optional
- `metadata`

### `UtterancePredictionData`
Output of the pipeline:
- `recording_id`
- `utt_id`
- `start_sec`
- `end_sec`
- `speaker_label`
- `text`
- optional debug metadata

### `EnrollmentStore`
Persistent speaker gallery:
- speaker name
- embedding vectors
- optional prompt labels
- optional note / timestamp

### `SpeakerMatch`
Result of identity scoring:
- best speaker name
- best score
- second-best score
- accepted / rejected
- reason

These contracts matter more than the first model you pick.

---

## 5. Exact implementation sequence

## Phase 0 — Freeze interfaces
Before model coding:
- finalize internal contracts
- finalize config schema
- finalize where model files live
- finalize where enrollments are stored

## Phase 1 — Build the patch skeleton
Create:
- package layout
- config loader
- contracts
- adapter
- audio loader
- unit tests for the non-model pieces

## Phase 2 — Implement a dummy end-to-end path
Make the pipeline return:
- a placeholder transcript
- `speaker_label=None`

This proves:
- Evaluation Tool integration works
- output formatting works
- `utterances.jsonl` contract works

## Phase 3 — Add ASR only
Implement:
- sherpa-onnx Whisper backend
- pipeline transcribes real audio
- external stub uses real ASR

Test first on:
- CMU Arctic
- tiny run
- no speaker matching yet

## Phase 4 — Add speaker embeddings / enrollment
Implement:
- WeSpeaker CAM++ ONNX backend
- enrollment store
- cosine scoring
- thresholds
- Unknown fallback

Test on:
- clean speaker enrollment samples
- then utterance-level evaluation records

## Phase 5 — Add punctuation
Implement:
- sherpa-onnx punctuation post-pass
- make it optional by config

## Phase 6 — Add VAD trim
Implement:
- Silero VAD or sherpa-onnx VAD trim
- apply conservatively

## Phase 7 — Optimize
After correctness and benchmarks:
- Olive quantization
- ORT format conversion if useful
- reduced runtime experiments
- Pi-specific model selection

## Phase 8 — Add alternative backends
Only after the first path works:
- Moonshine backend
- Parakeet backend
- optional diarization branch

---

## 6. Evaluation Tool integration guidance

Your existing harness already solves:
- dataset selection
- augmentation / simulation
- run folder creation
- scoring
- reporting

Therefore the integration strategy should be:

### Direct runner integration
Replace the stub runner logic so it calls your cached ONNX pipeline instance.

### Required behavior
- consume `record["inference_audio_path"]`
- honor `start_sec` / `end_sec`
- preserve `recording_id`
- preserve `utt_id`
- emit valid `UtterancePrediction`

### Do not do this
- do not create a separate scoring path
- do not change the manifest format
- do not remap keys
- do not run separate services unless the direct import path fails for a concrete reason

**Use the direct import path first.**

---

## 7. What ONNX is good at here

ONNX is a strong choice for:
- local inference portability
- multi-platform deployment
- CPU-friendly packaging
- model optimization and quantization
- keeping runtime dependencies smaller than many research stacks
- serving as the common layer across different model families

---

## 8. What ONNX is not good at here

ONNX is not the best answer for:
- deciding what the best model is
- generic diarization research leadership
- training-time convenience
- replacing all pipeline glue code on day 1

---

## 9. Recommended research questions

Before heavy coding, research these in order:

1. Which ASR backend wins on your datasets?
   - Whisper large-v3 / turbo
   - Moonshine
   - Parakeet

2. Which speaker embedding backend is stable under your enrollment protocol?
   - WeSpeaker CAM++
   - SpeechBrain ECAPA exported to ONNX
   - later maybe ERes2Net-family variants

3. What is the best enrollment prompt design?
   - one sentence vs several
   - same prompt vs prompt diversity
   - average embeddings vs exemplar bank

4. Is VAD trim helping or hurting record-level WER?
   - do not assume it helps automatically

5. What is the Pi deployment target actually able to run?
   - do not assume desktop choices transfer

---

## 10. Final recommendation

### Recommended version 1 stack
- **ONNX Runtime**
- **sherpa-onnx**
- **Silero VAD**
- **WeSpeaker CAM++ ONNX**
- **Olive** later
- **Optimum** only if export is needed
- **ORT Extensions** later, only if packaging benefits justify it

### Recommended version 1 scope
- record-level pipeline
- direct Evaluation Tool integration
- desktop-first
- speaker enrollment
- speaker matching
- Unknown fallback
- no full diarization yet

That is the fastest ONNX-first path that is technically serious and product-relevant.
