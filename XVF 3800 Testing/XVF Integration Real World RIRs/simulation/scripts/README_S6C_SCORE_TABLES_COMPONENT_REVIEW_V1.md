# Compact score-table collector independent review

Purpose: source-bind a bounded independent review of `s6c_score_tables.py` and reproduce its 31 synthetic fixtures. The added fixture checks exact retained CSV strings, split-route and alias preservation, empty versus zero/false behavior, multiline Unicode/JSON cells, and the three omitted-cell hashes/schema/key references. It does not export actual scores or read whole bank tables.

Inputs are the exact `compact_score_tables/COLLECTOR_CHECKS_V1.json` receipt, its held helper/README, and isolated synthetic CSVs. Output is a new immutable `independent_review/SCORE_TABLES_COMPONENT_REVIEW_V1.json` with source hashes, reproduced counts, explicit conclusions and limits. No neural model, scorer, raw audio, predictions or event tree is used. Existing receipts are never overwritten. Run once; an existing final review path intentionally rejects a duplicate publication.

PowerShell:

```powershell
$repo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$sim = Join-Path $repo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$repo\.edge-speech-env\python.exe" "$sim\scripts\test_s6c_score_tables_component_review_v1.py"
```

Anaconda Prompt / CMD:

```bat
set "REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "SIM=%REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"%REPO%\.edge-speech-env\python.exe" "%SIM%\scripts\test_s6c_score_tables_component_review_v1.py"
```

This is a source/fixture review, not approval of an unspecified final input catalog or new study results. The original collector's README controls any later real export. In particular, scope labels describe the explicit supplied authorities; the collector does not certify their case grid or reinterpret metrics.
