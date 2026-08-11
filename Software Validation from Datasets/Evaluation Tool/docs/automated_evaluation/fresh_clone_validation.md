# Fresh CPU and CUDA clone validation

## Final result

Two new clean Machine A clones were created from the final release commit. No `.venv`, `.stage8-envs`, model cache, campaign database, or runtime artifact was copied from development. Each clone used only the high-level operator commands in `START_HERE.md`.

| Acceptance check | CPU clone | CUDA clone |
|---|---|---|
| Clone path | `C:/Users/amiri/Documents/GitHub/just-peachy-production-cpu-20260811` | `C:/Users/amiri/Documents/GitHub/just-peachy-production-cuda-20260811` |
| Setup | PASS; new `.venv`, pinned CPU packages | PASS; new `.stage8-envs/core-cuda`, pinned CUDA packages |
| Package integrity | `pip check` PASS | `pip check` PASS |
| FFmpeg | 8.1.2 discovered without terminal restart | 8.1.2 discovered without terminal restart |
| Models | Tiny/Base/Small, ECAPA, Silero bootstrapped/reused and verified | Same production assets verified |
| Dataset setup | Existing licensed Machine A tree discovered and linked automatically | Existing licensed Machine A tree discovered and linked automatically |
| Real evaluator | 1 prediction, 0 failures, CPU/float32 | 1 prediction, 0 failures, `cuda:0`/float32, nonzero VRAM |
| Campaign | CPU massive materialized and validated | CUDA massive materialized and validated |
| Release binding | Current clean-clone HEAD and both assignments validated | Current clean-clone HEAD and both assignments validated |
| Machine A preflight | `READY_TO_LAUNCH`, 20/20, 12,368 items | `READY_TO_LAUNCH`, 20/20, 12,368 items |

The historical clone `C:/Users/amiri/Documents/GitHub/just-peachy-launch-a` was not modified.

## Reproducible CPU procedure

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git `
  C:\Users\amiri\Documents\GitHub\just-peachy-production-cpu-20260811
Set-Location C:\Users\amiri\Documents\GitHub\just-peachy-production-cpu-20260811
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cpu
```

`verify_worker.ps1` includes the real one-item CPU evaluator smoke and the same full preflight used at launch. No manual activation is required.

## Reproducible CUDA procedure

```powershell
git clone --branch handoff https://github.com/will-sloan/just-peachy.git `
  C:\Users\amiri\Documents\GitHub\just-peachy-production-cuda-20260811
Set-Location C:\Users\amiri\Documents\GitHub\just-peachy-production-cuda-20260811
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
```

CUDA setup installs the official pinned CUDA PyTorch wheels into its own environment. Verification requires `torch.cuda.is_available() == True`, identifies the RTX 3080, runs the real ordinary evaluator, confirms `cuda:0` and float32, and requires nonzero peak allocator VRAM. CUDA failure is terminal; there is no CPU fallback.

## What setup proved

- The checkout itself contains every production script, config, manifest source, schema, and operator document.
- Setup is idempotent and performs repository sanity checks, environment creation, package installation, `pip check`, FFmpeg handling, model bootstrap, model verification, dataset discovery/linking, RIR checks, massive materialization, assignment generation, release binding, and report initialization.
- Existing licensed datasets are shared through an approved Windows junction; raw contents are neither copied nor changed.
- Inference cannot download a missing model implicitly.
- Runtime outputs remain ignored, and `git status --short` stays clean after setup/verify.

## Optional dataset-root fallback

Only if automatic discovery genuinely fails:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 `
  -MachineId machine_a -Device cuda `
  -DatasetRoot "D:\authorized\Raw Datasets (Not formatted)"
```

This is the only supported routine machine-local override. Do not edit dataset mappings or frozen manifests.

## Evidence to inspect

```powershell
git status --short
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda -PreflightOnly
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_a -Device cuda
```

The first command should print nothing. Preflight must print release-binding `PASS` and finish `READY_TO_LAUNCH` without starting massive inference. Status must identify only Machine A's 20 assigned scenarios.

## Scope of this proof

Fresh-clone acceptance establishes reproducible Machine A CPU and CUDA setup and operation from the final commit. It does not claim that the physical Machine B has run. B must repeat its matching commands with `machine_b` and provide authorized datasets if discovery cannot find them.
