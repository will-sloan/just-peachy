# Stage 8 Extended Backend Qualification

## Purpose

This package prepares and independently qualifies optional speech backends without changing the Stage 0–7 core environment. It reads the existing inference component YAML, verifies pinned packages and local model assets, runs the real adapter twice, validates its output contract, and writes secret-free machine evidence. It does not add these backends to scientific screening; that is Stage 9.

## Inputs and outputs

Inputs are `configs/automated_evaluation/extended_backends.v1.yaml`, the Stage 8 environment and model-asset registries, existing component YAML, one local 16 kHz WAV, pinned packages, and verified local model assets. Credentials are accepted only through named environment variables; only presence booleans are recorded.

Outputs are written under:

```text
runs/extended_backend_qualification/
  <profile>.json
  core-cuda.json
  model_asset_inventory.json
  qualification_summary.json
  qualification_summary.json.sha256
```

Every backend has one explicit status. `qualified` and `qualified_with_warnings` require real repeated output; import or installation alone never qualifies a backend.

## Run from Anaconda Prompt or Command Prompt

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy
powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile extended-local -DownloadModels
.stage8-envs\extended-local\Scripts\python.exe "Software Validation from Datasets\Evaluation Tool\scripts\qualify_extended_backends.py" --profile extended-local

powershell -ExecutionPolicy Bypass -File scripts\install_stage8_profile.ps1 -Profile onnx -DownloadModels
.stage8-envs\onnx\Scripts\python.exe "Software Validation from Datasets\Evaluation Tool\scripts\qualify_extended_backends.py" --profile onnx

cd "Software Validation from Datasets\Evaluation Tool"
..\..\.venv\Scripts\python.exe scripts\consolidate_stage8_qualification.py
```

Use the corresponding `wenet`, `wespeaker`, or `credential-diarization` profile only after its prerequisites in `docs/automated_evaluation/extended_backend_setup.md` are satisfied.

## Run from PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy'
& scripts/install_stage8_profile.ps1 -Profile wespeaker -DownloadModels
& .stage8-envs/wespeaker/Scripts/python.exe `
  'Software Validation from Datasets/Evaluation Tool/scripts/qualify_extended_backends.py' `
  --profile wespeaker

Set-Location 'Software Validation from Datasets/Evaluation Tool'
& ../../.venv/Scripts/python.exe scripts/consolidate_stage8_qualification.py
```

The install script writes each environment to `.stage8-envs/<profile>` and its exact package freeze to `environment.freeze.txt`. It never upgrades `.venv`.

## Tests

```bat
cd /d C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool
..\..\.venv\Scripts\python.exe -m pytest tests\automated_evaluation\test_stage8_extended_backends.py -q --basetemp artifacts\pytest_stage8
..\..\.venv\Scripts\python.exe -m ruff check app\extended_backends scripts\qualify_extended_backends.py scripts\inventory_stage8_assets.py scripts\consolidate_stage8_qualification.py tests\automated_evaluation\test_stage8_extended_backends.py
```

Installed-backend qualification must be run with that backend's isolated interpreter. Missing packages, assets, licence approval, credentials, CUDA, or platform support produce explicit non-qualified results instead of a test failure or implicit download.
