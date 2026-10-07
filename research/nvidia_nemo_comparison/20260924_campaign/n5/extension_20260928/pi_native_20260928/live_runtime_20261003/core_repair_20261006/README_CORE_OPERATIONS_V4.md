# Reviewed build29 stage dispatch

Purpose: run the existing guarded dispatcher with the measured 2,201,258-byte stage29 payload. The earlier 2 MiB parser refused it before SSH. Only the exact action and payload hashes receive this allocation. Ownership, backups, storage, resources and native checks remain.

Inputs: reviewed ACTION.py/PAYLOAD.json from core-stage29 preparation and an unused label. Outputs: current owner/lifetime preread, backups, fresh baseline and retained dispatch result. Desktop activation and capture are separate operations.

PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v4.py" --label core-stage29-03 --action "$q/audit-preparation/core-stage29-preparation-31a0bbe5ef4f4a748f5123968b1b0448/ACTION.py" --payload "$q/audit-preparation/core-stage29-preparation-31a0bbe5ef4f4a748f5123968b1b0448/PAYLOAD.json" --writes
```

Command Prompt and Anaconda Prompt: run `powershell -NoProfile`, then the same block. Use fresh unused labels. Preserve failed roots and V2. This installation transfer allocation does not limit user recordings. Execution status is pending actual result inspection.
