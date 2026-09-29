# Native B01 archive and mode controls V1

Purpose: verify actual hidden Tk backend/Advanced open_with_names, Save/pin,
Open, Delete/cancel, Delete/confirm and baseline rollback callbacks using a fresh
copy of the completed B01 Stop/restart archive. Preserve raw text, formatted text,
labels, source intervals, span IDs and speaker histories against its bound snapshot.
No model inference, capture, playback, enrollment or visible window is allowed.
The source archive is hash-checked before/after and never deleted or modified.
Only the newly copied private archive is deleted through the real confirmation UI.

Inputs: closed b01-restart-gui-v1 with independent PASS, its unchanged source,
manifest and archive; fresh host census. Same CPUs2/3,total200%, hard768MiB virtual,
1MiB startup/native stacks,850MiB RAM/5GiB disk floors;90s service;32MiB reservation
within existing1GiB allowance. The target shared nonblocking flock protects dispatch.
Tk withdraws before idle mapping, deiconify is blocked, unmapped state asserted.
Label settling uses the real1.35s event loop, no clock modification.

Outputs: private b01-ui-archive-v1 and host b01-ui-archive-v1-evidence with admission,
owned-process/lease/result/closure, copied-archive outcomes and actual widget strings.
Every original row/history must be preserved; this is model-free replay, not new
accuracy, speech, on-screen/touch or live-UI-latency evidence.

PowerShell from campaign worktree:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b01_archive_v1.py --run-id b01-ui-archive-v1 --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V21.json
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b01_archive_v1.py --run-id b01-ui-archive-v1 --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V21.json
```

Run once; do not overwrite prior evidence. Independent reader and commands are in
README_B01_ARCHIVE_REVIEW_V1.md. A harness status or prepared launcher is not acceptance.
