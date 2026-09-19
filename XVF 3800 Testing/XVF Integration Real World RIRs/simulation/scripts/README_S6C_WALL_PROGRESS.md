# S6C observed wall progress

`s6c_wall_progress.py` makes one read-only observation of an explicitly named native invocation's `progress.json`. It compares `new_native_jobs` across separately requested snapshots, using actual observer wall time. This includes the scans, admission stalls and coordinator overhead occurring between observations. It does not edit the runner, relax resource checks, scan payloads, read raw logs, launch models or infer a new profile cost.

Use the invocation-specific path, not the shared root `HEARTBEAT.json`, because the latter can move to another phase or owner. Supply the expected coordinator PID and exact process creation time. A previous observation additionally requires its exact SHA256. Changed owner, source path, epoch, phase, requested grid, boot identity, reordered clock or decreasing counters is rejected; a new invocation requires a new observation chain.

## Inputs and output

- `--source`: explicit `.../epochN/invocations/<invocation>/progress.json`.
- `--pid` and `--creation-time`: expected coordinator identity from its bound owner/admission evidence. A PID alone is insufficient.
- `--output`: a fresh directory for this one observation.
- `--previous` and `--previous-sha256`: optional exact prior `OBSERVATION.json` and hash, supplied together.

The helper preserves the exact read buffer as `PROGRESS_SOURCE.json`. `OBSERVATION.json` binds that buffer and the live source path, stores at most 12 compact observations, the original runner ETA, independent observed-wall throughput and the new heuristic range. The helper/README and previous observation are hashed. Original progress data and prior observations are never modified. The entire operation uses bounded metadata reads, with a 2 MiB hard read limit. There is no polling loop, scheduled task or automation.

## PowerShell

Run pure fixtures without reading current progress:

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_wall_progress.py'
& $s6cPython $s6cScript checks
```

For a coordinator explicitly selected for observation, replace the source and expected identity if the phase changed. This concrete example names the enrollment invocation inspected during development; it is not a claim that it is still active when the command is later read:

```powershell
$s6cProgress = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\epoch2\invocations\20260910T165548_15520\progress.json'
$s6cObs1 = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\wall_progress\enrollment_observation_1'
& $s6cPython $s6cScript snapshot --source $s6cProgress --pid 15520 --creation-time '1789059342.344302' --output $s6cObs1
```

A separately requested second observation, within five minutes, may calculate a recent wall rate:

```powershell
$s6cPrior = Join-Path $s6cObs1 'OBSERVATION.json'
$s6cPriorHash = (Get-FileHash -LiteralPath $s6cPrior -Algorithm SHA256).Hash.ToLowerInvariant()
$s6cObs2 = Join-Path $s6cSim 'reports\S6C\20260910T123540Z\wall_progress\enrollment_observation_2'
& $s6cPython $s6cScript snapshot --source $s6cProgress --pid 15520 --creation-time '1789059342.344302' --output $s6cObs2 --previous $s6cPrior --previous-sha256 $s6cPriorHash
```

Each command is one observation and exits. Quote the creation-time text in PowerShell: an unquoted floating literal can lose precision when converted into a native command argument and is correctly rejected as a different identity. Do not turn it into continuous observation before independent review and a separate coordinator decision. Do not carry an old PID into another phase.

## Anaconda Prompt or Windows CMD

Use the existing Python directly; no environment setup or package changes are required:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_wall_progress.py"
"%S6C_PYTHON%" "%S6C_SCRIPT%" checks
set "S6C_PROGRESS=%S6C_SIM%\reports\S6C\20260910T123540Z\epoch2\invocations\20260910T165548_15520\progress.json"
set "S6C_OBS1=%S6C_SIM%\reports\S6C\20260910T123540Z\wall_progress\enrollment_observation_1"
"%S6C_PYTHON%" "%S6C_SCRIPT%" snapshot --source "%S6C_PROGRESS%" --pid 15520 --creation-time 1789059342.344302 --output "%S6C_OBS1%"
set "S6C_PRIOR_SHA=replace-with-exact-first-observation-SHA256"
"%S6C_PYTHON%" "%S6C_SCRIPT%" snapshot --source "%S6C_PROGRESS%" --pid 15520 --creation-time 1789059342.344302 --output "%S6C_SIM%\reports\S6C\20260910T123540Z\wall_progress\enrollment_observation_2" --previous "%S6C_OBS1%\OBSERVATION.json" --previous-sha256 "%S6C_PRIOR_SHA%"
```

## Formula and limits

The recent rate is the increase in the source's `new_native_jobs` counter divided by elapsed external monotonic wall seconds, using eligible observations within 300 seconds. Reported reused jobs are recorded separately and never enter the numerator. Remaining reported jobs are `requested - completed`, which includes active jobs. The central heuristic is remaining jobs divided by recent rate; the displayed range is 0.5–2 times that estimate. It is deliberately broad and is not a statistical confidence interval, latency qualification or completion guarantee.

The first observation, a flat/reuse-only latest interval, loading/validation without new completions, stale source older than 90 seconds, inconsistent optional counter snapshot, closed/unverified owner, or insufficient recent history has null ETA. No unobserved load or validation duration is substituted. When the counters report all jobs accounted, ETA remains null because final validation/closure has not been measured by these counters. Actual durable completion and process closure require the normal native receipts.

The old ETA remains separately labeled `original_worker_cost_eta_range_sec`. Frozen `run()` averages returned COMPLETE-job elapsed times, divides by configured worker count, and multiplies pending jobs only. It does not include active jobs in that pending term and does not measure serial submission scans or all validation/closure. A metadata scan duration is therefore a plausible explanation for underprediction, but the observer does not attribute a measured per-profile overhead or prove scans caused every delay.

Optional progress counters are not an atomic native ledger. In the existing code, `completed` counts returned rows and `reused` is derived as returned rows minus COMPLETE rows; near failure that second counter must not be promoted to a verified cache-hit count. This observer uses only the separately reported new-COMPLETE counter for throughput. Source updates occur roughly every 20 seconds and can be delayed, so completion increments are interval-censored. OS wall-clock changes and source-age problems are visible; monotonic observer time and boot identity protect rate arithmetic. Missing inspections remain unavailable, never treated as a confirmed closed process or zero overhead.

Fixtures cover formula arithmetic, reused exclusions, initial/flat/stale/closed/null cases, requested-count changes, owner/source/phase/boot changes, clock/counter resets, torn optional counters, duplicate JSON, finite identities and short recent windows. They are model-free guard evidence. One or two development observations do not authorize continuous monitoring or change any native execution claim.
