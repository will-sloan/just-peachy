# Independent projection diagnostic review

Purpose: verify the closed host projection diagnostic without rerunning inference. Inputs are private arrays, original retained feature/cache fixtures, original and compact ONNX graphs, source bindings, actual Job envelope and owner/lifecycle receipts. NumPy/ONNX only; no PyTorch/NeMo model load, checkpoint extraction, capture or accuracy scoring. CoordinatorCPU14 and one numerical-library thread/GPUoff are set before input reads/imports.

Verify complete input/graph hashes, exact original/extracted initializer values against the recorded projection weights, one MatMul in the compact graph, exact source feature slices, zero padding/stack layout/lengths, finite outputs and independent max-absolute discrepancies. Check BASIC and disabled-optimization outputs are identical. Original PyTorch first-cache arrays must exactly match retained original full-model references; tail ORT output must exactly reproduce the prior state failure. Validate a worst-discrepancy float64 dot product with scalar math.fsum per case. Retained repeat assertions remain executed-worker evidence, not new inference by this reader.

Outputs: private REVIEW.json localizing a projection arithmetic discrepancy if supported. Numerical violations remain failures of the unchanged1e-5 state gate. This does not prove every downstream mismatch is explained or that any repair works. No complete waveform/native runtime/speedup/GUI qualification. Preserve all old/new artifacts and exact natural owner/Job closure. Fixed output refuses overwrite.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_projection_v1.py
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"G:\Just_Peachy_N1\20260924_campaign\local\n2\nemo-py312\Scripts\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_projection_v1.py
```
The existing interpreter supplies ONNX/NumPy offline; no environment installation is needed. Wait for the supervised worker to finish before running. Arrays/weights remain private; only scoped findings/code/docs go to Git.
