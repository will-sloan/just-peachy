# Normal desktop idle check V2

`normal_classic_idle_action_v2.py` preserves the V1 chooser/normal Exit flow and corrects one source provenance assumption: `launch_production_idle_action_v2.py` is an external injected action, not an installed package member. The caller injects its exact independently backed bytes. The fixed allowed SHA256 is `f44d0910f37abd856dfd39d90da0b629768acc14c5f6c48d3cbf908b81d88a4b`, with a128KiB source cap. The retained action's original complete package inventory and production acceptance checks still run before launching the normal desktop command.

V1 and its failed `production-idle-02` output remain unchanged. That failure occurred before starting a target application. Do not retry that label. This is external instrumentation only: no runtime/package or recording changes are introduced.

## Purpose, inputs and outputs

Purpose: verify the activated single shortcut runs its actual normal `native_scope`, opens the real idle backend chooser in480x800 fullscreen at display270, and exits normally without OK/Start, audio or model execution. Preserve the independent90s watchdog, exact process/unit closure, closed capture, existing recordings and explicitly disabled login startup. Copy only the new native owner subtree independently.

Use all launch fields from [README_NORMAL_CLASSIC_IDLE.md](README_NORMAL_CLASSIC_IDLE.md), a fresh `production-idle-03` label, and add:

```json
{
  "prior_action_b64": "base64 of exact backed N/launch_production_idle_action_v2.py",
  "prior_action_sha256": "f44d0910f37abd856dfd39d90da0b629768acc14c5f6c48d3cbf908b81d88a4b"
}
```

The injected V2 helper is the guarded dispatch action. The external prior source must be backed and independently restored/read before use. The caller registers CPU14 before project reads, performs the complete fresh prior-owner/lease/resource census, supplies fresh current boot/expiry and reserves16MiB native plus16MiB independent PC output. The action returns the ordinary asynchronous JOB. Use existing `monitor_native_job`, exact closure and full independent private tree readback. `PRODUCTION_IDLE_RESULT.json` must report functional success, actual desktop Exec, normal Exit, zero new workers/capture, one shortcut and closed watchdog. Physical double-click/touch and reboot tests remain separate.

## Actual guarded commands

The dispatcher takes `--action` pointing to this V2 helper and `--payload` containing the reviewed JSON fields above. Root uses `host_repair_operations_v4.py` for the current repository's strict full-owner scan. `--writes` declares new owned metadata/unit creation; it does not authorize recording or model execution in this idle-only action. Do not substitute a bare SSH/Tk command.

From the `ui_restore_20261004` directory, PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\host_repair_operations_v4.py --label normal-classic-idle-03 --action .\normal_classic_idle_action_v2.py --payload 'ABSOLUTE_PATH_TO_REVIEWED_PAYLOAD.json' --writes
```

CMD and Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B host_repair_operations_v4.py --label normal-classic-idle-03 --action normal_classic_idle_action_v2.py --payload "ABSOLUTE_PATH_TO_REVIEWED_PAYLOAD.json" --writes
```

The displayed arguments match `host_operations_v6.main`, which this owner-aware V4 coordinator calls. Choose a fresh host label if any prior attempt used the example. The owner/CPU14 harness is mandatory and runs before request/source reads. Never run this helper as an independent executable or use the old inline compile examples without owner registration. Static review through the same registered preparation harness may compile/AST-parse the source; that provides no native result.
