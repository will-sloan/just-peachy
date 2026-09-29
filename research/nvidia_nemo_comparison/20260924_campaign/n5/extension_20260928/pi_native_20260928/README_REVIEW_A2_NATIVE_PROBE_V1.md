# Independent native A2 probe review

Purpose: independently check closed a2-native-probe-v1/v2 evidence without importing or rerunning the model/harness. Inputs are the fresh private target admission, complete code/runtime/asset hashes, actual live unit properties, process start identities, result, bounded service log and sampled resources. Checks require original app/install/config unchanged, research and hardware leases free, capture closed, natural exit and retained bytes within the original admission.

Failure status explicitly credits only recognizer creation followed by stream allocation failure and clean destruction. No input/full-source/accuracy/runtime acceptance follows. The success branch only covers the two-second prefix/repeat/lifecycle protocol. Kernel peak RSS and sampled virtual/RSS peaks have different scopes; very brief virtual peaks may be missed. Reads only, except small host private evidence copies and review receipts. No model loads, capture, playback, downloads or target changes.

PowerShell, from G:\Just_Peachy_N1\20260924_campaign\worktree:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/review_a2_native_probe_v1.py" --run-id a2-native-probe-v1
& $py -B "$p/review_a2_native_probe_v1.py" --run-id a2-native-probe-v2
```
CMD / Anaconda Prompt, no activation needed:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_a2_native_probe_v1.py --run-id a2-native-probe-v1
```
Replace the final run ID with a2-native-probe-v2 for its independent review. Each review refuses to overwrite its REVIEW.json/service.log. Outputs stay under local/n5/research-extension-20260928/pi-native-20260928/<run>-evidence. Do not publish private event text.
