# Machine B setup and launch

> Machine B is supported by the same commands as Machine A, but remains physically unverified until its operator completes setup, verification, and full assignment preflight on that computer.

## Before starting

- Choose the same device mode as Machine A for one distributed campaign: `cuda` is recommended when Machine B has a qualified NVIDIA GPU; otherwise both workers may use `cpu`.
- Make the authorized dataset tree available locally or on a stable mounted drive.
- Do not copy Machine A's virtual environment, model cache, assignment, or campaign database.
- No production credential or API key is required.

## Clone and setup

CUDA:

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cuda
```

CPU:

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git
cd just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_b -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_b -Device cpu
```

If dataset discovery is the only failure, rerun setup once with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 `
  -MachineId machine_b -Device cuda `
  -DatasetRoot "D:\authorized\Raw Datasets (Not formatted)"
```

No YAML, JSON, model path, assignment path, seed, hash, or device field should be edited.

## What verification must prove

| Check | Required result |
|---|---|
| Repository | Same published branch and release commit as Machine A; clean worktree |
| Release binding | `PASS` for campaign, launch-package hash, both assignments, profile, and commit |
| Environment | `core-cuda` / `cuda:0` / `float32`, or `core-cpu` / `cpu` / `float32` |
| Models | Tiny, Base, Small, ECAPA, and Silero available; configured hashes valid |
| Data | All source rows in Machine B's 21 assigned scenarios resolve and are readable |
| RIRs | Exact Dining and Restaurant identifiers and hashes resolve |
| Output | Campaign location writable; disk reserve passes |
| Real inference | One standardized prediction, metrics, report, and zero failed items |
| CUDA only | NVIDIA device identified and nonzero evaluator VRAM recorded |
| Full preflight | 21 of 21 assigned scenarios checked; 13,430 item executions represented |

Machine A may statically check Machine B's assignment coverage, but that does not prove Machine B's hardware, storage, data mount, environment, or runtime.

## Launch and operate

Replace `cuda` with `cpu` below only when both operators selected the CPU campaign.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action stop -MachineId machine_b -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action resume -MachineId machine_b -Device cuda
```

Resume is bound to Machine B's assignment and does not select Machine A scenarios.

## Export and handoff

After every assigned scenario succeeds:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_b -Device cuda
```

Transfer the generated `transfer_packages\campaign_06_massive_release_cuda\machine_b` folder to the coordinator. For CPU, the campaign folder is `campaign_05_massive_release`. The exporter refuses partial completion and existing destinations, writes file hashes, and excludes raw audio, model caches, secrets, environments, and the runtime database.

## Human action still required

The Machine B operator must provide access to legally acquired datasets if setup cannot discover them, run the documented commands on the physical machine, and copy the validated transfer folder to the coordinator. Everything else is automated.
