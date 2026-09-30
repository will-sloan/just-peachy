# Durable-session locator for retained GUI trial

Purpose: finish independent review of the existing V2 recording without capture/model rerun or changing its exit1 failure. V3 reader rejected the harness session pointer: it was captured during startup as the literal string `None`. V3 code and private failure receipt remain preserved; no V3 REVIEW was written. The actual archive epoch durably records native_session_path, source samples and full capture integrity.

`review_field_live_gui_v4.py` resolves only the sole completed epoch's native_session_path; requires its resolved parent to be this run's private data/sessions, the sole actual session, and exact equality of epoch samples/integrity with terminal source receipts. It then applies all original per-event session-ID, sample/PCM/model/EOF/route/resource/owner gates. This is a corrected evidence locator, not an audio/parity gate relaxation. The original optional punctuation_loads postcheck failure and unexecuted Save/Open/stopped-image branches remain failures/open as described in README_REVIEW_FIELD_LIVE_GUI_V3.md. No whole-trial success, numerical/quality/endurance or physical-touch claim.

Inputs: V2 immutable native evidence and exact v5 build, V3 private rejection receipt. Outputs: private REVIEW with success=false and scoped source/GUI-Stop findings, complete byte/hash-verified target backup. Manual review of existing idle/consent/running screenshots is separate. No repeated native inference/capture, no deletion, no source mutation.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B review_field_live_gui_v4.py
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_live_gui_v4.py
```
Run once; do not overwrite a prior reader/backup. Same CPU14/strictSSH/read-only native review/32MiBtarget/64MiBcombined bounds apply. Raw audio and transcript evidence stay private.
