# Review native withdrawn widgets and archive

Purpose: independently compare the completed V3 run with the previously reviewed native B05 final snapshot. Check all40rows' raw/formatted text, labels, span IDs, word spans/history and source intervals; verify actual Tk text-widget receipts, Save/Open/Delete cancel/confirm, baseline rollback, zero model loads, source preservation and exact process/worker/Tk closure. No inference, capture, playback, GUI launch or source mutation occurs in this reader. Withdrawn widgets do not establish physical480x800 layout, scanout, touch behavior, live UI latency, accuracy or release acceptance.

Inputs: private `b05-ui-archive-v3` ADMISSION/OWNER/RESULT/OPENED_SNAPSHOT, launch exit code, original B05 FINAL_SNAPSHOT and label review. All admitted sources are rehashed through strict SSH. Outputs: private AUDIT_INPUTS.json and REVIEW.json plus a matching Pi stage receipt. Raw transcript/widget text remains private; only counts and gate results belong in reports. Existing receipts cannot be overwritten.

PowerShell from the campaign worktree:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_native_ui_archive_v1.py
```

CMD or Anaconda Prompt from the same directory, without installing or activating anything:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_native_ui_archive_v1.py
```

Uses hostCPU14/remoteCPU3. Run only after the target owner has exited; exact boot/PID/start identity is checked. V1/V2 harness failures remain preserved and receive no complete acceptance. For another run, create a new reader/admission rather than editing evidence-bound files.
