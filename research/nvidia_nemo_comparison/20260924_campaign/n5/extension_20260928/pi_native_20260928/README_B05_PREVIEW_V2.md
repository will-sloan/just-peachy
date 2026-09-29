# B05 anonymous saved-file preview: bounded user entry

Purpose: expose the checked B05 File/Start/Stop/Close controls in a user-invoked Pi window. `launch_b05_preview_v2.py` is the host launcher; `b05_preview_app_v2.py` is the admitted native entry point; `b05_preview_v1.py` contains the unchanged restricted controller and shared caption UI. Read README_B05_PREVIEW_V1.md for input restrictions and the independently reviewed actual-button Stop/full-restart protocol.

V2 adds a withdrawn idle mode that exercises the same user main loop and real145second auto-close timer with no model inference. It samples idle/no-capture/unmapped state every500ms. It changes no inference code, controls or model geometry. Its source diff and idle lifecycle require independent review alongside the V1 full-model control review before user mode is enabled. Visible layout/touch/scanout and real speech remain unqualified.

Inputs: verified unchanged b05-native-gui-v1 source/assets/review, original44.6954375second saved mono16kHz PCM16, strict known-host SSH, a fresh host census, exact closed research owners, unchanged original app/boot, >=850MiB availableRAM and5GiBdisk. CPU2/3,total200%,native1thread,Tasks64,1MiBstartupstacks and hard768MiBvirtual space stay unchanged. Kernel MEMCG remains unavailable. No download or global setting change is made.

Outputs: fresh private host/target admission, owner, source hashes, launch/result/memory journals; user starts additionally produce private sessions. The idle check produces periodic idle-state counts and natural timer/worker/Tk closure. These are functional/resource results, never ASR/WER or speaker-quality metrics. The original rc5 app/install/data remain unchanged and available after this experimental window closes.

## User operation, after qualification

The window starts idle. Choose **File → Choose saved sample → Start file**. Selecting the file does not process it. **Stop** drains the session; **Start file** restarts the original file from zero. Captions appear first; anonymous labels can lag about25seconds on this sample. No personal names, microphone, playback, enrollment, other backends or arbitrary files are available. **Settings → Close preview** ends the preview. Automatic Close occurs after145seconds; systemd enforces180seconds. At most two starts are allowed, and each needs at least75seconds of remaining application time.

On Windows PowerShell, run this only when you want the experimental Pi window to open:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v2.py --mode user
```

CMD or Anaconda Prompt, with the existing interpreter and no installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v2.py --mode user
```

The launcher computes a fresh census (this can take several minutes), verifies B05_PREVIEW_V2_QUALIFICATION.json against the source, generates a unique run ID, and checks resources/owners before opening the Pi window. A missing qualification, changed source/boot, active research job, insufficient budget or expired October1 checkpoint causes refusal. This is a bounded research preview, not an installed/autostart replacement or N5 release. Never invoke user mode on an automated wakeup or run the target Python entry without its service admission. Each launch consumes the shared output budget and needs result/owner review before the next one.

## Automatic idle-loop check

Use the same PowerShell/CMD/Anaconda command with `--mode idle-check --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V18.json`. This fixed single-use run is b05-preview-idle-v1. Its root stays withdrawn and protected from mapping; no file is selected and no audio runs. A census must be under15minutes old. Never overwrite its evidence. Future variants need new source/run names and admission. Independent review commands are in README_B05_PREVIEW_IDLE_REVIEW_V1.md.
