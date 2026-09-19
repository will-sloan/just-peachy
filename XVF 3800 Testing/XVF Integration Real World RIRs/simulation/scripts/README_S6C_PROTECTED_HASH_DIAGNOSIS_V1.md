# Protected code fingerprint diagnosis

Purpose: test whether marshal serialization can change without protected function/code replacement, using the exact frozen driver's code and tiny returned-constant examples. No native/model execution or APP imports occur.

Inputs: held s6c_long_session.py (whole source compiled but module not executed), held fast L wrapper, and the first C065 failed worker log/CELL_OUTCOME plus its compact native RESULT. No original data or events are opened.

Outputs: fresh observer_fast_v1/protected_hash_diagnosis_v1/DIAGNOSIS.json with exact source/attempt bindings, interpreter version, raw versus structural comparisons and replacement-negative controls. Refuses existing output. The proposed structural function is diagnostic code only; no production guard or manifest is changed.

PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B 'C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/scripts/s6c_protected_hash_diagnosis_v1.py'
```

Anaconda Prompt or CMD:
```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "C:/Users/amiri/Documents/GitHub/just-peachy/XVF 3800 Testing/XVF Integration Real World RIRs/simulation/scripts/s6c_protected_hash_diagnosis_v1.py"
```

Run only in the root-authorized diagnostic window. Reproduction of a possible false guard rejection cannot recover missing per-function before/after fingerprints from the completed worker. The failed attempt remains failed at the outer layer even when its native RESULT is COMPLETE.

