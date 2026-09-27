# Resource guard probe with explicit completed-handle closure

## Purpose and preserved failure

The first guard probe passed all 87 tests. Its lock-contending helper returned
exit code zero with empty pipes, but the immediate exact-PID check still found the
process object. The probe preserved FAILED and stopped before its actual resource
census. No numerical worker was started, no guard qualification was issued, and
the main scorer continued. Keep `reservation-guard-v1-probe-v1` and its bound source.

V2 changes only the diagnostic helper closure. It records the helper's exact
identity and source immediately, waits for the process, closes its pipes and its
own completed Windows Popen handle, records that wait, and observes exact identity
disappearance for at most five seconds. It never closes a running helper's handle
as a substitute for waiting and never treats access denial as exit. A timeout
remains a preserved failure. The guard library and first probe remain unchanged.
The pinned interpreter's local `subprocess.Handle` supplies the idempotent `Close`
method used here; it is not a PID-based handle lookup or arbitrary process control.

## Inputs, outputs and limits

Inputs and guard API are in README_RESERVATION_GUARD_V1.md. V2 reruns all 87 tests,
adds four closure tests, then performs the actual two-process lock contention,
complete allocation census, own-remainder calculation, runtime checks and lock
release/reacquisition. It preserves CONTENDER_STARTED and CONTENDER_WAIT even if a
later exact-exit check refuses. The actual resource check uses the unchanged guard
library. Output includes ADMISSION, seven source snapshots, test and lock/guard
receipts, and RESULT or FAILED. Every attempt requires a fresh private directory.

The initial unchanged legacy guard, 8-MiB cap, 20-minute probe budget, CPU14,
BelowNormal, one math thread and GPU-off requirements are retained. One hidden
metadata helper is started; no model, numerical, GUI, audio, microphone, capture,
playback, enrollment or Pi work occurs. Shared ledgers and supervisor writer locks
are untouched. Whole-host exclusivity and N4/N5 acceptance are not claimed.

Seal RESERVATION_GUARD_CHECK_V1.json only after all 91 tests and the actual check
pass, exact probe/helper owners exit, and all evidence verifies. Its `code` field
binds the unchanged guard library's complete source set; `probe_code` additionally
binds this derivative and its tests/README. This qualifies the library, not a
production method/scorer/reviewer/application family. That integration and its
prediction/metric/provenance checks remain necessary before modes starts.

## PowerShell

Use an existing shell; background dispatch uses the established hidden convention
after fresh exact-owner, source and resource checks.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpN4\probe_reservation_guard_v2.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-guard-v2-probe-v1'
```

## CMD and Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_N4%\probe_reservation_guard_v2.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-guard-v2-probe-v1
```

Tests alone: PowerShell `& $jpPython -B -m unittest discover -s $jpN4 -p test_reservation_guard_closure_v2.py -v`;
CMD/Anaconda `"%JP_PY%" -B -m unittest discover -s "%JP_N4%" -p test_reservation_guard_closure_v2.py -v`.
The admitted probe is preferred because it preserves source and actual observations.
Live CM5 checks remain deferred. Packaging starts 2026-09-28 02:48:19 UTC and the
campaign deadline is 2026-09-28 14:48:19 UTC, unchanged.
