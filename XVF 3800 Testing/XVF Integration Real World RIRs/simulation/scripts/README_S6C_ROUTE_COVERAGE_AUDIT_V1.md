# S6C exact-route metadata coverage audit V1

Purpose: compare all190 current executable candidates/376 ASR+identity routes with completed non-fixture prediction-index metadata and matching completed core/name-analysis declarations. It also reconciles the28-condition native enrollment manifest with the30-condition gallery policy panel, and proves the two current/frozen same-tap aliases without running models.

Inputs are the V5 effective registry, epoch2 manifest, fixed56-case panel, direct epoch1–4 prediction-index JSONs, one-level analysis receipts, enrollment_v1 job manifest, and the exact C065/C083/C084 profile files. Only those metadata buffers are read and hashed. No input audio, model, vectors, prediction bodies, per-output scores or full journals are rehashed. Output is a new directory containing ROUTE_COVERAGE.json with exact source bindings and all376 route rows, plus a concise ROUTE_COVERAGE.md. Existing output directories are rejected. A changing metadata read is bounded-retried; this does not make the multi-file observation a transaction or final campaign closure.

The raw candidate/route/case coverage union does not count repeated references as new cases or physical inference. A completed score receipt only establishes its declared coverage here; this helper does not independently revalidate every score payload. C083/C084 remain explicit aliases rather than fabricated candidate-ID predictions. Missing cases can be queued, intentionally omitted or genuinely missing; the receipt does not infer which.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\s6c_route_coverage_audit_v1.py" --output "$sim\reports\S6C\20260910T123540Z\route_coverage_v1"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\s6c_route_coverage_audit_v1.py" --output "%SIM%\reports\S6C\20260910T123540Z\route_coverage_v1"
```

Use a new output suffix for a later snapshot. No frozen APP, execution inventory, running coordinator, prediction source or existing report is changed.
