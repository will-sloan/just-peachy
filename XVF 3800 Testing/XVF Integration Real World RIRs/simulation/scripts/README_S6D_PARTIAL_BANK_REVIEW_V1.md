# Review successful captures from an interrupted S6D bank

Purpose: independently verify the16 completed MAIN captures before the telemetry-finalization failure. This reuses the original whole-input/native framing/six-derivative/callback inspector. It deliberately keeps batch restoration and missing post-QA unresolved, and preserves S45_01_17 as FAIL. It cannot admit a new queue or promote these cases into a final calibrated catalog.

Inputs: immutable bank_queue_v3 first-group plan, interrupted owner's SUMMARY and restoration, physical ledger PASS/result bindings, original route contract and the16 actual audio/metadata/telemetry receipts. It reads full relevant source/native/derivative audio to verify exact packing and saved samples. No audio is played or regenerated and no model or device is opened.

Output: a fresh report at reports/S6D/20260913T195357Z/partial_bank_review_v1/MAIN_FIRST16_TRANSPORT.json. Existing reports are refused; a separately justified new review can use --output under the same report tree. Later accepted device restoration/post-QA must be separately bound before final bank acceptance.

PowerShell:

```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$sim\scripts\s6d_partial_bank_review_v1.py"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%SIM%\scripts\s6d_partial_bank_review_v1.py"
```

This is a file-only scientific artifact review; it creates no background process or automation. All failures, native source epochs and original charges remain unchanged.

