# Review native ORT feature cases

Purpose: independent read-only standard-library ZIP/NPY verification of all native first/repeat output arrays against retained PyTorch references, with exact repeats, finite shapes, probabilities in[0,1], unchanged1e-5 tolerance and exact lengths. Input NPZ hashes must also match the previously reviewed host inputs. Verify source/graph hashes, actual live limits, exact owners, natural exit/session release, baseline/config, closed capture and free leases. No inference/capture occurs; target reader runs onCPU3.

Inputs: closed `d1-ort-native-v1` and host reference/launcher receipts. Outputs: private exclusive `d1-ort-native-v1-evidence/REVIEW.json`, copied admissions/results/envelope/log. No array, audio, transcript or weights enters Git. A PASS covers these constructed native feature/cache cases only, not waveform/high-resolution/state driver, full audio, real time, accuracy or integrated release. PeakRSS includes session loading; conditional call timings cannot be compared as end-to-end RTF to a different native geometry.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/review_d1_ort_native_v1.py
```
CMD / Anaconda Prompt, no activation:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_d1_ort_native_v1.py
```
