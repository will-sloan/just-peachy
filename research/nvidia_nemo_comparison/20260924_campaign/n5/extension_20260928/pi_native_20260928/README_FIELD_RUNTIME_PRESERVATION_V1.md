# Runtime preservation partitions V1

Purpose: F04 complete success/failure tree backup and strict runtime owner collection. The production manager can retain up to four independent local broker copies. This pure contract separates manager metadata and each local copy so every stream keeps the original per-broker file/directory limits and256KiB manifest frame. A <=16KiB index pins all separate manifests. Full aggregate allocation is the sum of independently reserved partitions; no old per-producer cap is removed.

Inputs: finite runtime policy, pinned manager manifest, complete file size/SHA and directory inventory; separately, all completed OWNER/OWNERSHIP_CLOSURE bytes. Outputs: complete nonoverlapping partition manifests/index and strict typed owner records. Pending OWNER bytes remain ordinary preserved files and never create process identity. Unknown completed paths, roles, slot/policy bindings, malformed IDs and typed closures reject. Native process death must still be independently observed; decoding does not establish it.

Prepared pure API only. Native partition census/export, full host receiver closure and installer integration are still required before use. No local or Pi tree is copied by this module.

PowerShell syntax review from this directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_preservation_v1.py').read_bytes(),'field_runtime_preservation_v1.py','exec')"
```

CMD / Anaconda Prompt:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B -c "import psutil; psutil.Process().cpu_affinity([14]); from pathlib import Path; compile(Path('field_runtime_preservation_v1.py').read_bytes(),'field_runtime_preservation_v1.py','exec')"
```

API: partitions(files,directories,policy,manifest); decode_owners(records,policy). The complete source graph must be pinned, backed up and independently restored before execution. There is no standalone capture/export/deployment CLI. An empty or partial tree may be preserved within known allocations, but this is never certification of a complete working release.

