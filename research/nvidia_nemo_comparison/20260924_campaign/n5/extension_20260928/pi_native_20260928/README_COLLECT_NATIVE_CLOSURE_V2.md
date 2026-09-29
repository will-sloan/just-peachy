# Closure census under the updated allowance

Purpose: retain V1's exact identity, unit, original app/config/install, leases, capture, disk and output census checks, while reading the explicitly authorized cap from WINDOW_V2.json. It does not authorize a job or mutate any ledger. Inputs: current host supervisor, private native tree and target read-only state. Outputs: fresh private NATIVE_CLOSURE_V<number>.json and NATIVE_RESOURCES_V<number>.json; existing versions cannot be overwritten. Run only after owned work closes.

PowerShell from the worktree:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/collect_native_closure_v2.py --version 33
```
CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; same command without `&`, double-quoted interpreter. Select a fresh unused receipt version for later runs. No models, microphone, audio playback, download, visible UI or original settings changes.
