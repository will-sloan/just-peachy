# Independent native geometry reader

Purpose: collect only small private outputs from a closed native recipe job and independently verify complete sample/frame coverage, trace chronology, arrays, numerical repeat and same-geometry generic/A76 agreement. It rehashes every bound remote input, checks exact boot/PID/start-tick closure and refuses any active campaign unit. It does not run inference or score accuracy.

Inputs: one run made by dispatch_geometry_v2.py, terminal local LAUNCH_RESULT, remote CONFIG/INPUTS/ADMISSION/OWNER/RESULT, arrays and per-call traces. Outputs: private local copies, CLOSURE_REVIEW and REVIEW; the identical scoped REVIEW is stored in that run's Pi directory for a later reference binding. No shared ledger changes. A successful review qualifies only the declared native component scope, never application acceptance or real-life quality. A failed assertion leaves collected evidence for inspection and writes no PASS.

PowerShell, from this report directory:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' review_geometry_v1.py --run-id d1-geometry-stream-generic-v2
```

CMD/Anaconda Prompt:
```cmd
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" review_geometry_v1.py --run-id d1-geometry-stream-generic-v2
```

Use `cd /d` in CMD to this file's folder first; in PowerShell use Set-Location. The existing interpreter supplies numpy/psutil; no installation/download. Host coordinator is pinned toCPU14, remote collectionCPU3. Run once on a new closed job; preserve existing review receipts. See README_GEOMETRY_V2.md and README_GEOMETRY_DISPATCH_V2.md for execution bounds and strict SSH identity.
