# Normal production GUI35 workflow, V2 preparation

This separate source version fixes the host preparation proof for the existing
normal GUI35 acceptance workflow. It does not change model math, UI controls,
recording policy, resource limits, selected-session deletion or ownership rules.
The original `normal_gui35_20261006` folder and its failed host preparation remain
preserved. The failure occurred before SSH or any native mutation.

The pinned idle reference has six `16*1024**2` metadata reserve expressions and
one existing `file_limit_bytes=32*1024**2`. V1's reverse replacement changed that
original file limit to16MiB, so its whole-dispatch reverse AST check rejected the
preparation. V2 marks only the six reserve expressions with a unique sentinel,
reverses those markers to16MiB for the same full AST comparison, and substitutes
32MiB only after the proof passes. It checks the original file-limit occurrence
and marker counts. The derived dispatch still reserves32MiB independently on
native and PC storage, with the original32MiB per-file limit unchanged.

Status: V2 source prepared; no V2 Python, native action or qualification performed.
Root's observed finite Live53/Saved54 results do not qualify this ordinary policy
workflow. Hour08 and activation must finish before this final native check. No
recognition accuracy, biometric naming, natural conversation, physical touch or
300-second capture claim follows from this short workflow.

## Purpose, inputs and outputs

| File | Inputs | Outputs |
|---|---|---|
| `prepare_normal_gui_workflow.py` | Fresh boot/expiry, unused label, actual activated Desktop35 path/hash, production acceptance hash; the four paired sources and pinned idle reference | CPU14/FILETIME registration; five source backups and independent restores; reverse-AST-proved derived reference; `ACTION.py`, `PAYLOAD.json`, `SOURCE_CLOSED.json` in a fresh private preparation |
| `launch_normal_gui_action.py` | Those exact backed sources, sealed payload and current closed native baseline | Existing reviewed native job contract and named metadata output, with32MiB native/PC allocation |
| `normal_gui_control.py` | Actual Desktop Exec, current `native_scope`, exact new unit and request | Genuine Start/12s/Stop/selected Discard/Settings Exit proof; numeric policy/owner/count/closure records and named non-content copies |
| `SOURCE_DERIVATION.json` | Preserved original35 source hashes and this V2 source version | Source-only whole-action reversal and unchanged control/preparer checks; no execution proof |

Actual package manifest:
`5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f`.
Target: `/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-35`.
Control remains byte-identical SHA
`d281ca84e7cc8b594f2ca6049c9fe0ea32d91b950ea8962bf2704c294aeffa84`.
The reference is `N/full_application_20261004/launch_manual_idle_action_v2.py`, SHA
`b123694a1c530090ff860f1a544227ada4e8a5d413dfc5078f6a14cf7d79d40e`.
The copied preparer's relative reference path already resolves correctly from
this sibling folder. The preparer and control are unchanged.

## PowerShell preparation

Root allocates one CPU14 host slot after Hour08's full closed mirror and actual35
activation. Read the actual activated shortcut and acceptance hashes from root's
verified receipts. Expiry must be fresh and no more than600seconds ahead. The
actual shortcut is `/home/peachyprototype/Desktop/Just Peachy.desktop`; the lower
case autostart file is a separate unchanged setting.

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B "$d/normal_gui35_v2_20261006/prepare_normal_gui_workflow.py" --label production-normal-01 --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --expires-unix ACTUAL_FRESH_UNIX --desktop '/home/peachyprototype/Desktop/Just Peachy.desktop' --desktop-sha256 ACTUAL_ACTIVATED35_DESKTOP_SHA --production-acceptance-sha256 ACTUAL35_ACCEPTANCE_SHA
$naturalExit=$LASTEXITCODE
```

Record the actual exit status and independently confirm the registered host
PID/creation FILETIME is absent. Root verifies `SOURCE_CLOSED.json`, every
current/source/backup/restore hash, and the final action and payload hashes.

## Command Prompt and Anaconda Prompt

Use the existing interpreter; no package installation or environment change is
needed. Substitute the same actual receipt values used in PowerShell.

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\normal_gui35_v2_20261006\prepare_normal_gui_workflow.py" --label production-normal-01 --boot-id e60e67c2-f3f5-4b8b-8eab-2613df2de37e --expires-unix ACTUAL_FRESH_UNIX --desktop "/home/peachyprototype/Desktop/Just Peachy.desktop" --desktop-sha256 ACTUAL_ACTIVATED35_DESKTOP_SHA --production-acceptance-sha256 ACTUAL35_ACCEPTANCE_SHA
```

## Root dispatch and acceptance

Use unchanged reviewed V12 with the fresh V2 `ACTION.py` and `PAYLOAD.json` through
its existing bound action mechanism. Its default2MiB payload bound is sufficient;
no V13 or larger stage exception is needed. The command below is only for root
following source/payload review and the fresh closed baseline.

```powershell
& $py -B "$d/host_core_operations_v12.py" --label FRESH_OPERATION_LABEL --action ACTUAL_V2_ACTION_PATH --payload ACTUAL_V2_PAYLOAD_PATH --writes
$naturalExit=$LASTEXITCODE
```

Use the actual returned JOB with the existing full native-component monitor and
independent32MiB PC allocation. The aggregate full mirror must fit its reservation
and hash every member. Do not execute the action/control directly on Windows or
invent future JOB/owner/closure facts.

Required observed evidence:

1. Activated Desktop Exec; unique current-boot production unit, actual PID/start
   ticks/invocation/cgroup; manual lifetime with RuntimeMaxUSec infinity; GUI
   AS256MiB soft/1GiB hard and worker1GiB soft/hard.
2. Real Pyannote/ReDimNet/Live selection and no policy override. Actual policy has
   `manual_stop=true`, nullable backlog, finite disk-capacity source duration and
   equal finite drain duration. Visible Listening/Stop and at least192000 actual
   processed samples prove twelve seconds of acquisition without another consent.
3. Stop completes; worker return0/direct-child reaping/joined reader/no cleanup
   faults; exact worker/source owners gone; matching source-close metadata.
4. The newly observed session UUID alone is discarded via real controls. All nine
   selected database table counts are0, its artifact directory is absent, and its
   store-bound completed receipt has no pending deletion intent.
5. Settings Exit gives actual native_scope return0, durable unit closure,
   independent empty cgroup, and watchdog270second closure. Desktop/autostart,
   settings/display and closed capture state match the fresh baseline.

The external controller has210seconds, its watchdog270seconds and its owned
service300seconds. These are finite acceptance backstops, not product recording
limits. Faults preserve evidence; only the authenticated newly owned unit can be
signalled. Metadata helpers retain bounded parsing,128/256MiB AS and physical
free-space safeguards. Selected SQLite reads use read-only/query-only,256KiB
cache and a3second VM bound; no direct deletion, recovery or journal removal.

Keep this workflow the last native action. The unchanged historical collector
only admits its old idle/PIN21 nested receipts, so later native dispatch requires
a separate narrow binding to the actual normal35 receipts. Host publication V7
has no such native-map consumer. Root independently checks this run's exact
owners/cgroups/full mirror before host-only publication. `HOST_CLOSURE.json` is
checked and hash-recorded but not copied; its exact recorded launch ID permits
bounded independent original metadata readback without a historical sweep.
