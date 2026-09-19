# S6C prepared-source independent review

`s6c_source_material_review.py` verifies the completed source preparation before native enrollment. It reads the bound ECQ manifest, candidate freeze, Q manifest and preparation checkpoints. It hashes every accepted original and prepared WAV, decodes prepared PCM to check its exact hash, and recomputes the unchanged numerical activity/QC estimator. It also checks E/C/Q separation, whole-clip nested 5/15/30-second prefixes and sparse coverage. It makes no model, hardware, download or gallery call.

Inputs are the completed `enrollment_inventory/v2` receipts and their declared local files. Outputs are a compact JSON receipt, exact input/code bindings, per-source verified hashes and unavailable-tier rows. The output must be a new path below this run's report. A failure raises and never publishes PASS; all source files remain unchanged. This is source accounting, not naming accuracy, phonetic truth, independent-session proof or rights clearance.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_source_material_review.py --output '..\reports\S6C\20260910T123540Z\independent_review\SOURCE_MATERIAL_REVIEW_V1.json'
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_source_material_review.py --output "..\reports\S6C\20260910T123540Z\independent_review\SOURCE_MATERIAL_REVIEW_V1.json"
```

Use a new versioned receipt name for another admitted preparation. Do not change the helper or bound preparation code while the audit runs.

