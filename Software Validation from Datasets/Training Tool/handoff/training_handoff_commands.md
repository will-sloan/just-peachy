# Just-Peachy training receiver commands

## Purpose, inputs, and outputs

This runbook configures a Windows/WSL2 RTX 3090 receiver, verifies external
datasets and the exact Original Zipformer2 assets, reproduces the additive
successor freeze, qualifies the already-frozen adapter implementation, and then
runs the eight Original jobs. It does not put audio, checkpoints, environments,
logs, or Icefall in Git.

Inputs are this repository, the five portable roots, a WSL2 distribution, the
external dataset tree, and (for Common Voice) the operator's own Mozilla Data
Collective access. Outputs are machine-local successor manifests below
`JP_TRAINING_ROOT`, model assets below `JP_MODEL_ROOT`, and isolated run evidence
below `JP_RUN_ROOT`.

## 1. Clone and set roots (PowerShell or Anaconda Prompt with PowerShell)

```powershell
git clone <JUST_PEACHY_GIT_URL> D:\Work\just-peachy
Set-Location 'D:\Work\just-peachy'
$env:JP_REPO_ROOT = (Get-Location).Path
$env:JP_DATA_ROOT = 'D:\JustPeachyData'
$env:JP_TRAINING_ROOT = 'D:\JustPeachyTraining'
$env:JP_MODEL_ROOT = 'D:\JustPeachyModels'
$env:JP_RUN_ROOT = 'D:\JustPeachyRuns'
$env:JP_WSL_DISTRO = 'Ubuntu-24.04'

powershell -ExecutionPolicy Bypass -File `
  'Software Validation from Datasets\Training Tool\scripts\bootstrap_training_machine.ps1' `
  -Action Diagnose -WslDistro $env:JP_WSL_DISTRO

powershell -ExecutionPolicy Bypass -File `
  'Software Validation from Datasets\Training Tool\scripts\bootstrap_training_machine.ps1' `
  -Action Configure -Apply -WslDistro $env:JP_WSL_DISTRO
```

In classic Anaconda Prompt (`cmd.exe`), set the same inputs with `set` and then
call PowerShell:

```bat
cd /d D:\Work\just-peachy
set JP_REPO_ROOT=D:\Work\just-peachy
set JP_DATA_ROOT=D:\JustPeachyData
set JP_TRAINING_ROOT=D:\JustPeachyTraining
set JP_MODEL_ROOT=D:\JustPeachyModels
set JP_RUN_ROOT=D:\JustPeachyRuns
set JP_WSL_DISTRO=Ubuntu-24.04
powershell -ExecutionPolicy Bypass -File "Software Validation from Datasets\Training Tool\scripts\bootstrap_training_machine.ps1" -Action Diagnose -WslDistro "%JP_WSL_DISTRO%"
```

Before running the Python data commands in the next section, run
`BootstrapEnvironment -Apply` from section 3 once. It creates both the small
Windows control environment and the pinned WSL CUDA environment.

## 2. Place or acquire external datasets

The shared external layout is:

```text
JP_DATA_ROOT/
  Raw Datasets (Not formatted)/
    Common Voice.gz                         # accepted legacy archive name
    Common Voice/
      cv-corpus-26.0-2026-06-12/prepared/en/
    AMI Meeting Corpus/
    CHiME 6/
    CMU Arctic/
    VOiCES/
    LibreSpeech/                            # historical spelling is frozen
    Hi Fi TTS/
    MIT 271 RIRs/Audio/
```

Common Voice must be obtained by the receiver from Mozilla Data Collective;
the shared-folder convention does not grant redistribution rights. Place the
exact 94,639,372,950-byte archive as `Common Voice.gz`. Once all external
datasets are present, preview and run the single deterministic data-build
action:

```powershell
Set-Location "$env:JP_REPO_ROOT\Software Validation from Datasets\Training Tool"
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action MaterializeData
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action MaterializeData -Apply
```

The applied action deterministically rebuilds Phase 2 and its AMI licence-
correction successor, verifies the archive, selectively extracts only eligible
older-speaker clips, consolidates them into the preferred shared tree, and
rebuilds/verifies Phase 3, Phase 4, and the additive successor. It does not
full-extract the 95 GB archive. For an already-built machine, the consolidation
helper can be run independently while keeping the frozen legacy path usable:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\consolidate_common_voice_assets.ps1 -Action Plan
powershell -ExecutionPolicy Bypass -File scripts\consolidate_common_voice_assets.ps1 -Action Apply
```

## 3. Bootstrap and verify the pinned toolchain/model

The environment action is dry-run unless `-Apply` is supplied:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action BootstrapEnvironment
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action BootstrapEnvironment -Apply
..\..\.venv\Scripts\python.exe -m training_data.handoff acquire-models
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action VerifyModels
```

The model downloader pins Hugging Face revision
`37cb5606808f3d5e55a3fc73554bdf757d82465a` and stops on any SHA-256 mismatch.

## 4. Reproduce the plan, qualify the receiver, and estimate

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_adapter_research.ps1 -Action Plan -WslDistro $env:JP_WSL_DISTRO
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action Qualify
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_training_machine.ps1 -Action Qualify -Apply
powershell -ExecutionPolicy Bypass -File scripts\run_adapter_research.ps1 -Action Validate -WslDistro $env:JP_WSL_DISTRO
powershell -ExecutionPolicy Bypass -File scripts\run_adapter_research.ps1 -Action Estimate -WslDistro $env:JP_WSL_DISTRO
```

`Qualify -Apply` runs only the two bounded 250-step canaries. It does not run a
full adapter job.

## 5. Run the eight adapters later (not during handoff preparation)

Serial is the default and remains the safe receiver starting point:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_adapter_research.ps1 -Action Run
```

One exact job:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_adapter_research.ps1 -Action RunOne -ExperimentId O-VOICES
```

Optional parallel support remains blocked at two processes until measured RTX
3090 results pass the 25% gate:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_parallel_adapter_research.ps1 -Action BenchmarkProtocol
powershell -ExecutionPolicy Bypass -File scripts\run_parallel_adapter_research.ps1 -Action RecordBenchmark -MetricsPath D:\benchmarks\rtx3090.json
powershell -ExecutionPolicy Bypass -File scripts\run_parallel_adapter_research.ps1 -Action Run -ExperimentId O-AMI,O-VOICES -MaxParallelAdapterJobs 2
powershell -ExecutionPolicy Bypass -File scripts\run_parallel_adapter_research.ps1 -Action Run -ExperimentId O-AMI,O-VOICES -MaxParallelAdapterJobs 2 -Apply
```

Each job is a separate process with an isolated status path and run/checkpoint
directory. Never run GPU Large evaluation concurrently with adapter training on
the same RTX 3090. Training has priority; immutable completed checkpoints may be
exported only when export does not materially contend for the GPU.

## 6. Create a small completed-model transfer inventory

```powershell
Set-Location "$env:JP_REPO_ROOT\Software Validation from Datasets\Training Tool"
..\..\.venv\Scripts\python.exe -m training_data.handoff package-model --experiment-id O-AGE
```

This writes a small provenance manifest with checkpoint ID, SHA-256, size,
bundle, recipe, lineage, and export readiness. It does not copy the checkpoint
into Git; transport remains operator-selected.
