# Dispatcher V2 independent component review

Purpose: independently verify the narrow heartbeat replacement retry without running a dispatcher or touching its live files. `test_s6c_dispatch_v2_component_review.py` pins the held V2 source, reproduces its31 tiny source/file checks, restores the entire original V1 AST by reversing only the stated delta, and checks same serialized bytes during mutation, atomic target preservation, a permanent error following a transient error, and no retry starting after the monotonic deadline.

Inputs: unchanged V1/V2 dispatcher source, V2 test source and maintained README, and a new output directory. Outputs: original test reproduction plus a bound `REVIEW_RECEIPT.json`. Private temporary files and a private Windows reader handle are created and removed by fixtures. No queue, runtime heartbeat, model/audio, lease, closure record, native process or full storage tree is read. No dispatcher is launched. This code requires Windows and the existing EDGE Python for the original private-handle fixture.

The2-second retry/41-attempt limit is a user-space budget; OS calls cannot be preempted. Error5 may be permanent. Exhaustion or any noneligible exception is preserved and propagated. Passing this review is not permission to take over the existing C067 coordinator or reuse its dispatcher namespace.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B test_s6c_dispatch_v2_component_review.py --output '..\reports\S6C\20260910T123540Z\independent_review\dispatch_v2_component_v1'
```

Anaconda Prompt or Windows CMD, using the pinned interpreter directly without environment installation:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_dispatch_v2_component_review.py --output "..\reports\S6C\20260910T123540Z\independent_review\dispatch_v2_component_v1"
```

Use a new output directory for any authorized reproduction; preserve existing receipts and all original sources. This review does not require further scientific or native checks.
