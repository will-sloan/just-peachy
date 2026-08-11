# Manual actions required

The supported production workflow is clone, setup, verify, and launch. Normal operation requires no edits to Python, YAML, JSON, manifests, paths, hashes, device settings, or assignments.

## Human actions

| Owner | Action | Completion evidence |
|---|---|---|
| Release owner | Publish the final `handoff` commit and ensure both operators clone it | Both `git rev-parse HEAD` values match; release-binding validation says `PASS` |
| Machine A operator | Run CUDA setup and verification | Real RTX 3080 inference with nonzero VRAM; 20/20 assignment preflight says `READY_TO_LAUNCH` |
| Machine B operator | Make licensed datasets available, then run matching setup and verification | Physical B profile plus 21/21 preflight says `READY_TO_LAUNCH` |
| Both operators | Agree on one mode and start their own assignment | Same campaign ID, distinct assignment IDs, no overlap |
| Each operator | Monitor; use controlled stop/resume when needed | Completed assignment with validated scenario artifacts |
| Each operator | Run export and copy the generated transfer folder | `transfer_manifest.json` validates; no unexported scenarios |
| Coordinator | Place both transfers in the expected folder and run merge plus analysis | 41 scenarios merged, zero missing/conflicting IDs, final report generated |

## Only unavoidable local input

Licensed speech datasets must already exist on each machine or an authorized mounted drive. Setup discovers a complete local/sibling tree automatically. If it cannot, the operator supplies one path:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 `
  -MachineId machine_b -Device cuda `
  -DatasetRoot "D:\authorized\Raw Datasets (Not formatted)"
```

The project does not download, fabricate, copy, or modify licensed source audio.

## No credential work

No production API key or account token is required. Pyannote, Falcon, NeMo, WeNet, and other optional experimental backends are outside the release scope. Do not acquire credentials or models for them as part of this launch.

## Commands operators actually run

Machine A:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_a -Device cuda
```

Machine B uses the same four commands with `machine_b`. A CPU campaign uses `cpu` on both machines.

Coordinator:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action merge -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action analyze -Device cuda `
  -PrerequisiteEvidence "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_04_standard_release_cuda\analysis\report\release_qualification.json"
```

## Stop conditions

Do not launch when either worker preflight is not `READY_TO_LAUNCH`, commits or campaign hashes differ, the standard gate has not passed, datasets/RIRs are missing, CUDA verification did not record nonzero VRAM for a CUDA campaign, disk reserve fails, or assignments overlap. Fix the stated condition and rerun the same command; do not edit frozen artifacts.

## Not a blocker

Bedroom RIR remains excluded without substitution. Optional credential-gated or unresolved experimental backends remain out of scope. These facts do not block the Dining/Restaurant, Whisper, VAD, ECAPA, CPU, or CUDA production workflow.
