# Normal production GUI35 workflow, V3 read-only observation

Purpose: exercise the actual activated build35 shortcut and ordinary portrait
Start/Stop/selected Discard/Settings Exit. This separate source version fixes only
a transient read-only SQLite observation in the external acceptance controller.
It changes no runtime code, microphone consent, model math, recording policy,
database writes, resource guard, source ownership or deletion behavior.

Normal01 FAILED because the controller's capturing predicate received
OperationalError("database is locked") from its selected-session read. It had no
RUNNING/workflow proof. Its outer/nested owners and watchdog closed, and the full
34-file/280,284-byte mirror is preserved. This is a failed external acceptance
observation, not evidence that runtime Start failed, and it is not a GUI pass.

V3 catches sqlite3.OperationalError only around selected_database in capturing.
A numeric SQLite base code (error code &255) of5/BUSY or6/LOCKED returns None to
the existing deadline-bound wait. Extended BUSY/LOCKED codes have the same base
handling. Missing codes, other OperationalError values and all other exceptions
propagate. No message-text matching, database write/mutation retry, increased
SQLite timeout, unbounded wait or fabricated RUNNING proof is introduced.
The unchanged210-second controller deadline,270-second watchdog and300-second
external service remain acceptance bounds, not product recording limits.
Post-Stop and Discard database observations retain their original strict behavior.

The action is byte-identical to V2 SHA
77a3ac0aebbf706d2324e3676df5c7d47e2110f1fa6aa7baa1495e6df43069ba;
the preparer is byte-identical SHA
e730ad7c31de8d006775fe9e2ff502602385fd60c178a6c5f666096a376d2157.
V2's six-reserve sentinel proof and inherited32MiB FSIZE remain unchanged.
Original V2 sources and exact independent backups/restores are preserved.
Build35 manifest:
5e4b8f21a0cbd04bedbccc6c2504cee7910fc60deda09c4777dc9ffe07c05e3f.
Target:/home/peachyprototype/JustPeachy/research/nemotron-20260928/field-runtime-v29-build-35.

Status: source-only preparation. No V3 Python/test/native run or GUI qualification
is claimed. Build35 is activated and the repeated-source hour completed, but its
growing lag does not qualify sustainable real-time performance or naming accuracy.

## Inputs and outputs

| File | Inputs | Outputs |
| --- | --- | --- |
| prepare_normal_gui_workflow.py | Fresh current boot/expiry, unused production-normal label, actual desktop SHA and acceptance SHA; paired four sources and pinned idle reference | CPU14/FILETIME owner, five source backups/restores, exact derived dispatch, fresh ACTION.py/PAYLOAD.json/SOURCE_CLOSED.json |
| launch_normal_gui_action.py | Admitted backed sources, payload and current closed native baseline | Existing bound native job with independent32MiB native/PC allocation |
| normal_gui_control.py | Actual Desktop Exec/native_scope, authenticated new unit/request/worker/source, selected UUID | Real GUI/source/count/policy/owner/closure proof; bounded read-only BUSY/LOCKED observation wait |
| SOURCE_DERIVATION.json | Exact V2/current source hashes and one capture-read substitution | Whole-source reverse equality and unchanged action/preparer evidence; not execution proof |

Private preserved/ and SOURCE_DERIVATION.json are technical evidence, not public
source additions. Public V3 source selection is the three Python files plus this
paired README. No audio, transcript, people names, vectors or gallery contents
belong in the public source handoff.

## PowerShell preparation

Root first reviews the sources and allocates one CPU14 host slot. Read actual
current boot and activated desktop/acceptance hashes from closed receipts. Use
the fresh production-normal-02 label; do not reuse the failed normal01 output.
Expiry must be finite, future and no more than600seconds ahead.

    $py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
    $d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
    & $py -B "$d/normal_gui35_v3_20261006/prepare_normal_gui_workflow.py" --label production-normal-02 --boot-id ACTUAL_CURRENT_BOOT_ID --expires-unix ACTUAL_FRESH_UNIX --desktop "/home/peachyprototype/Desktop/Just Peachy.desktop" --desktop-sha256 ACTUAL_ACTIVATED35_DESKTOP_SHA --production-acceptance-sha256 ACTUAL35_ACCEPTANCE_SHA
    $naturalExit=$LASTEXITCODE

Independently verify actual natural exit and registered PID/FILETIME absence,
every source/backup/restore, SOURCE_CLOSED and the actual action/payload hashes.
Do not directly execute the controller or native action on Windows.

## Command Prompt and Anaconda Prompt

Use the existing interpreter; no conda activation/install/model download is
needed. Substitute the same actual receipt values used in PowerShell.

    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\core_repair_20261006\normal_gui35_v3_20261006\prepare_normal_gui_workflow.py" --label production-normal-02 --boot-id ACTUAL_CURRENT_BOOT_ID --expires-unix ACTUAL_FRESH_UNIX --desktop "/home/peachyprototype/Desktop/Just Peachy.desktop" --desktop-sha256 ACTUAL_ACTIVATED35_DESKTOP_SHA --production-acceptance-sha256 ACTUAL35_ACCEPTANCE_SHA

## Root native dispatch and acceptance

Root uses reviewed V13, whose collector binds the actual closed normal01/PIN35
receipts before the fresh normal02 dispatch. The native runtime/action policy is
unchanged. Actual V13 source/admission and fresh payload must be reviewed first;
this document does not assert that the collector or action has executed.

    & $py -B "$d/host_core_operations_v13.py" --label FRESH_OPERATION_LABEL --action ACTUAL_V3_ACTION_PATH --payload ACTUAL_V3_PAYLOAD_PATH --writes
    $naturalExit=$LASTEXITCODE

Use the actual returned JOB with the complete native-component monitor and
independent32MiB PC allocation. Root must independently verify:

1. Activated Desktop Exec and exact new current-boot unit/PID/start/invocation/
   cgroup. RuntimeMaxUSec infinity/manual_stop_storage_guarded, actual GUI
   AS256MiB soft/1GiB hard and worker1GiB soft/hard.
2. Actual six-row chooser, Pyannote/ReDimNet/Live and familiar portrait; no policy
   override. manual_stop true/nullable backlog/finite capacity-derived source
   and drain. Actual Listening/Stop and at least192000 processed samples.
3. Successful actual Stop and source/worker closure, exact owners gone,
   direct-child reaping/joined reader and no closure/cleanup fault.
4. Real selected Discard, all nine selected table counts0, audio/transcript
   directory absent and store/UUID-bound completed receipt, without direct SQL
   deletion or sidecar removal.
5. Settings Exit, natural production scope return0, durable unit closure, exact
   nested/outer owners gone, empty cgroup and watchdog closure; full mirror
   membership/digests and unchanged desktop/autostart/display/capture readbacks.

A requested Stop, copied receipt or quiet source does not replace those proofs.
This short test does not evaluate physical touch,300-second manual capture,
natural conversation, recognition/naming accuracy, raw Save or GUI endurance.
Keep it the last native action; later work is host-only final documentation and
publication. Unknown or healthy unrelated owners are never signalled.