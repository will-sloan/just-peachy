# Manual-Stop production envelope check

Purpose: reuse the existing strict production idle/normal Exit inspection with
the candidate's declared manual-Stop service lifetime. Only the nested GUI
lifetime assertion changes: runtime/deadline null and exact
`manual_stop_storage_guarded` policy are required. Outer finite120-second
inspection, independent watchdog, package, owner, capture, CPU/RAM/disk and
normal-Exit checks remain unchanged. This starts no speech/enrollment recording.

Inputs: reviewed parent-directory `launch_production_idle_action_v2.py`, exact
candidate manifest and desktop hash, current boot and disabled autostart pins.
Outputs: fresh private source backups/restores and `launch_manual_idle_action.py`,
then one `production-idle-NN` job and complete independent PC output mirror.
An idle/Exit pass does not establish sustained real-time or hour-long speech.

PowerShell, from this directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\prepare_manual_idle_check.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\host_full_operations_v6.py --label YOUR_FRESH_LABEL --action .\launch_manual_idle_action.py --payload 'G:/path/to/reviewed-idle-payload.json' --writes
```

CMD/Anaconda Prompt: double-quote the same executable/paths and omit `&`.
Preparation is CPU14 /2 MiB /600 seconds with actual early owner. Deployment and
the ordinary launcher are separate; preserve previous shortcuts and receipts.

The unexecuted first derivative still assumed the old dashboard and an empty
data store. Use `prepare_manual_idle_check_v2.py` and its output
`launch_manual_idle_action_v2.py` for the restored application. It checks the
actual scrollable chooser and independent Live/Saved selector, preserves
existing recordings, compares prior launch/owner names and copies only its own
new closed owner metadata. Use the same PowerShell/CMD/Anaconda commands above
with these v2 names. No existing data is moved or deleted.
