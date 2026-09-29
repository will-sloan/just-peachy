# Callback diagnostic dispatch V2

Purpose: correct only V1's host payload filename before native staging. V1 attempted to read nonexistent dispatch_check_callback_fault_v1.py and never staged/admitted/started a Pi job. Its source and PRE_STAGE_FAILURE_V1.json remain preserved. V2 explicitly binds its own filename and uses a fresh fixed callback-fault-v2 run; helper, real-callback cases and gate are unchanged.

Inputs/outputs, scope, no-capture policy and2MiB/CPU/memory limits are described in [V1 README](README_CALLBACK_FAULT_V1.md). Outputs use private callback-fault-v2[-evidence]. Eight actual-source callback cases use only synthetic arrays/fake status; no devices/models/audio files. This is unintegrated diagnostic preparation, not a callback-gap fix or real timing test.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_callback_fault_v2.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V34.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_callback_fault_v2.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; same commands without `&`, double-quoted interpreter path. No environment install. Census under15minutes; immutable fixed run and exclusive review. Preserve failures and use fresh versions rather than overwriting.
