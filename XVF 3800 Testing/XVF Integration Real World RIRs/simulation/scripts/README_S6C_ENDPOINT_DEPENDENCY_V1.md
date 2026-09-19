# Endpoint native dependency and job-grid checks

Purpose: verify that the last two endpoint-advice profiles require their actual full native profile and real cue stream, and cannot reuse N01 ASR observations merely because recipe_id is N01. This companion tests the frozen epoch6 native admission and policy-matrix dependency functions; it does not change their source or launch models.

Inputs: the SHA-pinned epoch6/V7 registry, original V6 parent registry, endpoint amendment, exact 224-job manifest, fixed input/panel bindings, frozen worker/common/matrix modules and unchanged model assets admitted by the V5 coordinator loader. Output: immutable `reports/S6C/20260910T123540Z/endpoint_factorial_v1/DEPENDENCY_CHECKS.json`, including every source binding, named guard result and explicit model-free scope. Existing results are never overwritten.

The check verifies exact 384-row preservation and four additions, 56-case/two-tap grid including all 11 empty/music cases, exact parent numeric settings and every native identity. It exercises the actual `job_identity`, `validate_job` and `exogenous_key` functions, plus the exact full-dependency guard AST extracted from the frozen policy loop. Guard extraction avoids executing the replay/output loop and is identified as such. Wrong/rekeyed profiles, decoder, cue condition, absent real telemetry and mismatched parent ID must reject. Positive cache-key separation is not evidence that alternative graphs were executed. No gallery, user data, raw source editing or model factory is used.

PowerShell, after endpoint registration, epoch6 freeze and 224-job preparation:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\test_s6c_endpoint_dependency_v1.py"
```

Anaconda Prompt or CMD (existing environment, no installation):

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\test_s6c_endpoint_dependency_v1.py"
```

This prepares no coordinator admission and launches no native worker. Root controls later execution through README_S6C_ORCHESTRATOR_SCAN_V5.md.
