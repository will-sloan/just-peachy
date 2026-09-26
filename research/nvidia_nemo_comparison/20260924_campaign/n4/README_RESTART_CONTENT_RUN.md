# Complete restart content and roster review

Purpose: join the selected restart run's existing stopped-owner, transport,
delivery, lifecycle, viewport and resource reviews with the fixed display roster
and native caption histories for both sessions. Existing qualified code remains
immutable. `review_restart_content_cell.py` is an internal cell API;
`review_restart_content_run.py` is the guarded complete-population command.

Inputs are the immutable selected restart plan/run, exact process identities,
two session journals and closures, unchanged full planned audio job, actual
delivered sample counts, prepared research gallery, both stopped Controller
snapshots, and viewport/resource ledgers. Source/catalog/gallery/runtime bindings
must match the qualified V3 application context. No evaluator truth enters this
review. Model weights and profile vectors are never loaded; saved profile vector
hashes are verified where required by the original baseline roster reader.

The first release retains its partial-delivery scope. Old captions visible in
the second viewport keep their original source clocks. Missing native revisions,
unfinished utterances, native spans never observed in the widget, and missing
resource samples remain explicit. Changed or swapped evidence, foreign roster
spellings, manual corrections, wrong caption text, missing pairs and reused
process/session identities fail. Both session snapshots must match the same
prepared roster and primary settings.

Outputs are private REVIEW_OWNER, ADMISSION, one full content JSON per pair and
REVIEW, or a preserved FAILED receipt. All captions, identities and raw evidence
remain under `local/n4`; public qualification contains counts and bindings only.
This composes evidence, not functional or performance acceptance. Naming accuracy,
consumed-event attribution, source-to-widget latency, physical scanout, controlled
resource fit, restart acceptance, deployment tier and N4 acceptance remain
unqualified until the campaign's actual runs and acceptance reviews establish them.

## Development qualification

`probe_restart_content_run.py` runs 21 composition/population tests plus 23
native-content and 24 complete-population regressions. New content tests call
the actual native, viewport and fixed-roster readers, using synthetic captions,
clocks and geometry. The earlier complete lifecycle reader is mocked in those
cell fixtures; selected plan admission and cell leaves are mocked in population
fixtures. These limits are recorded explicitly. No GUI, model, saved-audio source,
microphone, playback or Pi is started by the probe.

The probe observes the healthy V3 main bank before and after, checks exact
worker/supervisor identities and bound code, and records census uncertainty.
It uses CPU14 BelowNormal, one math thread, GPU disabled, the existing evaluator
writer lock, a 20-minute budget and 8 MiB private output. It accounts for the
active main allocation, 6 GiB pending reservations and 0.5 GiB contingency inside
the 50-GiB private limit; probe output comes from contingency. C:50/G:75 GiB floors
and the fixed packaging cutoff remain. Preserve failed attempts and use a fresh
output suffix. Qualification requires exited probe ownership and exact sources.

## PowerShell

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$appPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$stage = 'research\nvidia_nemo_comparison\20260924_campaign\n4'
$privateN4 = 'G:\Just_Peachy_N1\20260924_campaign\local\n4'
& $appPython -B "$stage\probe_restart_content_run.py" --output "$privateN4\restart-content-run-probe-v1"
```

Only after actual selected restart execution completes, all exact owners exit,
and RESTART_CONTENT_RUN_CHECK_V1.json qualifies this exact implementation:

```powershell
& $appPython -B "$stage\review_restart_content_run.py" --run "$privateN4\selected-restart-run-v1" --output "$privateN4\selected-restart-content-review-v1"
```

The production paths above are examples for the eventual selected run; choose
the actual verified terminal directory. Do not manufacture missing inputs or
review an active prefix. Review budget: one hour and 64 MiB private output,
charged to contingency. Complete next receipts are size-checked before creation,
including UTF-8 and platform newlines; 64 KiB remains for failure records. The original stopped-run admission reconstructs the
selected baseline plus at most five candidates and both required tap anchors.

## CMD and Anaconda Prompt

Use the existing absolute interpreter even if another conda environment is
active. No installation or environment change is required.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
set "APP_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "N4_STAGE=research\nvidia_nemo_comparison\20260924_campaign\n4"
set "N4_PRIVATE=G:\Just_Peachy_N1\20260924_campaign\local\n4"
"%APP_PY%" -B "%N4_STAGE%\probe_restart_content_run.py" --output "%N4_PRIVATE%\restart-content-run-probe-v1"
rem Only after qualified complete execution and exact owner exit:
"%APP_PY%" -B "%N4_STAGE%\review_restart_content_run.py" --run "%N4_PRIVATE%\selected-restart-run-v1" --output "%N4_PRIVATE%\selected-restart-content-review-v1"
```

The probe supplies private fixture roots and exact pure-module paths; standalone
unittest runs are not an admission workflow. The Pi remains off; live CM5 checks
are deferred until reconnection. No campaign deadline is extended.
