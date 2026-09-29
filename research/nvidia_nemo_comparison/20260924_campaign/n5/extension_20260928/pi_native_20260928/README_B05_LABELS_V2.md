# Native anonymous-label provenance reader

Purpose: review existing native B05 journals and the final controller presentation snapshot without another inference run. Check that delayed labels refer to earlier text revisions and actual session-local span IDs, are published after their acoustic evidence, use only Speaker 1–8/Unknown, and never introduce a personal name/profile. Verify source intervals remain coarse ASR revision windows, raw text equals its preserved span text, and final labels have matching native revision history. Count events/rows only as functional coverage, never speaker or transcription accuracy.

Inputs: a closed independently reviewed B05 Stop/restart run, its hash-bound application/model inputs, two session journals and final snapshot. Outputs: private LABEL_AUDIT_INPUTS_V2 and LABEL_REVIEW_V2 plus a permitted target stage receipt. This does not instantiate Tk widgets, contact a microphone, play sound, enroll anyone or validate acoustic speaker-assignment quality. The cumulative draft intentionally contains both sessions; the reader checks each revision's own session, rather than requiring the draft to discard earlier text. The reader fails closed if lineage, timestamps, raw text or expected anonymous semantics disagree.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b05_labels_v2.py --run-id b05-native-stack-v1
```
CMD or Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b05_labels_v2.py --run-id b05-native-stack-v1
```

The alternate supported existing run is `b05-stop-restart-lru1-v1`. Run only after its lifecycle review passes; output creation is exclusive. Host work is pinned to CPU 14, target reading to CPU 3, with existing strict SSH verification. No package installation or new download is needed.

V1 failed closed because it conflated upstream untimed ASR hypothesis IDs (`:rN:tM`) with presentation span IDs (`/token:N`). V2 independently reconstructs the existing presentation stable-prefix token contract from successive raw text revisions, requires every label target to belong to that exact revision, and verifies final span text against that lineage. It retains timing/session/anonymous/no-name checks. No model/application behavior or result is changed. The failed V1 source and diagnostic remain preserved.
