# C12 origin protocol fixtures

Purpose: exercise the actual AST-loaded admission/producer methods with fake16kHz header and stream objects, then require the unchanged bb1b dispatch contract. No pipeline import, neural model, source audio, process, thread start or device API is used. Wrong headers, missing/wrong rate, duplicate origin and original missing-field behavior are explicit negatives.

Inputs: source proposal JSON and its exact48-file source/runner/manifest bindings. Outputs: a fresh G fixture directory with RECEIPT.json; never a native result, queue, approval or altered historical event.

PowerShell:
```powershell
$sim='C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' -B "$sim\scripts\s6d_C12_origin_checks_v1.py" --proposal "$sim\reports\S6D\20260913T195357Z\application\beam_C_source_origin_proposal_v2\PROPOSAL.json" --output 'G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\C12_origin_v1\checks_v1'
```

Anaconda Prompt or CMD:
```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" -B "%SIM%\scripts\s6d_C12_origin_checks_v1.py" --proposal "%SIM%\reports\S6D\20260913T195357Z\application\beam_C_source_origin_proposal_v2\PROPOSAL.json" --output "G:\Just_Peachy_S6D\20260913T195357Z\review_fixtures\C12_origin_v1\checks_v1"
```

Choose a fresh output suffix for repeat checks. The original failed native attempt stays unaccepted. Header fixtures establish event construction and validation only; actual input/source/journal/full-consumption evidence and new root approval remain mandatory before any native completion.
