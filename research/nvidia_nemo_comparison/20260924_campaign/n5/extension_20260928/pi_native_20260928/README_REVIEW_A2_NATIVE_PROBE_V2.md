# Independent native A2 probe review

Purpose: independently check closed a2-native-probe-v3/v2 evidence without importing or rerunning the model/harness. Inputs are the fresh private target admission, complete code/runtime/asset hashes, actual live unit properties, process start identities, result, bounded service log and sampled resources. Checks require original app/install/config unchanged, research and hardware leases free, capture closed, natural exit and retained bytes within the original admission.

Failure status explicitly credits only recognizer creation followed by stream allocation failure and clean destruction. No input/full-source/accuracy/runtime acceptance follows. The success branch only covers the two-second prefix/repeat/lifecycle protocol. Kernel peak RSS and sampled virtual/RSS peaks have different scopes; very brief virtual peaks may be missed. Reads only, except small host private evidence copies and review receipts. No model loads, capture, playback, downloads or target changes.

PowerShell, from G:\Just_Peachy_N1\20260924_campaign\worktree:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/review_a2_native_probe_v2.py" --run-id a2-native-probe-v3
& $py -B "$p/review_a2_native_probe_v2.py" --run-id a2-native-probe-v4
```
CMD / Anaconda Prompt, no activation needed:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\review_a2_native_probe_v2.py --run-id a2-native-probe-v3
```
Replace the final run ID with a2-native-probe-v4 for its independent review. Each review refuses to overwrite its REVIEW.json/service.log. Outputs stay under local/n5/research-extension-20260928/pi-native-20260928/<run>-evidence. Do not publish private event text.

V2 distinguishes V3 native SIGABRT with no RESULT (OS-owner closure only, unknown accepted input count, no clean application finalization) from V4 prefix lifecycle evidence. Nonempty-text counts are reported only to distinguish empty-result passage, never as speech accuracy. Both hard memory limits must equal their actual live receipts. V3 uses the same metadata16 runtime as V4; these have no full-source or generic-versus-modified numerical qualification yet.
