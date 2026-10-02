# Failed-helper cleanup regression

Purpose: execute only manager6's changed failure_poll method against one real, naturally exited Windows subprocess, with one already-closed pipe and the other pipe still open. Verify drain/close, exact child death, release of the process handle and FAILURE/EXIT callback publication. Native ticks, journal and gate identity are synthetic; this is not Pi or runtime recovery proof. The source is extracted by AST without importing the manager or loading models.

Input: a fresh output directory. Outputs: CPU14 host and child owner receipts plus RESULT. Run once for this change; preserve failed output and do not reuse it.

PowerShell:

~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\check_runtime_failure_cleanup_v1.py --output NEW_PRIVATE_OUTPUT
~~~

Command Prompt / Anaconda Prompt:

~~~bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_runtime_failure_cleanup_v1.py --output NEW_PRIVATE_OUTPUT
~~~

Run after exact source backup and independent restore under the current bounded host scope. One subprocess,10-second wait, no Pi access or capture. Native candidate recording remains the next acceptance check.
