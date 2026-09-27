# V10 application setup and lease-open diagnostics

Purpose: preserve useful evidence when application setup fails and remove the
unnecessary filesystem resolution immediately before opening a renewable lease.
V9 stopped after one collected cell when its second child reported WinError 2
before constructing the application. The exact call site was not captured.
A filename may change while Windows resolves the directory entry to its target;
the new reader opens the already admitted absolute pathname in one CreateFileW
operation. No missing-file retry, permission override, new lease, expiry change,
or model/runtime setting change is introduced. The existing 5-second lease,
source/ownership/path containment checks and shared-read flags are unchanged.

V10 adds a bounded private failure phase/traceback (32 frames; no locals) and
reports the actual child setup error instead of attempting to read a nonexistent
application RESULT. Such failures still stop the whole run. Only the previously
qualified, independently verified closed lane timeout may continue, with zero
success credit. All prior sources and failed attempts remain immutable.

Inputs: qualified V9 ancestry, guarded V2 240-cell plan, exact interpreter,
existing saved audio/model/runtime bindings and fresh supervisor/resource census.
The development probe needs no model or GUI. Its 45 checks comprise 22 child
admission regressions, seven open-race/setup tests and 16 preserved failure tests.
It reconstructs the production plan and records both complete resource boundaries.
The concurrent fixture is at most 10,000 writes/30 seconds on one pinned CPU.

Outputs: fresh private probe with source snapshots, test log, concurrent-open
receipt, failed-cell reread and guard receipts. A closed passing probe can support
APPLICATION_FAMILY_CHECK_V10.json. The actual run retains the original 2-GiB,
four-hour ceiling and fixed panel population. Matching full outcome/transport/
content/naming consumers and continuity/restart remain required for acceptance.
Development tests and a finished collection queue do not accept N4 or N5.

## PowerShell

Only use the existing supervisor after all previous exact host/driver/job owners
are closed, no competing runtime is active, and fresh complete resource admission
passes. Write an immutable worker spec and dispatch admission, then call its
existing start interface. Do not directly start a second panel or mutate ledgers.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
Get-Content '..\..\..\..\..\local\supervision\worker.json'
Get-Content '..\..\..\..\..\local\n4\application-setup-v1-probe-worker.json'
```

The probe spec argv is the exact qualified Python executable, `-B`, absolute
`probe_application_setup_v1.py`, `--plan <qualified PLAN.json> --output <fresh
probe directory>`. Cwd is this n4 directory. Dispatch uses worktree PYTHONPATH.
After successful qualification and exact owner closure, the run spec substitutes
`paced_application_runner_v10.py run` with the same plan and fresh output.

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -c "import sys; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent/'supervision')); from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path('../../../../../local/supervision').resolve(),Path('../../../../../local/n4/application-setup-v1-probe-worker.json').resolve()))"
```

## CMD / Anaconda Prompt

Use the same checked admission and exact executable; no conda reinstall is needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
type ..\..\..\..\..\local\supervision\worker.json
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -c "import sys; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent/'supervision')); from metric_process import pin; pin(); import supervisor; print(supervisor.start(Path('../../../../../local/supervision').resolve(),Path('../../../../../local/n4/application-setup-v1-probe-worker.json').resolve()))"
```

Follow progress JSON and the exact supervisor identity. Do not edit bound files
or run Python/WSL/QEMU tests during paced evaluation. Keep raw evidence, audio,
models and profiles private. Pi connection and live CM5 validation stay deferred.
Preserve the September 28 02:48:19 UTC packaging reserve and 14:48:19 deadline.
