# Native Pi frontend checks

Purpose: execute the same portable NumPy frontend on CM5 against nine preserved pinned-NeMo cases. No model, capture, playback or new graph copy. Inputs: reviewed host d1-onnx-frontend-v1 NPZs (saved original full source and edge/zero/impulse arrays), checkpoint-derived frontend coefficients and unchanged candidate helper. Outputs: private first/fixed, irregular and repeat feature arrays, source/length checks, timings, live systemd envelope, source hashes, exact owners and closure receipts in d1-frontend-native-v1. Native independent review is separate.

Uses fresh target-inclusive32MiB output admission under WINDOW_V3 and original50GiB payload/reservations. Default hard768MiB virtual, initial850MiB available, sampled stop below192MiB available/above640MiB RSS, CPUs2/3,total200%,one native thread,1MiB stack,Tasks64,GPUoff,300s service/290s worker alarm/10s stop,4MiB per output file and bounded4MiB service log. Preserved input files can exceed4MiB and are staged before the worker. No OS/app/config changes. Research lease/exact boot/PIDs/baseline hashes/capture-closed checks apply. Boundaries and validity use the predeclared1e-4 log-feature gate; D1 output tolerance remains1e-5. Valid full-source features are4469; the NeMo batch includes masked padding. This does not qualify the complete D1 state/model/EOF driver.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_frontend_native_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V45.json'
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_frontend_native_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V45.json
```
Use a fresh V3 census under15minutes old. Fixed output path refuses reuse. Internal --gate/--worker are registered target entry points, not user commands. Do not repeat a completed unchanged case. Numerical passage is not real-world accuracy, speedup, GUI or release acceptance.
