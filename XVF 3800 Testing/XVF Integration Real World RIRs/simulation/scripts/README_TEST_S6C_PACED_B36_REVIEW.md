# Independent B36 paced admission review

This model-free check verifies the prepared40-cell B36 manifest against the exact preserved80-cell B00/B01 plan, sealed S6B epoch/profile, original coordinator function ASTs and original native driver. It executes only the actual pure conversion/validation guards, using the exact native interpreter because Python versions can differ in floating-point sum semantics. It does not import a model, hash bulk audio/weights, establish a quiet period or launch native work.

Inputs are the exact source-bound B36 source/README/fixture/manifest and their historical metadata dependencies. Outputs are the additive `independent_review/B36_PACED_ADAPTER_REVIEW_V1.json`, with exact bytes parsed, checks, limits and source bindings. Existing completed review output is not overwritten. Bulk input/model bytes are rechecked by the real runtime admission; this check only preserves and verifies their declared chain through the exact prior plan.

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' test_s6c_paced_b36_review.py
```

Anaconda Prompt / CMD:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" test_s6c_paced_b36_review.py
```

Run only once in the named review namespace; a later changed source requires a separately reviewed version. No packages or models are installed.
