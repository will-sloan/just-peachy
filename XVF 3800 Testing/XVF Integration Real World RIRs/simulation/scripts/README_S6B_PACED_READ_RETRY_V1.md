# Paced coordinator status-read repair, version 1

`s6b_paced_read_retry_v1.py` repairs one observed transient Windows sharing denial
while the original coordinator read `LIVE.json`. The first two paced cells
completed. The third, B10_S45_01_06_O0_R1, was interrupted after about20seconds;
its failure receipt, partial session, resource samples and source remain in
`paced_finalists_epoch2_v1`. The owned worker/helper and coordinator closed.
This is an orchestration recovery, not a model or accuracy-driven retry.

The wrapper hash-checks the unchanged original `s6b_paced.py` before import and
replaces only that module's coordinator JSON-reader function. It retries only
`PermissionError`, at most20attempts with at most0.95seconds scheduled sleep and
a1second deadline checked before every retry and after logging. An OS read
itself cannot be preempted; oversleep cannot authorize another read.
Missing files, invalid JSON, semantic errors and persistent denial still fail.
Every denial/recovery logs its path, time, retry count and measured delay.
Each backoff records scheduled and measured sleep; cumulative totals remain in
the wrapper completion receipt. Missed observer samples are not interpolated.
The native child argv still names the original frozen driver, whose `__file__`
is preserved. APP, profiles, models, source pacing, endpoints and scheduler are
unchanged. Original worker status writes are not patched.

## Inputs and outputs

Inputs are the exact original driver, the unchanged64-cell selection, and its
new `paced_finalists_epoch2_v2` manifest. The separately reviewed resume ledger
copies only the two COMPLETE receipts and their resource trajectories from v1
after exact job-key/artifact/PID-closure verification. Copies retain their
original absolute artifact references and remain byte-identical. The failed
B10 cell is never copied as success; it is attempted anew in v2. All v1 files
remain in place and are hash-bound before continuation.

The native driver's usual outputs go beneath v2. The wrapper writes its own
LAUNCH.json, READ_RETRY_EVENTS.jsonl and COMPLETION.json under a separate fresh
`--events-root`. They bind wrapper/driver source and record the coordinator's
PID+creation time. An existing events directory is rejected. The final summary
must disclose the interruption and that two completed cells used the original
coordinator while the remaining cells used the read-retry overlay. Retry waits
can irregularly space observer samples; they do not move model source clocks.
Resource and method-order comparisons retain this measurement limitation.

The forwarding boundary requires exactly one separate `--mode run`; duplicate,
equal-form and abbreviated options cannot switch execution into a worker.
No model is started by `--check-root`. Ten isolated checks exercise the actual
original reader through injected sharing denials, persistent refusal, unchanged
bytes, a between-read deadline, oversleep refusal, no retry for other errors and original
child-entry-point identity and the run-only argument boundary. The transient fixture uses actual errno13
PermissionError, without requiring a Windows winerror attribute. They
do not claim a new native success. Use a fresh check directory each time.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py "$sim\scripts\s6b_paced_read_retry_v1.py" --check-root "$sim\staging\s6b\20260909T230840Z\paced_read_retry_checks_v3"
```

Only after the resume ledger and wrapper are reviewed and the quiet interval
is re-confirmed, run the exact selection through the wrapper:

```powershell
& $py "$sim\scripts\s6b_paced_read_retry_v1.py" --events-root "$sim\reports\S6B\20260909T230840Z\paced\read_retry_overlay_v1_run1" -- --mode run --epoch epoch2 --profiles 'B00,B36,B10,B17' --repetitions 2 --streams 'O0,O1' --report "$sim\reports\S6B\20260909T230840Z" --output 'G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v2'
```

## Anaconda Prompt / Command Prompt

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6B_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%S6B_PY%" "%SIM%\scripts\s6b_paced_read_retry_v1.py" --check-root "%SIM%\staging\s6b\20260909T230840Z\paced_read_retry_checks_v3"
"%S6B_PY%" "%SIM%\scripts\s6b_paced_read_retry_v1.py" --events-root "%SIM%\reports\S6B\20260909T230840Z\paced\read_retry_overlay_v1_run1" -- --mode run --epoch epoch2 --profiles B00,B36,B10,B17 --repetitions 2 --streams O0,O1 --report "%SIM%\reports\S6B\20260909T230840Z" --output "G:\Just_Peachy_S6B\20260909T230840Z\paced_finalists_epoch2_v2"
```

Use the existing EDGE interpreter; no installation or activation is required.
Preserve all failed attempts and the earlier pre-paced accounting checkpoint.
The default `--driver` is the unchanged sibling `s6b_paced.py`, with its expected
SHA256 embedded in this wrapper. Exact successful v2 cells can later be reused
through the same driver rules and a newly named wrapper event directory. Any
new native interruption still requires explicit diagnosis and a preserved
attempt; this wrapper does not automatically retry an audio cell.
