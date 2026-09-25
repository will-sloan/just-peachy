# Supervised application panel runner

Purpose: `paced_application_runner.py` connects the complete reviewed panel plan,
exclusive parent slot, suspended private-desktop launcher, renewable child gate
and actual ApplicationCell source/drain path. It supplies one fixed coordinator
and one fixed child entry point. No worker starts from the development probe.
The production admission, supervised launch and real application-source branches
remain unexecuted until the full reviewed comparison inputs and exclusive slot
are available. Implementation and passing model-free tests are not N4 acceptance.

Inputs: a PLAN.json produced by the qualified paced panel planner from both full
main/mode scoring reviews, the exact qualified application Python interpreter,
unchanged frozen source/models/galleries/runtimes, existing supervision and a
fresh private run directory. `prepare` reconstructs the full plan from its passed
reviews, selection and preparation, rejects an active planner or changed source,
and binds runner code, prerequisite qualifications, interpreter and all inputs.
It writes ADMISSION.json and worker.json without launching a child or model.

`run` requires the exact supervised direct CPU14 coordinator; an ordinary shell
invocation cannot become that owner. It waits up to eight seconds for the existing
supervisor's child-registration publication, then holds a run writer lock and
revalidates the full plan. Every cell acquires its own exclusive slot and starts
one fresh CPU4 child below normal on a new private desktop. The suspended child
is registered before the parent writes its first permission lease and resumes it.
Only the planner's input allowlist enters the child. The full plan, comparison
reports, truth and selection rationale remain coordinator/evaluator metadata.

The coordinator renews the lease every 250 ms only after a successful slot check.
The child verifies actual desktop/identity/commands, then primes source and asset
bindings before importing the frozen app. It creates the actual Controller/Tk,
prepares the fixed roster/mode/tap, starts the saved source and always calls close,
including preparation/startup failures. It checks the lease and admission through
the existing source callback. No microphone enumeration, capture, playback,
training, human enrollment, Pi operation or desktop input/focus control is used.

Maximum child lifetime is the smaller of 3,900 seconds and source seconds times
25 plus 480 seconds. The parent polls root exit before checking ownership and
handles only the specific root-exit race; other resource/ownership failures
propagate. Finally, cancellation is the transport CANCEL file, followed by up to
150 seconds for graceful application shutdown and the launcher's bounded owned-job
cleanup. The slot is explicitly released only after verified empty job, root exit
and observed descendant exit. Failed cleanup records failure and does not report
a slot release. No process name/bare PID is used for termination.

Per-cell output is at most the slot's 512-MiB reservation, checked periodically;
each fresh admission rechecks the shared 50-GiB allowance with the conservative
6-GiB pending reserve and C50/G75-GiB floors. This is not an OS disk quota. Existing
bounded journal/resource writers remain necessary. The original packaging cutoff
applies to parent and child. One candidate runs at a time; unrelated user programs
are not stopped. The conservative runtime census can refuse admission when a
possible competitor cannot be inspected. Such uncertainty must be resolved or
remain an explicit blocker; never bypass it or disturb the user's other work.

Outputs: private RUN_OWNER.json, immutable per-cell progress receipts, each
cell's transport INPUT/PERMIT/LEASE/CHILD_RESULT/LIFETIME records, ApplicationCell
source/engine/archive/viewport/resource evidence, COLLECTED.json and
PARENT_CLOSURE.json, plus terminal RESULT.json. Any first failed cell stops the
run and preserves prior results and the failed attempt. There is no in-place
retry/resume. A fresh derivative must be reviewed to avoid corrupting evidence.
All transcripts, audio-derived observations and research profiles stay private.

COLLECTED_PACED_APPLICATION_PANEL_REQUIRES_REVIEW means only that the declared
panel/repeat cells collected and closed. It grants zero integrated N4 acceptance.
Content/naming/visibility/timing/resource review, other mode/release checks and
the separate 20-minute continuity sequence remain required. The prepared panel
has 40 cells per candidate and explicitly does not include continuity.

The development probe exercises 11 tests with model-free doubles for coordinator
and ApplicationCell execution. They verify parent check-before-renewal order,
guard failure, timeout, the precise root-exit race, successful/failed cleanup,
slot retention on unverified descendants, child prime/prepare/run/close order,
close after preparation failure and refusal of missing production input. A real
private-file lease writer round trip uses a synthetic permit and the CPU14 test
helper, checking atomic replacement and rollback refusal. It is not a successfully
supervised lease or application run. Existing native job/Tk lifetime qualification
is reused, not rerun or relabeled as production evidence.

The probe runs on CPU14 with the existing helper lock, verifies the current CPU4
ASR owner and resource/deadline policy, and writes immutable source snapshots,
ADMISSION.json, tests.txt and RESULT.json or FAILED.json. Do not run the probe
during controlled application measurements. Every attempt needs a new output.

PowerShell model-free probe:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_paced_application_runner.py" --output "$jpLocal\n4\paced-runner-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_paced_application_runner.py" --output "%JP_LOCAL%\n4\paced-runner-probe-v1"
```

After both full score reviews pass and a reasoned production selection is prepared,
use its actual plan path in these preparation examples. These paths are reserved
examples, not evidence that a production plan/run exists:

```powershell
& $jpPython -B "$jpCode\paced_application_runner.py" prepare --plan "$jpLocal\n4\paced-panel-plan-v1\PLAN.json" --output "$jpLocal\n4\paced-panel-run-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\paced_application_runner.py" prepare --plan "%JP_LOCAL%\n4\paced-panel-plan-v1\PLAN.json" --output "%JP_LOCAL%\n4\paced-panel-run-v1"
```

Only after fresh ownership checks establish that component/scoring workers have
exited, use the existing supervisor from CPU14 to start the prepared worker. Keep
the current helper itself out of the competing-runtime census by using the
existing start interface, then exit that launcher shell promptly:

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase replay --stage N4
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\paced-panel-run-v1\worker.json"
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase replay --stage N4
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\paced-panel-run-v1\worker.json"
```

Do not call `child` by hand, alter the shared ledger, create a second worker, or
edit any bound source to get around a refusal. Source/runtime repairs require a
new derivative with new hashes and the relevant retests.
