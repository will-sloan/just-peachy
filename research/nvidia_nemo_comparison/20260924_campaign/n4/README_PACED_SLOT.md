# Exclusive application ownership and resource guard

Purpose: `paced_slot.py` supplies a fail-closed guard for a future supervised,
source-paced application launcher. It checks exact PID/creation identities,
direct supervisor/coordinator/application ancestry, CPU affinity, fresh
heartbeat/run identity, known competing runtimes, output/disk capacity and
the original deadline. It does not start, signal, kill or modify a process,
change the shared supervisor ledger, reserve a GPU or authorize source execution.

Inputs: existing private supervision state, a fresh private N4 cell output,
the caller's actual identity and the future exact child executable/command
binding. The supervisor and coordinator must be CPU14; the one registered
direct application child must be CPU4. All Python, WSL/QEMU and known native
speech processes outside those exact identities are competing owners. A shell
mentioning this campaign and a Python script is also a helper. Access denial
for a possible competitor fails closed; a reused bare PID is not an allowed
owner. Nothing here requests or inspects microphone, USB or GPU devices.

This is a conservative known-runtime census, not proof that unrelated user
applications or every possible native program are idle. The future resource
report must retain that host-load limitation. The guard deliberately does not
stop other tasks or take over the desktop to produce better measurements.

`ExclusiveApplicationSlot(state, output)` is an internal API, with no neural
launch CLI. `acquire()` is called only from the exact already-supervised
coordinator after it has validated the full production panel plan and fixed
launcher code. It holds the private application and existing scoring OS locks,
rechecks the full shared payload allowance, and returns an observation receipt.
`register_application(owner, executable_binding=..., argv_sha256=...)` checks
the exact direct child after the future launcher has started it suspended and
pinned it. The launcher must control the spawn/register/resume interval and
must recheck admission in the child before any model/source acquisition.
`check()` rechecks ownership, competing runtimes and resources during execution.
`release()` refuses a live registered application and retains its locks on that
failure. The future launcher remains responsible for graceful cleanup and exact
process-tree cleanup on failure; this guard is not that cleanup implementation.

The guard admits at most 512 MiB per cell on top of the existing conservative
6-GiB pending reservations inside the shared 50-GiB allowance. It checks C50/G75
GiB free plus the cell reservation, rejects reparse points in cell outputs,
limits the output file census to 10,000 and scans cell output size every five
seconds. This is periodic refusal, not an OS-enforced disk quota. Source/log
writers still need their own bounds. The original September 28 packaging
cutoff cannot be extended by a later changed policy file. Full private payload
inventory occurs before cell admission, not on every source callback.

Outputs: API receipts and explicit exceptions; no supervisor mutation or worker
launch spec. `probe_paced_slot.py` writes private ADMISSION.json, tests.txt and
RESULT.json (or preserves FAILED.json). It runs nine tests and observes the
currently healthy ASR coordinator/model, proving both are detected as conflicts
for an unsupervised application helper. It does not acquire a real application
slot or launch a child. Its active-ASR expectation is deliberate: a later run
after a stage transition requires a fresh qualified probe, not edited evidence.

Tests include stale/future heartbeats, changed run/PID/parent/affinity, uncertain
ownership, competing helpers, original cutoff preservation, CPU/GPU/disk limits,
fresh output boundaries, an actual OS lock collision/release, refusal to release
while a current process is alive, and a read-only census of the test interpreter.
These qualify the guard only. Successful supervised admission, private process
spawn/suspension/resume, actual model/source execution, graceful or forced child
tree cleanup, application resources and N4 acceptance remain unexecuted.

PowerShell (model-free tests/probe only):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpCode\test_paced_slot.py" -v
& $jpPython -B "$jpCode\probe_paced_slot.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-slot-probe-v1'
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_CODE%\test_paced_slot.py" -v
"%JP_PY%" -B "%JP_CODE%\probe_paced_slot.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\paced-slot-probe-v1"
```

The probe pins CPU14 below normal, uses one math thread/GPU disabled, holds the
existing metric helper lock and respects the shared resource/deadline guards.
It may coexist with CPU4 component collection, but must not run during controlled
whole-application measurements. Every attempt needs a new output directory;
preserve failures and code bound to receipts. No passing fixture may substitute
for the future launcher's actual source, process ownership or shutdown evidence.
