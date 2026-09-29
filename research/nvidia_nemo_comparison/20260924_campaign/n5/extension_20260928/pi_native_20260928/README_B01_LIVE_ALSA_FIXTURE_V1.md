# B01 saved live-controller fixture with actual ALSA import

Purpose: check the full native B01 pipeline under the new process-local hardware-only ALSA configuration before any further microphone trial. This is a justified changed-dependency check after the actual live memory failure. It reuses the qualified app/models/whole delayed D1 geometry and original source. Original saved previews and failed live sources stay immutable.

Inputs: admitted `alsa_hw_only_v1.conf`, actual installed sounddevice/PortAudio and exact explicit I2S endpoint, qualified shared-app-b01-fir-v1 application/assets, saved715127sample16k source. The source fixture constructs48k input by repeating each saved sample3times, runs the unchanged FIR and passes original1x paced10ms blocks through Controller.start_live/LivePipelineSource/CaptureTimeline. This constructed diagnostic is not a microphone recording or accuracy test.

Changes relative to b01-live-controller-v1: initialize real sounddevice with the process-local ALSA config and verify the same endpoint before applying the existing fixture guards. The real module remains resident; all later application sounddevice imports/HostControl/hardware lease/inventory calls are blocked by the unchanged fixture guard. No stream is created or started and no XVF commands/audio capture/playback occurs. Tk remains withdrawn. Early Stop then full restart, original sample/frame/timestamp mapping, retained E0, D1 exact filtered-reference1e-5 checks, queue/archive/controller/Tk and natural owner closure gates stay unchanged. New E0-window numerical reference remains unqualified; finite/normalized vector checks are not speaker accuracy.

Outputs: private b01-live-alsa-fixture-v1[-evidence] source-bound admission, model diagnostics/transcripts/vectors, resource samples, RESULT and independent REVIEW. Nothing private is committed. No model training/downloads or system/current-app configuration changes. Original app remains running, making performance conditional. Limits: CPUs2/3,total200%,one model thread,Tasks64,768MiB virtual,1MiB stacks,>=850MiB availableRAM/5GiBdisk,180sservice/90sstop,32MiBoutput within combined1GiB. Actual hardware callbacks/48k stream fit/restoration still require a later user-ready test.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b01_live_alsa_fixture_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V33.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_alsa_fixture_v1.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`, same commands without `&`, double-quoted interpreter path. Existing Python; no activation/install. Census younger than15minutes. Fixed run and exclusive receipts: preserve failures, never overwrite or rerun an unchanged pass. Future actual capture needs fresh current readiness, admission and independent review.
