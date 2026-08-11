# Launch control sheet

> Product verdict: **PRODUCTION_READY**. Distributed CUDA launch authorization remains **WAITING_FOR_MACHINE_B** until the physical second computer passes setup and all 21 assigned scenarios in preflight. No optional backend or credential blocks this release.

| Final operational fact | Value |
|---|---|
| Repository | `https://github.com/will-sloan/just-peachy.git`; branch `handoff`; exact launch commit is current `git rev-parse HEAD` and is enforced by `release_binding.json` |
| CUDA campaign | `campaign_06_massive_release_cuda`; manifest `A101D43DD3784EEFD1F8738594A13556DD4F9908C55B96F983FBF6B8F628753D` |
| CPU fallback campaign | `campaign_05_massive_release`; manifest `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4` |
| Machine A | RTX 3080, `core-cuda`, `cuda:0`, `float32`; final clean-clone setup/real inference/full 20-scenario preflight: `READY_TO_LAUNCH` |
| Machine B | 21 scenarios statically valid on A; physical environment, data mount, GPU/disk, real inference, and full preflight still required on B |
| Gates | CPU component canary PASS; CUDA small PASS; CUDA standard PASS |
| Credentials | None |
| Models | Whisper Tiny/Base/Small, SpeechBrain ECAPA, Silero; setup downloads/reuses and verifies; no inference-time downloads |
| RIRs | Dining and Restaurant exact hashes; Bedroom excluded unresolved; no substitution |

## Launch facts

| Worker | Assignment | Items | Audio | Runtime estimate | Artifact estimate |
|---|---:|---:|---:|---:|---:|
| Machine A | 20 scenarios | 12,368 | 16.882998 h | 2.81-5.18 h; point 3.40 h | 2.31 GB plus reserve |
| Machine B | 21 scenarios | 13,430 | 16.837123 h | Provisional 2.81-5.17 h; re-estimate on B | 2.47 GB plus reserve |
| Final | 41 scenarios | 25,798 | 33.720121 h | One GPU scenario per machine | About 4.78 GB plus reserve |

Manual blocker: the Machine B operator must supply authorized datasets if discovery fails and must run setup/verify physically. Required free space is checked automatically. No credential, API key, YAML edit, model movement, or assignment selection is required.

## Exact launch commands

```powershell
# Machine A
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda

# Machine B
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_b -Device cuda
```

## Control, export, and coordinator

```powershell
# Replace machine_a with machine_b on B
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action stop -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action resume -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_a -Device cuda

# Coordinator after both transfer folders arrive
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action merge -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action analyze -Device cuda -PrerequisiteEvidence "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_04_standard_release_cuda\analysis\report\release_qualification.json"
```

Transfer folders: `transfer_packages/campaign_06_massive_release_cuda/machine_a` and `machine_b`. Expected final count: 41 checksum-valid scenarios. Expected report: `Software Validation from Datasets/Evaluation Tool/automated_runs/campaign_06_massive_release_cuda/analysis/report/campaign_report.md`.
