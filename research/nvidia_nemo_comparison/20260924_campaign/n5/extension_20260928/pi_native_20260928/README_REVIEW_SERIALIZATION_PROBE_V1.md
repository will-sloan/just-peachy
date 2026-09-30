# Review retained-packet scheduling diagnostic V1

Purpose: independently recompute timing-gap/cgroup deltas and exact event roundtrip for serialization-probe-v1. Inputs are immutable source/admission/owner/envelope receipts, original compact D1 journal, both variant outputs and raw bounded timestamp arrays. Outputs are private host/target REVIEW.json with diagnostic-only status, exact bindings and no live-cause/repair qualification. Verify peer, worker and dispatch owners closed, baseline/capture unchanged, finite bounded source path and output quotas. No capture, model inference, playback or changes to the bound application.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_serialization_probe_v1.py
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_serialization_probe_v1.py
```
Run after closure only; refuses existing review. Host coordinatorCPU14, target readerCPU3. Raw timestamps are scheduling intervals observed by probes, not direct GIL ownership measurements. No zero-throttling inference is transferable to the earlier live run. See README_SERIALIZATION_PROBE_V1.md for admitted protocol and bounds.
