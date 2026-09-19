# Isolated S6C historical paced controls

`s6c_paced_controls.py` prepares and coordinates new S6C paced sessions for exact
historical B00 and original S6B B01. It does not edit the native worker, app,
models, defaults or any previous paced results. Preparation and checks make no
model calls. `run` starts actual models and must wait for the parent's reviewed
quiet-period admission; this helper has not launched models during development.

## Exact control routes

B00 uses the 14-module S6A baseline snapshot and `PipelineEngine(config)` without
a research profile. Its execution contract is resolved through the sealed S6B
artifact index and that index's final paced manifest, then every baseline module
is checked against the original contract. B01 uses the exact S6B epoch2 app and
original `B01` voice/time profile.
It is not B36, a v3 imitation or a relabelled result. Both execute the unchanged,
hash-pinned `s6b_paced.py --mode worker` entry point with original native thread
settings and explicit original assets. Native numeric pools remain one as in the
original paced driver. Every cell has a fresh process, session and empty gallery.

Inputs are the original indexed mono 16 kHz prepared files. O0 already contains
its historical +3 dB gain and O1 unity; both enter at unity. Whole PCM hashes,
native journal length/hash, cursor closure, dispatch/tail evidence where exposed
and reported audio loss are verified by the original worker and coordinator.
The immutable B00 has less internal dispatch instrumentation; that remains
unavailable rather than retrofitted into the baseline.

## Panel, isolation and resources

Preparation requires an explicit reviewer-selected JSON panel with `case_ids`,
containing 12–24 unique canonical cases, and `repeated_case_ids` containing exactly
four unique members. No old four-case paced panel is treated as satisfying this
requirement. Both controls run on both taps once for the whole panel; only the
four prospectively selected sensitive cases repeat. Method order reverses on
repetition two. No favorable repeat is selected.

The current metadata-only proposal is
`design/confirmation_plan_v1/PACED_PANEL_PROPOSAL_V1.json`: 16 cases covering all
12 families, five rooms and three corpora, including music and silence controls,
seven subsecond and eleven one-to-under-two-second turns. The full pass gives
64 cells; repeating the four selected cases gives 16 more, for 80 cells total.
The initial unexecuted full-repeat adapter was preserved before this bounded
panel refinement. This selection does not establish that every runtime failure
category actually activates; that remains a results question.

New outputs live only under
`G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\<namespace>` and the matching
S6C report subtree. The source-bound manifest fixes worker/app/profile/model/
audio hashes, panel, deadlines, timeouts and job identities. The entire S6C G:
payload plus C: report/staging is counted against 120 GiB. At least 50 GiB on C:,
75 GiB on G: and 4 GiB available RAM are required. One native worker runs at a
time, with a PID/creation-time owner and a separate quiet-period lock. No
unrelated process is stopped. An inaccessible PID is an inspection failure, not
evidence that the process is closed. Only disappearance or actual PID reuse can
resolve a recorded identity as closed.
Admission also enforces these fixed budgets, the exact ordered control grid and
safe job names even if someone recomputes a changed manifest's digest.
Before each cell, a fixed 512 MiB output allowance is reserved below the global
cap and above both drive free-space floors. The coordinator checks actual global
bytes during each 20-second heartbeat and after native closure. This is bounded
metadata accounting overhead; the observed native runtime includes its possible
host contention. A cell cannot be admitted arbitrarily near the cap.

A root-created quiet-admission JSON must say
`status: AUTHORIZED_FOR_QUIET_PACED`, contain the exact `manifest_sha256`, set
`all_other_model_hil_work_stopped: true`, and provide `expires_utc`. The coordinator
also checks live study worker commands and all S6C `workers/*.json` identities.
The absolute deadline cannot exceed 71 hours after the S6C run start, reserving
one hour for closure. Each invocation has at most four hours of wall time.

`STOP_REQUEST` or the common S6C `STOP_REQUEST.json` in the output or report stops
at a cell boundary. `STOP_NOW` in
the output stops only the owned current worker. Failures retain all artifacts.
Complete cells can be verified/skipped in their own namespace. A partial launch
requires a separately reviewed recovery; the old hardcoded 35-cell S6B resume
wrapper must not be applied to this new panel.

## Observation and interpretation

The pinned `OptionalLiveReader` is reused programmatically for only the exact
manifest LIVE paths. Malformed optional LIVE becomes missing only after original
bad bytes are retained. Authoritative completion/native result JSON stays strict.
Read-call counts and missing calls are saved separately from process trajectory
rows. No interpolation or previous-value reuse occurs. Valid loading-phase LIVE
with no telemetry, not-yet-created LIVE and explicit malformed missing samples
remain distinguishable in raw observer/trajectory records.

Resource maxima are observed-sample maxima, not continuous-time peaks. Stored
process-tree flags cannot guarantee OS descendant enumeration between samples.
Coordinator RSS is separate. Native event emission times, modeled cue clocks and
source cursor times remain distinct. This is desktop file pacing, not GUI,
phonetic, device-clock or CM5 latency certification. Existing baseline pacing
semantics are not rewritten to improve timestamp appearance.

## Outputs

- `MANIFEST.json`: exact new source-bound cell grid and explicit per-repeat case
  sets, with no models started.
- S6C `paced_controls/<namespace>/PREPARATION.json`: plan binding and expected
  cell/audio duration counts.
- `jobs/<id>/`: unchanged worker results, native sessions, full journal,
  display events, process samples, ownership, COMPLETE or preserved FAILURE.
- `invocations/<id>/`: source-bound launch, reader anomalies with retained bytes,
  final observer counters and closure of the quiet owner.
- `HEARTBEAT.json`: current cell and completion/resource status.

Final table/closure analysis is a separate source-bound task after all workers
close. The adapter does not reuse the old S6B four-case SUMMARY as new evidence.

## PowerShell

Use the actual panel and reviewed deadline provided by the parent experiment.
The preparation example uses a filename expected from that review; it must exist.

```powershell
$jpRoot = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$jpSim = Join-Path $jpRoot 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$jpRunner = Join-Path $jpSim 'scripts\s6c_paced_controls.py'
$jpReport = Join-Path $jpSim 'reports\S6C\20260910T123540Z'
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpRunner checks
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpRunner prepare --panel (Join-Path $jpReport 'design\confirmation_plan_v1\PACED_PANEL_PROPOSAL_V1.json') --namespace controls_v1 --deadline-utc '2026-09-13T11:35:40Z' --repetitions 2
# Run only after the root publishes the exact quiet-admission receipt:
& (Join-Path $jpRoot '.edge-speech-env\python.exe') $jpRunner run --manifest 'G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_v1\MANIFEST.json' --quiet-admission (Join-Path $jpReport 'paced\CONTROLS_QUIET_ADMISSION_V1.json')
```

## Anaconda Prompt or CMD

```bat
set "JP_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy"
set "JP_SIM=%JP_ROOT%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "JP_RUNNER=%JP_SIM%\scripts\s6c_paced_controls.py"
set "JP_REPORT=%JP_SIM%\reports\S6C\20260910T123540Z"
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_RUNNER%" checks
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_RUNNER%" prepare --panel "%JP_REPORT%\design\confirmation_plan_v1\PACED_PANEL_PROPOSAL_V1.json" --namespace controls_v1 --deadline-utc "2026-09-13T11:35:40Z" --repetitions 2
rem Run only after the root publishes the exact quiet-admission receipt:
"%JP_ROOT%\.edge-speech-env\python.exe" "%JP_RUNNER%" run --manifest "G:\Just_Peachy_S6C\20260910T123540Z\paced_controls\controls_v1\MANIFEST.json" --quiet-admission "%JP_REPORT%\paced\CONTROLS_QUIET_ADMISSION_V1.json"
```

Never call the historical native worker manually: the new coordinator owns
quiet-period admission, resource accounting, missingness recording and closure.
