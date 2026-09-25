# Supervised application runner V2

Purpose: `paced_application_runner_v2.py` uses the qualified V2 panel planner's
production reconstruction and child allowlist to run the separate complete-log
application derivative. It preserves the V1 runner and receipts. The component
source and application derivative stay explicitly joined through the qualified
source context. Passing the model-free probe does not accept an application run.

Inputs: a real `PLAN.json` prepared by `paced_panel_plan_v2.py` after both full
main/modes scoring reviews, exact qualified interpreter, bound source/assets,
gallery/runtimes, existing supervision and a fresh private output directory.
`prepare` writes schema `n4-paced-application-run-v2` ADMISSION.json and worker.json
without starting a process or model. `run` requires its registered supervisor and
CPU14 coordinator. It starts one suspended CPU4 child on an owned private desktop,
registers its exact identity, writes the first lease, then resumes it. The child
does not call the CPU14 helper pin function. It primes bindings before importing
the application, prepares Controller/Tk, runs the saved source and always closes.

The unchanged exclusive slot, interpreter, private Job Object and child admission
guards retain their qualified limits: one model owner, one math thread, GPU off,
C50/G75-GiB floors, private 50-GiB allowance plus conservative 6-GiB reserve,
512-MiB per-cell reservation, 250-ms gated lease renewal, bounded shutdown and the
original packaging cutoff. Unknown possible competitors cause refusal; do not
bypass that gate or stop unrelated user programs. No visible desktop, focus/input
control, capture, device enumeration, playback, training or Pi access occurs.

After normal child/job closure, a new parent-side gate binds ENGINE_CLOSURE.json
to the planned audio-only job and engine. It requires a direct native session
under that cell's `application/data/sessions` directory without reparse paths.
The qualified journal reader reconstructs the complete event sequence, source
start, terminal event, clock ordering and drained queue census. Its bounded read
allows at most 256 MiB and 500,000 records. A well-formed incomplete journal is
saved in NATIVE_JOURNAL_ENVELOPE.json before rejection; malformed evidence also
fails collection. No incomplete cell is added to COLLECTED.json or progress.
The parent still releases the slot only after verified process/job closure.

Outputs: immutable private RUN_OWNER.json, transport records, application source,
closure/archive/viewport/resource evidence, NATIVE_JOURNAL_ENVELOPE.json,
COLLECTED.json, PARENT_CLOSURE.json, progress and terminal RESULT.json. The envelope
receipt records hashes/counts and source-path metadata, not transcript text.
Underlying event logs remain private. A failed attempt is preserved; use a fresh
directory for an admitted retry. Collection remains **zero accepted integrated
N4 cells** until independent full review. Native payload semantics, raw text,
naming, source-to-widget timing, full population selection, controlled resources,
continuity and stop/restart still require implementation or execution/review.
The V1 transport reviewer expects the V1 runner; a qualified V2 reviewer is needed.

The CPU14 development probe holds the existing helper lock, verifies the exact
healthy D1 owner and all its protected bindings before/after, checks resource
limits, snapshots the four new files and binds all dependencies. Sixteen tests
exercise model-free coordinator/child doubles, real synthetic-permit lease
writes, cleanup/renewal failures, V2 missing-plan refusal and real synthetic native
journal parsing. They test complete logs, preserved truncated-log rejection,
foreign/nested session rejection and mismatched jobs/engines. No child, application,
model or saved-audio source is launched by this probe. Production admission and
the actual source branch remain unexecuted. Run each attempt in a fresh directory;
do not run development probes during controlled application measurements.

PowerShell:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_paced_application_runner_v2.py" --output "$jpLocal\n4\paced-runner-v2-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_paced_application_runner_v2.py" --output "%JP_LOCAL%\n4\paced-runner-v2-probe-v1"
```

Only after the full scoring reviews, actual selection/plan and this runner's
qualification exist, prepare with the real plan path. The paths below are reserved
examples, not a claim that a production plan or run exists:

```powershell
& $jpPython -B "$jpCode\paced_application_runner_v2.py" prepare --plan "$jpLocal\n4\paced-panel-plan-v2\PLAN.json" --output "$jpLocal\n4\paced-panel-run-v2"
```

```bat
"%JP_PY%" -B "%JP_CODE%\paced_application_runner_v2.py" prepare --plan "%JP_LOCAL%\n4\paced-panel-plan-v2\PLAN.json" --output "%JP_LOCAL%\n4\paced-panel-run-v2"
```

When existing numerical/scoring workers have verifiably exited and the resource
slot is free, use the existing supervision interface; do not start another worker
or hand-edit its shared ledger. Exit the launcher promptly after dispatch:

```powershell
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" phase --root "$jpLocal\supervision" --phase replay --stage N4
& $jpPython -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "$jpCode\..\supervision\supervisor.py" start --root "$jpLocal\supervision" --spec "$jpLocal\n4\paced-panel-run-v2\worker.json"
```

```bat
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" phase --root "%JP_LOCAL%\supervision" --phase replay --stage N4
"%JP_PY%" -B -c "import psutil,runpy,sys; psutil.Process().cpu_affinity([14]); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')" "%JP_CODE%\..\supervision\supervisor.py" start --root "%JP_LOCAL%\supervision" --spec "%JP_LOCAL%\n4\paced-panel-run-v2\worker.json"
```

Do not invoke `child` manually or modify bound code after qualification. Repairs
require a new derivative and relevant retests. Preserve all V1 evidence.
