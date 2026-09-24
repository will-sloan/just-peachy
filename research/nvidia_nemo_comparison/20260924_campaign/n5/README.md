# N5 packaging tools

Purpose: prepare verified offline baseline and native ARM64 artifacts while
upstream comparisons run. N5 is PARTIAL, not release acceptance or campaign
closure. START_HERE.md is the operating index. README_ARM64.md covers the build,
static ELF audit and no-model QEMU loader probes.

`package_baseline.py` takes the existing N1 release receipt/archive, the original
hash-addressed model root, pinned ARM64 wheelhouse and publisher receipt. It
creates a fresh private ZIP plus a SHA-256/member receipt. It verifies all eight
models and 13 wheels before packaging and reads back every member. No original
file or personal store changes. The bundle is local-only because it contains
model weights. `verify_bundle.py` checks extracted member paths, sizes and hashes
before installation. `install-offline.sh` invokes the existing non-root ARM64
installer, using external data, versioned code/runtime and shared hashed models.

PowerShell from this campaign worktree:

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py research/nvidia_nemo_comparison/20260924_campaign/n5/package_baseline.py --models C:/Users/amiri/JustPeachy/shared/models --wheelhouse 'G:/Just_Peachy_PROTO1/arm64 cp311 wheels' --wheel-receipt research/nvidia_nemo_comparison/20260924_campaign/n5/ARM64_WHEEL_PUBLISHER.json --output G:/Just_Peachy_N1/20260924_campaign/local/n5/releases/just-peachy-baseline-cm5-offline-v2.zip
& $py -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_n5.py -v
& $py prototype/release_tools/run_checks.py --output G:/Just_Peachy_N1/20260924_campaign/local/n5/release-tests-v3 --wsl
```

CMD/Anaconda Prompt, without activation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%JP_PY%" research\nvidia_nemo_comparison\20260924_campaign\n5\package_baseline.py --models C:/Users/amiri/JustPeachy/shared/models --wheelhouse "G:/Just_Peachy_PROTO1/arm64 cp311 wheels" --wheel-receipt research/nvidia_nemo_comparison/20260924_campaign/n5/ARM64_WHEEL_PUBLISHER.json --output G:/Just_Peachy_N1/20260924_campaign/local/n5/releases/just-peachy-baseline-cm5-offline-v2.zip
"%JP_PY%" -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n5 -p test_n5.py -v
"%JP_PY%" prototype\release_tools\run_checks.py --output G:/Just_Peachy_N1/20260924_campaign/local/n5/release-tests-v3 --wsl
```

Actual baseline bundle is v1. Use a new filename for a repeat; do not overwrite
versioned evidence. The package verifier can be run as `PYTHON verify_bundle.py
--root EXTRACTED_BUNDLE`. The tests use temporary artificial byte fixtures,
including corruption, path traversal, duplicate paths and incompatible ELF;
they contain no audio. Install commands are in INSTALL_CM5.md.

`Start-N5-BASELINE.cmd` is a thin shortcut to ../Start-N1.ps1. From PowerShell,
run `& .\research\nvidia_nemo_comparison\20260924_campaign\n5\Start-N5-BASELINE.cmd`;
from CMD use the same path without `&`. It uses the earlier immutable installed
baseline and isolated manual-baseline data. Optional arguments are the existing
Start-N1.ps1 parameters. The output is an idle GUI and external user-selected
session data; do not run inference concurrently with admitted campaign jobs.

`package_checkpoint.py` creates the small analysis-first handoff from explicitly
listed small reports/scripts and writes ARTIFACT_INDEX/HANDOFF_RECEIPT. Inputs
are the prepared release receipts and live read-only upstream status; outputs
are N5_STATUS.json, dated coverage snapshot and a fresh ZIP. It never changes
the shared campaign ledger, schedules, source bindings or worker ownership.
Run from either shell with the same explicit Python above:
`PYTHON research/nvidia_nemo_comparison/20260924_campaign/n5/package_checkpoint.py
--output G:/Just_Peachy_N1/20260924_campaign/local/n5/handoffs/NVIDIA_CAMPAIGN_CHATGPT_HANDOFF_20260924_campaign.zip`.
Use a new output name if that archive exists. This filename is a checkpoint,
not a claim that the final campaign handoff or full N5 acceptance is complete.
