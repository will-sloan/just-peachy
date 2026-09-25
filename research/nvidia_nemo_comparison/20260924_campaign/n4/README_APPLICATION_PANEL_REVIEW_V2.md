# Complete planned V2 panel evidence coverage

Purpose: `review_application_panel_v2.py` reconstructs a qualified production
panel and reviews every declared cell through the V2 joined-cell reader. Expected
population comes from the reviewed selection/plan, never the available files.
Missing or failed cells cannot disappear from the denominator. This checks
evidence coverage, not N4 accuracy/performance acceptance.

Inputs: a completed V2 application run containing its immutable ADMISSION,
RUN_OWNER, RESULT, worker command, cells and per-cell progress; the unchanged V2
runner, planner and cell-review qualifications; and a fresh separate private
review output directory. Both preparer and coordinator must have exited with
their recorded creation identities. The fixed command/interpreter/code, output,
supervision root, admission/result/owner joins and reconstructed plan must match.
Production reconstruction rechecks the complete main/modes score reviews and
qualified derivative context. The review cannot create a selection or plan.

The complete terminal run must contain exactly 40 cells per selected candidate
(24 fixed-panel cells and 16 extra repetitions), with the planner's maximum of
six candidates/240 cells. Every cell directory, ordered COLLECTED binding and
numbered progress receipt must match. Additional, missing, duplicate, reordered,
partial, failed or prematurely accepted evidence is rejected. Paths must remain
inside the run without reparse points. Every cell then passes the independent
transport, complete native-envelope, source/worker/archive, viewport and resource
joins, including exact application identity. No model or application is launched.

Output: private REVIEW_OWNER.json, ADMISSION.json, compact per-cell records and
REVIEW.json with `PASS_COMPLETE_V2_PANEL_EVIDENCE_COVERAGE_ONLY`, or FAILED.json
preserving the partial attempt. Per-cell records retain all joined source evidence
bindings, population/visibility counts, phase intervals and a digest of the full
deterministically recomputable reader output; repeated nested metadata is omitted.
This bounds redundant output. Use the existing 8-MiB review-output guard, one-hour
review budget, C50/G75-GiB floors, private 50-GiB ceiling plus conservative 6-GiB
reserve and original packaging cutoff. Run on CPU14 under the helper writer lock.
Do not overlap this review with controlled application measurements.

`complete_planned_evidence_population_reviewed` describes only evidence coverage.
Raw native text, pane strings, naming, accuracy, latency interpretation, controlled
resource tiers, continuity and stop/restart remain unqualified. All resulting
records retain zero accepted integrated N4 cells. Public stage acceptance must
not treat this status as a completed N4 stage. Full logs and transcripts stay local.

The development probe has eight model-free tests: complete 40/240 populations;
missing/extra/duplicate directories/progress; failed/partial terminal runs;
collected ordering; exact progress counts/bindings; invalid plan census; scope and
binding preservation when compacting the previously qualified synthetic cell;
and missing-production-input refusal. These are explicit synthetic population
objects, not fabricated accepted plans. The positive production admission and
full application panel path remain unexecuted until real reviewed banks and a
completed application run exist. The probe snapshots its four new files, verifies
the healthy exact D1 owner before/after, and writes owner/admission/tests/result
receipts. No new source, model, GUI, microphone, playback or Pi work occurs.

PowerShell development probe:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_panel_review_v2.py" --output "$jpLocal\n4\application-panel-v2-review-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_panel_review_v2.py" --output "%JP_LOCAL%\n4\application-panel-v2-review-probe-v1"
```

After the real plan/run has completed and its owners have exited, replace these
reserved example run paths with the actual admitted run. Every review needs a
fresh output; preserve failures and never edit the run or qualified source.

```powershell
& $jpPython -B "$jpCode\review_application_panel_v2.py" --run "$jpLocal\n4\paced-panel-run-v2" --output "$jpLocal\n4\paced-panel-evidence-review-v1"
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_application_panel_v2.py" --run "%JP_LOCAL%\n4\paced-panel-run-v2" --output "%JP_LOCAL%\n4\paced-panel-evidence-review-v1"
```
