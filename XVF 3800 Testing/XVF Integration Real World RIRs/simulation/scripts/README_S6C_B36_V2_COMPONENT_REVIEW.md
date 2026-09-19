# Independent B36 V2 source and closure review

Purpose: reproduce the exact source-bound owner checks and independently exercise the new B36 C-side archive/closed-batch admission. Inputs: explicit owner SOURCE_CHECKS path/SHA, current source/README/test bindings listed there, existing small prior manifests, and a fresh output directory. Outputs: reproduced owner checks and REVIEW_RECEIPT.json. The reviewed source and all original native execution files remain unchanged.

Private synthetic40-cell JSONs test exact archive/owner/completion/reference and fresh inspection failures. Actual prior metadata verifies40 exact B36 jobs, both taps,16cases and4dependent repeats. No native sessions, PCM/models, original runtime cells, actual lease or full storage traversal is read or run. The closed-batch API proves recorded completion/closure; downstream scientific admission still validates native artifacts separately.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_b36_v2_component_review.py --source-checks 'ABSOLUTE_SOURCE_CHECKS.json' SOURCE_CHECKS_SHA256 --output '..\reports\S6C\20260910T123540Z\independent_review\b36_v2_component_NEW'
```

Anaconda Prompt / CMD (existing interpreter; no environment changes):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_b36_v2_component_review.py --source-checks "ABSOLUTE_SOURCE_CHECKS.json" SOURCE_CHECKS_SHA256 --output "..\reports\S6C\20260910T123540Z\independent_review\b36_v2_component_NEW"
```

Use the final reviewed owner receipt and a new output directory. No preparation or runtime command is part of this reviewer.
