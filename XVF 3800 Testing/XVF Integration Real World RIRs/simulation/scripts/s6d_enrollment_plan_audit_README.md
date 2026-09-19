# S6D input-plan reference audit

`s6d_enrollment_plan_audit_v1.py` independently validates the published input-plan schedule arithmetic and original reference linkage. It uses only Python's standard library. It does not render/read audio PCM, run models, or access hardware. It verifies all outputs from the input-plan binding receipt, exact E clip preservation/order/two-position counts, Q references against canonical source segments, fixed900s continuous lengths, actual metadata-supported silent path changes, known speech followed by music support, guard arithmetic and absence of invented ledger consumption.

Inputs: a published directory from `s6d_enrollment_plan_v1.py`, including its three plans and validation receipt. Outputs: `PLAN_REFERENCE_AUDIT_V1.json` and `CONTINUOUS_EVENT_ANNOTATIONS_V1.json` in a fresh directory. Event annotations use planned corpus/source/convolution support only; they are not observed speech judgments or actual DSP/device results. Existing source/template REVIEW flags remain explicit. The annotations provide exact proposed conversation offsets for the long pauses, seat-path switches and music after speech tails.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$plan = Join-Path $sim 'reports\S6D\20260913T195357Z\device_enrollment'
& (Join-Path $repo '.edge-speech-env\python.exe') (Join-Path $sim 'scripts\s6d_enrollment_plan_audit_v1.py') --plan-root $plan --output (Join-Path $plan 'audit_v1')
```

Anaconda Prompt or CMD:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PLAN=%SIM%\reports\S6D\20260913T195357Z\device_enrollment"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\s6d_enrollment_plan_audit_v1.py" --plan-root "%PLAN%" --output "%PLAN%\audit_v1"
```

Choose a fresh output directory on rerun, such as `audit_v2`; the helper refuses to overwrite prior evidence. No installation is needed. Root must separately review and authorize a builder before payload construction; this audit does not approve or launch capture.
