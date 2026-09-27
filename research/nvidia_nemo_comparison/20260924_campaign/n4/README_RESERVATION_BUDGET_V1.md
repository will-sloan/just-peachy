# Receipt-based reservation calculation

## Purpose and scope

`reservation_budget_v1.py` implements and checks the arithmetic proposed in
RESERVATION_RECONCILIATION_20260927.md. It retains every physical campaign byte,
adds the remaining output commitment of each supplied live allocation and a
fresh requested allocation, and keeps 2 GiB for future work plus 0.5 GiB of
contingency. Only the two completed, reviewed 2-GiB ASR and D1 reservations
can expire. No evidence file is removed or credited as free disk space.

This is a read-only calculation library and development probe. It does not
admit or launch the modes bank, replace any production guard, change the
shared ledger, or qualify N4/N5. The explicit live allocation set is supplied
by the caller; it does not establish a complete host/process census. Production
integration must add a verified complete allocation set and serialized
admission, and cover method execution, scoring, review and application slots
in fresh derivatives. Existing frozen guards and running sources remain intact.

## Inputs and outputs

`read_closed_components` reads the original full main plan, its accepted ASR
and D1 reviews, admissions, terminal receipts and all 2,880 reviewed result
bindings. It checks exact joins, complete counts, original 2-GiB limits, no
remaining component child and exact PID/creation-time exits. A reused PID
does not identify the old owner; access denial is never treated as an exit.

`live_allocation` verifies an immutable admission and its exact live owner,
private N4 root, hard allocation and used bytes. Reparse points, oversized
outputs, missing bounds or owner changes fail. Active usage must be sampled
before the whole campaign inventory so output growth cannot erase a commitment.

`calculate` adds all existing bytes, each nonoverlapping live remainder, the
requested output, 2-GiB future allowance and 0.5-GiB contingency. It rejects
duplicated owners, overlapping roots, fabricated/negative remainder, stale
owners, inventory errors, invalid numeric inputs, and exceeded limits.
The ceiling remains at most 50 GiB. C:50/G:75-GiB floors, stricter configured
floors and requested peak headroom all remain enforced. The cutoff is the
earlier of the configured cutoff and 2026-09-28 02:48:19 UTC; the deadline
cannot be extended by editing configuration.

`snapshot` combines those reads into private diagnostic evidence. No input
contains reference transcripts or model parameters. No model, device, GUI,
microphone, playback or Pi connection is started.

`probe_reservation_budget_v1.py` runs boundary/failure tests and one actual
snapshot for a proposed 1.5-GiB modes output with 280-MiB peak. Its active set
explicitly includes the current main scorer, automatic review waiter and the
probe itself. All must still be active with their exact identities; a later
stage requires a fresh derivative of the probe, not changed bindings or a
pretended active owner. The test process is CPU14/BelowNormal, one math thread,
GPU off, at most ten minutes and 8 MiB. It first passes the existing legacy
resource guard, so its own execution does not depend on the candidate policy.

A fresh private output contains ADMISSION, four source snapshots, a test log
and RESULT or FAILED. Temporary synthetic fixtures remain under that output;
their test-owned temporary directories are managed by Python's test fixture.
Failed attempts and immutable results must be preserved. Only seal the public
development qualification after the exact probe owner exits and every source
and output binding has been verified. A passed probe still authorizes no
production execution or GUI/resource acceptance.

## PowerShell

Use the admitted existing interpreter; no installation is needed. These
commands are for an existing shell. Campaign dispatch uses a hidden process
and must not launch another numerical worker or move desktop focus.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
& $jpPython -B "$jpN4\probe_reservation_budget_v1.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-budget-v1-probe-v1'
```

## CMD and Anaconda Prompt

Use the same isolated interpreter without activating or modifying another env:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
"%JP_PY%" -B "%JP_N4%\probe_reservation_budget_v1.py" --output G:\Just_Peachy_N1\20260924_campaign\local\n4\reservation-budget-v1-probe-v1
```

Both recipes refuse existing output. Preserve it and use a fresh suffix only
for a justified subsequent development check after inspecting active owners.
Tests alone can be invoked from PowerShell with
`& $jpPython -B -m unittest discover -s $jpN4 -p test_reservation_budget_v1.py -v`
or from CMD/Anaconda with
`"%JP_PY%" -B -m unittest discover -s "%JP_N4%" -p test_reservation_budget_v1.py -v`.
The admitted probe is preferred because it records source hashes, limits,
private test placement and the actual storage/ownership observations.

## Required next integration

This module is the shared arithmetic building block, not a workaround for
the running scorer's frozen six-GiB guard. A production derivative must obtain
a complete fresh reservation/owner census under the existing stage ownership
interfaces, account for its own remaining output before and during execution,
and retain source/plan lineage through independent review and downstream
selection. Add gate-specific integration tests and prediction/metric parity
evidence before dispatch. Do not silently patch constants, monkeypatch a
legacy guard, manually edit the shared ledger or relabel old results.

The two main scoring timeouts observed earlier (and any later failures) remain
separate metric-repair work. This storage calculation does not repair them.
The Pi remains offline; live CM5 validation is deferred until reconnection.
