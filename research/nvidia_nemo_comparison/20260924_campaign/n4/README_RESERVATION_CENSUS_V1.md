# Recorded N4 allocation census

## Purpose

`reservation_census_v1.py` discovers active output allocations by reading every
private N4 `ADMISSION.json`, rather than accepting a caller's list of active
allocations. It supports exact direct owners, legacy component owners recorded
in their bound terminals, dispatch receipts that delegate to another output,
and the two historical private-desktop launcher formats. Those historical
receipts prove a completed process-handle wait; the census does not fabricate
missing PID identities or launch a desktop.

The discovery is a prerequisite for the proposed reservation correction. It
does not replace a production guard or start the modes bank. The running
scorer keeps its original policy and immutable sources. The original 50-GiB
ceiling, C50/G75-GiB floors and packaging cutoff remain unchanged.

## Inputs, outputs and limits

Inputs: all recorded N4 admissions and associated terminal/launch receipts,
fresh exact process identities and commands, current supervisor ownership and
worker specification, the main plan's reviewed ASR/D1 closure evidence, and the
complete private campaign byte inventory. Live output usage is sampled before
the whole inventory so file growth cannot erase a commitment. The calculation
retains all physical bytes, live output remainders, the proposed 1.5-GiB modes
allocation, 2 GiB for future work and 0.5 GiB contingency. Only the independently
reviewed, closed ASR/D1 reservations expire. No payload or evidence is removed.

Unknown ownerless admissions, changed joins, orphan metric children, uncertain
identities/access denial, escaping output paths, unbound live commands, launch
races, stale supervision, changed admission sets, reparse points, inventory
errors, duplicate allocations and insufficient storage refuse the diagnostic.
The supervisor must join its exact launcher and actual interpreter to exactly
one discovered active allocation. Visible N4 Python processes must belong to
discovered owners, their descendants, or that supervisor/launcher pair.

This is complete discovery of the recorded N4 admission set over the checked
interval, plus an explicit visible-Python check. It is not whole-host resource
exclusivity, proof that arbitrary unrelated processes cannot write files, or
serialized production admission. The existing inaccessible command-window
ownership issue still blocks controlled GUI/resource measurements. A new
production family must serialize admission and recheck ownership/budget during
method execution, scoring, review and application slots. It must preserve
source/plan lineage and demonstrate prediction/metric parity before execution.
Do not use this receipt to bypass an old guard or edit the shared ledger.

`probe_reservation_census_v1.py` runs the existing reservation arithmetic tests
and the new discovery/failure tests, then one actual snapshot. It writes a fresh
private ADMISSION, four source snapshots, test log and RESULT or FAILED. Tests
exercise nested admissions, ownerless/legacy cases, dispatch alias accounting,
orphan children, output/source mismatch, process reuse/denial, heartbeat and
launch races, and visible unregistered Python processes. Temporary fixtures
stay under the probe output and are removed only by their own test contexts.

The read-only probe first passes the unchanged legacy resource guard. It uses
CPU14/BelowNormal, one math thread, GPU off, 8 MiB output and a 20-minute budget
checked between operations. It starts no numerical, model, GUI, audio, capture,
playback, microphone, enrollment or Pi worker. Never duplicate a probe or edit
source after dispatch. Seal qualification only after its exact owner exits and
the source, tests, actual snapshot and all bindings have been verified. A pass
is development evidence, not N4/N5 acceptance or measured memory readiness.

## PowerShell

Use an existing shell and a fresh destination. Background dispatch must use
the existing hidden-process convention; do not take desktop focus.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpN4\probe_reservation_census_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-census-v1-probe-v1'
```

## CMD and Anaconda Prompt

Use the pinned interpreter without installing or modifying any environment:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_N4%\probe_reservation_census_v1.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-census-v1-probe-v1
```

Tests alone, with the variables above: PowerShell
`& $jpPython -B -m unittest discover -s $jpN4 -p test_reservation_census_v1.py -v`;
CMD/Anaconda `"%JP_PY%" -B -m unittest discover -s "%JP_N4%" -p test_reservation_census_v1.py -v`.
The admitted probe is preferred because it records both test families and the
actual source/ownership/storage observations. Preserve every failed attempt.
Live CM5 checks remain deferred until reconnection. Packaging reserve and
deadline remain 2026-09-28 02:48:19 and 14:48:19 UTC, respectively.
