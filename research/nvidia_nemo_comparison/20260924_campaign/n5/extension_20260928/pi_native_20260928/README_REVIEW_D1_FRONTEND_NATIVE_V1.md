# Independent native frontend review

Purpose: a separate standard-library ZIP/NPY reader checks every stored fixed/irregular/repeat native array against the original host NeMo references. Verifies exact sample/valid-frame counts, shapes, finite values, zero padding, exact repeats and predeclared1e-4 log-feature tolerance. Also checks actual768MiB/1MiB-stack/CPU2/3/200%/300s unit properties, source hashes, natural exit and exact boot/process closure, unchanged baseline and free leases. No candidate code, model, capture or playback runs. Raw audio/features remain private.

Inputs: completed d1-frontend-native-v1 and reviewed host d1-onnx-frontend-v1 arrays. Outputs: write-once private receipts, retained service log and REVIEW.json under d1-frontend-native-v1-evidence. Copy hashes bind the native inputs to host references. Failure stops review without changing evidence. Scope is frontend only, not model output/cache/FIFO/complete driver/quality/speedup.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_frontend_native_v1.py
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_frontend_native_v1.py
```
The read-only target review stays onCPU3 and imports no numerical runtime. This script creates only compact host review files. Use once after closed execution; do not rerun unchanged passed checks for progress.
