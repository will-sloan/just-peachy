# Selected application stop/restart plans

Purpose: prepare two bounded restart pairs per reviewed release candidate, one
for each saved S45_03_03 O0/O1 tap. This is an existing timing regression anchor.
It is fixed before results, identical across candidates and independent of
reference content. Baseline leads at most five alternatives. Each pair uses a
fresh application; its two sessions retain the same Controller/UI/worker/model
store. The first stops at an observed positive prefix after the predeclared
midpoint threshold; the second starts the same full file at zero and reaches EOF.

`restart_plan_policy.py` supplies the light runtime control rule. Inputs remain
the exact eight-field full-file job, 2–120 seconds, unity prepared gain and 16 kHz.
The threshold is floor(frames / 2 / 320) times 320 samples. Actual delivered length
must be observed; threshold is not an exact stop time. The plan never truncates
the WAV or relabels the original file length. First-prefix closure needs the
separate restart readers. Old captions remain and require per-session attribution.

`restart_application_plan.py` reconstructs the qualified V3 selected panel from
both complete modeled score reviews and the reviewed selection. It verifies the
preserved lifecycle qualification, exact 24+16 source occurrences per candidate,
both fixed anchors in every candidate and repetition, and matching audio/contracts.
Its own application policy and cache keys distinguish paired restarts from short
panels and continuity. The 13-field child allowlist is unchanged: no references,
selection, report, stop metadata or evaluator plan enters inference. A future
fixed restart runner must derive the same threshold with restart_plan_policy.
The existing single-source runner cannot execute this plan.

Production input is an accepted `paced_panel_plan_v3.py` PLAN.json. Production
outputs are immutable ADMISSION.json, PLAN.json and RESULT.json under a fresh
private N4 folder. There are two pairs/four sessions per candidate. No positive
production plan is created until the full main/modes scoring review and selection
exist. Plan preparation grants no launch permission, restart qualification,
timing or N4 acceptance. The source files bound to earlier qualifications and
the active numerical run are unchanged.

## Development checks

`test_restart_plan.py` and `probe_restart_plan.py` exercise identity, tap, midpoint,
selection population, audio firewall, immutable lineage, negative upstream/live
owner admission, and false execution/acceptance claims. Routing fixtures cover
all 16 compositions (62 candidate/tap pairs including repeated baseline controls).
The probe also checks the two actual saved WAV hashes/headers read-only. It starts
no Controller, GUI, source, model or Pi and provides no actual paired-run evidence.

The existing Python environment is sufficient; no package installation is needed.
Probe runs on CPU14 below normal priority, one math thread and GPU off, with
healthy exact D1 ownership checks before/after, disk floors, shared allowance,
writer lock, 720-second budget and 8-MiB output bound. Inputs include existing
qualified lifecycle and application preparation receipts. Outputs include owner,
source snapshots, admission, tests, routing hashes and RESULT.json or FAILED.json.
Keep all attempts; change the output suffix for a repeat.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_restart_plan.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-plan-probe-v1'
```

CMD and Anaconda Prompt (the explicit interpreter is already configured):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_restart_plan.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-plan-probe-v1"
```

## Production preparation after upstream acceptance

Publish RESTART_PLAN_CHECK_V1.json only after the private development helper has
exited and its source/receipt hashes match. Replace the illustrative panel path
below with the actual qualified, reconstructed selected-panel PLAN.json; never
substitute fixture, partial or invented success receipts. Use a fresh output.

PowerShell:

```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B restart_application_plan.py --panel-plan 'G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-panel-v3\PLAN.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-plan-v1'
```

CMD / Anaconda Prompt, from the same directory:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B restart_application_plan.py --panel-plan "G:\Just_Peachy_N1\20260924_campaign\local\n4\selected-panel-v3\PLAN.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\restart-plan-v1"
```

Next: fixed exclusive runner integration within the existing 128-code-binding
child limit, native two-session/prefix envelopes, independent source/engine/
archive/viewport/resource review, then the actual model-backed paired execution.
Independent readers must partition retained history by native session. Physical
CM5 installation and performance checks remain deferred until reconnection.
