# V4 selected-panel runner and evidence review

Purpose: connect the V4 planner (qualified V3 scoring evidence) to a matching
supervised application coordinator, child permit gate, stopped transport/cell
readers and complete 40-to-240-cell panel review. These fresh derivatives preserve
the earlier implementations and their evidence. They do not select a candidate,
establish functional accuracy, qualify timing/resources, or accept N4/N5.

`application_family_v4.py` binds every parent dependency and all new files.
`paced_application_runner_v4.py` uses `paced_panel_plan_v4.admit_plan` and the same
source-delivery application/private process implementation. The runner's schema
is `n4-paced-application-run-v4`. `paced_child_admission_v2.py` increases only the
maximum code binding count from 128 to 256, because the complete retained lineage
exceeds 128. The permit/input bound stays 256 KiB; lease bound is 4 KiB and expiry
is five seconds. Exact expected hashes, CPU4 child/CPU14 coordinator, private
desktop, parent/supervisor identities, nonce, command, policy, source and slot
checks remain required. No dependency is dropped to fit the previous count.

`review_application_transport_v4.py` requires the exact new runner and checks the
expanded bounded dependency list. `review_application_cell_v4.py` joins its
stopped native/delivery transport with the unchanged observation reader.
`review_application_panel_v4.py` reconstructs the qualified V4 plan and reviews
every planned cell in exact order. Failed/missing/extra cells or progress cannot
reduce the denominator. The family qualification is
`APPLICATION_FAMILY_CHECK_V4.json`; all entrypoints use its exact code manifest.

Inputs: passed `PACED_PANEL_PLAN_CHECK_V4.json` and a real prepared V4 panel,
qualified private-process/source-delivery/child/transport/cell/population parents,
exact application interpreter, existing supervised slot/resource admission and
saved audio/models/research galleries. Runtime receives the existing 13-field
audio/configuration allowlist; evaluator references and selection reports remain
outside the child. Production requires both complete main/modes score reviews.

Outputs: runner preparation writes private ADMISSION and worker command files;
supervised execution writes owned transport, application, native and delivery
envelopes, closure, ordered progress and terminal results. Review writes a
separate private ADMISSION, compact per-cell evidence and REVIEW (or FAILED).
`PASS_COMPLETE_V4_PANEL_EVIDENCE_COVERAGE_ONLY` is a coverage status, with semantic
caption/naming, accuracy, source-to-widget latency, resource tiers, continuity,
restart and N4 acceptance still false/unknown. Full private evidence stays local.

## Development validation (no GUI/model/application launch)

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_application_family_v4.py --output G:/Just_Peachy_N1/20260924_campaign/local/n4/application-family-v4-probe-v1
```

CMD:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_application_family_v4.py --output G:/Just_Peachy_N1/20260924_campaign/local/n4/application-family-v4-probe-v1
```

Anaconda Prompt: use the same CMD commands and explicit application interpreter;
no conda environment changes. Subsequent attempts need a fresh private suffix.
Run tests through this probe because fixture source/closure contexts and bounds
must be admitted first. It snapshots all 14 files and preserves failures.

The 76 tests comprise nine child gate, twenty runner, eighteen transport,
eleven cell, ten population and eight cross-family checks. They exercise actual
atomic lease writes, synthetic RAM-source delivery, real evidence readers,
seven saved native lifetime classifications and fresh inert transport fixtures.
The new checks cover 256-record admission/readback, rejection of 257 and the old
runner, retention of every dependency, unchanged collection/child control flow,
and AST proof that the child gate differs only in its code count. Runner/slot/
child lifecycles and process/clock/viewport/resource facts are mocked/synthetic.
The CPU14 helper itself must still be rejected by the child gate before model or
source reads. This does not prove successful live application admission.

The development probe is bounded to 20 minutes/8 MiB and uses the existing helper
lock, CPU14/BelowNormal, one math thread and GPU off. It checks the active bank,
exact ownership, all source bindings, C50/G75-GiB floors and private allowance
(active V3 remainder + 6 GiB pending + 0.5 GiB contingency). Shared helper activity
does not qualify controlled performance. No microphone, playback, enrollment,
visible desktop, saved-audio inference or Pi contact is performed by the probe.

## Production preparation and review, after prerequisite completion

These future paths are examples, not evidence that the inputs exist or passed.
After both full score reviews and an evidence-based selection, prepare the V4
panel using README_PACED_PANEL_PLAN_V4.md. Then PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n4/paced_application_runner_v4.py prepare --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-plan-v4/PLAN.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-run-v4
```

CMD and Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/paced_application_runner_v4.py prepare --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-plan-v4/PLAN.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-run-v4
```

Preparation does not start anything. The generated worker.json is consumed only
by the existing authorized supervisor start interface after a fresh exclusive
resource admission. Do not run its `run` or internal `child` branch manually or
edit the shared ledger. One candidate owns CPU4; hidden private desktops preserve
the user's desktop input/focus. Application child lifetime remains bounded to
3,900 seconds, with the existing per-cell reserve, lease renewal and cleanup.
Preserve failed attempts. No live Pi connection is part of this campaign.

After the exact coordinator/children exit, review in a fresh separate directory.
PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B research/nvidia_nemo_comparison/20260924_campaign/n4/review_application_panel_v4.py --run G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-run-v4 --output G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-review-v4
```

CMD and Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/review_application_panel_v4.py --run G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-run-v4 --output G:/Just_Peachy_N1/20260924_campaign/local/n4/selected-panel-review-v4
```

Preparation/review retain the one-hour/8-MiB helper guard. A matching semantic
content composition and restarted/continuous application families still need
qualification. The old restart/content-population planners/readers must not be
silently substituted. Physical CM5 installation, GUI and performance validation
remain deferred until reconnection. Packaging reserve starts 2026-09-28 02:48:19
UTC; campaign stops by 2026-09-28 14:48:19 UTC. Keep audio, captions, profiles,
raw evidence and model weights out of GitHub; publish only code and redacted receipts.
