# Independent FP32 export evidence review

Purpose: independently read V3's stored NumPy arrays and exact source/owner/job receipts without running models. Inputs: immutable `d1-onnx-export-v3` admission, graph inventory/hash, original/dense-adapter/ORT arrays, job envelope, supervisor, result, lifecycle and frontend records. Verify finite equal-shaped arrays, max-absolute1e-5 gates, exact integer lengths, original-reference correspondence, all owner identities closed, natural exit, output bound and unchanged input desktop. No transcript/audio is read or scored. The hard Windows job6GiB committed-memory limit covers the process tree; root-launcher RSS sampling is not an aggregate model peak measurement.

Output: private exclusive `REVIEW.json`. A pass covers three host feature/cache cases only, not full waveform/frontend/cache/FIFO/EOF driver, high-resolution output, native ARM operator coverage, performance or N5. V1/V2 preserved failure/partial reviews were separately checked before each fresh derivative. Run only after supervisor and model exit; never overwrite a review.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_onnx_export_v3.py
```
CMD / Anaconda Prompt (no activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_onnx_export_v3.py
```
