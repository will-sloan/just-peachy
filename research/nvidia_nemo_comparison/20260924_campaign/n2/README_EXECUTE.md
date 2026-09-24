# Execute or observe the N2 numerical chain

`execute_campaign.py` joins the existing numerical coordinator to the offline finalizer. It verifies the frozen source, the complete isolated test suite through `check_suite.validate_completed_report`, and the exact nine-job population: 384 main Controller cells, 32 separate regression cells and six GUI cells. It performs no model calls itself. It never packages, commits, pushes, marks a project stage complete or invokes an LLM.

The v6 coordinator and its waiter ended after the preserved archive-integrity failure. The replacement coordinator started on 2026-09-24 at 18:24:56 UTC on v7 and fresh v2 result directories; its waiter attached at 18:25:23 UTC. **Do not start another copy while these owners are active.** This mode binds `state/worker_spec.json`, its exact coordinator/spec/output/state command, the supervisor host and child PID/creation times, and the existing coordinator admission. It observes that exact child every five seconds. It neither stops nor launches a coordinator and never substitutes a process whose PID has been reused. After the process ends, it requires the supervisor's successful zero-exit receipt, releases no locks belonging to another process, verifies the coordinator's complete 422-cell evidence, then launches `finish_campaign.py`. A transient gap before the supervisor writes the exit receipt is bounded to 30 seconds.

Without `--wait-for-existing`, the wrapper starts `run_campaign.py` as its owned child and waits for its exit before running the finalizer. This optional mode is for a separately authorized future launch or safe resume. The coordinator's existing cache owns job reuse; completed GUI jobs are not launched again. A nonzero coordinator exit or incomplete coordinator receipt prevents finalization.

Inputs are explicit `--spec`, `--output` (coordinator directory), `--state` (existing supervisor state directory), `--source-receipt`, `--test-report`, `--analysis-output` (fresh private finalizer directory) and `--public-out`. The GUI report is derived from the exact `gui-panel` job; no separate guessed path is accepted. Inputs, interpreter, wrapper, coordinator, finalizer, evaluation modules and I/O/supervisor helpers are hash-bound before execution. Each subprocess uses a structured argv list, private redirected logs, hidden Windows windows and BelowNormal priority. The wrapper allows CPUs 4 and 14; the coordinator retains its declared lanes and the finalizer chooses CPU 4. Its fresh coordinator timeout is the longest sum of declared lane timeouts plus 120 seconds; offline finalization is bounded to 7200 seconds.

Outputs stay in the private coordinator directory: `CHAIN_RESULT.json`, `chain.owner.lock` and `chains/<contract SHA-256>/CHAIN_ADMISSION.json`, `CHAIN_RESULT.json`, `coordinator.log` when launched, and `final_checks.log`. Different finalizer destinations receive distinct frozen chain admissions while preserving the same coordinator cache. A held lifetime lock, live/unverified prior chain child or changed contract prevents duplicate ownership. An interrupted waiter does not affect the externally supervised numerical process. The waiter stops itself on the existing packaging cutoff or a disk-reserve breach and records `INCOMPLETE`; it leaves the external process untouched.

Finalizer outputs are documented in `README_FINISH.md`: private analysis evidence and redacted `SCREEN_SUMMARY`, `REGRESSION_SUMMARY` and `FINAL_CHECKS` JSON/Markdown. Existing finalizer outputs are preserved. A failed or interrupted finalizer requires new private/public destinations before another attempt. An identical already successful chain verifies its saved report hashes and returns without another finalizer launch. Chain status is `INCOMPLETE` after coordinator/admission failure, `FAILED_FINAL_CHECKS` after finalizer failure, and `READY_FOR_REVIEW` only after a zero finalizer exit plus passing bound reports. The latter is a review handoff, not a stage-completion claim.

## Current replacement-coordinator invocation

Do not start a second copy if the root-owned waiter is running. These commands wait in the terminal, while their subprocess windows stay hidden. The campaign root owns background dispatch. After it starts the v7 coordinator with `numerical-spec-v4.json` and `numerical-v2`, this command adds only a lightweight waiter and, after a successful coordinator exit, offline final checks. The plan must have been generated with `--run-version v2`; all 384 main, 32 regression and six GUI cells rerun under the new common source. Preserve the earlier `numerical-v1`, v1 result roots and recovery receipts.

PowerShell, from any directory:

```powershell
$N2Dir = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2'
$PythonExe = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $PythonExe -B "$N2Dir\execute_campaign.py" --wait-for-existing --spec 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v4.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-v2' --state 'G:\Just_Peachy_N1\20260924_campaign\local\supervision' --source-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\SOURCE_RECEIPT.json' --test-report 'G:\Just_Peachy_N1\20260924_campaign\local\n2\checks\full-suite-isolated-v3\RESULT.json' --analysis-output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\final-analysis-v2' --public-out "$N2Dir\evaluation"
```

Command Prompt / Anaconda Prompt (the explicit interpreter avoids changing conda):

```bat
set "N2_DIR=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n2"
set "PYTHON_EXE=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PYTHON_EXE%" -B "%N2_DIR%\execute_campaign.py" --wait-for-existing --spec "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-spec-v4.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\numerical-v2" --state "G:\Just_Peachy_N1\20260924_campaign\local\supervision" --source-receipt "G:\Just_Peachy_N1\20260924_campaign\local\releases\n2-common-v7\SOURCE_RECEIPT.json" --test-report "G:\Just_Peachy_N1\20260924_campaign\local\n2\checks\full-suite-isolated-v3\RESULT.json" --analysis-output "G:\Just_Peachy_N1\20260924_campaign\local\n2\final-analysis-v2" --public-out "%N2_DIR%\evaluation"
```

## Focused verification without numerical jobs

`test_execute_campaign.py` checks exact population/source admission, strict supervisor command and process identity binding, sequential phase order, nonzero/partial failures, report preservation, live-owner rejection, read-only waiting and disk/deadline behavior. One real temporary Python child only prints text; it verifies actual Popen exit/identity handling. Other launches are mocked. These tests never start the coordinator, GUI, finalizer or models and do not touch campaign state.

```powershell
& $PythonExe -B -m unittest discover -s $N2Dir -p 'test_execute_campaign.py' -v
& $PythonExe -B "$N2Dir\execute_campaign.py" --help
```

```bat
"%PYTHON_EXE%" -B -m unittest discover -s "%N2_DIR%" -p "test_execute_campaign.py" -v
"%PYTHON_EXE%" -B "%N2_DIR%\execute_campaign.py" --help
```
