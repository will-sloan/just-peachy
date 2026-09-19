# Final S6A package

`s6a_handoff.py` verifies completed analysis and builds the compact ChatGPT handoff. Inputs are all final S6A receipts, the exact frozen application and B0 code, and four authored Markdown entry documents: START_HERE, S6A_JOINT_REPORT, NEXT_STAGE_INPUTS and WORKBOOK_UPDATE. It requires 480 baseline scores with360 exact historical matches, 720 completed native probes and3840 reference/control scores. It rehashes final native and scored evidence, checks saved zero-drop counters and owned process creation times, and produces an application diff from B0. It does not run models or audio hardware.

PowerShell:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' .\s6a_handoff.py
```

Anaconda Prompt / Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s6a_handoff.py
```

Outputs: FINAL_COMPLETION_AUDIT.json, S6_APP_CHANGE_FROM_B0.diff, LOCAL_ARTIFACT_INDEX.json and PACKAGING_RECEIPT.json in the report root; S6A_JOINT_CHATGPT_HANDOFF_20260909T202250Z.zip in simulation/handoffs. The ZIP contains Markdown, compact JSON/CSV, code and at most six PNGs. Raw audio, model weights, vectors, Word and full event logs stay local. CRC and member SHA checks run after creation. The target is10MiB and maximum20MiB. The script refuses to replace an existing ZIP; preserve it and deliberately version corrections. Inspect all figures and the authored report before invoking this final gate. No automatic commit, push, training, simulation expansion or source cleanup occurs.

Before packaging, finalize upstream analyses and design receipts, then refresh the component maps/plumbing, then the required-validation audit. The audit hashes its upstream evidence; plumbing stores only an informational path to the downstream audit, avoiding a circular hash dependency. The final gate requires every requirement row COMPLETE and verifies each bound evidence file. It also requires the actual neural prefix check to pass, the latest guarded RUN invocation to have returned, cleanup to match the current coordinator PID/creation time, and those owned processes to be absent. A stale cleanup receipt from an earlier invocation cannot satisfy closure.

The archive is first written to `.zip.building`, checked for CRC, member hashes, allowed payload types and size, and only then renamed to its final `.zip` name. An interrupted or rejected build is preserved for inspection rather than silently replaced.

Final audit also calls the resume guard's read-only verification function to rehash every declared native code, profile, raw/gained audio, telemetry and model-asset binding after execution. It does not call the guard CLI or replace the completed RUN pointer with a VERIFY_ONLY pointer. This complements the pre-dispatch verification and records the final unchanged-byte evidence.
