# Independent pipeline/controller boundary review

Purpose: verify the closed source-pipeline-v2 application-source boundary protocol independently. Check actual unit/child envelopes, exact hashes/owners, terminal acknowledgements, constructed FIR bytes by scalar97-tap reference at1e-7, all MemoryJournal sample extents, unchanged timing gates, blocked-controller ownership, explicit failure propagation and fresh-epoch byte equality. This reader does not qualify whole Controller startup, model inference, GUI, real capture or field release.

Inputs: immutable admitted code/source and saved WAV prefix; seven CASE_RESULT files, source/fake-device/terminal receipts, journal float bytes and controller cleanup evidence. Remote read-only CPU3/256MiB/110s, hostCPU14. Outputs: private REVIEW.json, full hash-verified target copy, BACKUP.json; target plus backup remain inside32MiB admission. The original files are never removed or overwritten. Source fixture times are constructed/paced, not acoustic truth or performance benchmarks.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_source_pipeline_v2.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_source_pipeline_v2.py
```

Run after exact native owner closure. No environment activation/download, hardware access, playback or model launch. Preserve reader failures; fixed review/backup roots reject overwrite. V1 source was superseded before dispatch by V2 ownership handling and remains preserved.
