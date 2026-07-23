# CODEX RUN ORDER

Run these prompts in order.

## Prompt 00 — repo audit
Purpose:
- inspect the Evaluation Tool repo
- confirm external runner interfaces
- confirm current `external_stub.py` shape
- avoid coding against wrong assumptions

## Prompt 01 — scaffold package
Purpose:
- create `app/onnx_pipeline/`
- add package structure and placeholder modules

## Prompt 02 — contracts and config
Purpose:
- define stable internal data contracts
- define YAML config schema

## Prompt 03 — audio utilities and evaluation adapter
Purpose:
- load / crop / resample audio
- adapt Evaluation Tool records into internal records

## Prompt 04 — dummy pipeline integration
Purpose:
- prove `external_stub.py` can call the new package without model code

## Prompt 05 — real ASR backend
Purpose:
- implement sherpa-onnx Whisper backend
- keep everything else unchanged

## Prompt 06 — external runner real ASR wiring
Purpose:
- replace dummy output with real transcription

## Prompt 07 — speaker embedding backend
Purpose:
- implement WeSpeaker CAM++ ONNX backend

## Prompt 08 — enrollment store and matching
Purpose:
- persist enrolled embeddings
- add thresholds and Unknown fallback

## Prompt 09 — punctuation backend
Purpose:
- improve transcript readability without touching the prediction contract

## Prompt 10 — VAD trim
Purpose:
- add conservative silence trimming only

## Prompt 11 — tests and smoke runs
Purpose:
- ensure the whole patch is stable
- define exact smoke test commands

## Prompt 12 — Olive optimization
Purpose:
- quantize and package only after correctness

## Prompt 13 — alternative backends benchmark
Purpose:
- add Moonshine / Parakeet branches
- compare accuracy and runtime

## Prompt 14 — docs and cleanup
Purpose:
- make the patch maintainable

---

## Guardrails for every prompt

- Do not modify scoring or report generation code.
- Do not change dataset registry or normalized metadata loading.
- Preserve `(recording_id, utt_id)` exactly.
- Use `record["inference_audio_path"]` for inference input.
- Honor `start_sec` / `end_sec` when present.
- Do not load models per record.
- Keep the pipeline config-driven.
