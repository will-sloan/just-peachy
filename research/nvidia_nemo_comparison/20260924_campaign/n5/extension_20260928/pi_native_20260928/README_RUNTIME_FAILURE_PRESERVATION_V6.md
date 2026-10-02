# Complete failed-runtime stream preservation

Purpose: F09/F16/F25 preserve both the closed broker tree and manager tree, including real audio. Version6 retains version5's complete owner/device/resource checks, one normal manager Stop, exact death and one pinned rollback. It replaces the 128KiB compressed inline-data path with bounded 16KiB streaming and independent full PC hash/readback. It does not claim that a failed broker succeeded.

Inputs: actual candidate install, complete prior identities, last inspection, private/local roots, a fresh host scope and unused output directory. The existing full independent install/runtime allocations remain charged. Each metadata frame is at most256KiB; the existing transport ceiling155669036B plus2MiB framing remains. If the combined actual trees exceed that conservative ceiling, this command rejects; it never reduces either root's reservation or silently raises the cap. Each file retains32MiB,1162files/264directories per tree and the policy's logical plus directory allocation. Native alarm150s, transport105s, original manager Stop47s bound and rollback20s wait remain finite.

Outputs: actual early owner persisted before payload, matching HELLO, complete census, streamed trees preserving empty directories, per-file full SHA256/readback, raw diagnostics, natural transport closure and independent PID absence before BACKUP.json. Partial destinations remain on any failure. On a transport fault SSH is closed and the native alarm remains a bound; no BACKUP or exact remote-closure claim is made from that fault alone. All data stays private. Copy only; no deletion.

PowerShell, from the native source directory:
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\preserve_runtime_failure_v6.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope CURRENT_SCOPE --output FRESH_PRIVATE_OUTPUT
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B preserve_runtime_failure_v6.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope CURRENT_SCOPE --output FRESH_PRIVATE_OUTPUT
~~~

Verify exact source backup and independent restore before use. Use once for a failed current candidate, not as an operation retry. The actual recording's model/audio/closure receipts must be reviewed separately. The transport and receiver are cooperative controls, not a kernel filesystem quota.
