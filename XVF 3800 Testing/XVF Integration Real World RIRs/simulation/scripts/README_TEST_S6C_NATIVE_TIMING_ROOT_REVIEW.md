# Independent one-pair timing review

This script independently checks the exact completed C105/S45_08_07/O0 native/cache diagnosis. It checks source hashes, frozen scheduler membership, byte-identical vector archives, the 39 listed discrete choices, actual partial/decision log order, and the mature/ASR arrival crossing against the two-second revision horizon and 0.75-second evidence expiry. It does not run models or policy replay. It reads only the existing bounded pair and its small authorities.

Inputs are the pinned completed diagnosis and the exact bindings it names. The default output is a concise JSON review printed to the terminal. `--output` optionally creates an immutable receipt at a new path; an existing output is never overwritten. This review establishes the observed path for one outcome-selected pair, not population incidence or the operating-system cause of compute differences.

## PowerShell

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& (Join-Path $s6cRepo '.edge-speech-env\python.exe') (Join-Path $s6cSim 'scripts\test_s6c_native_timing_root_review.py')
```

## Anaconda Prompt or Windows CMD

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\test_s6c_native_timing_root_review.py"
```

No environment installation is required. For a saved receipt, append `--output` and a fresh absolute JSON path within the existing report's `independent_review` directory. Use a different filename for a later repeat review.
