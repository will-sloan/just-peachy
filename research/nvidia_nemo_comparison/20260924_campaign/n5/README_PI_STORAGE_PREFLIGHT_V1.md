# Read-only Pi bundle and storage preflight

Purpose: make the later reconnect workflow check storage before installing the
preserved baseline bundle. `pi_storage_preflight_v1.py` runs on Windows for an
offline inventory, and later locally on Linux ARM64 for prerequisite metadata
and actual free-space observations. It does not connect to the Pi, install,
extract, activate, launch a GUI, enumerate audio devices or load a model.
Only the explicitly named JSON report is written; its parent must already exist.
The original bundle and installer remain unchanged.

Inputs: an existing baseline bundle, its separately trusted SHA256, an explicit
runtime/filesystem overhead budget, and a fresh output filename. Optional inputs
are an available-space scenario, reserve (at least 1 GiB), and extra rollback-copy
budget. For a later actual target observation use both explicit absolute install
and external data roots instead of a supplied available-space value. The roots
must be separate. No nominal 32-GB capacity is treated as actual free storage.

The tool checks the complete outer ZIP hash, every declared member hash/size,
exact inventory and safe canonical paths, then reads nested application/wheel
ZIP metadata without extraction. It checks the application's asset inventory
against the bundled models and counts a repeated identical model once. Different
physical filenames for the same digest are refused because the current installer
does not establish alias deduplication. ZIP symlinks, duplicate/case-colliding
paths, unlisted payloads, unsupported schemas and corrupt inputs fail closed.
Limits are 8 GiB per archive/expanded inventory, 50,000 ZIP entries, 1,000 outer
manifest rows, 1 MiB JSON metadata and five minutes. Hashing streams in 1-MiB
chunks. No runtime or model code in an archive is executed.

Outputs separate exact known logical payload sizes from estimates. The space
budget includes the transferred archive, extracted bundle, a new installed
application/model/wheel payload, the installer's extra source staging margin,
an explicit runtime/filesystem overhead budget, optional extra rollback copy
and reserve. Existing files receive no space credit. A prior installed release
remains in place; no rollback or personal files are deleted. This deliberately
overestimates additional need if the target already holds the archive/assets.
Wheel metadata sizes do not measure pip metadata, bytecode, filesystem blocks,
OS packages or actual runtime RAM. Those unknowns are not silently called exact.

`ESTIMATED_FIT` is a storage estimate only. Package status remains the original
preparation status; a space result does not qualify the package or authorize its
installation. Missing prerequisite packages, imports, native model/WAV operation,
GUI checks, rollback and real CM5 resources still require their separate checks.
This version supports the preserved baseline schema only. Accepted optional
backends need a later matching bundle/installer inventory; their space or device
availability is not inferred from this baseline result.

## Windows PowerShell

Use the existing interpreter; it pins only its own process to CPU14/BelowNormal,
one math thread and GPU off. No shell/window is launched. The example's 512-MiB
overhead is an explicitly unmeasured budget, not a runtime measurement. Choose a
fresh report name on repeat. The campaign's C50/G75-GiB floors apply to report writes.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPython -B research/nvidia_nemo_comparison/20260924_campaign/n5/pi_storage_preflight_v1.py --bundle G:/Just_Peachy_N1/20260924_campaign/local/n5/releases/just-peachy-baseline-cm5-offline-v1.zip --sha256 913e0a082e2de5f28e62f30503097cfb12f9008ed6d26fd1a803a7a2e8d32bbf --runtime-overhead-bytes 536870912 --output G:/Just_Peachy_N1/20260924_campaign/local/n5/baseline-storage-preflight-v1.json
& $jpPython -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_pi_storage_preflight_v1.py -v
```

## CMD and Anaconda Prompt

No environment activation or package installation is needed:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/pi_storage_preflight_v1.py --bundle G:/Just_Peachy_N1/20260924_campaign/local/n5/releases/just-peachy-baseline-cm5-offline-v1.zip --sha256 913e0a082e2de5f28e62f30503097cfb12f9008ed6d26fd1a803a7a2e8d32bbf --runtime-overhead-bytes 536870912 --output G:/Just_Peachy_N1/20260924_campaign/local/n5/baseline-storage-preflight-v1.json
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_pi_storage_preflight_v1.py -v
```

The 11 tests use tiny artificial ZIPs and no audio. They cover corruption,
inventory/path/alias errors, time/size/budget refusal, exact space boundaries
and confirmation that preflight does not create install/data roots. They are
software tests, not evidence that the package runs on ARM64.
The first development attempt exposed Windows ZIP filename normalization. Its
source and failed log are retained privately. The corrected fixture preserves
literal malformed header bytes, and the reader validates `orig_filename` before
the normalized filename; the passing rerun is recorded separately.

## Later, after the Pi is reconnected

This companion script is outside the immutable baseline ZIP. Transfer its
Git-verified version and the archive by the user's chosen USB or authenticated
wired route; verify the archive hash against ARTIFACT_INDEX.json. Do not use a
historical IP address as identity. Run locally on the Pi as the ordinary user,
substituting the actual USB path and a fresh report path:

```bash
python3.11 /ACTUAL_USB_PATH/pi_storage_preflight_v1.py \
  --bundle /ACTUAL_USB_PATH/just-peachy-baseline-cm5-offline-v1.zip \
  --sha256 913e0a082e2de5f28e62f30503097cfb12f9008ed6d26fd1a803a7a2e8d32bbf \
  --runtime-overhead-bytes 536870912 \
  --target-install-root "$HOME/.local/share/just-peachy" \
  --target-data-root "$HOME/.local/share/just-peachy-data" \
  --output "$HOME/just-peachy-preflight-v1.json"
```

The target check observes Linux ARM64, Python 3.11, glibc >=2.36, module metadata,
OS library locations, ordinary-user status, root access flags, filesystem identity
and free bytes. It does not test dynamic imports, render Tk, open audio or prove
write permission by writing a trial file. A failed prerequisite or insufficient
space must be resolved before following INSTALL_CM5.md. Keep the shared frontend,
baseline and external personal data; never silently fall back to another backend.
The campaign performs no target connection or live CM5 validation.
