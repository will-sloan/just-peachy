# Actual V5 launch JOB extraction

Purpose: persist the actual successful native launch JOB from the dispatcher
result for the existing status/readiness and closed-output monitor. A launch JOB
does not establish functional success. Never synthesize owner identities.

Inputs: actual wrapper dispatch RESULT.json and its exact classic-ui-check-NN
label, pinned to build25/current boot/V5 helper and fresh256MiB reservation.
Outputs: unique private CPU14 preparation with source backup/independent restore,
full original dispatch result, exact JOB copies and root NN-JOB.json. Existing
JOBs are never overwritten. Bound1MiB/600s and existing host storage floors.
No SSH, native operation, model or microphone is started.

PowerShell:
```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& $py -B "$s/extract_stabilization_job_v5.py" --result 'ACTUAL_WRAPPER_DISPATCH_RESULT.json' --label classic-ui-check-21
```
CMD or Anaconda Prompt: set JP_SOURCE to the same directory, then run:
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/extract_stabilization_job_v5.py" --result "ACTUAL_WRAPPER_DISPATCH_RESULT.json" --label classic-ui-check-21
```
The caller checks exact host-owner absence after natural exit. Existing
monitor_speech_ready.py/native_speech_ready_probe.py accept the actual generic
classic-job256MiB bound without changing their source or helper identity.
