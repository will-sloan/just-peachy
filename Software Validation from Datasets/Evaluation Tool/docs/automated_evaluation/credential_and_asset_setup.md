# Production credentials and assets

> The supported CPU and CUDA campaigns require no API key, login token, license acceptance, or hosted inference account.

## Production scope

| Family | Supported production choices | Setup behavior |
|---|---|---|
| ASR | Whisper Tiny, Base, Small | Downloaded from the approved OpenAI model URLs and hash-verified |
| VAD | Full-record/no-op, Energy, Silero | Energy is local code; Silero package/model is installed and verified |
| Segmentation | Full-record/no-op, VADChunker | Installed from the repository environment |
| Speaker embedding | SpeechBrain ECAPA | Downloaded to the local cache and hash-verified |
| Matching | Cosine-threshold contract | Local implementation; no external account |
| Diarization | Explicit no-op only | No credential-gated diarizer is in the release campaign |

Pyannote, Picovoice Falcon, NeMo, WeNet, Sherpa-ONNX, Vosk, faster-whisper, Resemblyzer, WeSpeaker, and WebRTC VAD remain optional or experimental. They are not installed, downloaded, requested, or checked by the supported production commands. Do not obtain credentials for this release.

## Automatic setup

Run one command from the repository root. It creates or reuses the isolated environment, installs packages and FFmpeg, bootstraps only the production models, verifies model files, discovers datasets, validates Dining and Restaurant RIR files, and materializes the selected massive campaign.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
```

For CPU, replace `cuda` with `cpu`. For the second computer, replace `machine_a` with `machine_b`. Setup is idempotent; rerunning it reuses valid assets.

## Model cache contract

The setup command owns the local `models\cache` directory. Operators must not move checkpoints into place or edit model paths. Inference is configured for offline use after setup, so a missing or invalid production checkpoint is a setup failure rather than an implicit inference download.

| Asset | Local identity |
|---|---|
| Whisper Tiny | `models/cache/whisper/tiny.pt`; SHA-256 `65147644A518D12F04E32D6F3B26FACC3F8DD46E5390956A9424A650C0CE22B9` |
| Whisper Base | `models/cache/whisper/base.pt`; SHA-256 `ED3A0B6B1C0EDF879AD9B11B1AF5A0E6AB5DB9205F891F668F8B0E6C6326E34E` |
| Whisper Small | `models/cache/whisper/small.pt`; SHA-256 `9ECF779972D90BA49C06D968637D720DD632C55BBF19D441FB42BF17A411E794` |
| SpeechBrain ECAPA | `models/cache/speechbrain/spkrec-ecapa-voxceleb/embedding_model.ckpt`; SHA-256 `0575CB64845E6B9A10DB9BCB74D5AC32B326B8DC90352671D345E2EE3D0126A2` |

## Licensed datasets

The repository never downloads or copies licensed corpora. Setup first checks the clone, `JUST_PEACHY_DATASET_ROOT`, and sibling Just-Peachy clones. If it finds the complete authorized dataset tree, it creates a Windows junction in the new clone without modifying source audio.

Only when discovery cannot succeed, provide the one unavoidable machine-local input:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 `
  -MachineId machine_b -Device cuda `
  -DatasetRoot "D:\authorized\Raw Datasets (Not formatted)"
```

Required production corpora are AMI, CHiME-6, CMU Arctic, HiFiTTS, LibriSpeech, and VOiCES. RIR validation requires the exact Dining and Restaurant files. Bedroom is unresolved and excluded; ParkingLot, Kitchen, or any other file must not be substituted.

## Verification

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
```

Verification checks packages, hashes, device and dtype, a real one-item Whisper Base evaluator run, release binding, and every assigned massive scenario. CUDA verification fails if CUDA is unavailable or the evaluator does not record nonzero VRAM; it never falls back to CPU.

## Inputs and outputs

- Inputs: machine ID, explicit CPU/CUDA mode, and only when necessary an authorized dataset root.
- Local outputs: `.venv` for CPU, `.stage8-envs/core-cuda` for CUDA, `models/cache`, ignored setup evidence under `Evaluation Tool/artifacts`, and ignored campaign state under `Evaluation Tool/automated_runs`.
- Shared outputs exclude raw datasets, model caches, environments, credentials, and campaign SQLite databases.
