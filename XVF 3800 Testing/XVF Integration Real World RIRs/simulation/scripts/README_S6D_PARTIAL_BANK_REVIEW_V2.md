# Review the eighteen successful captures in interrupted MAIN batch B3

Purpose: verify all eighteen saved S45_04_01 through S45_04_18 captures against their exact original inputs and six decoded output streams. The unchanged whole-transport inspector is pinned by SHA256. This is the original sixteen-case wrapper adapted only to the B3 plan, case roster and output namespace. The failed S45_04_19 attempt and its missing process-exit proof remain failed. Batch restoration and post-QA remain separate unresolved requirements.

Inputs: bank_queue_v4/groups/P_MAIN6_B3/CAPTURE_PLAN.json (SHA903bbf2b...), hardware_batches/bank_v3_P_MAIN6_B3/SUMMARY.json and restoration.json, physical_ledger.json, the original route contract, and exactly eighteen PASS result bindings and their source/native/decoded audio, callback and telemetry evidence. Full relevant audio is read for exact transport validation; nothing is played, regenerated or sent to a model/device.

Output: reports/S6D/20260913T195357Z/partial_bank_review_v2/B3_FIRST18_TRANSPORT.json. Existing output is refused. The report is transport evidence only and does not admit a queue or establish source-tail calibration, speaker efficacy, restoration or post-QA.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_partial_bank_review_v2.py"
```

Anaconda Prompt / Windows CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_partial_bank_review_v2.py"
```

Run once for this newly interrupted batch. All historical evidence and charges are preserved. Later restoration and QA must be accepted separately; do not rerun this whole-audio check without changed or adverse evidence.