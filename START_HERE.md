# Just-Peachy production start

Run these commands from the repository root in Windows PowerShell. CPU and
CUDA are separate campaigns; two workers contributing to one campaign must
choose the same device mode. CUDA never falls back to CPU.

## Machine A — CUDA (recommended)

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
```

## Machine A — CPU

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cpu
```

## Machine B — CUDA

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_b -Device cuda
```

## Machine B — CPU

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_b -Device cpu
```

If licensed datasets are not discoverable, rerun setup once with
`-DatasetRoot "D:\path\to\Raw Datasets (Not formatted)"`. No other routine
configuration edit is required.

## Release gates (release owner)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_release_gates.ps1 -Device cuda -Through all
```

Use `-Device cpu` for the independent CPU release hierarchy.

## Status, stop, and assignment-safe resume

```powershell
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action stop -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action resume -MachineId machine_a -Device cuda
```

Replace `machine_a` and `cuda` with the current worker and shared campaign
mode. Status reports only that worker's assignment. Resume requeues only
stopped scenarios in that same assignment.

## Export

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_b -Device cuda
```

Transfer the two generated folders below
`transfer_packages\campaign_06_massive_release_cuda\` to the coordinator.

## Coordinator — merge and analyze

```powershell
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action merge -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action analyze -Device cuda -PrerequisiteEvidence "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_04_standard_release_cuda\analysis\report\release_qualification.json"
```

For a CPU campaign, use `-Device cpu` in both coordinator commands and use
`campaign_04_standard_release\analysis\report\release_qualification.json` as
the prerequisite evidence.

The final Markdown report is under
`Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_06_massive_release_cuda\analysis\report\campaign_report.md`.

For command purpose, inputs, outputs, and troubleshooting, see
[`scripts/PRODUCTION_README.md`](scripts/PRODUCTION_README.md) and the operator
documents under `Software Validation from Datasets/Evaluation Tool/docs/automated_evaluation`.
