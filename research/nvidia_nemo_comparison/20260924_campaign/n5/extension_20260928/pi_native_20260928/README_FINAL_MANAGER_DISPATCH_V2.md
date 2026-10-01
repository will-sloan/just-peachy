# Final manager dispatcher V2

Use [V1 purpose, prerequisites, inputs, outputs and commands](README_FINAL_MANAGER_DISPATCH_V1.md), substituting dispatch_field_local_joint_v2.py. V1 failed before issuing a policy or creating a Pi root because the actual Pi observation clock was slightly ahead of the host clock. Its raw preflight and exact closure receipts are preserved under final-manager-joint-v1; no capture or manager mutation occurred.

V2 changes only the read-only probe return barrier: record actual native observation and host receipt timestamps; reject drift outside -120..+5seconds; if native time is ahead, wait at most5seconds for the host to reach that exact unchanged timestamp. Record measured wait and resulting host time. The original lifecycle120-second freshness/future rejection remains unchanged. No clock is set or retimestamped. The same barrier applies before receiver lifecycle validation.

PowerShell:
```powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\dispatch_field_local_joint_v2.py --help
```
CMD / Anaconda Prompt (after changing to the native source directory in V1):
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B dispatch_field_local_joint_v2.py --help
```
Actual CLI arguments and all full reservations/CPU/RAM/storage/deadline bounds are unchanged. Use a fresh private output and fresh observed owners/census; never rerun the failed output. A previously unadmitted and never-created Pi root has no consumed policy, but its absence must still be checked by native initialization.

