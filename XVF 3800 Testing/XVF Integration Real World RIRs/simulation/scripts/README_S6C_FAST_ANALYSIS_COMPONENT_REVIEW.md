# Independent unified fast-analysis source review

`test_s6c_fast_analysis_component_review.py` independently checks the held unified adapter's source and metadata interface. It reproduces the existing 38 tiny checks, tests all six family callbacks and preserved tuple/keyword signatures, and uses V7's actual reader factory on synthetic exact-buffer metadata. No real analysis preparation/run, native logs, predictions, audio, model assets or storage scans are performed.

Inputs are the SHA-pinned adapter and its original converter/V7 dependencies, plus temporary synthetic JSON. A fresh output directory receives `REPRODUCED_CHECKS.json` and `REVIEW_RECEIPT.json`, including source bindings, review scope and limitations. Existing review outputs are never overwritten. The parent source review does not imply a successful actual conversion or verified actual native closure.

PowerShell, from the simulation scripts directory:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_fast_analysis_component_review.py --output '..\reports\S6C\20260910T123540Z\independent_review\fast_analysis_component_NEW'
```

Anaconda Prompt or CMD; the exact existing interpreter needs no environment installation:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_fast_analysis_component_review.py --output "..\reports\S6C\20260910T123540Z\independent_review\fast_analysis_component_NEW"
```

Choose a fresh suffix for each reproduction. The receipt's manual source assessment records the independent reading; running these checks alone reproduces the executable guards, not that assessment.
