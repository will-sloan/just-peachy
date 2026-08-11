# Massive CPU and CUDA campaign guide

The product exposes two coverage-equivalent campaigns. `campaign_05_massive_release` uses `core-cpu` / `cpu` / `float32`; `campaign_06_massive_release_cuda` uses `core-cuda` / `cuda:0` / `float32`. Both use Whisper Base, full-record input, and the same scientific source/condition coverage.

Neither is yet an authorized release run. Machine B and the staged scientific gates remain outstanding.

## Frozen scientific scope

| Contract | Frozen value |
|---|---|
| CPU campaign manifest | `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4` |
| CPU scenario catalog | `24AD135F8F2F2450EED78D910727FC63B585958602D28429B3B46B5A1060367E` |
| CUDA campaign manifest | `A101D43DD3784EEFD1F8738594A13556DD4F9908C55B96F983FBF6B8F628753D` |
| CUDA scenario catalog | `1FCDEB638470AE55FC0F4EB88DBB77BF7AB8D5B06704DD1CCFCD5D6C3102B511` |
| Scenario count | 41 |
| Item executions | 25,798 |
| Repeated audio | 33.720 h |
| Seed | 3800 |
| Model | Whisper Base exact 145,262,807-byte checkpoint |
| RIRs | Dining Room and Restaurant only |
| Native policy | AMI, VOiCES, CHiME-6 and approved other rows remain native-only |

Source benchmark hashes remain identical. All CUDA scenario IDs differ from CPU because device is canonical identity; float16 scenarios would also differ by dtype. Assignment identities and `release_binding.json` change when bound to the final Git commit.

## Coverage

- Controlled clean: clean baseline; white and pink noise; Dining Room and Restaurant RIRs; selected approved RIR-plus-noise interactions.
- Native robustness: AMI, VOiCES, CHiME-6, and approved native rows without synthetic noise or RIR.
- Speaker protocol rows remain available for the frozen campaign structure, but this Whisper-only full-record candidate does not fabricate speaker embeddings, identification, or diarization outputs.
- Bedroom is unresolved and absent. ParkingLot and Kitchen are not substitutes.

## Runtime decision

A five-item real benchmark showed identical transcripts, WER, and CER for CPU float32, CUDA float32, and CUDA float16. CUDA float32 was the fastest GPU mode: pipeline RTF 0.1951 and ASR inference speedup 1.787x versus CPU. Peak PyTorch allocator usage was 418.89 MiB allocated and 426 MiB reserved. Float16 remains separately qualified but is not the campaign dtype.

## Expected operation

Machine A receives 20 scenarios/12,368 items and Machine B 21/13,430. The coverage split is deterministic and non-overlapping. Runtime estimates are about 3.4 hours per machine when run in parallel, with ranges near 2.8–5.2 hours. These estimates come from Machine A and must be replaced by Machine B measurements before launch.

Each worker materializes the same selected campaign from `launch_package.v1.yaml` for CPU or `launch_package.gpu.v1.yaml` for CUDA using `--bind-current-commit`, runs its own complete preflight, and uses the matching machine-specific wrapper. Results are exported into independent transfer packages, checksum-validated, merged without overwrite, and analyzed only with approved prerequisite evidence.

## Release gates

1. Machine A clean-clone preflight passes.
2. Machine B real smoke and complete preflight pass for the selected mode.
3. Component canary passes for the exact finalist configuration.
4. Small campaign gate passes.
5. Standard campaign gate passes and its evidence is frozen.
6. Both massive assignments run and export successfully.
7. Merge reports 41/41 valid scenarios and no conflict.
8. Analysis reconciles expected denominators and writes the final report.

No massive inference was started during CPU/CUDA preparation.
