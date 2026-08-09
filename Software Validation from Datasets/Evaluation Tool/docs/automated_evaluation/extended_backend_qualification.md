# Extended Backend Qualification Results

## Machine and method

These results were produced on Windows 11 with Python 3.12 and an NVIDIA GeForce RTX 3080. Each optional family used its own `.stage8-envs/<profile>` environment. Real qualification used a fixed local CMU Arctic speech WAV, local-only assets, explicit CPU unless stated otherwise, two executions, contract validation, component/config/model identity capture, and no implicit downloads.

`qualified` and `qualified_with_warnings` mean a real output passed. Installation, package import, or asset presence alone does not count. Diarization qualification proves bounded anonymous turns and RTTM conversion only; it does not claim DER/JER readiness.

## Backend status

| Family | Backend | Profile | Status | Evidence or blocker |
|---|---|---|---|---|
| ASR | Faster-Whisper | `extended-local` | `qualified` | Real transcript and no-speech behavior passed twice |
| ASR | Vosk | `extended-local` | `qualified` | Real transcript and no-speech behavior passed twice |
| VAD | WebRTC VAD | `extended-local` | `qualified_with_warnings` | Bounded monotonic regions, silence, and VADChunker composition passed; upstream import emits a deprecation warning |
| Embedding | Resemblyzer | `extended-local` | `qualified` | Finite normalized repeatable vector and minimum-duration behavior passed |
| ASR | Sherpa-ONNX | `onnx` | `qualified` | Verified local model produced repeated transcript |
| VAD | Sherpa-ONNX | `onnx` | `qualified` | Regions, silence, and chunking contract passed |
| Embedding | Sherpa-ONNX | `onnx` | `qualified` | Finite normalized repeatable vector passed |
| Diarization | Sherpa-ONNX | `onnx` | `qualified` | Anonymous bounded turns and RTTM conversion passed; no reference fallback |
| ASR | WeNet | `wenet` | `unavailable_asset` | Pinned runtime requires `final.zip`; downloaded registered archive has only incompatible `final.pt` |
| Embedding | WeSpeaker | `wespeaker` | `qualified_with_warnings` | Real repeated vector passed; isolated hdbscan metadata override, deprecated import, and unused checkpoint tensor are recorded |
| Diarization | pyannote Community-1 | `credential-diarization` | `licence_action_required` | User has not personally accepted gated model conditions |
| Diarization | Picovoice Falcon | `credential-diarization` | `licence_action_required` | User has not personally accepted Picovoice terms |
| Diarization | NVIDIA NeMo | `nemo-linux-cuda` | `platform_required` | Current host is Windows; Linux/CUDA and selected local checkpoints are required |

Summary: 9 of 13 extended backends produced real valid outputs; 4 are explicitly not qualified. The core CUDA prerequisite separately produced 4 of 4 real valid outputs for Whisper Tiny, Whisper Base, Whisper Small, and SpeechBrain ECAPA. Peak measured model VRAM was approximately 218 MiB, 428 MiB, 1.37 GiB, and 147 MiB respectively; this was a single-job contract gate, not a concurrency test.

## Machine-readable evidence

```text
runs/extended_backend_qualification/
  core-cuda.json
  extended-local.json
  onnx.json
  wenet.json
  wespeaker.json
  credential-diarization.json
  nemo-linux-cuda.json
  model_asset_inventory.json
  qualification_summary.json
  qualification_summary.json.sha256
```

Each profile result includes backend and component identity, exact package versions, model asset hashes, requested device, schema-validation outcome, initialization/inference timing where applicable, warnings, failure category, the redacted command, repetition count, and environment/package-freeze identity. The consolidated index validates exact catalog coverage and references each source artifact by SHA-256.

## Interpretation limits

- These runs establish availability and contracts, not comparative quality.
- No backend has advanced to Stage 9 screening from this document.
- No DER, JER, EER, FAR, FRR, verification, identification, calibration, or unknown-rejection performance is claimed.
- CPU timings across isolated libraries are smoke evidence, not a fair benchmark.
- The one GPU qualification was sequential and does not authorize parallel jobs.
- Warnings remain visible; they are not silently converted to success.
