# SQLite guard failure inspection

Purpose: read the exact failed check37 launch receipts and SQLite file metadata
without starting capture, opening a writable database, or loading models.
Inputs: a fresh expiry, build29 manifest pin, current guarded baseline and the
fixed failed launch ID. Output: private noncontent structural diagnostics with
file hashes, identities, failure stages and current sidecar metadata. It cannot
reconstruct an earlier inode's link count if no receipt recorded it.

PowerShell:

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B "$d/host_core_operations_v2.py" --label core-guard37-inspect-01 --action "$d/inspect_sqlite_guard_failure.py" --payload 'ABSOLUTE_PRIVATE_FRESH_PAYLOAD.json'
```

Command Prompt or Anaconda Prompt: run `powershell -NoProfile`, then the same
block using the existing interpreter. Payload fields are schema
`just-peachy.sqlite-guard-inspection.v1`, package_manifest_sha256 equal to the
build29 pin in the source, and expires_unix at most 600 seconds ahead. The host
dispatcher registers CPU14, reads owners, verifies source backups/restores,
uses strict SSH and records exact utility closure. Use a new label for a new
read; do not reuse the closed check37 root.
