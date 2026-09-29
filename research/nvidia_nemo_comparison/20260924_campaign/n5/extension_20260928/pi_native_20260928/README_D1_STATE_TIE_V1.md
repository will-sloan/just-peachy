# Isolated observed cache-tie diagnostic

Purpose: reconstruct only the failed third overlap update from the preserved deterministic generator, verifying all14 earlier generated input bytes against saved fixtures without rerunning their reference/model computations. Restore the previous cache snapshot and preserve the failing input before testing. Verify that the strict candidate rejects atomically. Then export a small ONNX compression-only graph to test whether ONNX Runtime reproduces original NeMo selection on this actual constructed tie. No full model inference, audio, capture or playback.

Inputs: immutable d1-onnx-state-v1 arrays/source/config and pinned NeMo module. Synthetic silence embedding stays identical. Reference compression first uses the original learned-embedding route; a process-local explicit embedding argument must be exactly equal before export. No installed source/weights change. Outputs: private reconstructed input, original/ORT/repeat arrays, graph, exception or mismatch, admission/job/source/owner receipts. Original1e-5 gate remains; an exported graph or a terminal exit is not parity or native acceptance. A mismatch is preserved and is not a silent backend fallback.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_state_tie_launch_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json'
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_state_tie_launch_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json
```
Fresh fixed run d1-onnx-state-tie-v1 refuses reuse. V3 target-inclusive16MiB output reservation, original50GiB payload/reservations, host CPU4/14total2/coordinator14,one native thread,GPUoff,hard6GiBjobcommit,600s and existing RAM/disk guards/supervisor. Only this small diagnostic is admitted; no large graph transfer. Independent review and actual Pi checks are still required.
