# Production command reference

## Purpose

The scripts in this folder provide the supported clone → setup → verify → run
interface for the Just-Peachy Evaluation Tool. They select the correct isolated
Python environment, discover licensed datasets, bootstrap and verify the
credential-free production models, bind frozen campaign assignments to Git
HEAD, preflight every assigned scenario, run one worker, export checksummed
results, merge independent transfers, and invoke the existing analysis engine.

Production scope is Whisper Tiny/Base/Small, Energy and Silero VAD,
VADChunker, SpeechBrain ECAPA extraction, cosine matching qualification, and
the no-op implementations needed to disable a family explicitly. Pyannote,
Falcon, NeMo, WeNet, and other credential-gated or unresolved experimental
backends are not production prerequisites. No API key is required.

## Supported inputs

- `MachineId`: `machine_a` or `machine_b`.
- `Device`: `cpu` or `cuda`. CUDA means NVIDIA device `cuda:0`, float32.
- Optional `DatasetRoot`: the authorized `Raw Datasets (Not formatted)` folder.
- Optional export/transfer paths for coordinator workflows.

Both workers in one distributed campaign must use the same device mode. CPU
and CUDA have different result-affecting scenario identities and cannot be
merged into one campaign.

## Outputs

- CPU environment: `.venv` (`core-cpu`).
- CUDA environment: `.stage8-envs\core-cuda` (`core-cuda`).
- Models: ignored local cache under `models\cache`.
- Campaign state and artifacts: `Software Validation from Datasets\Evaluation Tool\automated_runs\<campaign_id>`.
- Setup/verification/preflight reports: `Evaluation Tool\artifacts`.
- Worker transfer packages: `transfer_packages\<campaign_id>\<machine_id>`.
- Merged analysis: `<campaign_root>\analysis`.

Raw audio, model caches, virtual environments, secrets, and campaign SQLite
databases are not included in worker exports.

## PowerShell workflow

Setup is idempotent and activates no shell environment; every wrapper invokes
the correct interpreter directly.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda -PreflightOnly
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cuda
```

`setup_worker.ps1` requires a clean Git checkout and performs repository checks,
environment creation, pinned
package installation, `pip check`, FFmpeg handling, automatic model bootstrap,
model verification and automatic reacquisition of an invalid production cache,
dataset discovery/linking, exact Dining/Restaurant RIR hash checks, massive-campaign
materialization, assignment generation, release binding, and setup reporting.
If automatic data discovery fails, supply `-DatasetRoot` once; licensed
datasets themselves are never downloaded or copied.

`verify_worker.ps1` reruns package/model/device checks, runs a real one-item
Whisper Base ordinary-evaluator smoke, and executes the same complete
assignment preflight used at launch. CUDA verification requires nonzero VRAM
evidence and fails instead of falling back to CPU.

Run the actual component, small, and standard release gates before final
massive-campaign analysis:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_release_gates.ps1 -Device cuda -Through all
```

The gate command enforces the order. Small cannot run without a passed
credential-free component canary, and standard cannot run without the matching
passed small release qualification.

Control only the selected worker assignment:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action status -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action stop -MachineId machine_a -Device cuda -Reason "planned maintenance"
powershell -ExecutionPolicy Bypass -File scripts\worker_control.ps1 -Action resume -MachineId machine_a -Device cuda
```

The status wrapper validates the named assignment and reports only that
worker's completed and remaining scenarios, even though the local frozen
campaign also contains the other worker's globally assigned IDs.

Export and coordinate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\export_worker.ps1 -MachineId machine_a -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action merge -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\coordinator.ps1 -Action analyze -Device cuda -PrerequisiteEvidence "Software Validation from Datasets\Evaluation Tool\automated_runs\campaign_04_standard_release_cuda\analysis\report\release_qualification.json"
```

## Anaconda Prompt or Command Prompt

Anaconda is not required. From Anaconda Prompt or `cmd.exe`, stay in the
repository root and invoke the same PowerShell wrappers:

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
powershell -ExecutionPolicy Bypass -File scripts\setup_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\verify_worker.ps1 -MachineId machine_a -Device cpu
powershell -ExecutionPolicy Bypass -File scripts\launch_worker.ps1 -MachineId machine_a -Device cpu
```

Manual activation is optional. For direct diagnostics only, CPU Python is
`.venv\Scripts\python.exe` and CUDA Python is
`.stage8-envs\core-cuda\Scripts\python.exe`.

## Bounded operational rehearsal

The rehearsal uses the real executor and representative clean, noise, Dining
RIR, Restaurant RIR-plus-noise, native, and speaker-protocol selections:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_massive_rehearsal.ps1 -Action materialize -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\run_massive_rehearsal.ps1 -Action run -Device cuda
powershell -ExecutionPolicy Bypass -File scripts\run_massive_rehearsal.ps1 -Action finalize -Device cuda
```

The same wrapper accepts `status`, `stop`, and `resume`. Use
`-MaxScenarios 1` with `-Action run -Device cpu` for a bounded CPU executor
check.

## Troubleshooting

- Missing licensed data: rerun setup with the one authorized `-DatasetRoot`.
- CUDA requested but unavailable: fix the NVIDIA driver/CUDA PyTorch
  environment; no CPU fallback occurs.
- Existing nonempty local dataset path: move that local path aside only after
  inspecting it, then rerun setup; the script will not overwrite it.
- Transfer destination exists: preserve or move the old package and select a
  new destination; exports never overwrite silently.
- Deliberate stop: use `worker_control.ps1 -Action resume` for that same worker.

See the short copy/paste entry point at [`../START_HERE.md`](../START_HERE.md).
