# Arrival sentinel post-closure analysis

Purpose: admit and analyze the separately declared12-cell arrival-order sentinel (C088/C105, one scene, both taps, three repetitions). This source-only adapter wraps the held canonical post-closure converter without changing its native extraction, shared-policy parity, actual wall-emission metrics, source-support mapping or name API. It neither creates the experiment nor starts native/model execution.

Inputs: exact reviewed V5 sentinel manifest, its later actual completed PACED_INDEX, the closed native cell chains and original enrollment/Q/support authorities. Every event, finalization, export and process buffer is verified by the canonical converter. Source and native closure use V5's explicit sentinel metadata API. Outputs live under `REPORT/paced_arrival_analysis/<namespace>`: PLAN, per-cell observations and predictions, one PREDICTION_INDEX per repetition, and a final complete or preserved failure receipt. Repeats remain separate. The same-native prediction records its original canonical transformation helper; the outer plan/receipt additionally bind this explicit sentinel adapter and V5 source.

Only three orchestration functions are compiled in a separate namespace from the exact held canonical source: safe_output, prepare and run. The only literal changes are `paced_analysis` to `paced_arrival_analysis` in output paths. The namespace supplies the exact sentinel inventory API and separate analysis schema/source list. Original canonical/V4 globals stay unchanged; continuous compositions, historical generations and other new panels are not admitted.

PowerShell (checks require no actual paced run):

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cReport = Join-Path $s6cSim 'reports\S6C\20260910T123540Z'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$env:PYTHONDONTWRITEBYTECODE = '1'
& $s6cPython (Join-Path $s6cSim 'scripts\s6c_paced_sentinel_analysis_v1.py') checks
```

After actual sentinel completion, quiet-lease release, all recorded owner closure and independent source review:

```powershell
$s6cScript = Join-Path $s6cSim 'scripts\s6c_paced_sentinel_analysis_v1.py'
& $s6cPython $s6cScript prepare --manifest (Join-Path $s6cReport 'paced_arrival_sentinel\arrival_boundary_v1\MANIFEST.json') --index (Join-Path $s6cReport 'paced_arrival_sentinel\arrival_boundary_v1\PACED_INDEX.json') --namespace arrival_boundary_analysis_v1
& $s6cPython $s6cScript run --plan (Join-Path $s6cReport 'paced_arrival_analysis\arrival_boundary_analysis_v1\PLAN.json')
```

Anaconda Prompt or Windows CMD (use the exact existing Python, no install needed):

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_REPORT=%S6C_SIM%\reports\S6C\20260910T123540Z"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_sentinel_analysis_v1.py" checks
```

After the same actual closure and source review:

```bat
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_sentinel_analysis_v1.py" prepare --manifest "%S6C_REPORT%\paced_arrival_sentinel\arrival_boundary_v1\MANIFEST.json" --index "%S6C_REPORT%\paced_arrival_sentinel\arrival_boundary_v1\PACED_INDEX.json" --namespace arrival_boundary_analysis_v1
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\s6c_paced_sentinel_analysis_v1.py" run --plan "%S6C_REPORT%\paced_arrival_analysis\arrival_boundary_analysis_v1\PLAN.json"
```

Preparation without a real completed index is refused. Existing output directories/results are preserved, and active quiet leases prevent heavy post-analysis. Tests and prepared native manifests are not empirical paced evidence. Core/name score commands later consume each repetition's index separately under the unchanged scorer contracts. The original34 pure checks are reproduced, along with isolated namespace/API identity assertions; these checks do not replace independent review.

