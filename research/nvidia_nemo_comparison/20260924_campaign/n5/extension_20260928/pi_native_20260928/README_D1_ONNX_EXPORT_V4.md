# High-resolution D1 FP32 graph export

Purpose: retain original learned high-resolution predictions as a fourth graph output, alongside coarse probabilities and pre-encoded embeddings/lengths. V3's three outputs cannot reconstruct learned high-resolution values. This new source does not edit installed NeMo, previous graphs or the native Q8 path.

Inputs: the existing pinned198,676,480-byte D1 checkpoint and installed NeMo/Torch/ORT; six feature/cache/FIFO inputs with delayed geometry264/1/1/0/264/188. Reference executes the untouched original forward_for_export while observing its original forward_infer return before downsampling. The explicit wrapper must match all four original values exactly before export adapters are enabled. Dense attention and dynamic multiple-of8 padding reuse the qualified V3 transformations.

Predeclared gate: same FP32 maxabs1e-5 for coarse/high-resolution probabilities and embeddings; exact integer lengths. Warm2128features/cache264/FIFO0, cold32/0/0, dynamic17/8/3; ORT resident repeats must be bit-exact. These cases newly test learned outputs and BASIC optimization; they are not unchanged V3 reruns. No mixed-Q8 equivalence or whole waveform/time mapping is inferred.

Outputs: fresh private d1-onnx-export-v4 directory with sortformer_highres_fp32.onnx, operator inventory, original/adapter/ORT/repeat arrays, source hashes, preserved failures and independent supervision/lifetime receipts. This does not execute on the Pi or integrate frontend/state/EOF. No speed or quality claim.

Admission: WINDOW_V4 measured52GiB total/4GiB combined-window accounting with target bytes plus retained2.5GiB reservation; fresh complete census (within15minutes) and live target owner/unit/lease/resource checks.512MiB output,600seconds, hard6GiB Windows job commit, CPU4/14 total2/coordinator14, model1thread,GPUoff, hostRAM12GiBinitial/8GiBrunning,C50/G75GiB. Sampled file-byte bound is not a filesystem quota. Private registered process/job prevents Windows focus/input takeover. Original supervisor stays untouched; fresh root refuses reuse.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_onnx_export_launch_v4.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V51.json'
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_onnx_export_launch_v4.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V51.json
```
The fixed run refuses an existing root. Future execution needs fresh derivative/admission, not editing this bound source. Internal --guard and worker --root are supervisor-only. Preserve failed output; inspect all isolated owners before dispatch.
