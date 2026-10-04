# Strict repair-operation supervisor receipts

`host_repair_operations_v3.py` is a fresh host dispatcher derivative. It keeps the complete existing host/native owner, lifetime, identity, resource, storage, action, lease, current application and write guards from `host_operations_v6.py`. It does not grant a malformed receipt exemption or resume an old campaign.

Its purpose is to prevent repeated native preread refusals for two actual historical nested supervisor receipts in the complete `production-idle-01` mirror: the finite GUI readback unit (`7200` seconds, idle timeout `300`) and its separate watchdog (`120` seconds). Both get exact native-relative path, byte-count, whole-JSON SHA and independently restored closure/owner bindings. Their schemas are checked on the host and again by the native preread; current boot/PID/start ticks must show their actual owners absent before any action is admitted.

Inputs for the host-only review are the existing complete actual monitor mirrors, each mirror's full manifest/completion, and the nested ownership, registration, exit and closure receipts. Every owner-like JSON member in every complete actual mirror is read and hash-checked; duplicate paths must have identical bytes. Existing direct/source/journal bindings remain with the unchanged dispatcher. Unknown nested supervisor paths fail before SSH. Any unexpected native nested owner now reports its exact path and fields instead of a bare assertion.

Outputs are an early CPU14 `REGISTERED_OWNER.json`, compact `ACTUAL_NESTED_UNIT_MAP.json` and `ACTUAL_NESTED_UNIT_REVIEW.json` in a unique private preparation directory. The normal operation path retains all existing operation receipts, raw errors and source backup/readbacks. Typed logical closures remain distinct from process identities.

## PowerShell: host-only review

```powershell
$repair = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/ui_restore_20261004'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$repair/host_repair_operations_v3.py" --host-review
```

This command performs no Pi/network operation and starts no model or recording.

## Command Prompt and Anaconda Prompt: host-only review

```bat
set "REPAIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\ui_restore_20261004"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%REPAIR%\host_repair_operations_v3.py" --host-review
```

The explicitly pinned interpreter works independently of the currently active Conda environment.

## Separately reviewed native operation

After the host review and source backups close, the inherited operation arguments are `--label FRESH-LABEL --action ABSOLUTE_ACTION.py --payload ABSOLUTE_PAYLOAD.json`. Add `--writes` only for the separately reviewed write action. The named action/payload still require their exact current binding, bounded allocation and complete fresh preread; this wrapper does not authorize a native mutation merely by existing.

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' "$repair/host_repair_operations_v3.py" --label 'FRESH-LABEL' --action 'ABSOLUTE_ACTION.py' --payload 'ABSOLUTE_PAYLOAD.json'
```

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%REPAIR%\host_repair_operations_v3.py" --label "FRESH-LABEL" --action "ABSOLUTE_ACTION.py" --payload "ABSOLUTE_PAYLOAD.json"
```

Do not reuse a failed or completed operation label. Read the retained raw result first. A successful host map is not proof of current native process death, microphone readiness, startup or deployment.
