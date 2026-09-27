# Guarded-score adapter for application panels

Purpose: prepare a fresh, explicit planning schema for the accepted main V3
scores plus the independently reviewed guarded modes scores. The pure adapter
preserves the existing delivery-observed application source, paired panel order,
24 panel cases and 16 additional timing repeats per candidate, baseline-first
selection and six-candidate ceiling. It changes the score policy in cache keys;
the 13-field child payload and its false execution permission remain unchanged.
Existing V3/V4 sources, plans, failed attempts and running workers are untouched.

Inputs to the library are selection/review dictionaries, the exact saved-audio
manifest/panel/eight timing anchors, catalog and explicitly joined application
context. Outputs are in-memory plans or child dictionaries. It writes no plan,
launches nothing and has no production prepare/admit_plan API. Pure functions
accept fixture dictionaries; callers must not treat them as review admission.
The guarded reader independently checks actual closed reviews for the diagnostic.
No evaluator reference, review metadata or selection rationale enters the child.

This is preparation until the diagnostic actually passes and its exact owners
close. A later qualified production planner must bind and reconstruct actual
selected inputs, preserve its own resource provenance and match new application,
semantic, restart and continuity consumers. This adapter does not make an old V4
runner compatible. Source counts must remain explicit; never omit dependencies
to fit the child's source-manifest limit. GUI/resource ownership remains a
separate admission gate, and N4/N5 are not accepted by this diagnostic.

## Bounded diagnostic

`probe_paced_panel_plan_guarded_v1.py` takes the original modes plan, both actual
closed score reviews and a fresh private output directory. It writes the full
source manifest, four source snapshots, a 10-test log, 16 baseline/candidate
fixture comparisons (1,240 child payloads), resource checks and RESULT or FAILED.
It rechecks the real accepted component/application context and saved-panel WAV
hashes. It does not decode audio, load models, start Tk or connect to hardware.
V4 is called only for pure fixture payload comparison, not production admission.

The probe must run through the existing supervisor as the sole N4 worker, after
fresh complete resource census and exact prior-owner closure. Use CPU14,
BelowNormal, one math thread, GPU off, an 8-MiB cap and 20-minute maximum. The
qualified guard checks C50/G75-GiB floors, the 50-GiB allowance and unchanged
packaging cutoff. It uses a separate allocation lock and no manual shared-ledger
mutation. Initial/final complete resource checks and exact probe/supervisor exit
are required before reviewing the outcome. A failure remains preserved.

Run after the current independent modes score review and the prepared guarded
reader diagnostic pass. Do not start a standalone N4 helper beside an active
guarded worker. These are underlying argv examples for a supervised spec, not
permission for a duplicate or unsupervised worker. The suggested output must be
fresh; choose a versioned derivative after a failed attempt or code correction.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $jpPython -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_paced_panel_plan_guarded_v1.py --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-plan-v3.json --main-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-main-score-review-v3-timeout120-v1/RESULT.json --modes-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-score-review-guarded-v1/RESULT.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/panel-planner-guarded-probe-v1
```

CMD and Anaconda Prompt use the same interpreter without environment changes:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research/nvidia_nemo_comparison/20260924_campaign/n4/probe_paced_panel_plan_guarded_v1.py --plan G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-plan-v3.json --main-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-main-score-review-v3-timeout120-v1/RESULT.json --modes-review G:/Just_Peachy_N1/20260924_campaign/local/n4/integrated-modes-score-review-guarded-v1/RESULT.json --output G:/Just_Peachy_N1/20260924_campaign/local/n4/panel-planner-guarded-probe-v1
```

The 10 unit tests use in-memory fixtures, no audio or temporary admissions. In an
available admitted metadata slot, PowerShell can use
`& $jpPython -B research/nvidia_nemo_comparison/20260924_campaign/n4/test_paced_panel_plan_guarded_v1.py -v`.
CMD/Anaconda use the quoted interpreter above followed by the same arguments.
This direct test entry pins its own process. Tests alone do not qualify a plan.

Library example for a future qualified caller with this directory on its module
search path:

```python
from paced_panel_plan_guarded_v1 import application_context, build_plan, execution_payload
context = application_context(scored_context, application_source, source_binding, prestart_binding, common)
plan = build_plan(selection, reviews, jobs, panel, anchors, catalog, context)
child_dictionary = execution_payload(plan, 0)  # source_execution_authorized stays False
```

Preserve private audio, profiles, raw evidence and model weights outside Git.
Packaging reserve starts 2026-09-28 02:48:19 UTC; deadline 14:48:19 UTC, unchanged.
The Pi remains off and live CM5 validation is deferred until reconnection.
