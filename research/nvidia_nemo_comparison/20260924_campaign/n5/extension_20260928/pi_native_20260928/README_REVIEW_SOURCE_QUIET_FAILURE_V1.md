# Isolated physical startup failure accounting

Purpose: independently account for source-quiet-v1 stopping during AEC_MIC_ARRAY_TYPE readback, before route snapshot completion or any control setter. This reader accepts the failure/closure evidence only. It must not call the empty44-byte WAV a usable recording or credit the planned12s test,200ms pause, restoration or live B01 passage.

Inputs: immutable source-quiet-v1 admission, startup-failure/control-command receipts, child terminal and service envelope, zero-length audio/trace, empty WAV, exact owners. It verifies six read-only commands (VERSION/BLD_MSG/AEC_MIC_ARRAY_TYPE twice), zero setters, discarded priming/Stop frames, natural child exit1 with acknowledged failure, parent collector exit0, hardware capture closed, both leases free, unchanged original app/config/install and source hashes. Missing pre/post snapshots are explicit limitations; no restored volatile DSP state is claimed. The successful reader remains unexecuted and unqualified for this failed run.

Outputs: private REVIEW.json with failure-only status, all original target files copied to a hash-verified target backup, BACKUP.json. Remote readerCPU3/256MiB/110s and hostcoordinatorCPU14; no models, capture, playback or device-control commands. Combined target+backup remains under32MiB. Fixed review/backup roots reject overwrite; preserve any reader failure.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_source_quiet_failure_v1.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_source_quiet_failure_v1.py
```

No downloads/environment activation. A future justified device-recovery action needs its own fresh bounded admission and evidence. This result does not prove an evaluation timeout, scheduling cause or need for periodic reset.
