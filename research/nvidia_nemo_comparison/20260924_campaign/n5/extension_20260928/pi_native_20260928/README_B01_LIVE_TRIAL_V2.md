# Prepared B01 live trial with process-local ALSA configuration

Purpose: prepare a fresh user-ready retry after the preserved first live trial reached its768MiB virtual cap. V2 leaves original b01_live_trial_v1.py, model/app code,30second accepted-source bound and all model/queue/restoration gates unchanged. Only the service environment changes: ALSA_CONFIG_PATH selects the admitted hardware-only config inside this research process. Wrapper b01_live_trial_alsa_v2.py verifies the exact path/hash before delegating to unchanged V1 code; ALSA_ENVIRONMENT.json binds the executed setting. No system/user configuration or original app/autostart is changed.

Inputs: existing B01 source/assets, verified hardware-only import/explicit endpoint and new saved-model fixture review, fresh census, new config/wrapper/gate/launcher hashes. Before user mode, boundary mode must independently pass the original three accepted-sample/closure/discontinuity/overrun cases with the new service environment. This still opens no device or models. It does not prove actual hardware/model operation.

**User mode requires current physical readiness. Private audio/transcript/vector diagnostic retention was expressly consented to for this work; only ready/consenting speakers may participate.** User mode records real microphone input, targets480000accepted16k samples (30seconds), closes/restores the source before model drainage, and starts once. It has no playback/enrollment/reset. Source target is not an unconditional30second wall-clock microphone-open guarantee; priming/stalls/error cleanup can extend it. Service180seconds plus90secondstop; forced termination does not establish route restoration. Never run user mode on a heartbeat or automatically retry after a failure. Saved-file previews and original app remain unchanged.

The research gallery is empty, so no personal naming is qualified. Tk is withdrawn; physical display/touch is not tested. No WER/DER/accuracy scoring. No silence skips or alternate backend fallback. Native limits remain CPUs2/3,total200%,one model thread,Tasks64,hard768MiB virtual,1MiB stacks,>=850MiBavailableRAM/5GiBdisk. Combined output reservation32MiB inside the existing1GiB cap; refresh census within15minutes. Existing supervisor/target lease, exact boot/PID/start/source checks and unique user IDs apply. No downloads/training.

Outputs: new private b01-live-trial-alsa-boundary-v2 or b01-live-trial-alsa-user-<UTC> runs, audio journals/transcripts/vectors for user mode only, exact owners, model/resource/route diagnostics and independent review. Preserve every failure; no outcome follows from a terminal success. Review each user run separately.

PowerShell, no-capture boundary preparation:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b01_live_trial_v2.py --mode boundary --census <fresh-census.json>
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_trial_v2.py --run-id b01-live-trial-alsa-boundary-v2
```

Only when the user is currently ready, with private diagnostic consent:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b01_live_trial_v2.py --mode user --ready-now --allow-private-diagnostics --census <fresh-census.json>
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_live_trial_v2.py --run-id <returned-user-run-id>
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; same commands without `&`, double-quoted interpreter path. Reuse installed Python; no environment install. Detailed original source behavior and caveats remain in README_B01_LIVE_TRIAL_V1.md, which stays preserved with its failed trial.
