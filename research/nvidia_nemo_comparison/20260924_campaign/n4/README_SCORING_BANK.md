# Bounded scoring of closed modeled method banks

Purpose: `scoring_bank.py` scores the full declared method population after
prediction has stopped. It imports no application/model/GUI code. It validates
the exact terminal owner, admission, plan, frozen implementation, source files,
component bindings and full 7,680-cell main or 1,536-cell mode-panel census.
A complete bank requires its passed method review. A preserved failed bank may
be scored without pretending it passed: only its sealed prefix is converted,
with the exact failed and not-tested counts retained for the rest of the plan.
An active bank, changed artifact or silent reduction of the plan is rejected.

Inputs: immutable method-bank RESULT/ADMISSION/plan, optional complete-bank
review, full compressed publication and Controller artifacts, matching speaker
events and the frozen evaluator-only truth/strata. The original 480 audio jobs
must match the frozen preparation. Hash/CRC/expanded-size checks and actual
consumer/worker closure precede conversion. References never enter inference.

`metric_process.py` hosts the unchanged pinned established scorers in one
persistent subprocess. Requests bind sequence, SHA-256 and exact PID/creation
identity. Both the Windows venv launcher and its actual direct interpreter
child are tracked. A timeout terminates only those exact owned processes,
verifies exit and drains pipe threads. It never stops a process by name or
reused bare PID. Input is at most 16 MiB, a response 2 MiB, and retained stderr
64 KiB. Library stdout is redirected away from the JSON protocol. Exceptions
return only their type, not reference text. No models are loaded.

The parent and child use CPU14, below-normal priority, single-thread math and
GPU disabled. Launches use CREATE_NO_WINDOW. One Windows file lock excludes
duplicate scorer drivers/probes. These helpers may coexist with the separately
owned CPU4 collection worker, but must not run during controlled complete-stack
resource/timing measurements. The default per-cell timeout is 60 seconds,
maximum 120; default total scoring budget is four hours. It stops new scoring
at the original packaging reserve. After three consecutive conversion/metric
errors it accounts for remaining predictions without repeated worker restarts.
Successful predictions with unavailable metrics retain execution COMPLETE;
they do not become empty hypotheses or failed inference. Missing metric and
failed/not-tested execution denominators are reported separately.

Each new run needs a fresh private output below local/n4. A 512-MiB output
budget, C50/G75-GiB floors, the existing 50-GiB shared allowance and conservative
6-GiB pending reservations are checked; no new payload allowance is created.
The existing exact metric environment is verified once per parent startup.
Failed runs/artifacts are preserved; use a derivative for fixes or retests.

Outputs: ADMISSION.json, one cells/NNNNN.json per required plan cell, REPORT.json
and RESULT.json. Unexpected scorer failure writes FAILED.json with the sealed
prefix and unaccounted count. A normal partial report preserves missing metric
reasons, execution failures and not-tested rows. All detailed results stay private.
No production scoring is admitted until the corresponding terminal prediction
bank exists; helper tests and development probes are not matrix execution.

`scoring_report.py` pools integer edit counts by composition, mode and tap,
with reference/room/family/actor/SNR/orientation/short-turn strata. Empty-control
insertions use summed duration; estimated activity uses summed metric components.
Primary WER remains nonoverlap-only; cp/MIMO retain their distinct scopes.
Baseline-paired counts require matching scene/tap reference denominators;
excluded pairs remain explicit. Both taps stay in the same dependency cluster,
with the original 2,000-replicate bootstrap and room/actor/family sensitivity.
Fewer than eight clusters suppresses intervals. These are seen-bank descriptive
comparisons, not unseen-population validation. Naming, widget latency, complete
Controller/source parity, physical resources and N4 acceptance remain unavailable.

PowerShell from the campaign worktree (examples refer to future bank outputs):

```powershell
$jpMetrics='G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpMetrics -B "$jpCode\test_scoring_bank.py" -v
& $jpMetrics -B "$jpCode\probe_metric_process.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\metric-process-probe-v1'
& $jpMetrics -B "$jpCode\scoring_bank.py" --run 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-v1' --review 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-review-v1.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v1'
```

Command Prompt / Anaconda Prompt (use the isolated interpreter directly; no
installation into the active app environment):

```bat
set "JP_METRICS=G:\Just_Peachy_N1\20260924_campaign\local\n4\metrics\env\Scripts\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_METRICS%" -B "%JP_CODE%\test_scoring_bank.py" -v
"%JP_METRICS%" -B "%JP_CODE%\probe_metric_process.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\metric-process-probe-v1"
"%JP_METRICS%" -B "%JP_CODE%\scoring_bank.py" --run "G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-v1" --review "G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-review-v1.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v1"
```

For a FAILED_PRESERVED method bank omit --review and choose a new private output.
Never pass a review for another plan/run. --cell-timeout and --max-seconds can
reduce the fixed bounds; larger values are capped at 120 seconds and four hours.
Inspect partial status and denominators before comparing or selecting candidates.

The tests use dictionary plans and protocol fault fixtures, plus actual established
scorers on dictionary references. They exercise full matrix census, changed keys,
partial denominators, count-weighted pairs, exact process exit, hung/failed native
call boundaries, malformed/oversized/EOF responses and bounded stderr. The internal
fixture mode exists only in the test script; it is not a production worker option.
`probe_metric_process.py` reuses the 51 already-scored saved checks and requires
bit-for-bit metric-object parity through the persistent process, including every
successful empty control. It creates no new model inference or independent scenes.
