# Selected full-file application continuity runner

Purpose: collect the uninterrupted 20:06.78 saved O0 continuity file once per
selected backend through the real shared GUI application, with the qualified
source-delivery observer and complete native journal. This is a separate fixed
runner derived from `paced_application_runner_v3.py`; all prior files remain
immutable. It imports `continuity_application_plan.admit_plan` and its explicit
schema. A short-panel plan cannot be passed as a continuity plan.

Inputs: a stopped, reconstructed qualified continuity PLAN.json; exact application
Python; frozen source/model/runtime/gallery bindings; the existing campaign
supervisor and exclusive numerical/application slot. Production plan admission
rechecks the source short-panel plan against full main and modes score reviews
and compares the prepared PCM against all original segments. See
README_CONTINUITY_APPLICATION_PLAN.md. Run the actual short panels first. This
runner does not establish selection or replace review of those panels.

`prepare` writes private ADMISSION.json and worker.json without launching an
application. `run` is only for the existing supervisor; direct invocation fails
exact supervisor/coordinator ownership checks. Every candidate has a new owned
process on a private Windows desktop, CPU 4, one math thread, GPU off. The desktop
is never switched to the user's input desktop. The coordinator uses CPU 14 and
renews the child lease only while ownership, disk, resource, deadline and
exclusive-slot checks pass. No microphone access, playback, enrollment, training,
Pi connection or visible windows are permitted. Do not start a duplicate worker.

The child gate admits only the fixed audio/runtime allowlist before importing
the application. It prepares the Controller/UI/backend, starts the complete file
once, waits for normal source/consumer/model drain, records native output,
viewport, resource and source-delivery evidence, and closes the Controller. The
parent independently reviews complete native and delivery envelopes. The child
wall-clock limit remains at most 3,900 seconds (the cell retains its own tighter
bound). Timeout, partial delivery, incomplete journal, failed cleanup or uncertain
descendants preserve a failed attempt. Slot release requires verified closure.

Outputs: private cells/ directories, atomic leases, owned process lifetimes,
source/native envelopes, progress/ receipts, and terminal RESULT.json with schema
`n4-continuity-application-run-v1`. Complete collection reports
`COLLECTED_CONTINUITY_APPLICATION_REQUIRES_REVIEW`; it is not acceptance. All N4
credit stays zero. One uninterrupted initial reset is used; no joins or actor
labels reach prediction. Functional mid-file stop/restart is **not included**.
Fresh processes between candidates do not prove restart behavior. The explicit
continuity post-run reader and actual runs remain required; existing V3 short
panel readers intentionally reject this distinct runner identity/schema.

## PowerShell

These first commands are model-free; the last command is shown for the existing
supervisor's admitted worker only. Use fresh output directories and verified
input paths. No production plan exists until full comparisons and selection pass.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B probe_continuity_application_runner.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\continuity-application-runner-probe-v1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B continuity_application_runner.py prepare --plan 'G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_PLAN\PLAN.json' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_RUN'
# Only the existing supervisor may execute the prepared worker.json command:
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B continuity_application_runner.py run --admission 'G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_RUN\ADMISSION.json'
```

## CMD and Anaconda Prompt

Use the absolute interpreter; no environment installation or activation needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B probe_continuity_application_runner.py --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\continuity-application-runner-probe-v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B continuity_application_runner.py prepare --plan "G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_PLAN\PLAN.json" --output "G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_RUN"
REM Only the existing supervisor may execute the prepared worker.json command:
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B continuity_application_runner.py run --admission "G:\Just_Peachy_N1\20260924_campaign\local\n4\SELECTED_CONTINUITY_RUN\ADMISSION.json"
```

The probe snapshots source and owner before checking prerequisites, requires the
exact healthy D1 owner before/after, enforces private output/shared disk limits,
and runs 22 development checks. Existing cleanup/lease/prime-before-import tests
run on the new module, including failed resume, uncertain descendants, incomplete
native journals, old cell variants, delivery mismatch and foreign result paths.
Two additional checks cover distinct continuity admission and the long-file
supervision cap. Lifecycle fixtures are mocked; source-delivery fixtures use
bounded synthetic RAM input. They do not execute saved audio, models or a GUI.
Outputs include PROBE_OWNER.json, source/, ADMISSION.json, tests.txt, synthetic
envelope, RESULT.json or preserved FAILED.json. Publish qualification only after
the helper exits and source/evidence bindings match. Later campaign phases need
their own resource admission; do not bypass this D1-phase probe gate.
