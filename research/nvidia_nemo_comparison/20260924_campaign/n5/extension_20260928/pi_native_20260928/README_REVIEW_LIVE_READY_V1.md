# Independent quiet-route mock reader v1

Purpose: review the closed live-ready-mock-v1 admission, source hashes, natural service exit, exact owner identities and fake I2S source/restoration receipts without rerunning the source or opening a device. Inputs are existing private target and host receipts. Outputs are exclusive private REVIEW.json and copied bound receipts on the host, plus the same review on target. It does not qualify actual hardware, live speech, model performance or accuracy.

PowerShell, from the campaign worktree:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_live_ready_v1.py
```

CMD or Anaconda Prompt (existing interpreter, no installation/activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_live_ready_v1.py
```

Run once after successful natural mock closure. Never overwrite a prior review. The reader independently validates counts, route/channel/gain, reverse restoration values, zero accepted samples on rejected startup, no real capture and unchanged original app/config/install. Consent and failed-close retry assertions are source-bound mock contract results, not physical-device observations. User-run reviews require separate actual clock/ring/route/restoration evidence; this reader intentionally rejects user runs.
