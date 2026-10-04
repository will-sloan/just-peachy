# Closed-source XVF readiness repair

`xvf_readiness.py` provides `recover_previous_source(manager)` for the current
runtime manager. `xvf_readiness_helper.py` is its bounded native child. The
launcher calls the API only before a **new live Start**, after normal selection
authorization/service-room checks and after the previous worker closes. Saved
WAV use, successful source closures and unrelated errors do not invoke it.

The retained failure is specific: the physical source opened, accepted zero
model samples, then VERSION3.2.1/build `intdev-lr48-lin-i2c` succeeded and
AEC_MIC_ARRAY_TYPE returned255, `Resource could not respond`. Its source stream,
hardware lease and model worker must already be independently closed. The
secondary raw/model frame-count error remains preserved; it is not substituted
for the original control fault or treated as proof that the microphone never
opened. This procedure does not establish the underlying firmware fault cause.

## Purpose, inputs and outputs

Input is the current `Manager`, its persistent CURRENT_LAUNCH/HOST_CLOSURE,
original SOURCE_CLOSE, exact registered worker/source identities, package
inventory and current shared-unit ownership. The API rechecks the actual
original failure and owners. The helper must be present in the new immutable
package; it is not injected into an older release.

Each fault SHA has exactly one directory at `data_root/recovery/<fault-SHA>`.
Outputs include REQUEST, early REGISTERED_OWNER/CHILD_LAUNCH, exact unit and
closed-owner census, two independent verified tool/config restore copies,
per-command raw stdout/stderr, command PID/start/boot/reap receipts, RECOVERY
and caller HOST_CLOSURE. All outputs are private. Previous source/recording
files are not changed. Incomplete/failed attempt directories are preserved and
block another automatic attempt. Successful readiness receipts may be reused
without repeating the control sequence.

Under both exclusive research and hardware leases, with every ALSA capture
stream closed, the helper reads VERSION/build/AEC. A readable AEC sends no
maintenance command. Only the exact fresh AEC255 permits a durable
RESTART_INTENT and one literal `TEST_CORE_BURN 0`, never1. After2seconds it reads
VERSION/build/AEC again and requires unchanged firmware plus readable AEC.
Timeout/nonzero/uncertain sends are consumed failures: never retry them
automatically. Readable closed-stream controls are **not audio qualification**;
the separately owned next session proves capture and models.

The exact exercised xvf_host is1,773,304B/SHA256
`8cc5eebcb499faa61278c9378f7fcb92c6063a437176218404e56e610265e982`.
Before any control command, both verified native `before` and independent
`restore` copies exist for that tool, current.json, live_config.json,
settings.json and saved270degree kanshi config. Current bytes are checked
before commands and afterwards. No config/threshold/model changes, firmware
downloads or flash occur. Unreadable volatile DSP state is not claimed backed
up or restored.

## Resource and ownership integration

The helper uses the pinned interpreter in the current shared CPU2–3/200%/
Tasks64 service, with CPU3,128MiB hard+soft AS,1MiB stack,45second alarm and
50second caller watchdog. The unit's main owner/invocation/cgroup and at least
60seconds remaining lifetime must match. No additional model/source process
may remain in its cgroup. Helper/control execution uses an inherited descriptor
barrier: the parent records the actual PID/start/boot before releasing execution
to read the request or execute the control tool. Each control is directly reaped
and its exact identity must be gone before accepting its reply. At most7 control
commands have2second timeouts. No background polling or periodic reset is added.

A16MiB independent output reserve is checked before mkdir and again before
commands, preserving the greater of5GiB and the configured storage reserve
(including reserve fraction). Two tool copies plus two copies of four<=64KiB
configs are<4MiB. Fourteen<=64KiB raw command files, bounded receipts, two helper
logs<=2MiB each and directories remain within16MiB. Initial available RAM must
be850MiB;192MiB is the stop floor. Native receipt files are<=64KiB; package/helper
inputs are separately bounded. Lease files are existing/read-only opened.
The source fault and worker must belong to the current boot. A historical fault
after reboot does not trigger maintenance; readiness reuse matches the exact
helper owner and that same fault boot.

## Run on the Pi

Use the reviewed **Just Peachy** desktop shortcut. Choose the backend, press
OK, and use the original portrait application's Start. The new launcher calls
`recover_previous_source(manager)` before creating a live worker. A successful
repair continues that new Start. A refusal appears as a human error and keeps
the evidence; inspect Settings diagnostics rather than repeatedly pressing
Start to resend maintenance. Do not run the helper directly: its inherited
owner-acknowledgment descriptor and verified request are part of the API.

Deployment flattens these two named modules into the new package root. Source
checkout imports may use `ui_restore_20261004.xvf_readiness`; installed launcher
uses `from xvf_readiness import recover_previous_source`. Neither original
launcher.py nor worker.py is modified by these source files.

## Host check commands

These focused checks set CPU14 and publish the actual host owner before project
imports. They test the newly added eligibility/fencing/reuse behavior and exact
retained sequence semantics. They do not contact the Pi, run xvf_host or qualify
audio. OWNER must name a new file in an existing private preparation directory.

PowerShell:

```powershell
$N='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003'
$OWNER='G:\path\to\fresh-private-preparation\XVF_READINESS_TEST_OWNER.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$N\ui_restore_20261004\test_xvf_readiness.py" --owner-receipt $OWNER
```

Command Prompt and Anaconda Prompt use the same pinned executable without
environment installation or activation:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "OWNER=G:\path\to\fresh-private-preparation\XVF_READINESS_TEST_OWNER.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\ui_restore_20261004\test_xvf_readiness.py" --owner-receipt "%OWNER%"
```

Source precedent: retained `launch_xvf_recovery_action_v2.py` and
`README_XVF_RECOVERY.md`. This is a runtime Start integration with persistent
one-fault fencing, not authority to resume old research campaigns.
