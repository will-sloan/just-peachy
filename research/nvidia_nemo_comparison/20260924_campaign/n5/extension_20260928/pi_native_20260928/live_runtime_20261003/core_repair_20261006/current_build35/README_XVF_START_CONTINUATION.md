# Microphone startup recovery in the same Start

This change fixes the shared startup handling used by all six backend choices.
It preserves the original portrait application. Pressing **Start** remains the
explicit request to listen; startup recovery does not launch listening at login
or when the chooser opens.

`launcher.py` now keeps one continuation allowance for that user Start. If the
physical XVF source reports the exact retained AEC255 fault before accepting any
model samples, its worker and source must first be reaped and independently
observed closed. The original failed session, `SOURCE_CLOSE.json` and
`HOST_CLOSURE.json` stay preserved. The existing pinned readiness helper then
runs in one background thread. Tk remains responsive and no Tk call occurs in
the recovery thread. After the helper closes and the thread joins, the normal
launcher rechecks authorization, storage and service room and creates one fresh
worker with the unchanged backend, source policy and application settings.

A previously closed exact fault can be repaired before the first worker of the
new Start using the same asynchronous path. A failure in that fresh worker does
not trigger another continuation for the same Start. Recovery is not polling,
periodic firmware maintenance or a generic reset for every error.

## Eligibility and cancellation

Eligibility retains `xvf_readiness.qualifying_fault`: VERSION3.2.1 and the exact
retained build must be readable, AEC_MIC_ARRAY_TYPE must return255 with the
specific resource-not-responding diagnostic, the input stream must actually
have started, zero processed samples and acknowledgments must have been
accepted, no route must have been applied, and stream, hardware lease and exact
worker/source owners must be closed on the current boot. Signal-killed workers,
unjoined readers, unverifiable owners, output failures, partial recordings,
different-boot faults and unrelated errors do not qualify.

The retained helper reads current firmware/AEC under exclusive leases. A readable
AEC sends nothing. The exact fresh fault permits one durable intent and one
literal `TEST_CORE_BURN 0`. Uncertain or failed sends remain consumed and are
never automatically resent for that fault. Independent tool/config restore
copies precede control commands; no models or capture stream are opened by the
helper. Unreadable volatile DSP state is not claimed restorable.

**Stop** and **Exit** latch cancellation even when no model worker is running.
An already running bounded helper finishes and is reaped; it is not interrupted
mid-command and retried. Cancellation prevents the fresh worker and capture.
The launcher store/lease stay owned until the helper thread has joined. Other
session, gallery, settings and export controls remain unavailable while it is
pending. Saved replay does not invoke this physical-source recovery path.

The helper accepts two explicit supervisor lifetime policies. Finite test units
still require a finite non-boolean deadline with at least60seconds remaining.
Normal `manual_stop_storage_guarded` units require their exact receipt schema,
`runtime_max_seconds=None`, `deadline_monotonic=None`, idle300seconds and actual
systemd `RuntimeMaxUSec=infinity`. MainPID, boot/start identity, invocation,
cgroup, CPU2–3/200%, Tasks64 and sole GUI/helper process checks are retained.
The helper itself still has its45second alarm and50second caller watchdog.

## Inputs and outputs

Inputs are the pinned runtime binding/package, original user selection and
session policy, current launch/request/source/worker receipts, actual GUI unit,
current boot/owners, leases and storage/RAM floors. There is no new CLI setting,
weight, audio route, threshold or raw-qualification hash change.

Private outputs add `SOURCE_RESTART_INTENT_<uuid>.json` and
`SOURCE_RESTART_RESULT_<uuid>.json` alongside the original failed launch. They
bind its original request and source hashes, one continuation budget,
helper result/error, joined thread and cancellation decision. The existing
`data_root/recovery/<fault-SHA>` keeps the exact helper/control/restore/closure
receipts. A successful continuation receives its own ordinary launch/session
UUID and normal ownership/storage receipts. Failed-session storage is preserved
and charged; this is not recording-slot replenishment or evidence deletion.

## Run from the Pi desktop

Open the single **Just Peachy** shortcut, choose a backend and Live microphone,
then press **OK** and **Start** in the original application. If this exact startup
fault occurs, the display shows microphone preparation while Stop remains
available. A failed repair stays visible with retained diagnostics. The helper
must not be launched directly: its inherited owner-acknowledgment descriptor,
request and service ownership are required.

## Run from PowerShell, CMD or Anaconda Prompt

The PC shell is used for reviewed deployment/diagnostics; it does not start this
Pi-only helper directly. PowerShell can open the current operator documentation:

```powershell
$runtimeDocs = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\completion_20261001'
Get-Content -LiteralPath "$runtimeDocs\START_HERE_CURRENT.md"
Get-Content -LiteralPath "$runtimeDocs\MODE_GUIDE.md"
```

CMD and Anaconda Prompt use the same commands without an environment install:

```bat
set "RUNTIME_DOCS=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\completion_20261001"
type "%RUNTIME_DOCS%\START_HERE_CURRENT.md"
type "%RUNTIME_DOCS%\MODE_GUIDE.md"
```

Deployment requires a fresh immutable runtime and reviewed backups, not editing
build26 in place. The root operator uses the selected package/deployment README
and strict SSH wrappers with fresh current-state admission. See
`README_STABILIZATION_PACKAGE_V6.md` for package preparation, and
`../ui_restore_20261004/README_XVF_READINESS.md` for the retained helper protocol.
This README supersedes that older document's next-click-only behavior and finite
GUI lifetime assumption. Source implementation is not a native pass; the final
results report records actual first-Start and cancellation evidence separately.

## Focused developer check

`check_xvf_start_continuation.py` uses the actual backed Manager methods and
unit-policy check with synthetic subprocess/ownership/recovery callbacks. It
checks asynchronous continuation, prior-fault preflight, fresh Start state,
Stop/Exit cancellation, no lease release before helper join, unsafe-fault
rejection, and manual/finite service lifetimes. It performs no SSH, audio,
firmware, model or GUI operation and cannot establish a native microphone pass.
It sets CPU14 before project reads and writes one unique private result directory
under `live-runtime-20261003/audit-preparation`, bounded to2MiB/600seconds with
independent source restore copies. No input arguments are required.

PowerShell:

```powershell
$checkRoot = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$checkRoot\check_xvf_start_continuation.py"
```

CMD and Anaconda Prompt (use the existing interpreter; install nothing):

```bat
set "CHECK_ROOT=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%CHECK_ROOT%\check_xvf_start_continuation.py"
```

Output includes `REGISTERED_OWNER.json`, `HOST_SCOPE.json`, backed sources and
independent restores, `SOURCE_CLOSED.json`, and `RESULT.json`. Synthetic native
owners stay within temporary fixtures and are removed before the result is
published. The check is intended once for this changed path; native first-Start
and microphone verification remain separate root-operated checks.
