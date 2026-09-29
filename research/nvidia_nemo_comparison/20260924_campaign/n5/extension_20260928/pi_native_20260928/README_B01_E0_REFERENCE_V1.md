# Independent B01 E0 window reference V1

Purpose: independently reproduce every E0 embedding published by the closed short
and full B01 deferred-SciPy application, using a fresh standalone ONNX CPU session.
The dispatcher freezes an exact query plan with original source hashes, half-open
sample bounds and expected vectors. The driver retains original FP32 inputs,
CPU/sequential/one-thread/ORT-all-optimization options and L2 normalization. Each
window is computed twice; max-absolute application/reference/repeat tolerance1e-5
is fixed before execution. No accuracy, voice identity, enrollment or training claim.
No ASR/D1 model inference, GUI, microphone or playback in this reference run.

## Inputs and bounds

Original715127-sample44.6954375-second PCM source, qualified native-stack source/runtime
and installed model assets. Fresh comprehensive host census (<15 minutes), exact
closed identities, boot/install/source hashes, CPUs2/3, total200%, one model thread,
768MiB hard RLIMIT_AS, startup1MiB stack, >=850MiB RAM, >=5GiB target disk. The shared
preview flock stays held through service completion, including this non-UI job.
No visible Tk root is constructed. Service180s, application140s.48MiB output reservation
includes the linked source tree, small logs and private smaps snapshots. Existing
original app stays running, so performance is conditional diagnostic evidence.

## Run once (PowerShell)

From G:\Just_Peachy_N1\20260924_campaign\worktree:

```powershell
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$p/dispatch_b01_e0_reference_v1.py" --run-id b01-e0-reference-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V20.json'
```

CMD or Anaconda Prompt (uses the explicitly pinned environment, not the active conda Python):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b01_e0_reference_v1.py --run-id b01-e0-reference-v1 --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V20.json
```

Do not rerun the same ID or reuse an expired census. Old run paths are immutable.
If storage, source, identities or admission fail, leave the failure and use a fresh
reviewed derivative only when there is a justified change. No higher cap is permitted.

## Outputs / independent review

Private target b01-e0-reference-v1 and host b01-e0-reference-v1-evidence hold bound
QUERY_PLAN.json, independent reference_*.npy, case timings, input digests, owners,
logs and RESULT.json. The plan/vectors remain private. Independent closure review
must bind the plan and both application event journals, compare every array/case,
verify input sample hashes, finite normalization, exact owners and natural exit.
This adds numerical/lifecycle evidence only for those selected windows, not personal
naming accuracy, full real-life representativeness or other model configurations.
