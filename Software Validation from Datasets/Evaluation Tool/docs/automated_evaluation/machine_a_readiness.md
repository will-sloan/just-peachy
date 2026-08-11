# Machine A readiness

## Verdict

**Machine A is `READY_TO_LAUNCH` in the preferred CUDA mode and remains qualified for the explicit CPU fallback.** The final clean CPU and CUDA clones used only the documented setup and verification commands, did not copy environments, and passed real evaluator inference, release binding, and complete 20-scenario assignment preflight.

This does not fabricate Machine B readiness. The two-machine launch remains pending until B passes its own physical 21-scenario preflight.

## Current machine profile

| Field | Qualified value |
|---|---|
| Operating system | Windows 11, build family `10.0.26200`, AMD64 |
| CPU | 8 physical / 16 logical cores |
| RAM | 68,641,923,072 bytes, about 64 GiB |
| GPU | NVIDIA GeForce RTX 3080, index 0 |
| GPU UUID | Recorded in local machine profile; excluded from shared scientific identity |
| VRAM | 10,240 MiB |
| NVIDIA driver | 610.62 |
| Python | 3.12.7 |
| CPU PyTorch | 2.11.0+cpu; CUDA unavailable by design |
| CUDA PyTorch | 2.11.0+cu128; CUDA runtime 12.8 |
| Production CUDA mode | `core-cuda`, `cuda:0`, `float32` |
| CPU fallback mode | `core-cpu`, `cpu`, `float32` |
| FFmpeg | 8.1.2 |
| Credentials | None |

CUDA float32 is the production recommendation. In the bounded identical-source comparison it preserved the same predictions, WER 0.1463414634, and CER 0.1444444444 as CPU float32 and CUDA float16, while producing the strongest measured inference speedup. CUDA float16 remains qualified evidence but is not the selected production campaign identity.

## Real inference evidence

| Check | CPU | CUDA |
|---|---|---|
| Requested/observed device | `cpu` / `cpu` | `cuda` / `cuda:0` |
| Dtype | `float32` | `float32` |
| Selected items | 1 | 1 |
| Predictions / failures | 1 / 0 | 1 / 0 |
| WER / CER | 0.25 / 0.162162 | 0.25 / 0.162162 |
| Model allocator peak | GPU unavailable, recorded explicitly | 418.89 MiB allocated; 426 MiB reserved |
| Required outputs | Prediction JSONL, metrics, plots, and Markdown report | Prediction JSONL, metrics, plots, and Markdown report |

The CUDA verifier fails if the evaluator reports CPU or zero allocated VRAM. CPU verification never requires NVIDIA tooling and does not invent GPU values.

## Models, datasets, and RIRs

Setup automatically downloaded or reused and verified Whisper Tiny, Base, Small, SpeechBrain ECAPA, and Silero. Inference is offline and prohibits implicit model download.

The setup command discovered the existing authorized Machine A dataset tree and exposed it to each clean clone without copying raw audio. Complete assignment preflight resolved all required AMI, CHiME-6, CMU Arctic, HiFiTTS, LibriSpeech, and VOiCES source rows. Exact Dining and Restaurant RIR files and hashes passed. Bedroom remains excluded unresolved with no replacement.

## Massive CUDA assignment

| Field | Machine A value |
|---|---:|
| Campaign | `campaign_06_massive_release_cuda` |
| Assigned scenarios | 20 |
| Item executions | 12,368 |
| Unique source audio files | 2,750 |
| Repeated audio | 16.882998 hours |
| CUDA runtime estimate | 2.81-5.18 hours; point 3.40 hours |
| Estimated artifacts | 2.31 GB |
| Disk policy | Artifact estimate plus 5 GiB reserve; checked at launch |

Preflight checks every assigned scenario, not a sample. It validates commit, release binding, both assignments, environment profile, packages, models, source files and bounds, RIRs, output writability, system RAM, disk capacity, and GPU capability.

## Exact commands

Preferred CUDA:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda -PreflightOnly
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
```

Explicit CPU fallback:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cpu -PreflightOnly
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cpu
```

Do not run CPU and CUDA assignments as if they belong to one campaign. Their globally stable scenario IDs are intentionally different.

## Evidence locations

- Local setup: `Software Validation from Datasets/Evaluation Tool/artifacts/production_setup/machine_a_<device>.json`.
- Real verifier: `Software Validation from Datasets/Evaluation Tool/artifacts/production_verification/machine_a/<device>/worker_verification.json`.
- Machine profile and preflight: `Software Validation from Datasets/Evaluation Tool/artifacts/launch_readiness`.
- CPU/CUDA benchmark: `Software Validation from Datasets/Evaluation Tool/artifacts/gpu_qualification/comparison/whisper_base_cuda_qualification.json`.

These are machine-local evidence. Shared scenario artifacts retain privacy-safe environment identity and checksums without exposing credentials or absolute dataset paths.
