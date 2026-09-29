# D1 single-entry executable graph cache candidate

Purpose: investigate repeated-session virtual-address pressure by lowering D1 executable graph cache capacity from eight to one. This changes compute-graph retention only. Speaker/FIFO history, model weights, delayed geometry, eviction logic, metadata 2 MiB assertions, scheduler 2048 and its 95% guard remain unchanged. A2 ASR is not qualified for these D1-specific bounds. Compilation does not establish numerical or performance acceptance.

Inputs: already staged immutable scheduler source/object bundle, qualified LRU8 sortformer source, metadata2 runtime archive and retained native libraries. No downloads. Outputs: a fresh private target d1-lru1-build-v1 source/object/library, admission/owner/build logs and result; matching private host preflight/launcher receipts. The original app and earlier builds remain untouched. Native build uses CPUs2/3, 200% total CPU, 64 tasks, 600 seconds and hard 768 MiB virtual space, with 850 MiB available RAM and 5 GiB disk floors. New output reservation is 16 MiB; combined output cap remains 1 GiB.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_d1_lru1_build_v1.py --run-id d1-lru1-build-v1 --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V15.json
```
CMD or Anaconda Prompt: use `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, then the same explicit interpreter and arguments above, replacing PowerShell's `& 'interpreter'` with `"interpreter"`. No activation or package installation is needed.

Do not run the target build script directly outside admission. Independently verify owner closure, bound inputs, exact one-line cache change, retained runtime/objects and successful ELF link before inference. Next require full-source/repeat/reset/EOF same-geometry reference equality at unchanged 1e-5 and measure actual costs; graph rebuilding may increase latency. Keep the existing failed Stop/restart attempts and all thresholds.
