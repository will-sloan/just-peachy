# Independent actual S6C enrollment-result audit

`s6c_enrollment_result_review.py` independently verifies the completed native enrollment and C-only fitting output. It performs no model inference or hardware operation and changes no source, template, gallery, calibration or prediction.

Inputs are the completed enrollment receipt, authoritative plan2, source material/coverage,95 template receipts, actual176 gallery manifests, evaluator-only roster map,1,976 waveform-cache nodes,702 C windows and seven32-cell calibration grids. The script verifies bindings, reconstructs each E-tier centroid from the exact saved native window vectors and actual prepared waveform keys, checks native consistency/counts, loads galleries through the preserved actual ProfileStore, verifies C waveform/vector identities, and recomputes all calibration scores and selection arithmetic. This is cache/provenance and numerical-output validation, not a fresh neural accuracy test or Q identification result. Decoded E/C audio is read to hash native windows; Q audio is never read.

The sole output is additive `reports/S6C/20260910T123540Z/independent_review/ACTUAL_ENROLLMENT_RESULT_REVIEW_V2.json`, with exact source bindings and coverage. A completed existing output is preserved; use a reviewed new output version if the audit must change. Original source-material disjointness/QC remains supported by its separate prior audit.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_enrollment_result_review.py
```

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_enrollment_result_review.py
```

Use the exact original native EDGE interpreter and numerical package versions recorded in the enrollment plan. An explicit guard rejects another interpreter before reading payloads. The first V1 attempt under the separate analysis environment failed exact centroid equality; the original-native-EDGE attempt then passed. Prior helper/README bytes and accepted V1 receipt are preserved, and V2 binds that lineage. No installation is required. Keep dependencies unchanged during the audit. The script imports the preserved `speakers.ProfileStore` loader only; it does not construct SpeakerModels. Peak memory includes the prepared E/C waveform cache and is unrelated to deployment memory.
