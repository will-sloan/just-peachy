# Operational launch readiness

## Verdict

**Software product: `PRODUCTION_READY`. Machine A: `READY_TO_LAUNCH`. Two-machine campaign: `WAITING_FOR_MACHINE_B`.**

All locally achievable engineering, setup, CPU, CUDA, campaign, recovery, exchange, analysis, and documentation requirements passed final acceptance. The only remaining launch-day dependency is physical qualification of the second computer and its authorized dataset access. Optional Pyannote, Falcon, NeMo, WeNet, and other experimental backends are outside production scope and are not blockers.

## Acceptance matrix

| Area | Evidence-based result | Status |
|---|---|---|
| CPU setup and real inference | Isolated CPU environment; Whisper Base ordinary evaluator prediction, metrics, and report | PASS |
| CUDA setup and real inference | PyTorch CUDA on RTX 3080; evaluator device `cuda:0`; float32; nonzero VRAM | PASS |
| CPU/CUDA identity | Canonical IDs differ by device/dtype; no silent fallback | PASS |
| Models and FFmpeg | Automatic, idempotent setup; Tiny/Base/Small and ECAPA hashes; Silero; process PATH refresh | PASS |
| Dataset/RIR discovery | Machine A corpora discovered and linked; Dining/Restaurant exact hashes; Bedroom excluded | PASS |
| Component canary | 7/7 executable scenarios and 9/9 active component qualifications | PASS |
| CUDA small campaign | 26/26 scenarios executed, validated, exported, merged, analyzed, and release-qualified | PASS |
| CUDA standard campaign | 41/41 scenarios executed, validated, exported, merged, analyzed, and release-qualified | PASS |
| Massive campaign | 41 immutable CUDA scenarios; 25,798 item executions; two non-overlapping assignments | PASS |
| Machine A complete preflight | All 20 assigned scenarios and 12,368 item executions resolved; binding, data, models, RIR, disk, output, hardware | PASS |
| Bounded CUDA rehearsal | Clean, noise, Dining RIR, Restaurant-plus-noise, native, and speaker source; real executor | PASS |
| Recovery and exchange | Status, controlled stop, assignment resume, export, transfer validation, merge, analysis | PASS |
| Fresh clones | CPU and CUDA created without copied environments and passed documented setup/verify/preflight | PASS |
| Automated quality gates | Complete relevant tests, Ruff, mypy, CPU/CUDA `pip check`, Word render QA | PASS |
| Machine B physical qualification | Not fabricated; 21 scenarios statically valid on A, but physical B has not run | EXTERNAL PENDING |

## Supported production contract

- CPU: `campaign_05_massive_release`, `core-cpu`, `cpu`, `float32`.
- CUDA: `campaign_06_massive_release_cuda`, `core-cuda`, `cuda:0`, `float32`; preferred on Machine A.
- Active credentials: none.
- Active models/components: Whisper Tiny/Base/Small, full-record/no-op, Energy VAD, Silero VAD, VADChunker, SpeechBrain ECAPA extraction, cosine matching contract, explicit no-op diarization.
- Massive finalist: Whisper Base reference pipeline with exact frozen source and condition coverage.
- Concurrency: one GPU-heavy scenario at a time per machine.
- RIRs: Dining and Restaurant only; Bedroom unresolved and excluded without replacement.

## Machine A evidence

The final Machine A profile records Windows 11, 8 physical/16 logical CPU cores, about 64 GiB RAM, RTX 3080 with 10,240 MiB VRAM, NVIDIA driver 610.62, Python 3.12.7, PyTorch 2.11.0+cu128, CUDA runtime 12.8, selected `cuda:0`/`float32`, FFmpeg 8.1.2, production model identities, complete dataset/RIR coverage, disk reserve, campaign ID, and assignment ID. The real evaluator allocated approximately 418.89 MiB peak model VRAM and produced one valid standardized prediction with no failed item.

Machine-local reports are generated under `Software Validation from Datasets/Evaluation Tool/artifacts/production_setup`, `production_verification`, and `launch_readiness`. They are intentionally not exchanged as campaign results.

## Release binding

Setup materializes the selected frozen campaign and generates both assignments plus `release_binding.json` and its SHA-256 sidecar. Launch validates:

- current Git HEAD;
- launch-package hash;
- campaign ID and manifest hash;
- both assignment IDs, hashes, coverage, and expected profile;
- selected worker presence.

The check prints `release binding: PASS` or exits nonzero. Operators do not inspect or edit JSON.

## Remaining launch-day action

On Machine B, clone the same published `handoff` commit and run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cuda
```

If and only if licensed data is not discoverable, rerun setup with one `-DatasetRoot`. Authorize distributed launch only when B reports `READY_TO_LAUNCH` for all 21 assigned scenarios and 13,430 item executions, uses the same commit/campaign/profile as A, and records a real CUDA prediction with nonzero VRAM. Then both operators run `launch_worker.ps1` for their own machine ID.

## Final output contract

Each validated export excludes raw datasets, model caches, secrets, environments, and campaign SQLite. Coordinator merge must reconcile 41 global scenario IDs with no missing or conflicting duplicate and valid checksums. Final CUDA report path:

```text
Software Validation from Datasets/Evaluation Tool/automated_runs/
  campaign_06_massive_release_cuda/analysis/report/campaign_report.md
```
