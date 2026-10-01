# Offline runtime journal V1

Purpose: implement F04 persistent native metadata/ownership across separate user launches, using the F05 offline policy. Unlike a research batch, the installed policy has finite reserved recordings/launches and each manager launch has a24-hour idle ceiling; each active recording still gets a fresh600-second operation. Old sources and policies are unchanged.

Inputs: an already installed canonical runtime root containing exact control/RELEASE.json, control/MANIFEST.json and the complete pinned code directory, plus its actual policy SHA256. `RuntimeJournal(root, policy_sha256, create=True)` creates only the preallocated journal directories. Later opens use create=False and retain all old records. Outputs: bounded immutable launch OWNER/EXIT intent and recording RESERVED records, with pending files, directory synchronization and exact readback. No recording or model is started by this library.

Native requirements: aarch64, CPU3, hard/soft128MiB AS,1MiB stack and32MiB FSIZE; an external early-owner bootstrap must register before project imports and set a bounded process alarm/systemd envelope. The lifetime directory flock excludes duplicate managers. Launch reuse requires prior EXIT intent and actual prior PID/start/boot absence; incomplete/pending/failed records stay fenced. Policy and code are rechecked on use. The caller must verify capture/leases and other current resources before launch.

Prepared API: `begin_launch()`, `reserve_recording(profile)`, `recording_started(slot)`, `recording_closed(slot)`, `accept_local_backup(slot, receipt)`, `recording_failed(slot, reason)`, `end_launch()`, `close()`, `inspect()`. STARTED binds actual live broker/gate identities and systemd MainPID. Closure delegates the retained physical source/archive/owner checks. BACKUP requires complete source and independent local-copy membership/hash readback, stable filesystem identities and a final physical closure observation. Next recording and clean launch exit recheck these facts. PC offload may wait while its full independent space remains reserved. Failed sources stay fenced; production failure-recovery handling is still to be completed.

This library is PREPARED and NOT yet dispatchable/deployable. It requires the fresh `just-peachy.offline-broker-policy.v1` source-policy adapter, including exact runtime-policy and operation digests. The old expiring qualification broker policy is rejected. The production stager, gate/ACK connection, copier, capsule graph, bounded native bootstrap and installer must be wired and verified before execution. No supplied success booleans can certify native closure. This is implementation in progress, not a completed F04 gate.

Host static compilation only (sets CPU14 before source read):

PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import json; from pathlib import Path; Path('NEW_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))); p=Path('field_runtime_journal_v1.py'); compile(p.read_bytes(),str(p),'exec')"
```

CMD / Anaconda Prompt, from this source directory:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B -c "import psutil; me=psutil.Process(); me.cpu_affinity([14]); import json; from pathlib import Path; Path('NEW_OWNER.json').open('x').write(json.dumps(dict(pid=me.pid,create_time=me.create_time(),affinity=[14]))); p=Path('field_runtime_journal_v1.py'); compile(p.read_bytes(),str(p),'exec')"
```

These commands do not construct a native journal or prove Linux durability. Actual controlled execution requires a fresh admitted wrapper, early owner, complete source backup/independent restore, current native baseline/resources and closure/copy implementation. No direct native CLI is provided until those bindings are complete.
