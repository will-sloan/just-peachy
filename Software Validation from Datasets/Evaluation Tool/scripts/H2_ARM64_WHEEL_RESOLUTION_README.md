# H2 Linux ARM64 wheel-resolution receipt

## Purpose

`resolve_h2_arm64_wheels.py` proves that the pinned lean H2 runtime can be
resolved to an exact binary-only CPython 3.12 Linux ARM64 wheel set. It records
filenames, sizes, SHA-256 hashes, target tags, the requirements hash, protocol
identity, and frozen runtime identity.

This is portability preparation, not Raspberry Pi validation. It does not
install packages, download models, run ARM64 code, claim numerical parity, or
change scientific settings.

## Inputs and outputs

Inputs:

- the active v17 H2 workspace on C:;
- `deployment/h2_arm64/requirements-linux-arm64.txt`;
- `protocol_manifest.json` and `runtime_implementation_identity.json`;
- the official `https://pypi.org/simple` package index.

Output:

`<workspace>\storage_maintenance\arm64_wheel_resolution_receipt.json`

Wheel files are downloaded only into a temporary directory under the selected
workspace on C:. The temporary wheelhouse is deleted before the signed receipt
is published. No wheel payload is kept in the final research package.

## PowerShell

```powershell
cd "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
$Workspace = "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
$Python = "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe"
$Output = Join-Path $Workspace "storage_maintenance\arm64_wheel_resolution_receipt.json"

& $Python -B .\scripts\resolve_h2_arm64_wheels.py `
  --workspace $Workspace `
  --output $Output `
  --python $Python

& $Python -B .\scripts\resolve_h2_arm64_wheels.py `
  --workspace $Workspace `
  --validate $Output
```

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
set "H2_WORKSPACE=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\automated_runs\h2_complete_product_pipeline_v17"
set "H2_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe"
"%H2_PYTHON%" -B scripts\resolve_h2_arm64_wheels.py --workspace "%H2_WORKSPACE%" --python "%H2_PYTHON%"
```

## Verification

Run the focused tests without touching campaign data:

```powershell
& "C:\Users\amiri\Documents\GitHub\just-peachy\.venv\Scripts\python.exe" `
  -m pytest -q .\tests\test_h2_arm64_wheel_resolver.py
```

A valid receipt has status `PASS_RESOLVED_EXACT_ARM64_BINARY_SET`. ARM64 import,
dynamic-link, audio-device, numerical-parity, sustained-streaming, and hardware
resource validation remain explicitly `NOT_RUN_REQUIRES_ARM64_LINUX`.
