# Prepare immutable build26 staging

Purpose: bind the actual build26 archive and expanded package to the unchanged
stage24 installer/action. V26 preparation changes only the expected new target,
label/output and README identity from stage25 preparation. It does not deploy.

Inputs: actual closed package folder, archive, exact archive/manifest SHA and
current boot. Full archive and expanded membership/bytes are independently
verified. The original2MiB archive bound,8MiB/600s host scope, disk floors and
complete target allocation formula are retained. Output is a unique private
CPU14/FILETIME-registered preparation with backed ACTION, installer, payload,
README, independent restores and SOURCE_CLOSED. Package26 does not overwrite25.

PowerShell:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B './prepare_stabilization_stage26.py' --package 'ACTUAL_PACKAGE26' --archive 'ACTUAL_ARCHIVE26' --archive-sha256 ACTUAL_ARCHIVE_SHA26 --manifest-sha256 ACTUAL_SHA26 --boot-id 0561d730-3cad-48e0-940a-fe3930c89665
```

CMD and Anaconda Prompt:

```bat
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B prepare_stabilization_stage26.py --package "ACTUAL_PACKAGE26" --archive "ACTUAL_ARCHIVE26" --archive-sha256 ACTUAL_ARCHIVE_SHA26 --manifest-sha256 ACTUAL_SHA26 --boot-id 0561d730-3cad-48e0-940a-fe3930c89665
```

After exact host closure, Root dispatches printed ACTION/PAYLOAD with the unused
label stabilization-stage26-01 through host_stabilization_operations_v5.py
`--writes`. Native inventory/readback is distinct from functional qualification.
Staging neither changes the desktop nor starts a microphone/model/application.
