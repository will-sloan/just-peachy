# Independent preview dispatch review

Purpose: verify that b05-preview-guard-v1 rejected a simultaneous lock contender, launched its minimal systemd probe within the unchanged envelope, exited naturally, and released both exact owners and the lease. Inputs are source-bound admission, dispatch/probe owners and results and host launcher exit. Outputs are private AUDIT_INPUTS/REVIEW plus a target stage REVIEW. No GUI, inference, capture, playback or accuracy scoring runs in this reader.

`review_b05_preview_guard_v1.py` rehashes dependencies, compares owner PID/start/boot identities, checks no active research unit and reacquires/releases the lease without changing its contents. It verifies CPUs2/3,200%quota,hard768MiBaddress space and1MiBstack from the actual probe. It does not qualify new model behavior; that evidence comes from the earlier reviewed control run using unchanged app/controller code.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b05_preview_guard_v1.py
```

CMD or Anaconda Prompt, existing interpreter:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b05_preview_guard_v1.py
```

Run after the launcher closes. Files use exclusive creation and must never overwrite existing evidence. Combine this limited pass with the full-model control pass, real idle-loop/timer pass and reviewed source inheritance before enabling the bounded user launch. A future actual preview has its own new run and needs separate result/owner closure review.
