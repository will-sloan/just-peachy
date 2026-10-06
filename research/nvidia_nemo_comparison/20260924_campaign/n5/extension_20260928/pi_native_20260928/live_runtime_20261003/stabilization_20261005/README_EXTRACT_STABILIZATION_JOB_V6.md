# Extract an actual build26 live JOB

Purpose: persist only the successful guarded-launch result's actual JOB,
with exact build26 manifest, unchanged V5 helper, current boot, unit, owner,
invocation,256MiB copy limit and canonical output root. V6 differs from V5 only
in manifest and README identity. No native action or assumed process closure.

Inputs: actual wrapper RESULT.json and its exact classic-ui-check label.
Outputs: private CPU14/FILETIME registered preparation, independent source/input
restores and a fresh `<label>-JOB.json`. Existing JOB files are never replaced.
Wait for complete native closure before using the JOB for finalization.

PowerShell:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B './extract_stabilization_job_v6.py' --result 'ACTUAL_WRAPPER_RESULT.json' --label classic-ui-check-29
```

CMD and Anaconda Prompt:

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B extract_stabilization_job_v6.py --result "ACTUAL_WRAPPER_RESULT.json" --label classic-ui-check-29
```

Root verifies exact host-owner absence afterward and uses the existing complete
unit monitor for the actual JOB. Do not print embedded startup payloads or private
session contents. A launch JOB cannot certify a completed recording.
