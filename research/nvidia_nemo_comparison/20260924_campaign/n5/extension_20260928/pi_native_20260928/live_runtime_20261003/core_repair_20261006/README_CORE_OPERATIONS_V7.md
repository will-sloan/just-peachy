# Stage30 archive validation memory admission

Purpose: run the unchanged native installer for build30 with a finite 256 MiB
metadata utility address-space ceiling, after Stage01 failed at 128 MiB during
pure archive validation before mkdir. Stage01's raw failure and exact closure
remain evidence. The runtime/model limits are unchanged.

This allowance is bound only to the exact fresh 2,128,181-byte Stage02 payload
SHA256 8eca70c51ea9c441861f437e6f72ae307bbaf9ed6edc3db77f349c57745064a0
and unchanged native installer action. Current initial RAM must exceed 978 MiB;
the later 850 MiB available floor, CPU3, 1 MiB stack, finite lifetime, disk
floors, complete owner/capture/lease checks and source backups are retained.
The result records actual hard AS and peak utility RSS. Ordinary other actions
keep their existing limits. No unlimited-memory or global cap removal occurs.

Inputs: exact fresh stage admission and complete accepted backup13. Outputs:
private full raw dispatch/closure evidence, STAGED_ONLY and utility memory.

PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$p='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation/sidecar-stage30-v2-preparation-bac018b83bb74c169cf9b8434ec9a0a3'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v7.py" --label core-stage30-02 --action "$p/ACTION.py" --payload "$p/PAYLOAD.json" --writes
```

Command Prompt/Anaconda Prompt: run `powershell -NoProfile`, then that block.
Do not reuse the consumed label, expired payload or installed target. A future
operation needs fresh source and admission review; staging is not activation.
