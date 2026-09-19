# Independent S6C execution guard checks

This model-free checker imports exact copied bytes of the current S6C execution/common helpers and calls their real `make_job`, `validate_job` and `verify_job` functions against small synthetic metadata and byte files. It checks registered job identity, canonical input binding, cue binding, model-asset identity, output containment and named ASR/identity PCM cache routing. It does not launch a coordinator, a worker, models, hardware or audio decoding, and it does not modify real campaign artifacts.

Inputs: `simulation/scripts/s6c_execution.py`, `s6c_common.py` and a fresh output child under this run's report. The helper records exact source snapshots before import and verifies the live source did not change while checking. If the owners are editing those sources, wait for a stable review slot before accepting the result.

Outputs: `CHECK_RECEIPT.json`, source snapshots and tiny preserved synthetic fixture files in the requested new directory. Every case retains PASS/FAIL; a failure or source change returns nonzero. A successful fixture run is not actual native/runtime or real-cache acceptance. Gallery condition-to-roster matching must be reviewed separately once the gallery registry exists.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' s6c_execution_review_checks.py --output '..\reports\S6C\20260910T123540Z\execution_review\checks_v1'
```

Anaconda Prompt or Command Prompt (use the existing project interpreter; no installation):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" s6c_execution_review_checks.py --output "..\reports\S6C\20260910T123540Z\execution_review\checks_v1"
```

Use a new output directory, such as `checks_v2`, for a reviewed code revision. Existing results are never overwritten.

