# Same-Controller stop and restart lifecycle

Purpose: `restart_application_cell.py` implements two saved-file sessions in the
same Controller, UI, Tk root, command worker and model store. It reuses the
qualified private-desktop preparation, backend/roster configuration and resource
observer. The first source is deliberately stopped after a planned positive
prefix. Only after its complete drain passes does the second session start the
same full file from sample zero. Engine, source, journal, consumer, source-clock
and viewport observers must be new, with consecutive Controller epochs and
distinct native session paths. Previous caption history remains in the UI.

Inputs to this internal primitive: the independently admitted private application
child, original eight-field audio job (at most 120 seconds), backend contract,
frozen source, runtime metadata, fixed gallery and current exclusive admission
callback. Call prepare with the same arguments as the delivery ApplicationCell,
then `run_pair(admission_check=..., stop_after_samples=...)`, then close in finally.
The threshold is a positive multiple of 320 samples and leaves at least 640
samples before EOF. Plan it before execution. The full job is never shortened.
The inherited single-source run entry point is disabled. Total pair time is
bounded to 900 seconds from construction, including preparation; transitions
have shorter limits and repeat admission while pumping the private GUI.

Outputs in a fresh private application folder include RESTART_PREPARED.json,
sessions/01 and sessions/02, each with delivery capture/raw trace, engine closure,
archive, source clock, Controller snapshot, viewport scope and RESULT.json.
The first viewport retains the prepared root viewport directory; the second has
its own session directory. Source/consumer observers close before arming the
next epoch. Both native sessions are pinned. PAIR_OBSERVATION.json records the
observed object identity joins and ordered source origins. Final RESULT.json
requires both releases and Controller/resource cleanup; failures preserve
available receipts, native outputs and failed delivery capture. No application
recording is enabled. Model reuse does not replace the need to review native
runtime reset/state evidence later.

`restart_archive.py` is an explicit archive-reader derivative for an **open**
Controller with released session owners. It retains every queue, error/loss,
sample-count, handle/worker, epoch and persisted metadata check. The older N3
archive validator, also used by `restart_session_closure.validate_complete`,
requires a closed Controller and cannot qualify this between-session boundary.
The paired cell uses `restart_session_closure.capture_engine/validate_engine`
with the new `restart_archive.capture_archive/validate_complete`. Do not fake
closed-Controller flags or pass this new schema to full-shutdown validators.
Earlier qualified files and receipts remain unchanged.

VIEWPORT_SCOPE.json identifies the current native session and prior sessions.
Raw retained-history observations can include old captions alongside the new
source clock. A later reader must match caption keys/publication sessions before
interpreting latency or naming. Neither this collection nor the development
probe grants accuracy, timing, uninterrupted continuity, target performance,
restart acceptance or integrated N4 credit. A selected-job planner, exclusive
launcher integration, native two-session envelope/independent reader and actual
runtime execution still remain. Never start this cell while D1 owns resources.

## Development checks: PowerShell

No dependency installation is needed. The probe uses CPU14, below-normal
priority, one math thread, GPU off, the current healthy-D1 identity checks,
shared allowance/disk floors and an 8-MiB private output limit. Preserve existing
attempts and use a new output suffix for reruns. Do not bypass phase gates.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_restart_application.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-application-probe-v1'
```

## CMD and Anaconda Prompt

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_application.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-application-probe-v1"
```

The 21 development checks invoke the actual new lifecycle methods with entirely
mocked Controller/UI/source/model/observer/closure/admission facts. Separate
archive tests use synthetic open-Controller metadata joined to unchanged bound
historical archives. Tests cover ordered two-session execution, same and distinct
owners, epoch/offset reset, complete cleanup, retained history, admission/deadline
failure, invalid stop thresholds, failed first/second reviews and duplicate runs.
Nothing starts a real Controller, GUI, source, model or Pi; there is no positive
production admission or actual engine-capture run. Probe outputs are owner/code
snapshots, ADMISSION.json, tests.txt, labeled synthetic examples and RESULT.json
or preserved FAILED.json. Publish only after the helper exits and hashes match.

The preserved v1 attempt passed 14/16 checks. Its synthetic clock did not advance
between first-session completion and second-session source start, correctly
triggering the strict ordering check. V2 advances the fake clock at source start;
the runtime ordering check is unchanged. Four more tests cover revoked admission,
repeated source origins, failed GUI cleanup and retained-history session scopes.
V2 passed all 20 checks. V3 additionally verifies that the retained UI still
references the original Controller/root and remains open, with a rejection test
for changed bindings. Run the final version into a fresh
`restart-application-probe-v3` directory, preserving both earlier attempts.
