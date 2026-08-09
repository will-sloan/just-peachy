# Stage 9 Extended Backend Screening Design

## Eligible scope

Eligibility is derived from the checksummed Stage 8 qualification summary, not documentation or package imports.

| Family | Stage 9 candidates | Environment |
|---|---|---|
| ASR | Faster-Whisper, Vosk | `extended-local` |
| ASR | Sherpa-ONNX ASR | `onnx` |
| VAD | WebRTC VAD | `extended-local` |
| VAD | Sherpa-ONNX VAD | `onnx` |
| Embedding | Resemblyzer | `extended-local` |
| Embedding | WeSpeaker | `wespeaker` |
| Embedding | Sherpa-ONNX embedding | `onnx` |
| Diarization composition | Sherpa-ONNX diarization | `onnx` |

Whisper Tiny/Base/Small, full-record, Energy, Silero, VADChunker, and ECAPA remain the core controls. WeNet is excluded because `final.zip` is unavailable. pyannote and Falcon are excluded because licence actions are incomplete. NeMo is excluded because Linux/CUDA qualification is incomplete.

## Initial screening matrix

The released plan has 19 unique candidates and 228 scenarios. Every candidate uses the same 165 controlled-clean source items from CMU Arctic, LibriSpeech clean, and HiFiTTS clean and the same smoke conditions. The initial stages are:

- six ASR pipelines with full-record segmentation and no speaker/diarization processing;
- nine VAD/segmentation pipelines with Whisper Base fixed;
- four embedding pipelines over identical fixed full-record segments;
- one Sherpa diarization composition pipeline with scientific evaluation deferred.

There is no initial VAD × ASR × embedding × diarizer product. Targeted ASR/VAD and segmentation/embedding interactions appear only after explicit shortlist input. Incompatible profile combinations are rejected before scenario hashing.

## Comparison rules

- Model-quality comparisons reuse identical items and retain environment as a covariate.
- Runtime-implementation comparisons are Pareto-analyzed only within the same environment/hardware group.
- Hardware-performance comparisons require matching OS, Python/package freeze, CPU/GPU, CUDA, device, and profile identities.
- Environment compatibility is reported separately and is never presented as model quality.
- Failed and missing predictions use the declared empty-hypothesis policy for primary WER/CER and remain explicit reliability counts.
- Unsupported reference-dependent VAD metrics are listed as unsupported rather than fabricated.
- Embedding extraction includes success, validity, dimensions, norms, repeatability, minimum-duration behavior, paired drift when supplied, timing, and resources. Enrollment artifacts are never shared between embedding backends.
- EER/FAR/FRR/identification/calibration/unknown rejection remain Stage 10. DER/JER remain Stage 11.

## Real smoke evidence

All nine eligible backends were rerun on the same real CMU Arctic utterance in their isolated profiles. Nine of nine produced repeated contract-valid output with no implicit downloads. The ASR smoke produced zero WER on that one utterance for Faster-Whisper, Vosk, and Sherpa-ONNX. This is a contract/metric smoke only, not a scientific shortlist or release-quality comparison.

The full small-screen campaigns are intentionally separated by environment using `scenario_catalogs_by_environment.json`. This avoids installing mutually isolated native backends together while retaining global scenario IDs for merge and analysis.
