# Review staged ONNX graph before loading

Purpose: read-only independent verification of the private target graph bytes/hash, source bindings, actual live unit limits, natural transfer exit, exact boot/PID/start closure, baseline hashes, closed capture and leases. Inputs are the closed `d1-onnx-stage-v1` target and host transfer receipts. Output is private `d1-onnx-stage-v1-evidence/REVIEW.json` and copied receipts; exclusive creation preserves history. No model, audio or GUI runs. Transfer PASS is not inference qualification.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_onnx_stage_v1.py
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_onnx_stage_v1.py
```
