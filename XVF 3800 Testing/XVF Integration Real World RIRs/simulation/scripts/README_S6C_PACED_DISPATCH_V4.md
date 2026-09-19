# Serial paced dispatcher V4

Purpose: continue the original saved-file S6C queue with an explicit B36 V2 coordinator that archives its quiet lease on C:. V3 telemetry, sequencing, deadline, exact process ownership, per-cell completion, stop and failure behavior are preserved. Additions are the independently pinned B36 V2 schema/namespace, exact preparation admission and its explicit C-side closure proof. Original V3 and old B36 files are preserved.

Inputs: exact PATH SHA256 pairs for the finite queue and root quiet authority. These bind source, each wrapper/manifest, unique output roots, counts and deadline. B36 keeps the same original forty job objects. The other remaining batches retain their original manifest bindings. Root creates the launch authority only after independent review and actual quiet-owner closure. No concurrent heavy analysis or model work.

Outputs: reports/S6C/20260910T123540Z/serial_paced_dispatcher/QUEUE_NAMESPACE contains ADMISSION, launch/exit/transition records, bounded immutable heartbeats and RESULT. Namespace must be new; no implicit resume. A failed dispatcher may leave a child running: inspect exact PID plus creation before continuing. No kill or lease deletion is performed. Native outputs remain at each manifest root.

PowerShell:
~~~powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B s6c_paced_dispatch_v4.py run --queue 'ABSOLUTE_QUEUE.json' QUEUE_SHA256 --authority 'ABSOLUTE_AUTHORITY.json' AUTHORITY_SHA256
& .\s6c_paced_status_v3.ps1 -Namespace remaining_batches_after_controls_v4 -QueueName PACED_RUNTIME_QUEUE_AFTER_CONTROLS_V4.json
~~~

Anaconda Prompt / CMD:
~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_paced_dispatch_v4.py run --queue "ABSOLUTE_QUEUE.json" QUEUE_SHA256 --authority "ABSOLUTE_AUTHORITY.json" AUTHORITY_SHA256
powershell -NoProfile -File s6c_paced_status_v3.ps1 -Namespace remaining_batches_after_controls_v4 -QueueName PACED_RUNTIME_QUEUE_AFTER_CONTROLS_V4.json
~~~

Use the exact actual command from the runtime transition README. Placeholders above are not invented hashes or approval. User continuation is every30 minutes. Native queue transitions are automatic; avoid intermediate model polling.

B36 admission requires the reviewed new wrapper's original COMPLETE40 cell chain, closed identities, successful observer with storage/source guards, durable C release, exact preserved lease bytes and absent legacy G archive. The dispatcher also matches owner/argv, helper and quiet authority. This does not replace scientific analysis, current whole-study inventory, disposition or final acceptance. No hardware access or new experiment selection.

