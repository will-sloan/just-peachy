# Whole-panel application content review

Purpose: `review_application_content_panel.py` applies the qualified application
content composition to every cell in a stopped, independently reconstructed V2
panel. It reuses the immutable V2 plan/run admission and exact population checks.
The expected denominator comes from that plan, never the folders that happen to
exist. Each collected cell must match its planned audio job, backend contract,
cell ID and receipt. Each content review joins process/source/closure facts,
prepared display roster and native captions to recorded widget content.

Inputs: `--run` is the immutable completed V2 application run directory;
`--output` must be a fresh separate directory under private `local/n4`. The
qualified full main/modes banks and shortlist must already support the V2 plan.
All 40 to 240 planned cells and progress records must be present and complete,
with stopped exact owners. This tool never launches an application, source,
model or device and cannot bypass the upstream plan gate.

Outputs: private ADMISSION.json, compact `cells/NNNN.json` reviews, a deduplicated
INPUT_BINDINGS.json and REVIEW.json, or a preserved FAILED.json. Each compact
record fingerprints its full reconstructed content review and input bindings.
Original native/viewport histories remain intact and permit reconstruction;
compact counts are not substitutes for raw evidence in future metrics. The
shared registry preserves all exact content input bindings and rejects conflicts.
Per-composition/kind/tap totals retain unobserved native spans, never-visible
observed spans, missing final visibility, missing caption revisions, ambiguous
predecessors and cells without native segments. These are cell-span counts;
repeats and taps are separate, not deduplicated corpus words or people.

`PASS_COMPLETE_V2_PANEL_CONTENT_COVERAGE_ONLY` means every planned cell passed
the content/roster consistency review. It is not accuracy, naming, inference
completeness, precise event attribution, source-to-widget latency, continuous
visibility, resource-tier, continuity, stop/restart or N4 acceptance. The maximum
recorded observation interval is a sampling-gap diagnostic only. All integrated
acceptance counts remain zero. Private texts, labels, rosters, galleries and
evidence must never enter public Git.

The reviewer runs on CPU14/BelowNormal with one math thread, no GPU, the helper
lock, a one-hour limit, an 8 MiB output cap and campaign disk/private allowance.
It bounds panels at 240 cells and input bindings at 32,768. Output size is
checked before each receipt write. Run outside exclusive paced measurements.
The child runner and all earlier qualified code remain unchanged.

The guarded development probe uses fresh attempt directories, source snapshots,
exact helper ownership, a 12-minute cap and before/after D1 identity, heartbeat
and protected-code checks. Fourteen tests reuse eight qualified population
tests (including 40/240-cell synthetic populations), then test compaction of a
saved synthetic all-reader cell, scope flags, row joins, missing visibility,
repeat/tap grouping, conflicting bindings, changed rosters and invalid sampling
intervals. The positive production plan gate and a real panel have not run;
these tests never manufacture an admitted production plan.

PowerShell development probe (use a fresh suffix for every rerun):

```powershell
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$jpCode='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
$jpLocal='G:\Just_Peachy_N1\20260924_campaign\local'
& $jpPython -B "$jpCode\probe_application_content_panel.py" --output "$jpLocal\n4\application-content-panel-probe-v1"
```

Command Prompt and Anaconda Prompt (use the pinned interpreter directly):

```bat
set "JP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "JP_CODE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4"
set "JP_LOCAL=G:\Just_Peachy_N1\20260924_campaign\local"
"%JP_PY%" -B "%JP_CODE%\probe_application_content_panel.py" --output "%JP_LOCAL%\n4\application-content-panel-probe-v1"
```

Production review, only after an actual admitted V2 run has fully stopped.
Replace the placeholders with its existing directory and a fresh output:

```powershell
& $jpPython -B "$jpCode\review_application_content_panel.py" --run '<stopped V2 run directory>' --output '<fresh private N4 review directory>'
```

```bat
"%JP_PY%" -B "%JP_CODE%\review_application_content_panel.py" --run "<stopped V2 run directory>" --output "<fresh private N4 review directory>"
```

The saved scopes and flags deliberately preserve unfinished acceptance work.
Keep the original V2 panel reviewer and qualifications; invoke this new wrapper
explicitly when content coverage is required.
