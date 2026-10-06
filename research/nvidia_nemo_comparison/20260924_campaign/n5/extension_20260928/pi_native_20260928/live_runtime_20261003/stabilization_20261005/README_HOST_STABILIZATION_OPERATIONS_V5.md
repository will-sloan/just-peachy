# Exact current coordinator FILETIME V5

Purpose: repair kept-source21-inspect-01's host-only false live-owner report.
Its current coordinator's validated kernel FILETIME converted to Unix time as
1791244277.6561558; psutil reported1791244277.656156. V4 excluded self by float
equality, so it stopped before SSH. The failed receipt and V4 remain immutable.

V5 changes only the generated host decoder's current-coordinator exclusion.
It reads the actual current Windows kernel FILETIME and retains exact FILETIME
sets for already validated typed audit owners. Self is excluded only when both
PID and the whole exact FILETIME set match the actual process. A same-PID wrong
FILETIME cannot disappear through float-key collision. Existing thin legacy
self receipts still require the original exact psutil value after the original
current-owner CPU14 guard. Every other live PID, owner schema check, full file
read, lifetime/resource/lease/floor guard and native binding remains unchanged.

The inline coordinator_filetime_source function matches coordinator_filetime_v1.py
and reversibly changes exactly three original source anchors; it does not invoke
a decoder CLI or run a historical campaign. Unknown owners still reject. V5
retains every original V4 nested-unit, backup09 and exact format correction.

Inputs/outputs: fresh unused operation label, reviewed action and payload, optional
authorized --writes, full original strict owner/lifetime prerequisites, immutable
source and independently restored preparation, bounded complete preread, actual
native result/closure or preserved failure. This is a dispatcher, not the field
launcher. Normal operation scope remains600s; host preread300s; all other caps
and SSH/closure behavior remain the original V4 behavior.

PowerShell (only after source check and exact host closure):
```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& $py -B "$s/check_coordinator_filetime_v1.py"
& $py -B "$s/host_stabilization_operations_v5.py" --label kept-source21-inspect-02 --action 'ACTUAL_CLOSED_READONLY_ACTION.py' --payload 'ACTUAL_CLOSED_READONLY_PAYLOAD.json'
```
CMD and Anaconda Prompt: set JP_SOURCE to the same source directory.
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/check_coordinator_filetime_v1.py"
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/host_stabilization_operations_v5.py" --label kept-source21-inspect-02 --action "ACTUAL_CLOSED_READONLY_ACTION.py" --payload "ACTUAL_CLOSED_READONLY_PAYLOAD.json"
```

The focused check first registers an actual fulltyped CPU14/FILETIME owner,
backs and independently restores all source inputs, and compares the entire
V4/V5 AST except the one added binder and one return wrapper. It executes only
small private owner fixtures with actual self/kernel timestamps and an existing
other live process: exact self accepted, adjacent wrong FILETIME rejected,
another live PID rejected, and a matching float-key collision rejected when
present. It performs no SSH, native action, GUI, audio or model execution. Output
is a fresh private2MiB/600s SOURCE_CLOSED/RESULT plus fixture receipts; the caller
must record exact host-owner absence after natural exit before dispatch.
