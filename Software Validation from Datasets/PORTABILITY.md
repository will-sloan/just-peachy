# Evaluation Tool portability

## Purpose

The Evaluation Tool can be cloned or copied to any directory without changing
dataset, model, component, scenario, campaign, or environment-profile
identities.  Physical locations are resolved only when the tool opens local
files.  The committed logical paths such as `RawDatasets/...` and
`models/cache/...` remain unchanged.

Existing checkouts require no configuration.  Their defaults remain:

| Root | Default |
| --- | --- |
| repository | checkout containing `Software Validation from Datasets` |
| datasets | `<repository>/Software Validation from Datasets` |
| models | `<repository>/models` |
| ordinary Evaluation Tool runs | `<repository>/Software Validation from Datasets/Evaluation Tool/runs` |
| training workspace | `<repository>/training` (reserved; no training is activated) |

## Run the diagnostic

From Anaconda Prompt, Command Prompt, PowerShell, or a Linux shell, first use
the interpreter for the existing environment.  This command only reports
roots; it does not download data, load models, run inference, or train.

```powershell
Set-Location 'C:\work\just-peachy\Software Validation from Datasets\Evaluation Tool'
..\..\.venv\Scripts\python.exe -m app.utils.paths
```

On Linux/WSL:

```bash
cd '/work/just-peachy/Software Validation from Datasets/Evaluation Tool'
../../.venv/bin/python -m app.utils.paths
```

The JSON output is the input/output contract for this diagnostic: it reports
each root, the environment variable that can override it, the physical path,
whether it exists, and whether it came from the default or an override.

## Optional roots

Set a variable before running existing commands. Existing CLI options retain
precedence where they already exist: for example `--project-root` overrides
`JP_DATA_ROOT`, and `--runs-root` overrides `JP_RUN_ROOT`.

Windows PowerShell:

```powershell
$env:JP_DATA_ROOT = 'D:\SpeechData'
$env:JP_MODEL_ROOT = 'D:\JustPeachyModels'
$env:JP_RUN_ROOT = 'D:\JustPeachyRuns'
$env:JP_TRAINING_ROOT = 'D:\JustPeachyTraining'
# Optional only when the checkout itself is elsewhere:
$env:JP_REPO_ROOT = 'D:\research\just-peachy'
```

Linux/WSL:

```bash
export JP_DATA_ROOT=/mnt/data/speech
export JP_MODEL_ROOT=/mnt/data/just-peachy-models
export JP_RUN_ROOT=/mnt/data/just-peachy-runs
export JP_TRAINING_ROOT=/mnt/data/just-peachy-training
# Optional only when the checkout itself is elsewhere:
export JP_REPO_ROOT=/work/just-peachy
```

`JP_DATA_ROOT` must contain `Normalized Metadata` and a supported raw-data
directory such as `Raw Datasets (Not formatted)`. `JP_MODEL_ROOT` represents
the directory that replaces the committed `models` prefix: a configured
`models/cache/example` path therefore opens
`<JP_MODEL_ROOT>/cache/example`. Explicit roots must already exist; the tool
fails clearly rather than falling back to an old machine's data or cache.

`JP_RUN_ROOT` is used only by the ordinary `run` and `full` CLI commands when
they have no existing `--runs-root` value. Campaign roots continue to use their
declared locations and are not relocated by this phase. `JP_TRAINING_ROOT` is
diagnostic-only preparation for a future authorized training phase.

## Inputs and outputs

Inputs are the existing repository, optional root environment variables, and
the same metadata/model files that the Evaluation Tool already required. The
normal outputs are unchanged. The new path diagnostic writes no files.

Changing a physical root does **not** create a new scientific identity.
Changing file bytes, model configuration, dataset contents, or any
result-affecting configuration does create a different identity. Do not edit
frozen manifests, scenario catalogs, completed campaigns, or qualification
evidence to relocate a checkout.

## Bounded verification

From the Evaluation Tool directory, run the portability and existing focused
tests with the installed environment:

```powershell
..\..\.venv\Scripts\python.exe -m pytest tests\test_portable_roots.py tests\test_path_artifacts.py tests\inference_pipeline\test_asr_interface.py
```

The command uses tiny fixtures and performs no inference, downloads, or
training. Existing PowerShell launch scripts remain rooted through
`$PSScriptRoot`; invoke them from any working directory exactly as documented
in their existing runbooks.
