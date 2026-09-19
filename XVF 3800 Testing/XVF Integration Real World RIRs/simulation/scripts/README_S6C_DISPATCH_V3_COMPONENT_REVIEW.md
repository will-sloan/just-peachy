# Dispatcher V3 independent component review

Purpose: review only the immutable heartbeat delta against accepted V2. `test_s6c_dispatch_v3_component_review.py` pins production V3, reproduces its43 source/private-file checks, restores the whole original V2 module AST, checks the exact16KiB/20,000th-snapshot boundary, and runs unchanged dispatcher code in isolated synthetic globals to inject heartbeat fsync failure.

The failure fixture proves that a readable heartbeat is not completion: the dispatcher propagates the error, retains possible live-child identity, records stopped status, and never calls the completion gate or starts the next batch. No real process is launched. The reproduced Windows sharing fixture uses only a private file and owned reader handle.

Inputs: held V2/V3 dispatcher source, V3 test source and README, plus a new output directory. Outputs: reproduced source checks and `REVIEW_RECEIPT.json`, binding all source bytes. Temporary synthetic files are removed by their fixture context. No actual queue, heartbeat, native/lease/closure record, audio, model, inventory or scientific evidence is accessed. This review does not authorize a queue or infer why an earlier Windows access denial occurred.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_dispatch_v3_component_review.py --output '..\reports\S6C\20260910T123540Z\independent_review\dispatch_v3_component_v1'
```

Anaconda Prompt or Windows CMD, with the exact existing EDGE interpreter and no installation:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_dispatch_v3_component_review.py --output "..\reports\S6C\20260910T123540Z\independent_review\dispatch_v3_component_v1"
```

Always use a new output path for an authorized reproduction. Prior source checks are preserved; no V2 retry suite or broader scientific checks are repeated. Immutable snapshots may briefly be incomplete while written; readers must use a successfully parsed observation and must still require the independent original RESULT/owner/lease completion chain.
