# Failed restart review

Purpose: inspect the preserved B05 Stop/restart V2 failure. Verify immutable hashes, exact owner closure, exit 1, early Stop's sample passage and queue/handle/archive drainage, then explicitly retain the failed restart and its allocation error. This does not clear any inference or full-file gate. Inputs are the closed native V2 run and private launcher receipt. Outputs are private FAILURE_AUDIT_INPUTS and REVIEW plus a permitted target stage REVIEW. No inference, capture, playback or accuracy scoring occurs.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b05_restart_failure_v1.py
```
CMD or Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b05_restart_failure_v1.py
```

Outputs are exclusive and cannot replace historical evidence. A clean failed-session teardown is not a working restart. V1's independent failure receipt is preserved separately; V2 removes the harness strong reference but still fails.
