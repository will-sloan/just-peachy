# Independent S6D intake and angle review

Purpose: verify every declared pack checksum, independently aggregate all 13,986 angle rows for all six streams at 5/2/0 degrees, check fixed populations and monotonic interval errors, and bind all 240 per-case results. No device access, neural inference, raw-data rewrite or Word edits.

Inputs: --pack is the extracted V2 pack; --report is the existing S6D run; --output is a new JSON receipt path. Outputs: one scoped verification receipt plus a concise stdout summary. A failed assertion exits without a PASS receipt. Use a fresh output filename for another review; existing evidence is never overwritten.

PowerShell:
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$s6dSim\scripts\s6d_root_review_v1.py" --pack 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\Just_Peachy_S6D_Expanded_Capture_Pack_V2\Just_Peachy_S6D_Expanded_Capture_Pack_V2' --report "$s6dSim\reports\S6D\20260913T195357Z" --output "$s6dSim\reports\S6D\20260913T195357Z\intake\ROOT_INTAKE_ANGLE_REVIEW_V1.json"
```

Anaconda Prompt / Windows CMD (existing interpreter; no activation/install):
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%S6D_SIM%\scripts\s6d_root_review_v1.py" --pack "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\Just_Peachy_S6D_Expanded_Capture_Pack_V2\Just_Peachy_S6D_Expanded_Capture_Pack_V2" --report "%S6D_SIM%\reports\S6D\20260913T195357Z" --output "%S6D_SIM%\reports\S6D\20260913T195357Z\intake\ROOT_INTAKE_ANGLE_REVIEW_V1.json"
```

This checks the reported aggregate arithmetic and evidence bindings independently. It does not duplicate the complete raw-telemetry rescore, rerun the native pipeline, validate human listening, or close S6D.
