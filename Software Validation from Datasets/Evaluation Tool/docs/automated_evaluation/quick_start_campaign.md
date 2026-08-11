# Quick-start campaign

Use these commands from the repository root. CUDA is the recommended Machine A mode after qualification; CPU remains a fully supported explicit fallback. Two workers contributing to one result set must select the same mode.

## CUDA worker

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
```

## CPU worker

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cpu
```

Change `machine_a` to `machine_b` on the second computer. If authorized datasets cannot be discovered, add one `-DatasetRoot` argument to setup; do not edit configuration files.

## Preflight without inference

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda -PreflightOnly
```

This is the same release-binding, campaign, assignment, machine, dataset, model, RIR, disk, and output validation used at launch. A zero exit and `READY_TO_LAUNCH` are required.

## Release owner gates

Before the massive campaign, run the component canary, small campaign, and standard campaign in order:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_release_gates.ps1 -Device cuda -Through all
```

The CUDA chain uses the canonical CPU component canary, followed by explicit CUDA small and standard scenarios. Use `-Device cpu` only for the independent CPU hierarchy.

## Status, stop, and resume

```powershell
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action stop -MachineId machine_a -Device cuda -Reason "planned maintenance"
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action resume -MachineId machine_a -Device cuda
```

Resume requeues stopped work only from the named worker assignment. Completed scenarios validate and skip.

## Export

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_a -Device cuda
```

The default output is `transfer_packages\campaign_06_massive_release_cuda\machine_a`. Existing folders are never overwritten. CPU uses `campaign_05_massive_release`.

## Coordinator

Place both worker transfer folders under the same coordinator clone, then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action merge -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action analyze -Device cuda `
  -PrerequisiteEvidence "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_04_standard_release_cuda\analysis\report\release_qualification.json"
```

Expected final scenario count is 41. The final report is `Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_06_massive_release_cuda\analysis\report\campaign_report.md`.

For CPU, replace `cuda` with `cpu`; analysis evidence comes from `campaign_04_standard_release`, and the final campaign is `campaign_05_massive_release`.
