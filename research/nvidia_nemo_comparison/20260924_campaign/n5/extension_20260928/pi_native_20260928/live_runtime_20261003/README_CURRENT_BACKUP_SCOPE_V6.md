# Lossless bounded discovery transport V6

Purpose and all selected roots are unchanged from V5. V5's complete packed
inventory exceeded its estimated 80 KiB action allowance; no result or backup
success was published. Its read-only failure and exact process closure remain.

V6 preserves the entire v2 discovery JSON and transports its canonical UTF-8
bytes as zlib+base64, with exact uncompressed size and SHA256. Bounds remain
2 MiB uncompressed discovery, 64 KiB encoded payload, and 262,144 bytes for the
complete enclosing inspector result. No roots, members, metadata pins, absence
proofs or historical exclusions are omitted. The preparer must independently
verify the bounded compressed stream, EOF, size, digest and strict JSON before
decoding the exact root-index/relative member list. This is metadata transport,
not a new backup or a file-hash verification claim.

Inputs: fresh actual boot/expiry JSON; immutable V6 source. Output: bounded
`just-peachy.production-scope-transport.v1` envelope containing the full discovery.
Use `prepare_production_scope_v3.py` to consume it. Native action remains read-only.

PowerShell from this directory, using the existing interpreter and fresh payload:

```powershell
$PY='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $PY -B ./host_operations.py --label production-scope-06 --action ./discover_production_backup_action_v6.py --payload FRESH_PAYLOAD.json
```

CMD and Anaconda Prompt:

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
"%PY%" -B host_operations.py --label production-scope-06 --action discover_production_backup_action_v6.py --payload FRESH_PAYLOAD.json
```

Never reuse a consumed label. See V4/V5 instructions for private source backups
and original namespace review. The host dispatcher compiles and backs up exact
action/payload bytes with independent restores before any SSH access.
