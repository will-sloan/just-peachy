# N1 code supervisor

Purpose: durable campaign status, ETA, one-writer/worker locks and independent
background workers. `supervisor.py` uses existing Python/psutil. It does not call
an LLM, control a desktop, open a microphone or contact the Pi. The exact current
Codex session ID is recorded in structured review requests. Automatic CLI resume
is deliberately unavailable without a verified atomic cross-turn idle/queue guard;
numerical work still finishes/checkpoints independently. Requests are queued for
manual review. No ambiguous `--last`, security bypass or competing resume is used.

Inputs: explicit state root; campaign start UTC and session ID; worker JSON with
`argv` list and `cwd`; worker-produced `panel_progress.json` with completed, total
and elapsed_seconds. Outputs in the external state root: campaign.json,
worker.json, status.json, logs, probe receipts and bounded review-request deltas.
Review requests contain state/errors, not transcripts or personal profiles.

OS tasks run every 10/15/30 minutes for setup/inference/replay respectively. Each
probe checks its expected phase; only the current phase aggregates status. All
use one OS-held writer lock and Scheduler `IgnoreNew`. A running host has a
separate OS lifetime lock. Process identity includes creation time to protect
against PID reuse. Healthy unchanged status does not enqueue another review.
Changed/error/completion states enqueue a small request without invoking an LLM.
Hosts refresh their heartbeat every five seconds and run at Below Normal priority
on at most two CPU logical processors. Original data and other jobs are untouched.

PowerShell (no activation needed):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\supervision'
$jpState='G:\Just_Peachy_N1\20260924_campaign\local\supervision'
& $jpPython -B "$jpCode\supervisor.py" init --root $jpState --thread-id 01a0d3df-f647-75f1-bd82-aab88c1f570b --started-utc 2026-09-24T14:48:19.949192+00:00
& "$jpCode\register_supervisor.ps1" -StateRoot $jpState
& $jpPython -B "$jpCode\supervisor.py" phase --root $jpState --phase inference
& $jpPython -B "$jpCode\supervisor.py" start --root $jpState --spec 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\supervision\baseline_worker_spec.json'
& $jpPython -B "$jpCode\supervisor.py" probe --root $jpState
& "$jpCode\register_supervisor.ps1" -StateRoot $jpState -Action Inspect
```

CMD / Anaconda Prompt:

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\supervision"
set "JP_STATE=G:\Just_Peachy_N1\20260924_campaign\local\supervision"
"%JP_PY%" -B "%JP_CODE%\supervisor.py" status --root "%JP_STATE%"
"%JP_PY%" -B "%JP_CODE%\supervisor.py" start --root "%JP_STATE%" --spec "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\supervision\baseline_worker_spec.json" --resume
powershell.exe -NoProfile -File "%JP_CODE%\register_supervisor.ps1" -StateRoot "%JP_STATE%" -Action Inspect
```

Resume uses the same checkpoint-aware worker command; it refuses an active owner.
Host identity is checked even after a terminal status is written, until the
lifetime lock is released. New hosts record child PID and creation time. A
surviving child blocks resume after unexpected host death; a missing/denied
identity or unfinished spawn fails closed for manual recovery. Legacy records
without child creation time are never assumed safe while that PID exists.
Confirm the specific owned process has ended before recovery; do not delete
locks or kill an uncertain process. STARTING and RUNNING both have watchdogs.
ETA excludes cached completions and remains unavailable until a measured
current-launch throughput interval exists. Completed work reports zero ETA.
Task registration uses the current logged-in user, Limited privileges and no saved
password. It does not wake or reboot the computer. Logged-out/sleep time is not
claimed to be supervised. A stale heartbeat flags review; no unrelated process is
killed. Startup refuses allocation below the configured disk reserves. Scheduled
probes stop only the verified owned worker tree if a reserve is breached and
request review; partial evidence stays for explicit checkpoint resume. Detection
occurs at the phase probe interval, so reserve headroom remains essential.

At campaign completion, after the worker ends, remove only owned tasks:

```powershell
& "$jpCode\register_supervisor.ps1" -StateRoot $jpState -Action Remove
```

CMD/Anaconda uses the same `powershell.exe -NoProfile -File` command above with
`-Action Remove`. The removal receipt verifies absence. Keep state/receipts and
checkpoints for audit; no recursive deletion is needed.

Process-contract tests (temporary isolated state only):

```powershell
& $jpPython -B "$jpCode\test_supervisor.py" -v
```

CMD/Anaconda: `"%JP_PY%" -B "%JP_CODE%\test_supervisor.py" -v`.
These start harmless child Python commands that deliberately exit 7, then resume
from a text checkpoint, and test interprocess overlap and lock cleanup. They do
not register tasks. Output is unittest text; the task-trigger/removal receipt is
tested separately with the reserved `JustPeachy-N1-20260924-test` task prefix.
The final N1 suite has10 tests, including startup death/staleness, surviving
child/PID-reuse/uncertainty guards and resumed-ETA arithmetic. The actual receipt
is `local/checks/supervisor-final-v3.txt`; earlier attempts remain local for audit.
