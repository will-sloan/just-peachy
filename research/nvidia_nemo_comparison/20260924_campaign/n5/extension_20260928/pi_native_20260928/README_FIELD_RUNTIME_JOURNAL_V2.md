# Runtime journal V2 and local backup V1

Purpose: finish F04/F05 native lifecycle integration. V2 retains the V1 journal's finite recording allocation, actual closure and complete independent local-copy readbacks. It switches to production policy V2 and can adopt a pre-import OWNER published by the same actual process while holding the inherited exclusive directory lock. Every older launch must still have EXIT plus actual process death. An unclosed previous launch remains fenced. This is not crash recovery.

The bootstrap must register the actual PID/start ticks/boot in the next allocated launch before importing any project code, hold the root's exclusive directory descriptor, verify policy and complete code manifest, then pass inherited_lock_fd and early_launch to RuntimeJournal. The constructor checks the descriptor's actual directory identity and the journal independently checks the prepublished policy/slot/owner/purpose. Normal V1-style construction remains available for bounded qualification only.

field_runtime_backup_v1.copy_closed adds the actual runtime policy to the existing copier signature and validates the production operation at entry and throughout the copy. All source closure, service state, owners, leases,16KiB writes, full independent allocation, source/mirror identities, complete membership, independent hash readbacks and no-overwrite behavior are retained. The old research-operation validator is replaced only in this new derivative; old policies and sources remain immutable.

Inputs: an installed pinned manager root, exact policy SHA, inherited native lock/launch (when using the bootstrap); for copy, the actual closed source, fresh destination, source policy SHA, unit, complete file pins, operation, runtime policy, finite monotonic deadline and full maximum_bytes. Outputs: immutable journal records or a complete-copy receipt. Failed paths remain preserved and block reuse.

These are libraries, not standalone launchers. Native bootstrap/manager integration and a fresh measured device admission are required before execution. Neither native path has been executed yet.

Host syntax review only, PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; [compile(Path(n).read_bytes(),n,'exec') for n in ('field_runtime_journal_v2.py','field_runtime_backup_v1.py')]"
```

CMD / Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; [compile(Path(n).read_bytes(),n,'exec') for n in ('field_runtime_journal_v2.py','field_runtime_backup_v1.py')]"
```

Run from this README's directory after source backup and independent restoration. Compilation is not a native lifecycle/copy test. Full selected invocation will be supplied by the runtime launcher README; do not invoke a consumed research dispatcher.

