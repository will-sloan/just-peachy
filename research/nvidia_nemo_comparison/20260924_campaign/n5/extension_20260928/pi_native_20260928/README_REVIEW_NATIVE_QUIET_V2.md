# Real quiet-route / one-shot restart reader v2

Purpose: independently review existing native user quiet-run or xvf-restart-v1/v2 receipts; no device audio/control/model work is started. Inputs are a run ID, exact admitted files, result/owner/service/route receipts and fresh closed process/capture state. Outputs are exclusive private REVIEW.json and bound receipt copies, mirrored to the target. It probes only the existing hardware lease for availability, then releases it.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_native_quiet_v2.py --run-id <existing-run-id>
```

CMD / Anaconda Prompt (existing Python, no installation or activation):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_native_quiet_v2.py --run-id <existing-run-id>
```

Allowed IDs are live-ready-user-UTC or xvf-restart-v1/v2. Run once per closed receipt; preserve all failed reader attempts. A failed actual startup must have zero accepted samples, no device setters, closed stream/lease and no cleanup error. A passing quiet source must have192000model samples/576000native frames,1200blocks,48k actual stream,1ms FIR delay, correct I2C O0/+3dB route, no dropped samples and restored changed controls. Restart review checks exactly one TEST_CORE_BURN0, matching VERSION/build, closed capture and original app/config/install; it does not establish restored DSP processing. Every outcome remains separate from B01 live model passage, speech quality, acoustic timestamp calibration, long-run resources and release acceptance. No recorded audio is collected by this reader.

V2 correction: V1 correctly rejected the reset attempt because no TEST_CORE_BURN command reached the tool. The live adapter allowlist blocked it; the application raw success/reset flag is not credited. V2 explicitly preserves that rejection with zero sent reset commands. For approved maintenance V2 it instead binds MAINTENANCE_COMMAND.json, exact fixed argv/zero argument, single intent, return status and firmware identity. A nonzero/timeout remains uncertain and is never retried. User quiet-source success/failure gates are unchanged. Preserve REVIEW_READER_ATTEMPT_V1.json.
