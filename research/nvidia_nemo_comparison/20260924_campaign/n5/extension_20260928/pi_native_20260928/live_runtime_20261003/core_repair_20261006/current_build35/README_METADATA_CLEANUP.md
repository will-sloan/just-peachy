# Cleanup after metadata exhaustion

Purpose: keep a failed recording failed while attempting source Stop/join,
refiner, motion, archive, writer, saved-source lease and model cleanup even if
metadata publication fails. The original run failure remains in worker RESULT.
The separate cleanup receipt lists only completed operations; it never claims
physical process death. The external owner/cgroup check remains required.

Inputs are one admitted worker session and the existing finite storage policy.
Outputs are the unchanged failed-session result plus `cleanup_error`,
`cleanup_attempted` and the in-memory cleanup facts. A prelaunch journal receipt
failure does not skip the installed finalizer. If native lanes remain alive,
model ownership remains retained; other independent cleanup is still attempted.
No model threshold, audio sample, recording duration or storage cap is changed
by these two source changes. A separately reviewed storage derivative reserves
terminal metadata before admitting the next recording.

Worker RESULT also retains `source_facts` independently of an engine result:
accepted processed samples, observed timeline/physical-start packet, source
owner, child return code and thread join. A null failed engine result therefore
cannot mean "source never started." Missing observations mean unavailable
evidence, and do not prove capture never happened. The portrait UI uses the
retained primary failure and these facts alongside external source closure.

Fresh storage exposes `write_terminal_event`. The engine uses the separately
reserved pool for one bounded `session_cleanup` fact and, for rich replay, one
`saved_spatial_closed` fact. Ordinary text/events cannot spend that pool. The
cleanup fact includes operation names, error count/hash and retained model
ownership; full failures remain in worker RESULT. This API requires a new spec
with the terminal reservation, and does not upgrade old recordings or allocations.
Worker specs explicitly reserve 256 KiB for terminal facts; that additional pool
also contributes to the finite per-file/SQLite-journal admission. Native storage
plans and both independent copies must include it before dispatch.

The separately measured session19 failure also requires a fresh ordinary
metadata allocation. New worker specs use
`metadata_reserve_bytes = 2 * (16 MiB + maximum_session_seconds * 256 KiB)`
and `metadata_split='text1_sqlite1_v2'`: equal bounded text/SQLite portions,
with the separately reserved 256 KiB terminal pool. At the 70-second check
policy, text receives 35,127,296 bytes and SQLite receives 36,175,872 bytes,
of which 35,913,728 are ordinary and 262,144 are terminal. This is a new
reservation included in the complete storage plan and independent native/PC
copies, not a retroactive allowance for failed session19. The finite per-file
limit also includes current history DB extent and bounded SQLite journal
overhead; it must be remeasured as history grows. The normal 300-second policy
remains configurable and requires its own complete measured allocation.

The sources are packaged through the versioned stabilization builder; do not run
worker.py on Windows or overwrite a deployed package. Native use requires fresh
package pins, admissions, backups and current process/lease checks.

PowerShell, from this directory:

```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B './check_metadata_cleanup.py'
```

CMD and Anaconda Prompt:

```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_metadata_cleanup.py
```

The focused host check accepts no arguments. It extracts the actual changed
cleanup method and worker function, uses controlled failures, and verifies the
resource ordering, retained errors and model-ownership fence. It starts no model,
microphone or GUI. Its output is a fresh private bounded receipt with CPU14 early
owner, exact source backups and independent restores. Host fixtures do not prove
native physical closure or that a speech recording fits its metadata allocation.
