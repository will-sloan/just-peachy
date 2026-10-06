# Prepare normal Exit from the latest closed inspection

Purpose: derive a fresh payload for the unchanged normal portrait Exit action
from an explicitly selected, closed read-only operation. A reopened application
has new identities; this preparer never reuses the old diagnostic's fixed PIDs.
It does not send SSH, touch a GUI, start capture/models, or issue a device command.

Input: `--snapshot` is the absolute private path to the latest operation's
`dispatch/RESULT.json`. Its same-directory `NATIVE_CLOSURE.json` and `PHASE.json`
must verify the inspector's natural return0, exact owner absence, joined readers
and reaped SSH. The inspected operation must be read-only with closed capture
and free hardware/research leases. Exactly two current project processes must
be the pinned build26 portrait GUI and its supervisor on that inspected boot.

Output: a unique private `audit-preparation/current-gui-exit-v2-<UUID>` directory,
with early CPU14/FILETIME registered owner, finite HOST_SCOPE, exact source and
input snapshots, separate backup/restore copies, `PAYLOAD.json` and
`SOURCE_CLOSED.json`. Every written file is fsynced and read back byte-for-byte.
The maximum cumulative output is2MiB, maximum preparation time30s, and existing
C50GiB/G75GiB free-space floors remain. Failure preserves its unique output.

The payload owner, supervisor, unit and UNIT_OWNERSHIP path are derived from the
actual inspected commands. The unchanged native action rechecks those exact
current identities/package/owned unit again, finds the actual Settings/Exit
widgets, invokes normal Exit once and waits for both owners to disappear.
It never forcibly terminates an app. The unchanged host wrapper performs its
fresh guards before dispatch, so a stale preparer snapshot cannot authorize
closing a different owner or an active capture.

## PowerShell

From this source directory, prepare the current operation snapshot:

```powershell
$taskSnapshot='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operation-closed-recovery-inspection-01/dispatch/RESULT.json'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\prepare_current_gui_exit_v2.py --snapshot $taskSnapshot
```

Use the returned directory as PREPARED. After its host owner is closed and the
fresh dispatch prerequisites pass, run one unique normal Exit:

```powershell
$taskPrepared='G:/.../audit-preparation/current-gui-exit-v2-RETURNED_UUID'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\host_current_gui_exit.py --label first-start-normal-exit-02 --action "$taskPrepared/normal_current_gui_exit.py" --payload "$taskPrepared/PAYLOAD.json"
```

Replace the PREPARED example with the actual returned absolute path. Omit
`--writes`; only normal application closure is requested. A later invocation
needs a fresh inspection/preparation and a new unused label.

## Command Prompt or Anaconda Prompt

```bat
set TASK_SNAPSHOT=G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/operation-closed-recovery-inspection-01/dispatch/RESULT.json
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B prepare_current_gui_exit_v2.py --snapshot "%TASK_SNAPSHOT%"
set TASK_PREPARED=G:/.../audit-preparation/current-gui-exit-v2-RETURNED_UUID
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B host_current_gui_exit.py --label first-start-normal-exit-02 --action "%TASK_PREPARED%/normal_current_gui_exit.py" --payload "%TASK_PREPARED%/PAYLOAD.json"
```

The original diagnostics01/exit01 outputs and old runtime remain unchanged.
Preparation alone is not proof of GUI Exit or successful subsequent staging.
See [the original first-Start tools](README_FIRST_START_REPAIR.md) and
[the guarded host operation](README_HOST_STABILIZATION_OPERATIONS_V5.md).
