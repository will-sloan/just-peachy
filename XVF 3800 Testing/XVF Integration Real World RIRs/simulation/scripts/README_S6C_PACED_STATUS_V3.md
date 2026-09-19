# S6C dispatcher V3 status reader

Purpose: make one bounded, read-only hourly progress observation without invoking a model or reading audio. It reads the final dispatcher result when present; otherwise it finds the newest readable immutable snapshot in at most20 blocks with at most1,000 filenames per block. An incomplete newest snapshot falls back to an earlier one, with the skipped count and the observation timestamp exposed. It then reads the active child's small heartbeat, checks each recorded PID and creation time, and reports lease presence. Process inspection errors remain unknown.

Inputs default to the S6C report20260910T123540Z, dispatcher namespace remaining_batches_after_c118_v3 and design/PACED_RUNTIME_QUEUE_AFTER_C118_V3.json. Optional parameters are -ReportRoot, -Namespace and -QueueName. Outputs are compact JSON on standard output; no files, processes, leases or settings are modified. No installation or Conda activation is needed. Windows PowerShell or PowerShell7 can run this script.

## PowerShell

~~~powershell
& 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_paced_status_v3.ps1'
~~~

## Anaconda Prompt / CMD

~~~bat
powershell -NoProfile -File "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts\s6c_paced_status_v3.ps1"
~~~

Use this once per scheduled check. Missing/stale observations, process disappearance or RESULT presence alone do not prove a completed batch. On a stopped dispatcher inspect its original result, possible child and exact owner/grid/archived-lease chain before further work. Never restart a queue or remove a lease through this reader. Every existing mutable heartbeat is opened with read/write/delete sharing and closed promptly. Snapshot timestamps can precede the current read; output labels retain that distinction. Final scientific acceptance remains separate.
