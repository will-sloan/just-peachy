# Serialized allocation and runtime guard

## Purpose

`reservation_guard_v1.py` adds a separate OS-held allocation lock, exact owner and
producer-source checks, runtime/output/free-space limits, and accounting of the
current output's remaining commitment exactly once. It uses the qualified V2
complete recorded-admission census and V1 closed-reservation arithmetic. It does
not edit either predecessor or the healthy scorer. No shared ledger is modified.

The lock is `local/n4/reservation-guard.owner.lock`, held for the guarded producer's
lifetime. It is distinct from the supervisor writer lock, which must never be held
across a long inventory scan. A second cooperating producer fails immediately;
process death releases the OS lock. A provisional ADMISSION may be written before
acquisition, but that alone authorizes no numerical or application work. A future
producer must require its own qualified execution family, bind its original
prediction plan and new coordinator/resource contract, pass `refresh`, and preserve
RESULT or FAILED. Production checks refuse every other live N4 allocation and
require this exact process to be the supervisor's driver. This prevents starting
modes alongside a scorer using the unchanged legacy guard.

This is a guard library and qualification probe, not that integrated production
family. It cannot authorize a method bank, scoring run, application slot or stage
acceptance. The next family must demonstrate unchanged prediction/conversion/metric
contracts and independently review its new execution provenance. Read-only census
qualification must not be substituted for that work. Whole-host resource exclusivity
is not established; the inaccessible command-window ownership issue remains separate.

## Inputs, outputs and API

Inputs: a fresh private N4 output with an exact owner, unique source bindings, one
output cap and an explicit time budget; the original reviewed main plan for ASR/D1
closure; campaign policy; actual process identities/commands/ancestry; all recorded
N4 admissions and the individually bound fixture inventory; physical bytes and free
space. No audio or model data is opened by this library. Original files remain.

Use `with OutputGuard(local, output, code, main_plan_binding, maximum_seconds,
production=True) as guard`. Production use requires its sealed library qualification
and the caller's separately qualified producer family. `guard.refresh(peak_bytes)`
checks the full census and exact accounting before work and at bounded checkpoints.
It starts with a conservative one-byte prospective census, then replaces that byte
with the already recorded owner's remaining allocation in the exact arithmetic;
the owner is removed from the other-allocation list so its cap is counted once.
All physical bytes, every other live remainder, 2 GiB future reservations and
0.5 GiB contingency remain. Only the already reviewed 4 GiB ASR/D1 future reserves
expire. No physical storage is subtracted. `guard.fast_check(peak_bytes)` checks
actual output usage, affinity/priority, CPU-only math settings, unchanged policy,
time, free space and a 1-MiB terminal reserve between units. It does not replace
periodic full shared-budget checks. Preserve the returned checks in stage receipts.

The original campaign maximum is 50 GiB, with C50/G75-GiB floors plus temporary
peak. Stricter configured floors and earlier deadlines apply; later deadlines cannot
extend the original cutoff. A changed campaign policy refuses the current guard.
The coordinator remains CPU14/BelowNormal, one math thread and GPU off. Production
native-child ownership and controlled measurements still need the application gate.

`test_reservation_guard_v1.py` tests single counting, growth, overlap and missing
allocations, production concurrency/supervision, identity/source/root joins,
headroom, exact deadline/runtime/floor boundaries, and failure-preserving release.
`probe_reservation_guard_v1.py` runs these and all 69 predecessor tests, then an
actual development guard over its own output. While holding the separate lock it
starts one hidden metadata helper, verifies that helper cannot acquire the lock,
waits for its exact exit, performs the actual census/check, releases/reacquires the
lock, and checks that a running supervisor heartbeat advanced. It starts no numerical,
model, GUI, microphone, capture, playback, enrollment or Pi process. It does not
claim development concurrency is acceptable for controlled resource measurements.

Outputs: ADMISSION, four source snapshots, test log, LOCK_CONTENTION, GUARD_CHECK,
and RESULT or FAILED in a fresh private directory. The unchanged legacy guard is
checked before admission and after execution. Probe bounds: 8 MiB, 20 minutes
checked between operations, CPU14/BelowNormal, one math thread and GPU off. Keep
all failures. Seal the small public qualification only after the exact probe owner
and helper exit and source, tests, lock, census and arithmetic evidence verify.

## PowerShell

Use an existing shell and a fresh output. Background execution must use the existing
hidden-process convention with fresh process/resource ownership checks.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpN4\probe_reservation_guard_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-guard-v1-probe-v1'
```

## CMD and Anaconda Prompt

Use the pinned existing interpreter without changing any environment:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_N4%\probe_reservation_guard_v1.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-guard-v1-probe-v1
```

For tests alone: PowerShell `& $jpPython -B -m unittest discover -s $jpN4 -p test_reservation_guard_v1.py -v`;
CMD/Anaconda `"%JP_PY%" -B -m unittest discover -s "%JP_N4%" -p test_reservation_guard_v1.py -v`.
The library's `--test-lock` command is an internal, non-numerical helper used only
by the admitted probe; running it alone does not qualify anything. Live CM5 checks
remain deferred. Packaging starts 2026-09-28 02:48:19 UTC; the deadline is
2026-09-28 14:48:19 UTC. Neither limit is extended.
