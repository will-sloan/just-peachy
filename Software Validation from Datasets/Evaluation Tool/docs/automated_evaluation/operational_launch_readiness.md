# Operational launch readiness — CPU and CUDA

## Verdict

**`NOT_READY_TO_LAUNCH`**

The CPU and CUDA implementations are supported and isolated. Machine A has separate final clean-clone environment, real evaluator, release-binding, and complete-preflight evidence for both modes. Machine B and scientific gate evidence do not yet exist.

## Readiness matrix

| Requirement | Machine A | Machine B | Global consequence |
|---|---|---|---|
| CPU runtime (`core-cpu`/`cpu`/float32) | Passed in new clean clone | Not tested | CPU launch blocked until B passes |
| CUDA runtime (`core-cuda`/`cuda:0`/float32) | Passed: 2.11.0+cu128 on RTX 3080 | Not tested | CUDA launch blocked until B passes |
| CUDA nonzero VRAM evidence | Passed: 418.89 MiB peak allocated | Not tested | Required only for CUDA launch |
| Exact Whisper Base model hash | Passed in both Machine A clones | Not tested | Blocked until selected workers pass |
| Complete assignment preflight | Passed for CPU and CUDA: 20/20, 12,368 items, zero blockers | Not tested | Blocked |
| Campaign/assignment binding | Passed in both Machine A clones; runtime binding matched checkout | Pending | Blocked |
| Credentials | None required | None required | Clear |
| Canary/small/standard gates | Not passed for either final campaign | Shared requirement | Blocked |

CPU-only machines are supported and do not need NVIDIA tooling. CUDA machines must use CUDA-enabled PyTorch and may not fall back. A two-worker launch must use assignments from one coherent CPU or CUDA campaign; mixed profiles are a separately identified comparison, not interchangeable work.

## Frozen candidates

- CPU: `campaign_05_massive_release`; manifest `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4`; catalog `24AD135F8F2F2450EED78D910727FC63B585958602D28429B3B46B5A1060367E`; `core-cpu` / `cpu` / `float32`.
- CUDA: `campaign_06_massive_release_cuda`; manifest `A101D43DD3784EEFD1F8738594A13556DD4F9908C55B96F983FBF6B8F628753D`; catalog `1FCDEB638470AE55FC0F4EB88DBB77BF7AB8D5B06704DD1CCFCD5D6C3102B511`; `core-cuda` / `cuda:0` / `float32`.
- Work: 41 scenarios; 25,798 item executions; 33.720 repeated audio hours.
- Model: exact Whisper Base checkpoint; no credentials; no implicit downloads.
- RIRs: Dining Room and Restaurant. Bedroom unresolved and excluded.

Both campaigns are supported public contracts. A CUDA result may not be placed under a CPU scenario ID, or vice versa.

## Evidence required to change the verdict

1. Machine B environment, real smoke, bounded measurement, and 21/21 preflight pass.
2. Both workers select one coherent CPU or CUDA campaign and their final release bindings name the same approved commit.
3. Both assignment sets agree, cover 41 scenarios, and have zero overlap.
4. Canary, small, and standard reports are approved for the exact selected CPU or CUDA configuration.

Only then may the launch control sheet be signed off. The expected final report path is `automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md` for CPU or `automated_runs/campaign_06_massive_release_cuda/analysis/report/campaign_report.md` for CUDA.
