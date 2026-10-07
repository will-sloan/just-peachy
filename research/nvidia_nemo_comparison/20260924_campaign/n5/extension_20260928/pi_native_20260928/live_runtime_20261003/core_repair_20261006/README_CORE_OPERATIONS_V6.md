# Guarded build30 staging

Purpose: reuse V5's complete owner/lease/current baseline dispatcher for the
exact independently reviewed build30 staging payload. The only admission change
is the hash-bound 2,128,208-byte payload (SHA256
debf77292b2f4601915eb719157acbf0e7f5d67f0966453caa73bdd9a09ce3b5),
whose native action is unchanged. This is a finite operator transfer allowance,
not a recording corpus quota. All other parser limits, actual resource floors,
strict SSH, early CPU14 owner registration, source backups and exact closure
checks are retained. Backup13 is complete: 2,870 files/677,122,259 bytes with
independent full readback and current native owner/cgroup closure.

Inputs: reviewed stage30 ACTION.py/PAYLOAD.json, current full owner inventory,
actual boot/resources and complete backup13. Outputs: private raw dispatch
receipts and the STAGED_ONLY result. No desktop change or capture is requested.

PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$p='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/sidecar-stage30-preparation-8eb78da779f345f1868ebcd7b13adc8a'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v6.py" --label core-stage30-01 --action "$p/ACTION.py" --payload "$p/PAYLOAD.json" --writes
```

Command Prompt and Anaconda Prompt: run `powershell -NoProfile`, then the same
block. The reviewed preparation expires; once dispatched, preserve its receipts
and never rerun its closed label/root. A new operation needs fresh admission.
Staging success alone is not activation or native functional qualification.
