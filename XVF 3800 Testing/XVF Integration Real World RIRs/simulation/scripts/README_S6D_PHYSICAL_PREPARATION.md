# S6D physical input preparation and supervisor bridge V1

This maintained README covers `s6d_physical_prepare_v1.py`,
`s6d_physical_prepare_checks_v1.py`, `s6d_qualification_diagnostics_v1.py`, and
`s6d_capture_supervisor_bridge_v1.py`. The first three are file-only tools. They
do not enumerate devices, load vendor DLLs, set controls, open audio streams,
run neural models, or create execution authorization. The bridge is a future
hardware entry point and must be admitted by the root coordinator before use.
Frozen capture owner V3 remains unchanged. The latest withheld proposal uses
additive owner V4 and the independently source-reviewed runner V3.

## Purpose, inputs and outputs

The preparation tool verifies the original ECQ manifest and the first declared
whole C clip for each original A15/B15 person. It preserves original source
quality information, transcripts, identities and E/C/Q source separation. It
uses the exact measured Library R04/R12 four-channel RIR files, full convolution,
one common origin and unity input gain. An original documented instrumental-only
canonical scene supplies an unchanged common four-channel crop. No waveform is
normalized, clipped, independently shifted, or trimmed to a word interval.

It writes thirteen FLOAT/16 kHz/four-channel microphone input WAVs: eleven
short control inputs (including a deterministic four-channel tagged sentinel)
and two whole-C30 calibration sequences. Headroom must pass at unity; a failure
requires a reviewed construction decision, never automatic gain adjustment.
Repeated C copies are calibration/control material, not independent enrollment.
The sentinel has four independent even PCM24 tag vectors followed by whole C
speech. Exact MIC comparison applies only to INPUT_QA output columns 2–5.

Outputs include `PREPARATION_RESULT.json` with source and WAV hashes,
`CAPTURE_PLAN_PROPOSAL.json`, `CAMPAIGN_BATCH_PROPOSAL.json`,
`BUDGET_FORECAST.json`, `QUALIFICATION_ANALYSIS_CONTRACT.json`,
`SUPERVISOR_QUEUE_PROPOSAL.json`, `ADMISSION_REQUIREMENTS.json`, a firmware
duration evidence audit and a source snapshot. These are proposals, deliberately
not executable capture/queue schemas. Safety and authorization fields are absent
or null until real user evidence and root review exist. Nothing created here
grants permission to run hardware.

The bridge runs the maintained, hash-bound V4 owner in its own process, without
starting or terminating another capture owner. It translates only a matching
run/job/child/PID/process-creation STOP into a shared stop event first, then the
owner's STOP_REQUEST file. File-relay delivery and unresolved I/O errors are
recorded separately. Event delivery remains effective when the file relay fails.
It emits
five-second heartbeats and polls STOP at 0.1 s. Durable ledger/file changes count
as progress; heartbeat count does not. File-byte progress is not a sample cursor
or acoustic clock. The owner retains its callback/telemetry watchdogs and checks
the shared event in its callback. Progress scans test closed/stop between entries.
Atomic publication retries PermissionError at most six times with unique temp
names and20/40/80/160/250 ms delays. Persistent errors remain failures. STOP is
rechecked after the observer joins and immediately before completion publication;
an observed late STOP preserves RESTORED separately and prevents COMPLETE.

Supervisor RESTORED requires fresh, same-process owner acquisition and the
global ledger's exact hash-bound restoration receipt, PASS, exact configuration
match, closed telemetry and released hardware lease. PID exit alone is never
restoration. An existing batch is rejected, including after a crash; root must
review recovery. COMPLETE additionally verifies exact plan/authorization/attempt
admission, every result, transport PASS, source-epoch preservation, and summary
membership. Per-stream LIMITED rail evidence and pending route/tail qualification
remain explicit; COMPLETE does not certify physical qualification or S6D success.
If admission fails before owner acquisition, no restoration is invented. The
runner must preserve an unresolved hardware lock until root reviews the evidence.

## Model-free commands

PowerShell (replace only the fresh output suffix when intentionally starting a
new preserved preparation epoch):

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py -B "$sim\scripts\s6d_physical_prepare_checks_v1.py" --output "$sim\reports\S6D\20260913T195357Z\physical_preparation_checks_v1.json"
& $py -B "$sim\scripts\s6d_physical_prepare_v1.py" --output "$sim\reports\S6D\20260913T195357Z\physical_preparation_v1" --payload-root 'G:\Just_Peachy_S6D\20260913T195357Z\physical_preparation_v1'
```

Anaconda Prompt or CMD (the explicit interpreter provides NumPy, SciPy,
SoundFile, psutil and pypdf; Anaconda Python 3.12 also supports these file-only tools):

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\anaconda3\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_physical_prepare_checks_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\physical_preparation_checks_v1.json"
"%PY%" -B "%SIM%\scripts\s6d_physical_prepare_v1.py" --output "%SIM%\reports\S6D\20260913T195357Z\physical_preparation_v1" --payload-root "G:\Just_Peachy_S6D\20260913T195357Z\physical_preparation_v1"
```

Fixtures use temporary files and synthetic arrays. Their output path must be
fresh. They exercise wrong identity STOP, stale or missing restoration,
source-bound completion, LIMITED stream retention, unchanged heartbeat progress,
QA channel swaps/duplicates/source loss, common-lag diagnostics and silence.
Diagnostic functions can be imported for real captured files after root review;
they only read arrays and do not repair or replace WAVs. `pair_diagnostics`
chooses one shared lag from the first four compatible streams and reports each
stream's correlation/RMS ratio at that same lag. Zero/gated streams are
unidentifiable, never silently treated as transport failure. No correlation score
by itself certifies a named physical route.

## Future hardware bridge admission

Root must first resolve actual safety acknowledgement, firmware duration
evidence, a literal v1 capture plan, exact authorization, baseline/init/output
policy bindings, source freeze, disk headroom and global ledger continuity.
The first admitted job should be only the pre-QA sentinel. Later jobs are staged
behind actual QA, route and observer review; do not admit the whole campaign as
one unreviewed queue. Every new recipe/profile group adds pre/post QA; optional
hypotheses and retries require a new budget forecast.

The reviewed runner provides `S6D_RUN_ID`, `S6D_JOB_ID`, `S6D_CHILD_RUN_ID`,
`S6D_HEARTBEAT_PATH`, `S6D_COMPLETION_PATH`, `S6D_STOP_REQUEST_PATH` and
`S6D_RESTORATION_PATH`. Its literal argv uses Anaconda Python 3.12 and the
maintained bridge path as argv[1]. Do not manually supply these identities or
launch this example. This documents the future exact argument shape only:

```text
C:\Users\amiri\anaconda3\python.exe
<SIM>\scripts\s6d_capture_supervisor_bridge_v1.py
--owner <SIM>\scripts\s6d_capture_owner_v4.py --owner-sha256 <reviewed V4 SHA256>
--plan <root-adopted capture v1 plan> --plan-sha256 <its SHA256>
--authorization <root-issued exact authorization> --authorization-sha256 <its SHA256>
--batch <fresh literal batch ID> --attempt-ids <exact literal IDs>
```

Use the runner's normal PowerShell/Anaconda/CMD commands from
`reports/S6D/20260913T195357Z/runner/README_NATIVE_PILOT_RUN.md` only after root
creates a reviewed hardware queue and its separate approval. A hardware job
must have `allow_owned_termination=false`, exact RESTORED predicates, and a
deadline covering source guards, resets, conversion, diagnostics and restoration.
Preserve unmatched STOP files and all old epochs; never clear them automatically.

Every pass charges original source duration +1 s pre-roll +3 s post-roll
+16383/48000 s worst final callback padding exactly once. The two continuous
900 s source passes use a 904 s carrier and charge 904.3413125 s each, with no
internal reset. The local User Guide v3.2.1, PDF page 6 (printed page 2), section
2.1 documents an eight-hour evaluation-board limit after power-on/reset. The
prepared playback duration is below 28800 s. Admission still needs actual reset
and readiness timestamps, since the entire uninterrupted DSP epoch includes
initialization and telemetry readiness before playback. Guard silence
changes initial adaptation relative to historical passes; new same-pass controls
are paired, with no claim of identical hidden state.

The 40 GiB cap applies to all new S6D payloads, including prepared inputs,
canonical/decoded files, derivatives and telemetry. Each owner enforces its
payload subtree; the supervisor must additionally monitor the whole shared
`G:\Just_Peachy_S6D\20260913T195357Z` root and C reports, and C>=50/G>=75 GiB
free. Forecasts are not ledger consumption. Partial/failed acquisition,
qualification, observer repeats, enrollment and continuous attempts all charge
the same global ledger, with no automatic retries.

The file-only builder records C/G headroom but can prepare G WAVs while C is
below the physical 50 GiB floor, provided C still has 1 GiB for its small reports
and G has 75 GiB. It marks physical admission blocked in that case. This is a
file-construction allowance, with no change to owner or runner physical floors.

## Prepared result and additive review freeze

The completed input build is `reports/S6D/20260913T195357Z/physical_preparation_v2`
with thirteen WAVs on G under the matching suffix. V1 parse/headroom logs and
empty roots remain preserved. The proposal contains 33 qualification-group
attempts, including four whole-C calibration passes and four QA passes. Across
the full base campaign, 29 additional qualification/calibration/observer passes
and 44 QA passes give 427 attempts / 19670.0340625 charged seconds. Reserving
24 optional 45 s hypothesis passes plus eight QA passes gives 459 attempts /
20952.9560625 s, leaving 21 attempts / 647.0439375 s. Optional passes are not
scheduled. All failed/partial attempts and any new profile-group QA spend this
remaining reserve; no automatic retry is allowed.

Each C30 sequence is 126.4730625 source seconds. Four MAIN/SCAN × R04/R12
captures would charge 523.2575 s, already included above. The separately hashed
`C_CALIBRATION_PARTITION.json` verifies the selected 30 C IDs against all original
E sources and actual Q occurrences, including native bytes, decoded PCM and
prompt identifiers. It includes original quality flags and the inherited known
alias limits. Its status remains PARTITION_BOUND_SCORING_PENDING. Thresholds,
gallery/profile bindings and captured output hashes belong in a later separately
admitted C scoring receipt; missing evidence cannot be imputed. The selector's
same-span waveform correlation must not use qualification's lag search.

To verify the existing WAVs and create a fresh additive review epoch without
building more inputs, use fresh suffixes for `--output`. PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$r = "$sim\reports\S6D\20260913T195357Z"
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py -B "$sim\scripts\s6d_physical_prepare_checks_v1.py" --prepared-result "$r\physical_preparation_v2\PREPARATION_RESULT.json" --output "$r\physical_preparation_checks_v4.json"
& $py -B "$sim\scripts\s6d_physical_prepare_v1.py" --review-preparation "$r\physical_preparation_v2" --checks "$r\physical_preparation_checks_v4.json" --output "$r\physical_preparation_review_v1"
```

Anaconda Prompt/CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "R=%SIM%\reports\S6D\20260913T195357Z"
set "PY=C:\Users\amiri\anaconda3\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_physical_prepare_checks_v1.py" --prepared-result "%R%\physical_preparation_v2\PREPARATION_RESULT.json" --output "%R%\physical_preparation_checks_v4.json"
"%PY%" -B "%SIM%\scripts\s6d_physical_prepare_v1.py" --review-preparation "%R%\physical_preparation_v2" --checks "%R%\physical_preparation_checks_v4.json" --output "%R%\physical_preparation_review_v1"
```

The latest review freeze includes runner V3 source SHA256
`3c0e5f71578f5fc6bbd34bddde42393912d878107f1b07d5c5edc0d2a258b1b3`
and its independent21-framework/9-focused review receipt. This is source review,
not hardware admission. Owner V4 source/fixtures still require root review.
Use `physical_preparation_checks_v5.json` and output
`physical_preparation_review_v2` for the latest existing freeze command inputs.
The new event/atomic/final-STOP epoch passes60 bridge fixtures,33 actual input
checks and48 V4 owner/transport fixtures; no real device was used.

The review freeze retains all prepared-input provenance and supersedes the
additive owner/bridge/fixture/README bindings and withheld queue/capture proposals.
It does not change V3 or any input WAV. The C partition also lists the already
budgeted same-C two-path, ABA, overlap and source-swap MAIN/SCAN controls as a
narrow2person panel. It adds no attempts. Accepted case-results remain empty
until actual acquisition review; duplicate resolution defaults disabled and
requires adequate actual C evidence before it can be enabled.
Source snapshots are evidence copies; future
execution uses maintained SIM/scripts paths so relative roots stay correct.
