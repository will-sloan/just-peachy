# Independent V5 inventory review

Purpose: independently review the held metadata-only inventory adapter before actual end-of-study accounting. The test reproduces63 owner fixtures, separately derives the literal-only sentinel function transformation with an AST tree walk, checks ten compiled functions, and admits the actual prepared24-cell canonical gate,12-cell sentinel and one B36 O0 continuous manifest. The original V4 globals must remain unchanged.

Inputs: pinned V5/source dependencies, the three exact manifest hashes in the test, and their original JSON authority chains. Output: a fresh JSON receipt plus exact consumed metadata snapshots in `independent_review/INVENTORY_V5_ROOT_METADATA_SNAPSHOTS_V1`. No event log, PCM, model bank or process trajectory is scanned. This is not a full inventory collection or native result.

PowerShell:

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& (Join-Path $s6cRepo '.edge-speech-env\python.exe') (Join-Path $s6cSim 'scripts\test_s6c_inventory_v5_root_review.py') --output (Join-Path $s6cSim 'reports\S6C\20260910T123540Z\independent_review\INVENTORY_V5_ROOT_REVIEW_V1.json')
```

Anaconda Prompt or Windows CMD:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%S6C_REPO%\.edge-speech-env\python.exe" "%S6C_SIM%\scripts\test_s6c_inventory_v5_root_review.py" --output "%S6C_SIM%\reports\S6C\20260910T123540Z\independent_review\INVENTORY_V5_ROOT_REVIEW_V1.json"
```

Use the exact existing interpreter; no install or audio device is needed. Existing output/snapshot namespaces are refused. Before repeating after an intentional source change, preserve the old test and create a separately reviewed version. The historical-session fixture proves only preparation and source lineage; final actual closure is still required.

