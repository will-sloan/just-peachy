# Independent source bridge reader

Purpose: independently verify nine native real-source callback/read/stop cases connected through IPC, without importing the source, bridge, transport, NumPy, PortAudio or models.

Inputs: immutable admission/prototype/WAV, original97coefficients parsed from AST, per-case constructed raw frame counts, private AUDIO.f32 and LiveBlock traces, cached Stop/final Close/cleanup receipts, exact main/gate/child identities and live unit envelope. Recompute direct FIR with standard-library math.fsum, float32 rounding and explicit O0/O1 selection/gain at the predeclared1e-7 amplitude gate. IPC hashes, offsets, native/model counters, ADC fixtures, clock order and terminal bytes must be exact. No downstream D1 gate changes. Verify zero pending accepted raw tail, preserved pre-drain status, private lock released and route-before-stream-close ordering; restoration mismatch and callback faults remain explicit negative cases.

Outputs: private immutable REVIEW.json plus target copy, per-case numerical/structural observations, process peaks and closure. Target reader usesCPU3,128MiB virtual,45s bound. No capture or hardware read/write. Fake source startup/restoration does not qualify actual microphone start/readback, combined B01 memory/performance, GUI or field release.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_live_source_bridge_v1.py
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_live_source_bridge_v1.py
```
Run after all owned source processes close. Preserve any assertion failure; no changed thresholds or overwriting receipts. Raw audio/metadata/receipts remain private and are backed up with hashes. See README_LIVE_SOURCE_BRIDGE_V1.md for admitted execution and limitations.
