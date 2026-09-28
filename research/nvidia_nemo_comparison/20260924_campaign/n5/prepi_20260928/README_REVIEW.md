# Independent saved-file lifecycle review

Purpose: read closed pre-Pi Windows evidence without starting inference or UI.
The reviewer independently joins admission, source/runtime/audio hashes, both
phase outputs, normal Windows job closure, exact exited supervisor/coordinator,
all-sample counts, native D1 activity, actual E0 encoder use and saved-state
render/reopen/delete. It rejects successful process exit with Controller errors,
missing phases, retained workers, forced termination or source changes.

Inputs: a completed run under local/n5/prepi-20260928 and a fresh output JSON.
Outputs: a compact, transcript-free scope receipt. PASS is one saved-file
lifecycle only, not N4/N5 acceptance, personal recognition or Pi performance.
All raw captions stay in the original private evidence. The script pins itself
to CPU14 at BelowNormal and reads only metadata/assets for hashing.

PowerShell from this directory, only after the exact run owners have exited:

```powershell
$prePiPython='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $prePiPython -B review_lifecycle_v1.py --run 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-d1-e0-v2' --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-d1-e0-v2-REVIEW.json'
```

CMD / Anaconda Prompt, existing interpreter, no activation/install:

```bat
set "PREPI_PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PREPI_PY%" -B review_lifecycle_v1.py --run "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-d1-e0-v2" --output "G:\Just_Peachy_N1\20260924_campaign\local\n5\prepi-20260928\a0-d1-e0-v2-REVIEW.json"
```

Use matching fresh paths for A2. Failure is preserved; do not weaken the
inference or lifecycle checks to obtain acceptance.
