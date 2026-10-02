# Verified recording and independent local-copy export

Purpose: F16 copy a successfully closed runtime recording AND its independent Pi-local backup to the PC, preserving the Pi originals and leaving the idle manager running. This is a read-only derivative of the actually used version6 stream preserver. It removes manager Stop/rollback and requires the exact successful CLOSED/BACKUP receipts, all recording owners dead, capture closed, current manager identity and complete matching source/local-copy membership and SHA256.

Inputs: actual runtime install receipts, complete prior owners, previous inspection, local/private evidence roots, fresh host scope, recording slot01..04 and a new private output directory. Destination must use the original separately reserved PC allocation, outside a small metadata-only scope directory. Both actual source trees are copied independently; old matching host bytes are not substituted. The original runtime/install reservations remain fully charged.

Outputs: early exporter identity before payload, exact matching HELLO, whole closed census, two complete private trees with empty directories,16KiB data chunks, individual and whole hash/readback, raw transport/closure and BACKUP.json only after natural exporter exit and independent exact PID absence. Source identity/membership is checked before and after streaming under shared locks. Copy only, no source deletion, capture or model execution. Manager remains idle and running.

PowerShell (from the native source directory):
~~~powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B .\export_runtime_recording_v2.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope CURRENT_SCOPE --slot recording-01 --output NEW_PRIVATE_OFFLOAD
~~~
Command Prompt / Anaconda Prompt:
~~~bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B export_runtime_recording_v2.py --local LOCAL_ROOT --private PRIVATE_ROOT --prior-closure PRIOR_BINDING --previous-inspection LAST_INSPECTION --candidate-install ACTUAL_INSTALL --scope CURRENT_SCOPE --slot recording-01 --output NEW_PRIVATE_OFFLOAD
~~~

Current prepared example uses field-runtime-v7-install and recording-01. Use exact current paths from the operator mode guide when published. Do not rerun into an existing destination. Every invocation requires fresh host/native owners and resource guards. Retains original32MiB/file,1162files/264directories per tree,256KiB frames and the conservative155669036B combined data transport ceiling; larger combined trees explicitly require separate bounded exports. Native150s alarm/105s host timeout, CPU/RAM/disk floors and full independent allocations remain. A transport failure retains partial files without claiming BACKUP or exact remote closure. This command does not establish full-capacity transfer speed, power-loss resilience or noisy-world accuracy.

This version validates each observed completed operation against its exact installed profile manifest, so both E0 and E1 are accepted only when pinned in the current immutable runtime policy. No model is loaded by inspection/offload, and no current process or file is changed. The same strict owner, complete copy, resource and transport checks remain.
