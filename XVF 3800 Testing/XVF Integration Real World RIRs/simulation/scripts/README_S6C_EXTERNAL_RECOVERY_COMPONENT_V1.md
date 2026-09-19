# Independent external lease recovery review

Purpose: source and small private-fixture review of the exact held one-event recovery helper. This does not perform actual recovery, inspect original80 cells, or authorize any native work. Inputs are the SHA-pinned helper/README/owner test and held canonical release source. Outputs are a reproduced28-check receipt and an independent review receipt in a fresh directory. Ten independent checks include original command/cell namespace faults, strict closed-state typing and rename-success/archive-verification-failure preservation. Temporary synthetic lease files are confined to a private OS temporary directory.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_external_recovery_component_v1.py --output '..\reports\S6C\20260910T123540Z\independent_review\external_recovery_component_NEW'
```

Anaconda Prompt / CMD (existing interpreter; no activation/install needed):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_external_recovery_component_v1.py --output "..\reports\S6C\20260910T123540Z\independent_review\external_recovery_component_NEW"
```

Use a new output name on every reproduction. The review binds the original mutation helper and never edits it. Actual release requires separate root authority and its exact documented recovery command.
