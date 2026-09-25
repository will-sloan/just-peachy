# Application panels with explicit logging-derivative lineage

`paced_panel_plan_v2.py` prepares and reconstructs paired application plans using
the full reviewed component/method/score banks as the comparison parent and the
qualified complete-journal source as the actual application. The old V1 planner,
plans and source receipts remain intact. The new schema is
`n4-paced-panel-plan-v2`; old plans cannot be passed through its execution API.

Inputs are both complete main/modes scoring reviews, an explicit proposed
selection covering all 16 compositions with inclusion/exclusion reasons, the
existing 480-input preparation and fixed 24-input panel/eight timing anchors,
and JOURNAL_APPLICATION_PRESTART_CHECK_V1.json with its source-context proof.
The source context proves that only common event retention changed and that
the copied catalog bytes, runtime metadata, original gallery payloads and
prediction files are unchanged. The prepared metadata retains the scored parent
bindings separately from the actual derivative bindings. Every cache key binds
that complete context, so an older application's evidence cannot silently alias
the derivative. Child inputs retain the unchanged audio-only allowlist: actual
source/catalog/gallery/runtime/model assets only, without score reports, source
parent metadata, selection rationale or evaluator truth.

The selection rules, source-speed policy, exact baseline, 40 cells per candidate
(24 panel plus 16 timing repeats), file/repetition/candidate ordering, fresh
process requirement and one-candidate resource policy reuse the unchanged V1
planner. The V2 context join additionally requires exact scored-parent and
runtime matches. The real preparation/reconstruction path still calls the
qualified complete-score review gate and verifies actual saved-waveform/model
bindings. It will refuse missing or partial banks. It does not choose candidates,
launch an application or assign acceptance/resource tiers.

Outputs of the production CLI are immutable ADMISSION.json, PLAN.json and
RESULT.json with PREPARED_PANELS_AND_REPEATS_ONLY. The internal
`admit_plan(path)` independently reconstructs the full plan after its preparer
exits; the future V2 runner and reviewer should use that API. `execution_payload`
returns a defensive copy of the unchanged child schema for one row. The current
V1 runner is still bound to V1 planning and must not be used with these plans.

First run the development probe, using a fresh output. It checks six targeted
source-lineage/cache/firewall/partial-review cases and rehearses 1,240 payloads
across all 16 actual catalog routes with explicit unavailable-review fixtures.
No production plan or shortlist is written. It reads/hashes saved input files
without audio execution, uses CPU14, checks exact active D1 ownership and source
bindings, the helper lock, 720-second limit, 8-MiB output limit, C:50/G:75 GiB floors
and the shared 50-GiB allowance including the 6-GiB reserve. D1 remains on CPU4.

PowerShell probe:

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_paced_panel_plan_v2.py" --output "$jpLocal\n4\paced-panel-plan-probe-v2"
```

Command Prompt and Anaconda Prompt probe (no activation/install):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_paced_panel_plan_v2.py" --output "%JP_LOCAL%\n4\paced-panel-plan-probe-v2"
```

Only after both complete scoring reviews and a justified selection exist, and
the V2 planner qualification has been published, run production preparation.
Replace the capitalized filenames below with actual reviewed private paths:

```powershell
& $jpPython -B "$jpCode\paced_panel_plan_v2.py" --main-review "$jpLocal\n4\MAIN_REVIEW.json" --modes-review "$jpLocal\n4\MODES_REVIEW.json" --selection "$jpLocal\n4\SELECTION.json" --output "$jpLocal\n4\PACED_PLAN_FRESH"
```

```bat
"%JP_PY%" -B "%JP_CODE%\paced_panel_plan_v2.py" --main-review "%JP_LOCAL%\n4\MAIN_REVIEW.json" --modes-review "%JP_LOCAL%\n4\MODES_REVIEW.json" --selection "%JP_LOCAL%\n4\SELECTION.json" --output "%JP_LOCAL%\n4\PACED_PLAN_FRESH"
```

The guarded probe is phase-specific to active D1; re-observe and version its
admission if the phase changes. Keep failed attempts, gallery/audio data and
full private evidence. Successful development qualification is
PASS_JOURNAL_DERIVATIVE_PANEL_PLANNING_CHECKS_ONLY and explicitly does not prove
the complete production gate has passed. Actual app source execution, full
native/pane/naming/timing review, exclusive resource measurement, continuity,
stop/restart and N4/N5 acceptance remain outstanding.
