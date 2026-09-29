# Native ReDimNet / ONNX Runtime lifecycle diagnostic

Purpose: separate retained E0 embedding functionality and native process shutdown from the combined B01 address-space failure. This uses the existing ReDimNet2-B2 model and installed ONNX Runtime, with the documented process-local ORT_DISABLE_TELEMETRY=1 switch set before initialization. It is not new enrollment, identity accuracy, a personal voice profile, ASR/WER scoring or complete application acceptance.

Inputs: hash-bound installed ReDimNet model/runtime binary and the original saved 44.6954375-second PCM file. `ort_e0_lifecycle_v1.py` uses its first 0.5, 2 and 12 seconds as constructed component diagnostics, twice each. It retains the production CPU provider, graph optimization and one-thread settings. It checks finite 192-dimensional output, nonzero normalization, unchanged input samples and repeat error <=1e-5. It releases the session and returns normally; only exact OS/systemd closure can establish a naturally exited process. No microphone, audio playback or personal gallery is used.

Outputs: private admission, OWNER, RESULT and six embedding arrays. Do not put vectors, source audio or raw evidence in Git. `dispatch_ort_e0_lifecycle_v2.py` enforces fresh host/target census, exact closed workers, preserved app/boot identity, window and storage/output limits. Independent review must rehash inputs, recompute array dimension/finite/norm/repeat checks and verify natural launcher exit plus owner closure. Component passage does not validate naming or fix B01.

## PowerShell

From this directory with a census less than 15 minutes old:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_ort_e0_lifecycle_v2.py --run-id ort-e0-lifecycle-v2 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V11.json'
```

## CMD / Anaconda Prompt

Use `cd /d` to this folder and the same quoted Python executable/arguments, omitting `&`. No activation/install/download is needed. Strict SSH stdin stages a fresh job; the existing Pi interpreter runs under systemd/taskset. Existing run IDs are refused, not overwritten. CPU 2/3, total CPU 200%, one model thread, 64 tasks, 180 seconds, hard 768 MiB virtual space, 850 MiB available RAM and 5 GiB disk floors remain. Reserve 16 MiB within the combined 1 GiB output allowance. Original app/install and global OS/swap remain unchanged.

The process-local switch is documented in the [official ONNX Runtime privacy/runtime documentation](https://github.com/microsoft/onnxruntime/blob/main/docs/Privacy.md) and [v1.29.0 release notes](https://github.com/microsoft/onnxruntime/releases/tag/v1.29.0), checked September 29, 2026. The earlier failed B01 trace motivates this check; a standalone pass alone cannot prove the combined failure path has been fixed.

V1 staging stopped before admission/execution because it assumed the original deployment-relative asset path. The installed store is content-addressed. V2 resolves the exact model path by its SHA256 from the already verified B01 V2 admission, verifies that file again, and uses the unchanged ort_e0_lifecycle_v1.py harness. The partially staged V1 directory is preserved.
