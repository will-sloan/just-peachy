# One guarded main-score review handoff

## Purpose

`advance_main_score_review_v1.py` waits for this exact main scorer and starts
the existing independent score reviewer once. It saves the delay until the next
hourly assistant check. It does not change that schedule, invoke an LLM, modify
the shared ledger by hand, change the scorer, or mark a stage accepted.
It uses the existing supervisor's `start` interface and its writer/lifetime
locks. A separate OS-held handoff lock prevents duplicate waiters.

The handoff binds the supervisor run ID, supervisor and venv-launcher PID plus
creation time, the actual Python driver beneath that launcher, the immutable
scoring admission, exact worker command and qualified source. Healthy RUNNING
state only waits. Stale heartbeat, changed owner/command, AccessDenied,
failed/partial scoring, a foreign output, a missing row or an unresolved
metric child stops the handoff with preserved failure evidence. PID reuse does
not substitute a live owner for the original identity.

It requires all 7,680 scored rows, zero failed/untested/unavailable prediction
scores, null stop reason, bound complete report and stopped exact metric
owners/closed pipes for 7,680 requests. Each score/report hash is checked before
dispatch. The existing reviewer then independently checks inputs and totals.
A dispatched review is not a passed review or N4/N5 acceptance.

## Inputs and outputs

Inputs: `local/n4/integrated-main-scores-v3/ADMISSION.json`, its future sealed
RESULT/report/score files, `integrated-main-scoring-worker-v3.json`, current
supervision, `SCORING_HISTORY_CHECK_V3.json`, and the handoff's own passed
`SCORE_REVIEW_ADVANCE_CHECK_V1.json`. The latter is sealed only after the
development test process exits. No model, audio, device, Pi or GUI is opened.

Use a fresh output such as `local/n4/main-score-review-advance-v1`. It contains
ADMISSION with exact owners, three source snapshots, preserved prior supervision
and log, READY, an immutable `review_worker.json`, and RESULT or FAILED.
The reviewer writes separately to `local/n4/integrated-main-score-review-v3`.
Never overwrite either directory or retry an ambiguous dispatch. First inspect
current supervision and the exact original processes, including venv children.
An hourly follow-up must inspect this handoff before attempting manual dispatch.

The waiter pins itself to CPU14/BelowNormal with one math thread and GPU off.
It polls at most once per minute, for at most five hours, and stops at the
existing packaging reserve. It preserves the 50-GiB allowance, C50/G75-GiB
drive floors and its 8-MiB output bound. Inventory is checked before waiting
and again before dispatch; disk/deadline/source/ownership gates remain active.
The inherited reviewer retains its own two-hour, 8-MiB and metric-writer guards.
No healthy scorer is interrupted and no process is killed by this waiter.

## PowerShell

The following runs in the current shell. Campaign background dispatch uses
CREATE_NO_WINDOW; do not open a visible shell or launch a duplicate waiter.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpN4\advance_main_score_review_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\main-score-review-advance-v1'
```

## CMD and Anaconda Prompt

Use the admitted interpreter without installing or changing packages:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_N4%\advance_main_score_review_v1.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\main-score-review-advance-v1
```

## Development checks and limits

`test_score_review_advance_v1.py` exercises exact PID/creation/run-ID changes,
all three still-live owner positions after terminal publication, healthy and
stale supervision, pending launch, access denial, unsuccessful exits, complete
population and missing/foreign/duplicated score/report/admission cases. It calls
the real qualified terminal validator over synthetic metadata. It does not
start a supervisor, metric process, reviewer, model or application. Tests are
guard checks, not completed production handoff or scoring acceptance.

PowerShell uses the same variables above:

```powershell
& $jpPython -B -m unittest discover -s $jpN4 -p test_score_review_advance_v1.py -v
```

CMD/Anaconda: `"%JP_PY%" -B -m unittest discover -s "%JP_N4%" -p test_score_review_advance_v1.py -v`.
For qualification, retain the log, exact source bindings, test count and test
owner in a fresh private receipt, then verify its exit before sealing the public
qualification. Failed attempts must remain available. Never put private scores,
captions, audio, profiles or model weights in Git. The Pi remains offline;
live CM5 validation is deferred. Packaging reserve and deadline remain
2026-09-28 02:48:19 and 14:48:19 UTC respectively.
