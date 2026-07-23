# ONNX prototype

This package is a handoff bundle for building an **ONNX-first speech pipeline** inside the existing Evaluation Tool.

## What this package does

It gives you four things:

1. a **report** on the ONNX/ONNX Runtime ecosystem for your speech pipeline;
2. a **recommended implementation plan** aligned to the existing Evaluation Tool integration point;
3. a **full Codex prompt sequence** so work can be generated in controlled steps;
4. a **target patch skeleton** you can drop into the Evaluation Tool repo and finish with Codex.

## Blunt conclusion

Do **not** interpret “use ONNX everywhere” as “manually write raw ONNX Runtime code for every task.”

That would be the wrong engineering choice.

The defensible ONNX-first stack is:

- **ONNX** for model format, validation, and graph utilities
- **ONNX Runtime** for inference
- **sherpa-onnx** for high-level speech tasks already solved on top of ONNX Runtime
- **Silero VAD** as the simplest high-quality ONNX-friendly VAD
- **WeSpeaker CAM++ ONNX** for speaker embeddings / enrollment matching
- **Olive** after correctness is proven, for quantization and packaging
- **Optimum** only when you need export / conversion for Hugging Face-compatible models
- **ORT Extensions** only when you need custom pre/post-processing packaged into ONNX graphs

## Recommended v1 stack

### Desktop / evaluation-first
- VAD: **Silero VAD**
- ASR: **sherpa-onnx + Whisper large-v3 or turbo**
- Speaker embeddings: **WeSpeaker CAM++ ONNX**
- Punctuation: **sherpa-onnx punctuation**
- Runtime: **ONNX Runtime CPU or CUDA**
- Optimization later: **Olive**
- Export helpers later: **Optimum**

### Raspberry Pi / edge fallback
- VAD: **Silero VAD**
- ASR: **sherpa-onnx + Moonshine or NeMo Parakeet int8**
- Speaker embeddings: **same ONNX speaker model if it fits**
- Runtime: **ONNX Runtime CPU**, optionally test **Arm NN EP** later

## Weakest ONNX area

The weakest part of an all-ONNX path is **generic diarization**.

If your goal becomes open-world diarization / overlap-heavy meeting diarization, the strongest widely cited baseline remains **pyannote**, which is not ONNX-native. The ONNX path is still viable for your named-speaker product if you prioritize:
- record-level or VAD-level segmentation,
- speaker enrollment,
- conservative identity matching,
- transcription.

## Existing project context this package assumes

This bundle is designed around the existing Evaluation Tool architecture:

- integration point: `Evaluation Tool/app/model_runner/external_stub.py`
- required prediction file: `predictions/utterances.jsonl`
- prediction key: `(recording_id, utt_id)`
- inference input field: `record["inference_audio_path"]`
- segment-aware datasets may also provide `start_sec` / `end_sec`

This package also assumes the latest user correction: **simulation mode and augmentation already exist across all datasets**, even though one earlier handoff text said otherwise. Verify the actual code paths in your repo before making assumptions.

## File map

- `REPORT.md` — full ONNX speech stack report
- `LICENSE_MATRIX.md` — code/model license breakdown
- `STATE_OF_ART_COMPARISON.md` — where ONNX is strong and where it is not
- `IMPLEMENTATION_PLAN.md` — exact coding sequence
- `CODEX_RUN_ORDER.md` — prompt order
- `codex_prompts/` — step-by-step prompts for Codex
- `target_patch/` — patch skeleton for the existing Evaluation Tool repo
- `REFERENCES.md` — source list used to build this package

## Recommended usage order

1. Read `REPORT.md`
2. Read `IMPLEMENTATION_PLAN.md`
3. Read `STATE_OF_ART_COMPARISON.md`
4. Run Codex prompts in `CODEX_RUN_ORDER.md`
5. Copy the `target_patch/` content into the Evaluation Tool repo
6. Start with a **single record-level pipeline**
7. Only then optimize with Olive

## What not to do

- Do not start with full conversation diarization.
- Do not start with Olive optimization.
- Do not load models inside `predict_one()` on every record.
- Do not change `(recording_id, utt_id)`.
- Do not redesign the evaluation harness.
- Do not assume ONNX automatically makes a model state-of-the-art.
- Do not assume the biggest model is deployable on Raspberry Pi.

## Decision rule

Use the **highest-level ONNX-native tool that removes engineering risk**.

That means:
- use raw ONNX / ONNX Runtime where you need control;
- use sherpa-onnx where the task is already solved;
- use Olive after correctness;
- use Optimum only when export is required;
- use pyannote only as a non-ONNX benchmark, not as your ONNX production path.
