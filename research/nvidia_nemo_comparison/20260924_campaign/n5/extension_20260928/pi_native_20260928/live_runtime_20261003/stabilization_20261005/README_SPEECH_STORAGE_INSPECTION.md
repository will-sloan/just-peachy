# Failed speech session19 storage inspection

Purpose: diagnose the actual speech-path SQLite allocation failure while
preserving build24 and failed session `8c5d357f0acc4640bfcda4697d7e325b`.
This is a fresh external read-only action, not a Store constructor or repair.

Inputs: current boot/build24 pin, exact failed19 JOB and worker request hash,
launch `75bd9635afc54076a4bc6b611d479a90`, complete clear current-owner census,
and a fresh <=600s payload. The action rechecks full package pins, failed unit
and main/worker/source exact absence before querying existing history.sqlite3.

Outputs: only numeric session/spec allocation, per-event-type counts and
original/stored/compressed lengths and charges, metadata used/limit, caption
counts/nonempty counts/total bytes, segment counts, receipt SHA/closure booleans
and actual old identities. No transcript text, vectors or media are returned.

Database cap128MiB; WAL/journal16MiB andSHM1MiB bounds. Nonempty WAL/journal is
refused: never ignore pending pages or create a snapshot on the Pi. With a clean
database, immutable read-only/query-only SQLite, memory temporary storage,
2MiB cache,8s/20million-opcode progress limits and32event-type output cap retain
the no-write contract. An existing session lock is held SH; none is created.
Database/sidecar identities must remain unchanged. No live capture is started.

## PowerShell

The delivery task prepares independently backed ACTION/PAYLOAD files and closes
their actual early CPU14 owner before dispatch. Use the printed exact path:

```powershell
$py = 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$source = 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
$prep = 'ACTUAL_CLOSED_SPEECH19_INSPECTION_PREPARATION'
& $py -B "$source/host_stabilization_operations_v2.py" --label speech-storage-inspect19-01 --action "$prep/ACTION.py" --payload "$prep/PAYLOAD.json"
```

## CMD or Anaconda Prompt

```cmd
set JP_SOURCE=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005
set JP_PREPARATION=ACTUAL_CLOSED_SPEECH19_INSPECTION_PREPARATION
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/host_stabilization_operations_v2.py" --label speech-storage-inspect19-01 --action "%JP_PREPARATION%/ACTION.py" --payload "%JP_PREPARATION%/PAYLOAD.json"
```

Use the existing FSIZE0 metadata-helper envelope; omit --writes. The calling
dispatcher supplies its early native identity, full census and bounded CPU/AS/
stack/alarm/response handling. Root performs native dispatch and exact closure;
host preparation proves no native outcome. Preserve numeric findings alongside
the original failed session and actual source/model cleanup flags.

