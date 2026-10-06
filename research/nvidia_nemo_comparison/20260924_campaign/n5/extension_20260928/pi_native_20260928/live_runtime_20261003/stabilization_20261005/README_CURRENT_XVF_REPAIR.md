# One current-fault XVF repair

`launch_current_xvf_repair_v2.py` is a fresh external action for one exact current
boot raw-qualification-08 fault, not a runtime edit or periodic maintenance task.
It preserves the old package, source closure, recordings and ledgers. The failed
source is PID3769/start364608 on boot0561d730-3cad-48e0-940a-fe3930c89665;
the independently closed main job is PID3754/start364571.

The exact source fault is hash-bound by the action and payload. The
retained `xvf_readiness.qualifying_fault` and `recovery_sequence` functions are
copied exactly and reviewed by AST. The sequence first reads VERSION, BLD_MSG
and AEC_MIC_ARRAY_TYPE. A readable AEC sends nothing. Only a fresh matching AEC255
allows one fenced `TEST_CORE_BURN 0`, then unchanged firmware and AEC readback.
Uncertain sends, failed commands, existing intent or unreadable post-check never
permit another send for that fault. No microphone, model or audio stream opens.

Inputs: fresh full baseline JSON, exact complete PC mirror of raw08, same current
boot, reviewed immutable package and native probe pins, tool/config/display bytes
and independent PC restore copies. The native action requires all current project
owners clear, independently verifies the failed unit/cgroup/source closure, checks
capture closed and owns the research and hardware leases. It separately creates
native exact backups and independent restore/readbacks of the tool, settings,
live config, install pointer and saved display270 before any possible send.
Volatile DSP state is explicitly not restorable.

Outputs: fresh `xvf-recovery-NN` root and owned JOB; native backup/restore receipt,
early wrapper owner, per-command actual PID/start/boot/closure/stdout/stderr,
durable intent, `RECOVERY.json` and complete closed PC mirror. Independent target
and PC output reservations are each16MiB; CPU3/128MiB AS/1MiB stack,75s alarm,
80s service runtime/sharedCPU2,3/200%/Tasks64 and existing floors remain enforced.
Metadata/tool command output is capped at64KiB per file within32MiB outer file
limits. The action rechecks pins, streams,192MiB RAM stop and5GiB disk before each
utility. No claims of live audio qualification or underlying fault cause follow
from an AEC repair.

## Prepare on the PC

`prepare_current_xvf_repair_v2.py` sets CPU14 and registers its actual host owner
before project reads. It backs up/restores the new action/README before import,
validates the full actual raw08 mirror and retained trigger, and derives fresh
payload/config/tool backups from the supplied latest baseline. It never SSHs.
Use fresh output and an unused two-digit native recovery label.

PowerShell:

```powershell
$repairSource = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
$repairPrivate = 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$repairSource\prepare_current_xvf_repair_v2.py" --baseline 'G:\path\to\latest\BASELINE.json' --fault-mirror "$repairPrivate\raw-qualification-08-monitor-01" --previous-repair-mirror "$repairPrivate\xvf-recovery-03-monitor-01" --output "$repairPrivate\current-xvf-repair-04-preparation" --label xvf-recovery-04
```

CMD or Anaconda Prompt:

```bat
set REPAIR_SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005
set REPAIR_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%REPAIR_SOURCE%\prepare_current_xvf_repair_v2.py" --baseline "G:\path\to\latest\BASELINE.json" --fault-mirror "%REPAIR_PRIVATE%\raw-qualification-08-monitor-01" --previous-repair-mirror "%REPAIR_PRIVATE%\xvf-recovery-03-monitor-01" --output "%REPAIR_PRIVATE%\current-xvf-repair-04-preparation" --label xvf-recovery-04
```

## Native action and closure

Only the root operator executes the action after fresh complete owner/baseline
preread. The existing runner preserves strict SSH and early native utility
registration. PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$repairSource\host_stabilization_operations_v2.py" --label current-xvf-repair-04 --action "$repairSource\launch_current_xvf_repair_v2.py" --payload "$repairPrivate\current-xvf-repair-04-preparation\PAYLOAD.json" --writes
```

CMD or Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%REPAIR_SOURCE%\host_stabilization_operations_v2.py" --label current-xvf-repair-04 --action "%REPAIR_SOURCE%\launch_current_xvf_repair_v2.py" --payload "%REPAIR_PRIVATE%\current-xvf-repair-04-preparation\PAYLOAD.json" --writes
```

After natural closure, use the retained `monitor_native_job.py` complete mirror
command with that owned JOB and a fresh PC output. Inspect `RECOVERY.json` and
every command/owner/closure before any new live admission. Do not edit the old
CURRENT_LAUNCH pointer, manufacture a source SESSION, clear the raw fault or retry
this fault/root. Prepared source is not a completed repair.


## Preserved failed repair03 and v2 startup envelope

Repair03 exited naturally with MemoryError before any command or durable intent.
Its complete mirror is preserved. Fresh repair04 requires independent current
closure and hash-verified commands=[]/sends=0/attempted=0/no COMMAND/no INTENT
both on the PC and natively. It does not reuse repair03's root or admission.
The suspected cause is wrapper threads reserving allocator arenas while under
768MiB AS before the driver lowered its cap to128MiB. That cause is not measured
by repair03. The v2 wrapper applies128MiB hard/soft AS before imports/threads;
systemd sets MALLOC_ARENA_MAX=1 before Python startup. No AS cap is increased.
WRAPPER_START_MEMORY, WRAPPER_DRIVER_MEMORY and DRIVER_ENTRY_MEMORY record actual
VmSize/RSS/status, AS limits and allocator environment. Failed RECOVERY records
the exact phase, bounded traceback and memory status. The retained recovery
sequence and fault trigger remain byte-for-byte/AST unchanged.

Read RECOVERY.post_aec_readable and the individual command receipts explicitly:
a process exit0 alone does not prove AEC became readable. A failed or uncertain
send with an intent still permanently fences that exact fault's only send.


## Actual repair04 and subsequent raw09 results — October 5

The independently mirrored `xvf-recovery-04-monitor-01` completed one conditional
TEST_CORE_BURN 0 after fresh AEC255. Post-AEC returned0/readable, VERSION3.2.1
and build `intdev-lr48-lin-i2c` remained unchanged; all five pinned tool/config/
install/settings/display files read back unchanged. All seven command processes
were directly reaped/exactly closed; main PID4898 and its recursively inspected
unit were closed before the complete private PC mirror. This exact fault has a
durable one-send intent and must never be resent.

Actual DRIVER_ENTRY_MEMORY reported VmSize31120KiB, VmRSS20112KiB and3threads,
with hard/soft AS134217728B and startup MALLOC_ARENA_MAX=1. This demonstrates the
new bounded startup ran successfully. Repair03's preserved MemoryError had no
command or intent and no entry VM measurement: reserved thread allocator arenas
under its earlier768→128MiB transition remain an inference, not a proven cause.
The original physical AEC fault's underlying cause is also unproven.

Separately, `raw-qualification-09-monitor-01` passed80,000processed mono samples
and80,000samples on each physical MIC0–MIC3 channel (5s at16kHz; firmware packed
transport48kHz). Processed320,000B and raw1,280,000B were independently read back;
source clock and full transport partition were checked, all route controls
restored, source/stream closed and the owned unit recursively empty before the
complete independent PC mirror. It loaded no ASR/diarizer/embedding models.
It proves this bounded physical raw/processed route, not sustained operation,
speech accuracy, calibrated equal acoustic latency or a full backend pass.
The raw08 failure and repair03 failure remain immutable and are not retroactively
passed. No additional recovery or capture was executed to write these findings.
