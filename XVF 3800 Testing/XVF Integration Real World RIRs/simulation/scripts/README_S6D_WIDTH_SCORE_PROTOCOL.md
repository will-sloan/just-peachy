# S6D width scorer supervisor protocol V1

This maintained README covers `s6d_width_score_protocol_v1.py` and
`s6d_width_score_protocol_checks_v1.py`. The production helper is an offline,
same-process wrapper around the already frozen `s6d_angle_width_score.py`.
It does not modify that source, its plan V2, any S6C REPORT global or registry,
the physical owner, models, audio or policy replay. Actual scoring still requires
root review and explicit queue/input-index admission. No authorization is supplied.

## Purpose, inputs and outputs

The production CLI accepts the exact scorer adapter plan V2, root scorer
authorization, and one or more literal complete prediction indices covering all
16 width jobs / 3840 cells. Constants bind adapter plan SHA256
`5504e9a6cd49767816ad7dc17c913f5a4f3a76db44f0f235ed30153a619a05dd`
and scorer SHA256
`2ff5541276d66332392d43400b21494b63c65ee79f29e65e424a45a8ee238939`.
The 1920 original control cells and 156/47/26/11 population counts are fixed.

The root-issued authorization must contain the frozen scorer's fields
`root_review_passed`, `adapter_plan_sha256`, `prediction_indices` in CLI order,
plus this wrapper's `protocol_wrapper_sha256`, exact `run_id`, literal `job_id`,
`owner_thread_id` and `owner_session_id`. The two root owner IDs are
`01a0812d-3ff0-7ed0-a06c-4df61b62a459`; run ID is `20260913T195357Z`.
The runner supplies child-run ID, actual PID and process creation time. STOP
packets use the reviewed runner's actual five-field run/job/child/PID/creation
identity. Root identity is bound by authorization; the wrapper does not pretend
the runner transmits additional root fields in STOP packets.

The observer emits five-second heartbeats. Scientific progress advances only
when a fully parsed score at one of the exact declared paths matches its
analysis identity, hash key, profile, tap, population and required metric payload.
Heartbeat count, partial JSON and the appearance of a partial aggregate CSV do
not count as progress. Once all new scores exist, aggregation can remain active
without a new committed counter; the queue's stall allowance must cover that
bounded final aggregation phase.

Matching STOP or observer failure uses the already reviewed offline protocol's
`_thread.interrupt_main()` to request KeyboardInterrupt in the same process.
The original scorer receives the interruption normally; no monkeypatch, model
invocation or second process is involved. A long native numerical operation may
defer Python interruption until it returns. This is an offline job, so the
reviewed runner's owned-process timeout policy remains available after its
cooperative grace period. This wrapper never terminates a process itself.

Scans check closed/STOP between exact expected paths and hash chunks; per-score
JSON reads are capped at 16 MiB. Observer close waits at most 3 seconds. Partial
STOP JSON receives at most 2 seconds during execution; an unresolved final STOP
is a failure. Mutable receipt publication retries transient PermissionError six
times, with 20/40/80/160/250 ms waits and a unique temporary file. Persistent
failure preserves the named temporary and never publishes partial JSON.

Before COMPLETE, the observer joins, the main thread rescans every score,
validates the final scorer receipt, all 15 exact aggregate bindings, and complete
unique coverage/scene membership for 3840 new + 1920 reused cells. During these
checks, the main thread publishes a throttled five-second FINALIZING heartbeat during
reads/hashes and subsequent source checks, with the actual committed score count
unchanged. Verification count is a separate diagnostic; revalidating a score
does not count as new scientific progress. No checkpoint/publish recursion occurs.
It checks the frozen helper/plan/source graph, exact admission and index bytes again and
checks STOP immediately before atomic publication (also on publication retries).
An observed late STOP, changed source/admission, missing/duplicate row or changed
artifact prevents COMPLETE. STOP after the final commit check is a later request
against an already completed offline scorer, with no further job launched here.

Outputs use runner-provided heartbeat/completion/stop paths. Failure produces
`SCORER_PROTOCOL_FAILURE.json` when storage permits, with partial scientific
files preserved. No hardware restoration receipt is fabricated for this offline
job. COMPLETE binds actual scorer receipt/proof, admission, plan, indices, helper
and wrapper, and only claims the declared scorer result. It does not claim
native confirmation, physical qualification or overall S6D completion.

## Model-free fixture commands (all scratch and outputs on G)

Use a fresh suffix; existing fixture roots are never overwritten. The inherited
analysis interpreter provides psutil 5.9.0 and pinned NumPy/SciPy/MeetEval. The
fixtures do not call the real scorer, MeetEval, a model or hardware. They use a
tiny fake scorer with two new cells and one control, and do not repeat the
previous 21 width-matrix fixtures.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = "$sim\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
& $py -B "$sim\scripts\s6d_width_score_protocol_checks_v1.py" --fixture-root 'G:\Just_Peachy_S6D\20260913T195357Z\width_score_protocol_checks_v1'
```

Anaconda Prompt/CMD uses the explicit pinned interpreter:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=%SIM%\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%PY%" -B "%SIM%\scripts\s6d_width_score_protocol_checks_v1.py" --fixture-root "G:\Just_Peachy_S6D\20260913T195357Z\width_score_protocol_checks_v1"
```

Read the resulting `RESULT.json` for each specific fixture and source hashes.
The initial G-only fixture epoch passed all 48 checks. Its receipt and log are
bound by `reports/S6D/20260913T195357Z/angles/width_score_protocol_review_v1/SOURCE_FREEZE.json`,
which also binds the three maintained files, their immutable `source_epoch`
copies, the unchanged scorer plan/helper and their separate root review.
Tests cover normal finalization, partial/wrong score identity, changed count or
artifact, missing/duplicate control coverage, partial scorer failure, changed
admission, wrong-owner STOP, actual cooperative interruption, STOP after observer
join and before completion publish, bounded scan cancellation and atomic I/O.
An additional fake-clock fixture advances finalization time without sleeping,
proves fresh heartbeats with unchanged scientific progress, and confirms STOP
and changed source/admission rejection remain active.

## Pending production admission

Root must independently review these sources/fixtures, bind the actual completed
3840 prediction index or indices (not placeholder or partial receipts), create a
real scorer authorization with the fields above, and create/validate a literal
offline queue under the independently accepted runner V3. Required environment
paths are `S6D_HEARTBEAT_PATH`, `S6D_COMPLETION_PATH`, `S6D_STOP_REQUEST_PATH`,
along with `S6D_RUN_ID`, `S6D_JOB_ID`, `S6D_CHILD_RUN_ID`. All output paths and
scorer G/C namespaces must be fresh, and current C>=50/G>=75 GiB experiment
admission floors and the 40 GiB total new-payload cap remain unchanged.

Future literal argv shape (documentation only, not a launch command):

```text
<PinnedAnalysisPython> <exact reviewed s6d_width_score_protocol_v1.py>
--adapter-plan <R>/angles/width_scorer_plan_v2/ADAPTER_PLAN.json
--authorization <root-issued exact scorer authorization.json>
--prediction-indices <actual complete index or indices covering all 16 jobs>
```

The script is argv[1] under the runner; do not insert `-B` before it in a runner
queue. Root can set `PYTHONDONTWRITEBYTECODE=1` as an ordinary environment value.
The queue must verify COMPLETE status, `scoring_complete=true`, observer closed,
3840 committed new scores, 5760 exact coverage and scene cells, 15 bound aggregate
artifacts, and zero hardware/model calls. Production is not authorized by running
these synthetic tests. The helper's lower `run_protocol` API exists for tiny
fixtures; the production CLI always enforces the fixed plan/helper/matrix hashes.
