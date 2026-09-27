# Fixture-aware allocation discovery

## Purpose and preserved failure

The V1 live census passed 53 tests but refused a preserved synthetic admission
with `pid=1, create_time=0`. Its failed probe, source snapshots and logs remain
unchanged in `local/n4/reservation-census-v1-probe-v1`. A strict process identity
check must not treat this deliberately invalid test value as an exited worker.

V2 uses the unchanged V1 discovery, process, command, supervision and arithmetic
helpers. It adds an individually hash-bound inventory of 32 test admissions from
10 closed probes. Each fixture must join its actual parent admission and terminal,
the parent's exact exited owner, the admitted producer and test source, the named
test method, and its retained test log. An older failed probe may use its preserved
source snapshot only when its byte count and hash match the original admission;
current replacement code cannot stand in for that original. Failed probes remain
evidence. One fixture
intentionally recorded its real probe's PID to test rejection of a live reviewer;
its parent has since exited. Synthetic fixture PIDs are never queried. No blanket
`tests` directory exclusion is applied during the census. New or changed evidence
must be reviewed explicitly; it cannot acquire this exemption by its filename.

## Inputs and outputs

`reservation_census_v2.py` builds the private fixture manifest from the reviewed
producer table and existing evidence, validates it, then writes the small public
binding receipt. The manifest contains paths and hashes, not copied audio. All
fixture bytes stay in the physical campaign inventory. Neither their stored bytes
nor any actual worker's remaining allocation is subtracted as fixture credit.

`probe_reservation_census_v2.py` runs the 26 arithmetic tests, 27 unchanged census
tests, and new fixture provenance tests. It then performs a complete actual N4
admission census and prospective budget calculation while preserving the running
scorer. Inputs include the fixture receipt, reviewed ASR/D1 closures, all private
N4 admissions, current supervisor and worker specification, exact process owners,
commands and ancestry, private byte inventory and free space. Outputs in a fresh
private directory are ADMISSION, five source/receipt snapshots, tests.txt, and
RESULT or FAILED. Temporary unit-test fixtures remain inside that output and are
cleaned only by their creating test contexts.

The prospective request is 1.5 GiB for modes and 280 MiB temporary peak. Calculation
retains physical bytes, live allocation remainders, 2 GiB future reservations and
0.5 GiB contingency. The prior qualified arithmetic expires only the separately
reviewed and closed 4 GiB ASR/D1 future reservations. C50/G75-GiB free-space floors,
the 50-GiB campaign ceiling, and the original packaging cutoff remain enforced.

The probe first passes the unchanged legacy guard. Limits: CPU14, BelowNormal,
one math thread, GPU off, 8 MiB output, and 20 minutes checked between operations.
It starts no numerical, model, GUI, audio, microphone, playback or Pi worker and
does not mutate shared ledgers. It holds no supervisor lock during scans. Stable
before/after owner and admission epochs plus fresh heartbeat checks reject races.
The complete recorded admission set is checked; whole-host exclusivity is not
claimed. The inaccessible command-window owner remains a separate barrier to
controlled GUI/resource measurements.

This diagnostic is development evidence. It does not integrate a production guard,
serialize production allocation admission, authorize modes, or establish N4/N5
acceptance. That still requires a fresh qualified method/scorer/reviewer/application
family with unchanged numerical contracts and source/plan lineage. Never modify a
bound source, copy this result into a production acceptance field, or bypass the
running scorer's legacy policy. Seal qualification only after the exact probe owner
exits and every source, snapshot, test, receipt and actual census is verified.

## PowerShell

Run in an existing shell. A background dispatch must use the established hidden
process convention, fresh destinations and verified resource ownership. The first
command builds an immutable fixture inventory; use it once. For later probes reuse
that verified receipt. Never overwrite an existing attempt.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpN4='research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpN4\reservation_census_v2.py" --local $jpLocal --output "$jpLocal\n4\reservation-census-fixtures-v2\RESULT.json" --receipt "$jpN4\RESERVATION_CENSUS_FIXTURES_V2.json"
& $jpPython -B "$jpN4\probe_reservation_census_v2.py" --output "$jpLocal\n4\reservation-census-v2-probe-v1"
```

## CMD and Anaconda Prompt

Use the pinned existing interpreter without changing any environment:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_N4=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_N4%\reservation_census_v2.py" --local "%JP_LOCAL%" --output "%JP_LOCAL%\n4\reservation-census-fixtures-v2\RESULT.json" --receipt "%JP_N4%\RESERVATION_CENSUS_FIXTURES_V2.json"
"%JP_PY%" -B "%JP_N4%\probe_reservation_census_v2.py" --output "%JP_LOCAL%\n4\reservation-census-v2-probe-v1"
```

For tests alone use PowerShell `& $jpPython -B -m unittest discover -s $jpN4 -p test_reservation_census_v2.py -v`
or CMD/Anaconda `"%JP_PY%" -B -m unittest discover -s "%JP_N4%" -p test_reservation_census_v2.py -v`.
The admitted probe is preferred because it preserves actual evidence and source
bindings. Live CM5 checks remain deferred until reconnection. Packaging starts
2026-09-28 02:48:19 UTC; the deadline is 2026-09-28 14:48:19 UTC.
