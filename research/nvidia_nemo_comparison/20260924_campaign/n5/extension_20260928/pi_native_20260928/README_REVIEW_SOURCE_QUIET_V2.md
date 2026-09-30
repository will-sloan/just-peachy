# Independent isolated quiet-source review

Purpose: read the closed source-quiet-v2 receipts independently and verify actual capture counts/chronology, float-to-PCM conversion with scalar rounding, SHA lineage, terminal ACK, queue bounds, child/main/service limits, natural closure, full pre/post route equality and unchanged original app/config/install. This reader does not open audio hardware, play audio or run models. It accepts source-only evidence; no B01/controller repair or speech-quality claim.

Inputs: immutable admission, source/code hashes, actual quiet float master/WAV/TRACE, startup/Stop/Close/terminal receipts and unit/owner records. Output: private REVIEW.json and hash-verified full target backup plus BACKUP.json. All target files are copied without deletion or compression of preserved originals. Failure raises before acceptance; retain failed reader output and use a fresh reader if a correction is justified. Limits: remote read-onlyCPU3/256MiB/110s; hostcoordinatorCPU14, target-inclusive32MiB allowance remains. No new waveform processing or model inference is dispatched.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_source_quiet_v2.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_source_quiet_v2.py
```

No activation/download required. Run only after exact worker/child/dispatcher closure, never against an active capture. Fixed backup/review roots refuse overwrite. Hardware readiness is confined to this source-only duration and deliberate consumer pause; whole-app model load and sustained operation remain separate.

V2 additionally checks the reviewed single-recovery bindings. The restoration target is the readable post-restart route snapshot; unreadable pre-restart volatile DSP state is not restored. Child ru_maxrss is labelled a reported high-water value; sampled aggregate RSS remains distinct and does not prove a hard aggregate cap. Prior V1 failure and readers are retained.
