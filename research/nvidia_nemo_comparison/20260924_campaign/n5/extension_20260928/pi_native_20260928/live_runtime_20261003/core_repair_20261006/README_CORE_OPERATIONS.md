# Current repair operations

Purpose: keep the existing guarded dispatcher and bind new closed backup
supervisors through their independent complete PC mirrors. A failed snapshot
can prove process/lease closure without claiming successful source verification.
No source failure becomes a successful backup. Unknown owner schemas still fail.

Inputs: fresh action/payload, all current owner/lifetime files, and independently
mirrored closed backup units. Outputs: current baseline, source backups/restores,
raw SSH result and exact native utility closure. Only the selected action writes.

PowerShell (replace the fresh label and payload for the reviewed action):

```powershell
$n='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B "$n/core_repair_20261006/host_core_operations_v2.py" --label core-full-backup-03 --action "$n/launch_backup_action.py" --payload "$q/audit-preparation/core-full-backup-request-03.json" --writes
```

Command Prompt/Anaconda Prompt: `powershell -NoProfile`, then the same block.
Use the existing interpreter; no installation. Every dispatch reads all owners,
checks current boot/processes/leases/resources, and retains the original strict
SSH host-key checking. This is an operator entrypoint, not a desktop shortcut.

V2 binds one preserved seed-copy owner by exact path, bytes/hash and actual
FILETIME. Its initial registration spelled the CPU field `cpu14: true`; only
this exact record is decoded as CPU14. The raw registration remains unchanged,
and the V1 precheck refusal occurred before SSH. No generic malformed owner is
accepted and no missing process identity is reconstructed.
