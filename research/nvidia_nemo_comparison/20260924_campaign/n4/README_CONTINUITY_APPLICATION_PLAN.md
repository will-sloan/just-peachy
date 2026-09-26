# Selected application continuity planning

Purpose: prepare one uninterrupted, source-paced 20:06.78 O0 file for the same
baseline and up to five alternatives selected for the qualified V3 short panels.
This is development and planning code. A prepared plan does not launch inference,
select a backend, pass N4, or establish continuity, timing, resource, restart or Pi
acceptance. The Pi stays off. No microphone access, playback or visible UI occurs.

`continuity_application_plan.py` reconstructs the stopped, qualified V3 panel plan
from full main (7,680) and modes (1,536) scored-review populations. It then checks
the frozen continuity preparation, its code and stopped preparer, reproduces
its 27-session metadata/truth transformation, verifies all file hashes and WAV
headers, and independently compares every original PCM byte with the combined
file using bounded reads. It does not reassemble or modify that file.

The production input is an existing admitted `paced_panel_plan_v3` PLAN.json.
The source, model assets, runtime metadata, gallery and selected backend contracts
come from that exact plan. The fixed `CONTINUITY_INPUT_PREPARATION_V2.json` binds
the 19,308,429-frame mono 16-kHz PCM16 file and evaluator-only references. Each
candidate receives one eight-field audio job and the existing application child
allowlist. Selection reports, joins, actor labels and reference text are omitted.
Only the initial file reset occurs; no internal join commands exist. This is
host software continuity across saved captures, not continuous physical XVF
state. O1 continuity and exact word timestamps are not claimed.

Output in a **fresh private directory**: ADMISSION.json (owner, qualified code,
input panel and inventory), PLAN.json (distinct continuity schema, population,
contracts and cache keys), and RESULT.json (`PREPARED_SELECTED_CONTINUITY_ONLY`).
The qualified numerical/application supervisor must still admit a dedicated
continuity runner; the short-panel runner intentionally rejects this schema.
Run actual short-panel validation before continuity, and validate real mid-file
stop/restart separately. Restarting an application between candidates is not
functional stop/restart evidence.

## PowerShell

Use the exact application Python below. Model-free helpers pin themselves to
logical CPU 14, below-normal priority, one math thread, GPU off. They enforce
campaign disk/output/time limits. These examples do not launch applications.
Replace example input/output paths with verified existing panel evidence and a
fresh output directory; do not run production preparation before complete review.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_continuity_application_plan.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\continuity-application-plan-probe-v1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B continuity_application_plan.py --panel-plan 'G:\Just_Peachy_N1\20260924_campaign\local\n4\REVIEWED_PANEL_PLAN\PLAN.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_PLAN'
```

## CMD and Anaconda Prompt

No environment installation or activation is needed; the absolute interpreter
ensures the same dependencies in either prompt.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_continuity_application_plan.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\continuity-application-plan-probe-v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B continuity_application_plan.py --panel-plan "G:\Just_Peachy_N1\20260924_campaign\local\n4\REVIEWED_PANEL_PLAN\PLAN.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_PLAN"
```

The probe checks the exact active D1 owner before/after, takes immutable source
snapshots, checks the prepared PCM, runs 14 tests and exercises all 16 backend
contracts through 31 fixture payloads. Its development placeholders cannot pass
production reconstruction. Private outputs include PROBE_OWNER.json, source/
snapshots, ADMISSION.json, tests.txt, bounded synthetic PCM tests and RESULT.json
or preserved FAILED.json. No production plan is saved and no model runs. The
qualification receipt binds these results only after the exact helper exits.
The probe specifically targets the current healthy D1 phase; later phases need
a separately reviewed resource admission rather than bypassing its owner check.

Tests cover changed references, reset scope, waveform identity/duration/tap,
candidate membership, source/runtime context, child data isolation, partial
production review rejection, false acceptance claims, and changed PCM/header/
digest. The actual future continuity runner and complete post-run reviewer remain
separate requirements; these checks qualify only the planner.
