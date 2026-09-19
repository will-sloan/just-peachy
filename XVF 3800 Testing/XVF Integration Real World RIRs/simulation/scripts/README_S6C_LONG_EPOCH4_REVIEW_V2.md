# Independent epoch4 long-wrapper review V2

Purpose: independently verify the held epoch4 long-native wrapper's exact source/README/source-check bindings and two repaired authority/lease boundaries. It reruns47 pure fixtures, checks the exact pre-review source preservation, and adds independent same-length/old-mtime buffer replacement, rename failure, archive collision, and post-rename verification-failure tests in a temporary directory. AST guards confirm pre-native authority rechecks and native-outcome → release-attempt → final-closure ordering.

Inputs are the held wrapper, SOURCE_CHECKS_V2.json and its small declared source/manifest/README metadata dependencies. This does not call load_sources, source_checks, prepare or run, read models/audio/event payloads, start neural inference, reserve quiet time, or certify a current process/storage census. Output is a new immutable review JSON. The wrapper remains responsible for later actual admission, full asset/audio verification, native completion and externally checked PID closure.

PowerShell:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$env:PYTHONDONTWRITEBYTECODE = '1'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$sim\scripts\test_s6c_long_epoch4_review_v2.py" --output "$sim\reports\S6C\20260910T123540Z\independent_review\LONG_EPOCH4_COMPONENT_REVIEW_V2.json"
```

Anaconda Prompt / CMD:

```bat
set "SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "PYTHONDONTWRITEBYTECODE=1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" "%SIM%\scripts\test_s6c_long_epoch4_review_v2.py" --output "%SIM%\reports\S6C\20260910T123540Z\independent_review\LONG_EPOCH4_COMPONENT_REVIEW_V2.json"
```

Use a distinct output filename to repeat the same source-bound review. A later wrapper revision needs a separately admitted review; do not edit this check's pinned bytes to imply it covered a prior execution.
