# Two-machine launch runbook

> Both operators clone the complete repository. Each setup command generates a non-overlapping worker assignment with globally stable scenario IDs. No shared SQLite database or network-drive coordinator is used.

## 1. Select one campaign mode

| Mode | Campaign | Profile | Device and dtype | Machine A share | Machine B share |
|---|---|---|---|---|---|
| CUDA, recommended | `campaign_06_massive_release_cuda` | `core-cuda` | `cuda:0`, `float32` | 20 scenarios / 12,368 items | 21 scenarios / 13,430 items |
| CPU | `campaign_05_massive_release` | `core-cpu` | `cpu`, `float32` | 20 scenarios / 12,368 items | 21 scenarios / 13,430 items |

Do not merge CPU and CUDA work into one campaign. Device and dtype are result-affecting scenario identity fields.

## 2. Clone, setup, and verify

Machine A CUDA:

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
```

Machine B CUDA:

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cuda
```

For CPU, replace `cuda` with `cpu` on both machines. If discovery fails, only the affected operator reruns setup with `-DatasetRoot`.

Verification must finish with a clean release binding, one real prediction, and full assignment preflight: 20/20 on A and 21/21 on B. Machine B is not considered verified until this occurs physically on B.

## 3. Launch independently

Machine A:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
```

Machine B:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_b -Device cuda
```

The workers may start at different times. Each local database leases only scenarios in that worker's immutable assignment. One GPU-heavy scenario runs at a time per machine.

## 4. Control a worker

```powershell
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action stop -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action resume -MachineId machine_a -Device cuda
```

Use the correct machine ID on each computer. A stop is persistent. Resume is assignment-scoped, preserves completed work, validates successes, and never silently overwrites artifacts.

## 5. Export each completed assignment

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_b -Device cuda
```

Each export is checksum-validated and rejected if assigned scenarios remain incomplete. Transfer only these folders:

```text
transfer_packages/
  campaign_06_massive_release_cuda/
    machine_a/
    machine_b/
```

## 6. Merge and analyze

On the coordinator clone:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action merge -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action analyze -Device cuda `
  -PrerequisiteEvidence "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_04_standard_release_cuda\analysis\report\release_qualification.json"
```

Merge validates both transfers, checks all 41 global IDs, recognizes byte-identical duplicates, rejects conflicts, reports environment differences, and refuses missing or corrupt content. Analysis consumes the merged index and passed standard-gate evidence.

## Recovery rules

- If power or inference stops unexpectedly, run `status`, then the same worker's `resume` command.
- If setup or preflight reports a missing dataset, supply the authorized root; never copy raw audio into a campaign.
- If CUDA fails, repair CUDA or intentionally start a separate CPU campaign. Never reinterpret CUDA scenario IDs as CPU work.
- If a transfer is interrupted, discard only the incomplete copied destination and recopy the original validated export. Do not modify its contents.
- If duplicate results differ, preserve both folders and investigate; the coordinator must not choose one silently.
