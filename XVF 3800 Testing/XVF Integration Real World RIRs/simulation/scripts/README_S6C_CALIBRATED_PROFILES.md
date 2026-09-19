# Compile registered C-only naming alternatives

Purpose: retain the109 original S6C candidate settings and add the seven previously registered C-only threshold alternatives as actual validated v3 profiles. This makes no model calls and does not inspect Q outcomes. Unsupported calibration retains its explicit unavailable status.

Inputs: immutable V1 registry, the seven-candidate calibration amendment, completed enrollment/C_ONLY_CALIBRATION_INDEX.json and exact RESEARCH_GALLERY_INDEX.json. The compiler checks candidate, roster, tier and registered numeric grid consistency. C110–C116 files are created once; the original registry is unchanged.

Outputs: EFFECTIVE_PROFILE_REGISTRY_V2.json and fourteen actual per-tap profiles. Freeze a new execution epoch using that explicit registry before running them.

PowerShell from repository root:

```powershell
$sim = Join-Path (Get-Location) 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& '.\.edge-speech-env\python.exe' "$sim\scripts\s6c_calibrated_profiles.py"
& '.\.edge-speech-env\python.exe' "$sim\scripts\s6c_execution.py" freeze --epoch epoch2 --registry "$sim\reports\S6C\20260910T123540Z\EFFECTIVE_PROFILE_REGISTRY_V2.json"
```

Anaconda Prompt / CMD from repository root:

```bat
set "SIM=%CD%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
".edge-speech-env\python.exe" "%SIM%\scripts\s6c_calibrated_profiles.py"
".edge-speech-env\python.exe" "%SIM%\scripts\s6c_execution.py" freeze --epoch epoch2 --registry "%SIM%\reports\S6C\20260910T123540Z\EFFECTIVE_PROFILE_REGISTRY_V2.json"
```

Use a new named revision for changed source/fit data. Existing epoch and original profile files must remain unchanged.
