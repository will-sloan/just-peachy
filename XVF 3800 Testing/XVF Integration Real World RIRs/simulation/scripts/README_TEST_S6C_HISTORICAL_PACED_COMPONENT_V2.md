# Historical paced converter independent synthetic review V2

`test_s6c_historical_paced_component_v2.py` validates the narrow converter repair after preserving V1's exact source and failure proof. It requires corrected converter SHA `982e1c7b2bf38fdc7a92a023cff0e73e2cbccf2072233924e6eaa5e84657a712`. It imports the exact original S6B tracker/scheduler through admitted prepared B36 metadata, feeds synthetic source-cursor watermarks and observations, then runs the unchanged original extractor/replay functions. It does not read real cell events, trajectories, PCM or model weights, and constructs no neural model.

Inputs are the held converter, V4 inventory, exact prepared historical manifest/code authorities and the preserved V1 converter. Output is one fresh JSON receipt containing synthetic observations, native/replay transcript records, parity result, exact source bindings and six semantic rejection results. Whole executable AST is required identical to V1 except the explicit exclusion set, which adds only native `release_watermark_lower_bound_sec` and `release_after_all_lanes_closed`. Actual release values are retained in the synthetic/native output. Causal availability, source support, text, first-display label, decision label and final retained label mutations must fail. This is source-only validation, not empirical paced/native accuracy evidence.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& "$repo\.edge-speech-env\python.exe" -B "$sim\scripts\test_s6c_historical_paced_component_v2.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\HISTORICAL_PACED_ROUNDTRIP_REPAIR_V2.json"
```

Anaconda Prompt / CMD:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"%REPO%\.edge-speech-env\python.exe" -B "%SIM%\scripts\test_s6c_historical_paced_component_v2.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\HISTORICAL_PACED_ROUNDTRIP_REPAIR_V2_CMD.json"
```

Use a fresh output filename. The prior V1 fixture and its failure receipt remain unchanged. The converter's original `checks` and `source-checks` actions should also be reproduced after this repair; they read only tiny synthetic fixtures and already prepared metadata/code.
