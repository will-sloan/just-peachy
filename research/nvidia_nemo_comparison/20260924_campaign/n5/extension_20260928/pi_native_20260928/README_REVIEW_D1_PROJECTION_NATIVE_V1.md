# Independent native projection review and backup

Purpose: review the new ARM projection observations using an independent standard-library NPY reader, without rerunning inference. Read the completed `d1-projection-native-v1` target admission, outputs, live service properties and exact process/lease/baseline state. Verify all four source fixtures and compact graph against the already reviewed host files; compare first/repeat arrays, stack/length bytes and finite projection values against original PyTorch and host ORT separately. The original absolute1e-5 gate remains unchanged. A mismatch review is not numerical acceptance or a repaired waveform runtime.

Inputs: exact immutable target files plus host projection reference hashes and successful launcher closure. No model, ONNX/Torch/NumPy import or microphone. Target reader usesCPU3/256MiB virtual/110s alarm; host coordinatorCPU14. Outputs: private `REVIEW.json`, `BACKUP.json` and verified flat-file `target` backup within the same evidence directory. Refuse overwrites, links/traversal or unexpected tar members; originals are retained. Check target<32MiB and target plus host receipts/backup<64MiB. No new graph/model copy, downloads, audio or accuracy score. Every actual unit limit and exact boot/PID/start identity is reviewed before success; transient-unit defaults cannot substitute.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_projection_native_v1.py
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_projection_native_v1.py
```

Run only after the launcher and gate close. No installation needed. Read the returned scoped status and cases: `REVIEWED_NATIVE_PROJECTION_MISMATCH_ONLY` means failed numerical limits were independently accounted for; `PASS_NATIVE_PROJECTION_CASES_ONLY` would still exclude the complete waveform, state updates, GUI, speedup and release. Private features/embeddings/weights stay out of Git.
