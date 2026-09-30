# Independent isolated-source transport reader

Purpose: verify the13 native saved-fixture IPC cases without importing the transport, fixture, application or models. This is component evidence only, never live capture or release acceptance.

Inputs: source-bound admission, original WAV, per-block trace/config/CASE_RESULT, child terminals and exact process owners, actual service envelope, dispatch and final results. Reconstruct float bytes independently with standard-library struct, compare every block hash/sample/native-frame/epoch interval, terminal prefix hash, expected fault and source closure. Check bounded credits, actual child128MiB/main768MiB virtual limits,CPU2/3,total200%,1MiB stacks,Tasks64,300s/10s service, aggregate target bytes and baseline/capture/leases. Abrupt child exit7 is an expected negative case with no fabricated terminal. A real source's raw-ring drain, route restoration, live microphone timing and combined model resource fit remain untested.

Outputs: private immutable REVIEW.json and target copy; exact per-case observations and main/maximum-child RSS. Sum of individual peaks is not a measured simultaneous peak. Reader uses targetCPU3/128MiB/45s bound and no model/capture. Any assertion failure remains a failure; preserve it and use a new version if needed.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_isolated_source_v1.py
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_isolated_source_v1.py
```
Run only after exact main/gate/child closure. Retain raw evidence privately and verify its backup. See README_ISOLATED_SOURCE_V1.md for protocol bounds and execution.
