# Private Windows process lifetime

V3 preserves both earlier probes and their source snapshots. V1 reached empty
jobs but failed three assertions that assumed only Python processes were counted.
V2 recorded the actual system console helpers and exposed a brief process-table
lag after job accounting reached zero. V3 additionally waits, within the declared
cleanup deadline, for every observed exact member identity to disappear. Tests
require additional live fixture members to be the system `conhost.exe`, on CPU14.
Root-exit and parent-death tests still require the complete job to become empty;
console helpers are included in both cleanup and exit checks.

Purpose: `private_application_process_v3.py` starts a bound Python child suspended
on a new private desktop, places it in an owned Windows Job Object, verifies its
identity/command/CPU, and calls a registration callback before resuming it. It
owns cancellation and bounded cleanup of the job, including descendants that
remain after the root exits. The desktop is never switched to the input desktop.
No mouse, keyboard, microphone, audio, Pi or GPU device APIs are used.

Inputs: hashes of the executable and fixed child script, a fresh private output
directory, literal child arguments, CPU14 for development or CPU4 for a separately
admitted application, and a caller registration callback. Only CPU4/CPU14 are
allowed. The child starts below normal priority, with one math thread and CUDA
disabled in its environment. A job affinity limit also covers descendants. The
job allows at most 16 processes, has no breakaway flags and has a non-inherited
kill-on-close handle. It is a lifecycle mechanism, not a sandbox for untrusted
child code or a replacement for resource/production-plan admission.

Internal API: construct `PrivateApplicationProcess`, call `spawn_suspended()`,
then `resume(register)`. A future launcher must connect `register` to the admitted
`ExclusiveApplicationSlot.register_application`, check its production plan before
spawning, and check admission again in the child before model/source acquisition.
The current development probe does not acquire that slot. There is no CLI that
accepts arbitrary commands or starts the actual speech application.

`close(grace_seconds=2, force_seconds=10)` creates the owned `CANCEL` file. A
cooperating child must observe it and close its own source/application. After the
grace period, only this object's retained job handle is terminated. If job
assignment fails, only its just-created suspended process handle can be stopped.
The implementation queries active job processes until zero, verifies root exit
and waits for all observed exact member identities to disappear before releasing
handles. Job membership is read directly with a maximum of 16 active entries;
access-denied observations fail closed. Kill-on-close on an exceptional cleanup path is
containment, not proof of exit; a failed observation produces failed evidence.
No broad PID/name search or termination is performed. Input-desktop names before
and after are compared; that comparison does not claim to measure all focus or
all other host activity.

Outputs: one immutable `LIFETIME.json` per process lifetime with exact root
identity, source hashes, event chronology, final job accounting, exit code,
forced/graceful cleanup and input-desktop observations. Fixture directories also
contain small synthetic start/cancel/Tk receipts. All remain private. Failed
attempts and their source bindings must be preserved. No application resource
benchmark or successful source execution can be inferred from these fixtures.

`probe_private_application_process_v3.py` is the runnable entry point. It pins the
helper and all fixtures to CPU14, holds the existing metric helper lock, checks
disk/shared allowance/deadline, and verifies that the existing ASR model remains
on CPU4. It must not run during controlled whole-application measurement. It
creates a fresh private output with ADMISSION.json, tests.txt, seven lifetime
receipts, and RESULT.json or FAILED.json. Every attempt needs a new output name.
Eight tests cover suspended registration, real private-desktop Tk creation and
destruction, registration rejection, child exception, graceful cancellation,
forced root/descendant cleanup, orphan descendant cleanup after root exit,
last-job-handle cleanup after abrupt owner death, and invalid inputs. Descendant
fixtures have their own 15-second fallback bound in case a test fails.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpCode\probe_private_application_process_v3.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\private-process-probe-v3'
```

Command Prompt and Anaconda Prompt (invoke the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_CODE%\probe_private_application_process_v3.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\private-process-probe-v3"
```

Production application launch, real-source cancellation/drain, supervised slot
admission and N4 acceptance remain separate unexecuted gates. Do not use a passing
fixture receipt to start a second numerical worker or infer those gates passed.

API references: Microsoft documents [job object containment and lifetime](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[process creation flags](https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags),
[job limit structure](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_limit_information),
and [job accounting queries](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-queryinformationjobobject).
