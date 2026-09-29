# Process-local ALSA hardware-only import candidate

Purpose: investigate the roughly141MiB virtual-mapping increase seen when installed sounddevice/PortAudio initializes with the default ALSA configuration. This isolated candidate uses ALSA_CONFIG_PATH inside its own process to point to `alsa_hw_only_v1.conf`, before importing sounddevice. It never writes system/user ALSA configuration or modifies the original app. The file defines explicit `hw` PCM/control templates and no software conversion/mixer/default aliases. This is an experiment, not a supported general audio configuration or accepted live release.

The native diagnostic repeats the same before-app/after-app/after-sounddevice mapping census for this changed configuration, then runs the actual app's inventory with no control config and its exact endpoint resolver. It requires the unchanged explicit XMOS I2S name, ALSA and8input channels. PortAudio host-API initialization/endpoint enumeration may probe hardware capabilities, but no stream is constructed/started and no audio is read, saved or played. No XVF control commands, reset, models or GUI. Capture status stays closed. No claim that enumeration qualifies48000Hz stream operation, combined B01 fit, restoration or quality.

Inputs: existing qualified app/installed dependencies, private original live_config, fresh host census, new admitted process-local config. Outputs: private live-alsa-import-v1[-evidence] admission/owners, status/smaps stages, endpoint resolution, RESULT and independent REVIEW. Raw mappings stay private. Limits and original research lease are unchanged: CPUs2/3,total200%,Tasks64,hard768MiB virtual,1MiB stacks,one numerical thread,180sservice/10sstop,>=850MiB availableRAM/5GiBdisk,8MiBoutput allowance inside the combined1GiB cap. No downloads or model retraining.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_live_alsa_import_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V33.json
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_live_alsa_import_v1.py
```

CMD / Anaconda Prompt: `cd /d G:\Just_Peachy_N1\20260924_campaign\worktree`; same commands without `&`, double-quoted interpreter path. Existing Python is used directly. Census must be under15minutes old. Fixed immutable run; preserve any failure and use a new version for repairs. Future combined models/actual stream validation need fresh admission, and microphone capture needs current user readiness. Do not copy this config into the original app or system defaults.
