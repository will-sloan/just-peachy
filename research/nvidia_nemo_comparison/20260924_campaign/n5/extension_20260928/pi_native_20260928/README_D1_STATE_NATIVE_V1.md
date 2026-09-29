# Native ordered state with explicit ONNX compression

Purpose: compare the15 constructed state updates against original NeMo on CM5, including the observed finite overlap tie. The unchanged ordered NumPy shell delegates every cache compression to the explicitly selected39,566-byte ONNX helper. No silent fallback to a different selector. Graph SHA1cb14c34f9c8ed009f05425a74dab7334cde7ed29fe83481c27202d62ec3a323; repaired boolean union and one host tie case are already reviewed. This protocol adds broader native evidence; it must not assume general tie or whole-model equivalence.

Inputs: fourteen original pinned-reference fixtures plus reconstructed observed tie/PyTorch result, synthetic512D silence embedding, fixed graph/helper/source hashes. Outputs: private first/repeat cache/FIFO/current-probability arrays, exact length/source-offset/reset/finish/rejection checks, resource/envelope and owner receipts. No model inference, audio, capture or playback. Cache arithmetic is not learned model/whole-stream/accuracy/GUI acceptance.

Fresh target-inclusive64MiB output reserve includes staged fixtures, new state arrays and compact host receipts under WINDOW_V3/original50GiB reservations. Default hard768MiB virtual,850MiB available before dispatch, sampled stops192MiB available/640MiB RSS,CPUs2/3,total200%,one native thread,1MiB stack,Tasks64,GPUoff,300s service/290s alarm/10s stop,4MiB per output file,4MiB log. Original app/config/install and leases checked. Existing full graph/weights are not copied.

PowerShell:
```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/d1_state_native_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json'
```
CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\d1_state_native_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V48.json
```
Requires a fresh census under15minutes and closed host/native workers. Fixed root d1-state-native-v1 refuses reuse; internal --gate/--worker are owned entry points only. Original1e-5 value gate, exact shapes/repeats and independent stored-array reader apply. Preserve prior strict-selector rejection and invalid export, regardless of this result.
