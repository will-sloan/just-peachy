# Native withdrawn Tk and copied archive check V4

V3 collected controls successfully, but independent reader V1 correctly rejected pending widget labels in an immediate snapshot. Inspection found the existing0.2s candidate stabilization and1.2s pending timeout; this was not proof of an application defect. V4 records initial labels and allows1.35s of real monotonic/event-loop time before checking settled widgets. No model runs, artificial clock override or application code change. The final-label/raw-text gate remains unchanged; initial collecting labels are retained separately.

V2 completed the widget/archive controls but failed its harness-only assertion for a nonexistent baseline punctuation counter. V3 checks the actual ResidentModels counters (ASR, speaker, streams, enhancer), absent model objects and absence of the ASR-owned punctuator. It checks the hybrid bundle before baseline rollback too. V2 is retained as failed; no application change or numerical-gate relaxation is involved.

V1 opened the ordinary mode page and incorrectly expected the advanced anonymous button there. Its exact failure/clean process closure is preserved. V2 navigates the existing Advanced page. No application code or acceptance gate is changed.

Purpose: exercise real native Tk widgets and shared-controller backend/mode, Save/pin, Reopen, Delete/Cancel and Delete/Confirm on a private copy of the completed B05 transcript. The original archive and app are preserved. This is model-free replay of existing native results, not new inference, live rendering latency, physical screen/layout validation, speech quality or release acceptance.

Inputs: the hash-bound successful b05-native-stack-v1 source, reviews, FINAL_SNAPSHOT and one completed conversation (about10MiB), existing installed Python/Tk, current DISPLAY=:0 authority, fresh host census and target admission. The harness withdraws its root immediately before any idle processing; it prohibits deiconify and asserts it remains unmapped. It never clicks outside its own widgets or changes desktop focus. No screenshot, capture, audio-device query, playback, download, enrollment or model inference is requested. It uses a fresh data root and only deletes its copied archive after exercising the application's confirmation workflow.

Outputs: private ADMISSION/OWNER/RESULT, OPENED_SNAPSHOT, widget text receipts and launcher logs. Raw text remains private. Source hashes are rechecked after the test. The dispatcher uses strict known-host SSH and no visible terminal. CPU2/3,200%total,Tasks64,1MiBstartup stacks,hard768MiBaddress space,90seconds,at least850MiBavailableRAM/5GiBdisk; hostCPU14,32MiBoutputreservation. The kernel's missing MEMCG is not bypassed: RLIMIT_AS remains explicit. All old sources/results are immutable.

From the campaign worktree, PowerShell:

```powershell
$p = 'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$p/dispatch_native_ui_archive_v4.py" --run-id b05-ui-archive-v4 --census 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V17.json'
```

CMD or Anaconda Prompt, same working directory and existing interpreter (no activation/install needed):

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\dispatch_native_ui_archive_v4.py --run-id b05-ui-archive-v4 --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V17.json
```

These commands describe the immutable attempt. The census must be fresh (under15minutes), owners closed and paths nonexistent. Never rerun over evidence; derive a fresh named attempt/admission. A collected terminal result requires independent source/owner/row/receipt review before credit. Actual visible GUI geometry, user interactions and integrated live/saved inference remain separate gates.
