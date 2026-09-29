# Independent host frontend reader

Purpose: independently compare every retained candidate feature to the pinned NeMo reference, with exact valid lengths, zero padding and repeat arrays. Also verify source bindings, actual Windows job/CPU envelope, natural exit, exact supervisor/model closure and output bound. Inputs: private d1-onnx-frontend-v1 receipts/NPZ arrays. Output: write-once private REVIEW.json. No model/capture/playback. Gate1e-4 is log-feature FFT parity only; downstream D1 probability gate stays1e-5. This reader neither imports nor executes the candidate frontend.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_frontend_v1.py
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_frontend_v1.py
```
Run only after the fresh host protocol closes. Failures remain preserved; do not overwrite REVIEW or reinterpret a partial run as a pass. Native Pi frontend and full audio/model/state integration need separate evidence.
