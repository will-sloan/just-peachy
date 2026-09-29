# Native B01 label/evidence lineage reader V1

Purpose: independently check the retained-ReDimNet early-Stop/full-restart caption provenance. This is a read-only journal/snapshot review; it does not run models, score accuracy, play audio or use the microphone. Existing scoped Tk and archive reviews remain separate.

Input: closed `b01-restart-gui-v1`, its successful passage review, immutable admission files, both session journals and final snapshot on the authorized Pi. The reader verifies source hashes and exact Linux boot/PID/start-tick closure before reuse. It reconstructs stable presentation token IDs from ASR revision text; it checks session, target revision, raw words, anonymous slot, publication ordering, actual embedding/identity evidence links and stored label history. The new empty, uncalibrated research gallery must yield Unknown personal identity. Numerical embedding/probability parity comes from the separately bound passage/reference reviews.

Outputs: private `LABEL_AUDIT_INPUTS_V1.json` and `LABEL_REVIEW_V1.json` beside host evidence, plus a new target label-review receipt. These contain private evidence and must not be committed. Exclusive creation rejects overwriting a prior result. No stage/release/identity-quality acceptance follows.

PowerShell (from the campaign worktree):
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_labels_v1.py --run-id b01-restart-gui-v1
```

CMD and Anaconda Prompt (use the pinned interpreter; no installation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_b01_labels_v1.py --run-id b01-restart-gui-v1
```

Host affinity14, remote read-only affinity3; strict existing SSH host-key identity from `dispatch_geometry_v2.py`. Retain failures rather than relaxing checks. The review checks source-window chronology, not phonetic word alignment, personal recognition, speech quality or live-route performance.
