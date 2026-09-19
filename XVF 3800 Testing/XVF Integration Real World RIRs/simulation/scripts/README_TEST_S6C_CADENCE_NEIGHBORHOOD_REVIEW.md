# Independent S6C cadence neighborhood admission review

Purpose: reproduce the actual model-free due-ledger checks and independently verify C191–C194, their eight effective profiles, all 448 prepared jobs, immutable parent profiles, epoch source parity and the coordinator's unchanged core paths. This never calls a model, native worker, hardware or launch function. Source/model/audio metadata is checked; only small execution/JSON bytes are rehashed. The original coordinator still must perform current resource, process and native dependency admission at launch.

Inputs are the explicitly SHA-pinned V5/V6 registries, cadence amendment/check receipt, epoch5 manifest, exact prepared job/admission JSON and their declared small dependencies. Output is the new immutable `independent_review/CADENCE_NEIGHBORHOOD_ADMISSION_REVIEW_V1.json`. Existing outputs are never overwritten; a repeated run deliberately fails at publication after validation.

Use the exact EDGE environment so the real frozen profile and evidence admission API is loaded. No environment installation is needed.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $py "$sim\scripts\test_s6c_cadence_neighborhood_review.py"
```

Anaconda Prompt or CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
"%PY%" "%SIM%\scripts\test_s6c_cadence_neighborhood_review.py"
```

The threshold changes when a debt entry becomes due. An admitted global acoustic window acknowledges all due entries; these fixtures do not demonstrate that a particular debtor spoke. No outcome, improvement or currently quiet resource state is asserted by PASS.
