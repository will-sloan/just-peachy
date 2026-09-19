# Independent inventory V3 adapter review

Purpose: review the revised outer-long-lineage collector without collecting a real inventory. Inputs are ADAPTER_V3_CHECKS_V2.json, exact current adapter/base source and READMEs, and preserved previous source buffers. It reruns44 model-free adapter checks, adds invalid observed creation time and exception-restoration checks, and verifies that a constructed invalid outer admission adds no physical session while preserving unknown closure. Temporary fixtures have no real study receipts or models.

Output is a new source-bound independent review JSON. It does not execute collect, scan actual banks, read audio/models/vectors/predictions/events or alter held code. Later actual long evidence requires a separate inventory run and saved-snapshot validation.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\test_s6c_inventory_adapter_review_v3.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\INVENTORY_ADAPTER_COMPONENT_REVIEW_V3.json"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\test_s6c_inventory_adapter_review_v3.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\INVENTORY_ADAPTER_COMPONENT_REVIEW_V3.json"
```
