# Guarded native B05 saved-file preview

Purpose: make the qualified anonymous Sherpa/PnC + delayed Nemotron pipeline accessible through explicit File, Start, Stop and Close controls. The original rc5 app, autostart, data and operating-system settings stay unchanged. `b05_preview_v1.py` wraps the shared controller/UI; `b05_preview_app_v1.py` is the native entry point; `launch_b05_preview_v1.py` creates a fresh resource admission and systemd service over strict known-host SSH.

The window starts idle, with no selected file and no model inference. Choose File, choose the saved sample, then Start file. Selection alone does not start processing. Stop drains the session; Start file begins the same original file again from zero. Only the hash-bound 44.6954375-second, 16kHz mono PCM16 source is admitted. No microphone, playback, enrollment, named speakers, backend fallback or alternate source is exposed. Restrictions also apply at the controller command boundary. Captions appear first; anonymous labels can arrive about25seconds later on this sample. No accuracy or sustainable real-time claim follows.

The process permits at most two starts. It rejects a new start unless at least75seconds remain in its145second application window; Close is requested automatically at the end of that window, with a180second systemd hard bound. Start/Stop, source selection and rejected alternatives are checked using actual widgets, while the automatic check keeps the root withdrawn. Physical480x800 layout, scanout, touch and real speech remain separate validation. User mode opens a visible window only when the user explicitly invokes it; never run user mode on a scheduled wakeup.

Inputs: the verified CM5 boot/app identities; unchanged b05-native-gui-v1 source, assets and passing reference review; a fresh comprehensive host census; at least850MiB available target RAM and5GiB free disk; combined new-output headroom and C/G floors. Every launch rechecks owners and hashes. Native CPUs2/3, total200%, one model thread, Tasks64, hard768MiB RLIMIT_AS and process-startup1MiB stacks remain. The original app remains active, so timing is conditional. No download or global setting change occurs.

Outputs: a fresh private target run and matching host evidence directory with admission, exact owner, launch result, memory/closed-session journals and application RESULT. The automatic check also emits Stop/final snapshots and control receipts for independent review. Raw audio/text/probabilities remain private. Review is required; exit0 alone is not acceptance. Historical identifiers are never overwritten. User launches require a separate `B05_PREVIEW_V1_QUALIFICATION.json` binding this exact source; without it they fail before dispatch. This receipt is created only after independent control/passage/drain review.

## Automatic withdrawn control and pipeline check

From PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v1.py --mode check --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V18.json
```

CMD or Anaconda Prompt, using the existing interpreter without installation:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/launch_b05_preview_v1.py --mode check --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V18.json
```

The census must be less than15minutes old. The fixed check ID is b05-preview-controls-v1 and is single use. A failed attempt requires a fresh derivative; do not overwrite or rerun it unchanged.

## User-invoked preview, after qualification

Use the same PowerShell or CMD/Anaconda command above with `--mode user` and **omit `--census`**. The launcher computes a new census, generates a unique run ID, checks the qualification hashes, and opens the Pi window after fresh target admission. This command can take several minutes while counting existing campaign data. The original app remains in place underneath; closing the experimental window returns to it. No autostart replacement or installation is performed. Source identity, checkpoint or budget changes cause a refusal rather than an automatic relaxation.

The shell command must be invoked from the campaign worktree shown above. Do not invoke the native Python entry point directly: it requires the newly bound admission, process limits and service ownership. Each preview consumes the shared output allowance and ends within three minutes. Review its RESULT and exact unit/process closure before another launch.
