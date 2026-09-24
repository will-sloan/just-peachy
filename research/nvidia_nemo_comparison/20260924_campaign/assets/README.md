# N1 official assets and environment audit

This folder pins official NVIDIA model revisions, snapshots their model cards and terms, and stages only explicitly selected model files. It never loads a neural model, requests credentials, opens microphones, runs remote model Python code, or changes the working application environment.

`stage_assets.py` uses Python 3.11 standard-library HTTPS. Inputs are the six fixed official Hugging Face repository IDs, a model ID, an exact file name, and an optional campaign cache path. Outputs are `official_metadata.json`, `download_receipts.json`, metadata snapshots, and a cache keyed by the official LFS SHA-256. Existing metadata pins are retained unless `metadata --refresh` is explicitly requested; never refresh a frozen campaign. Re-running a download verifies existing bytes. Downloads preserve 75 GiB free on G: and 50 GiB on C:, enforce a 50 GiB cache cap, and limit transfer speed to 40 MiB/s. No dataset, noise, or denoiser files are selected.

## PowerShell

```powershell
$audit = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\assets'
$python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $python "$audit\stage_assets.py" metadata
& $python "$audit\stage_assets.py" download --model D1 --filename Nemotron-3-Diarization.q8_0.gguf
& $python "$audit\stage_assets.py" inspect
```

## Command Prompt or Anaconda Prompt

No conda activation or package installation is needed; call the existing absolute interpreter directly:

```bat
set "AUDIT=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\assets"
set "PYTHON_EXE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PYTHON_EXE%" "%AUDIT%\stage_assets.py" metadata
"%PYTHON_EXE%" "%AUDIT%\stage_assets.py" download --model D1 --filename Nemotron-3-Diarization.q8_0.gguf
"%PYTHON_EXE%" "%AUDIT%\stage_assets.py" inspect
```

Use `--model E1`, `A1`, `A2`, `A3`, or `X1` and a filename from `official_metadata.json` for another explicitly needed artifact. Read `MODEL_ACCESS_MATRIX.md` and `runtime_receipt.json` before attempting inference: downloaded weights do not establish portable runtime support, model quality, or a 2 GB memory claim. `.nemo` archives are staged as data and are not deserialized during this audit.

The optional `inspect` command reads only tar member listings, small text configuration files and GGUF metadata. It writes `asset_structure_receipt.json` and small configuration snapshots under the external cache. It never unpickles weights or evaluates model code. Readable aggregate status is in `MODEL_ACCESS_MATRIX.md`; the compact next-stage candidate interface is `model_manifest.json`. Hardware/tool availability and free-space receipts are in `environment_receipt.json`. Only run one staging/build command at a time; these scripts are not concurrent download managers.

Asset payloads and full official metadata snapshots remain outside Git in `G:\Just_Peachy_N1\20260924_campaign\local\assets`. Only scripts, small evidence receipts, and audit reports belong in the campaign commit. No personal profiles or audio are inputs to this task.

## Rebuild the isolated CPU runtime

`build_runtime.py` consumes the three pinned source archives listed in its `ARCHIVES` table and their extracted folders under the external cache's `source` folder. The exact download URLs, archive SHA-256 values and revisions are in `runtime_receipt.json`. Download those URLs to the receipt's archive paths, check their SHA-256 values, then use PowerShell `Expand-Archive -LiteralPath <archive> -DestinationPath <cache>\source`. This is source staging only; the script verifies archive hashes again before compiling.

The existing Visual Studio 2022 C++ toolchain and its bundled CMake 3.30.5 are used. The separate CMake 3.21 on PATH is too old. No packages, Windows features, drivers, PATH variables, or global environments are installed or changed. Build commands run with one job at below-normal priority and write all outputs to the external campaign cache. Microphone capture, CUDA, HTTP, gRPC, TTS, NMT, Flashlight, ITN and additional model downloads are disabled. Only CLI version/help is executed; no model inference is part of this N1 build check.

PowerShell, after setting `$python` and `$audit` as above:

```powershell
& $python "$audit\build_runtime.py"
```

CMD or Anaconda Prompt, after the `set` commands above:

```bat
"%PYTHON_EXE%" "%AUDIT%\build_runtime.py"
```

Outputs: `runtime_receipt.json`, timestamped command details and hashed logs under `local\assets\build_logs`, source build outputs under `local\assets\build`, and an isolated `local\assets\runtime_install` prefix with the executable, DLLs, public C API, documentation and license notices. This is a Windows x64 build. ARM64 execution, CM5 memory, model parity, inference quality and streaming timing remain next-stage checks.
