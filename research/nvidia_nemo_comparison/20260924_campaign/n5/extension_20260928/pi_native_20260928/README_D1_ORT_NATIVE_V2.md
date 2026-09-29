# Run three native FP32 four-output cases including original learned high-resolution predictions and resident repeat. No capture or complete waveform driver.

Inputs: Reviewed staged high-resolution graph, host original PyTorch feature/cache/reference fixtures, fresh V4 census; 2128/cache264/FIFO0,32/0/0,17/8/3.

Outputs: Target four-output arrays, metrics, live envelope and lifecycle; host launch receipts. Gate1e-5 for float outputs, integer lengths/repeats exact, unchanged inputs. No audio RTF, speedup, GUI or quality claim.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_ort_native_v2.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V52.json
```
CMD / Anaconda Prompt (no activation):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_ort_native_v2.py --census G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V52.json
```
Fixed fresh IDs refuse existing output. Internal receive/gate/worker flags are registered service entry points, not manual launch commands. Review only after exact owners close. Keep old failures/graphs; no fallback or installed-source edits.

Numerical admission:1536MiB hard virtual/1MiBstack,CPU2/3 total200%,Tasks64,one thread/BASIC/sequential CPU only,initial1408MiBavailable, sampled stop192MiBavailable or1152MiBRSS,300s/10sstop/290salarm,32MiBoutput,4MiBper-file/log cap. No MEMCG enforcement/RSS hard bound or per-job swap claim. Baseline active makes timings conditional. V4 budgets retain all prior usage.
