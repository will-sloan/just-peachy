# Actual Discard and startup inspection

Purpose: inspect activated build28 without changing the application or retained
data. The bounded read-only action reports database/sidecar extents, filesystem
capacity/inodes/mount state, current process identities and file limits, recent
session structure and closure errors. It reads SQLite only when no data handle
or nonempty WAL/journal is observed; it never ignores a hot journal, repairs a
database, starts capture or loads models. No transcript, audio or vectors are
returned. Existing application processes are observed and left running.

Inputs: exact build28 manifest SHA and a fresh expiration in a JSON payload;
all original owner/lifetime prerequisites and resource guards. Output: fresh
private source backup/independent restore and the original host dispatch's full
native result and exact utility closure, or preserved failure. The wrapper
permits existing applications only for this exact SHA-bound nonmutating action.
All other original guards remain. Each operation label must be unused.

PowerShell (replace PAYLOAD with the reviewed fresh file):
```powershell
$D='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B "$D/host_inspect_core.py" --label core-storage-inspect-01 --action "$D/inspect_core_storage.py" --payload 'ACTUAL_FRESH_PAYLOAD.json'
```

CMD and Anaconda Prompt use the same interpreter; no download is needed:
```bat
set "D=G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006"
set "PY=C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe"
"%PY%" -B "%D%/host_inspect_core.py" --label core-storage-inspect-01 --action "%D%/inspect_core_storage.py" --payload "ACTUAL_FRESH_PAYLOAD.json"
```

Payload fields are exactly `schema` (`just-peachy.core-storage-inspection.v1`),
`package_manifest_sha256` (the activated build28 SHA) and `expires_unix` (finite,
at most 600 seconds ahead). Do not pass `--writes`. Never reuse a failed label.
