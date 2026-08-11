# Massive campaign guide

The production product provides coverage-equivalent CPU and CUDA campaigns. CUDA is preferred on Machine A after qualification; CPU remains an explicit, first-class mode. Both use frozen source manifests, seed 3800, Whisper Base, one scenario at a time, and the ordinary Evaluation Tool executor, scoring, plots, reports, artifact validation, and analysis.

## Frozen campaign identities

| Property | CPU | CUDA |
|---|---|---|
| Campaign ID | `campaign_05_massive_release` | `campaign_06_massive_release_cuda` |
| Manifest SHA-256 | `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4` | `A101D43DD3784EEFD1F8738594A13556DD4F9908C55B96F983FBF6B8F628753D` |
| Scenario catalog SHA-256 | `24AD135F8F2F2450EED78D910727FC63B585958602D28429B3B46B5A1060367E` | `1FCDEB638470AE55FC0F4EB88DBB77BF7AB8D5B06704DD1CCFCD5D6C3102B511` |
| Environment | `core-cpu` | `core-cuda` |
| Runtime | `cpu`, `float32` | `cuda:0`, `float32` |
| Scenarios | 41 | 41 |
| Item executions | 25,798 | 25,798 |
| Repeated audio | 33.720121 hours | 33.720121 hours |
| Unique source rows | 8,258 | 8,258 |

CPU and CUDA have distinct canonical scenario IDs because device and dtype affect scientific identity. Absolute paths, worker identity, retry number, and output locations do not affect IDs.

## Scientific coverage

- `controlled_clean`: clean CMU Arctic, LibriSpeech clean, and HiFiTTS clean with approved clean, white-noise, pink-noise, Dining RIR, Restaurant RIR, and selected RIR-plus-noise conditions.
- `native_robustness`: AMI, CHiME-6, VOiCES, and approved native rows without synthetic augmentation.
- `speaker_protocol`: disjoint enrollment and probe source selections, including clean and degraded probes. The massive ASR campaign preserves these source roles; dedicated embedding and speaker metrics remain tied to compatible output contracts.
- RIR policy: exact `h025_Diningroom_8txts.wav` and `h093_Restaurant_2txts.wav` hashes only. Bedroom remains unresolved and excluded. There is no ParkingLot, Kitchen, or other substitution.

## Release hierarchy

```text
CPU component canary (7 scenarios plus 9 component qualifications)
  -> small release (26 scenarios)
  -> standard release (41 scenarios)
  -> massive campaign preflight and launch (41 scenarios)
```

The CUDA release chain intentionally uses the canonical CPU component canary, then CUDA-specific small and standard scenarios. A passed standard release-qualification artifact is mandatory input to final massive analysis.

## Worker partition

| Worker | Scenario count | Item executions | Repeated audio | CUDA point estimate | Estimated artifacts |
|---|---:|---:|---:|---:|---:|
| Machine A | 20 | 12,368 | 16.882998 h | 3.405 h | 2.31 GB |
| Machine B | 21 | 13,430 | 16.837123 h | 3.402 h | 2.47 GB |
| Total | 41 | 25,798 | 33.720121 h | Parallel wall time about 3.4 h after B qualification | 4.78 GB |

Runtime estimates are planning values, not guarantees. Machine B must produce its own measured profile. Setup generates both assignment manifests and a checksummed `release_binding.json` tied to current Git HEAD; the launch preflight validates that binding automatically.

## Artifact layout

```text
Software Validation from Datasets/Evaluation Tool/automated_runs/<campaign_id>/
  campaign_manifest.json
  campaign_manifest.sha256
  benchmark_manifests/
  worker_assignments/
  database/
  scenarios/<scenario_id>/
    resolved_scenario.json
    run_config.yaml
    status.json
    predictions/
    metrics/
    resource_logs/
    logs/
    report/
  analysis/
```

Each scenario records source and benchmark identities, model/config hashes, condition and RIR identity, seed, environment fingerprint, predictions, failures, metrics, telemetry, status, and checksums. Writes are atomic; completion requires validated artifacts and reconciled counts.

## Supported commands

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda -PreflightOnly
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
```

Status, stop, resume, export, merge, and analysis use the root wrappers documented in `START_HERE.md`. Routine operation requires no configuration edits, model movement, activation command, credential, assignment path, or manual hash entry.

## Final completion contract

The campaign is analytically complete only after both worker transfers validate, merge reports all 41 expected IDs with no conflicting duplicate or missing scenario, merged artifacts validate, and analysis uses the passed matching standard gate. The final CUDA report path is `automated_runs/campaign_06_massive_release_cuda/analysis/report/campaign_report.md`; CPU uses `campaign_05_massive_release`.
