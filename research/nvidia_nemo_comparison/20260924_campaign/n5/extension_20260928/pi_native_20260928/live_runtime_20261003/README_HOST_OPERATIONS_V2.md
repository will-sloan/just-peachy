# Exact completed optional-child ownership decoder

`host_operations_v2.py` preserves the prior full host/native inspection and all
resource, lease, output and action gates. It adds only the actual closed
`optional-first-01` child owner: exact path,131-byte SHA-pinned owner,517-byte
SHA-pinned CLOSURE, exact70-file complete mirror digest, actual parent job,
boot/InvocationID/cgroup and physical closure. The child's natural failure1,
incomplete EOF and unqualified quality status remain unchanged.

It inserts the complete observed owner object only at that actual historical
path. Existing native exact-object comparison, PID/start ticks and current
process scans remain enforced. No arbitrary malformed owner or live child is
ignored. Unknown future optional receipts require their own reviewed decoder.

Inputs/outputs are those in `README_HOST_OPERATIONS.md`: exact reviewed action
and payload, fresh operation label, complete prior private mirrors, and the
normal independent PC/native reserve. This host action is not authorization
for a native model or mutation by itself. Use only the already reviewed action
and its fresh admission; add `--writes` only where that action requires it.

PowerShell:

```powershell
& $PY -B "$N/host_operations_v2.py" --label $FRESH_LABEL --action $ACTION --payload $FRESH_PAYLOAD --writes
```

CMD or Anaconda Prompt:

```bat
"%PY%" -B "%N%\host_operations_v2.py" --label %FRESH_LABEL% --action "%ACTION%" --payload "%FRESH_PAYLOAD%" --writes
```

The runner sets CPU14 and registers its actual host owner before project
reads. It creates the same bounded operation directory and receipt/restore
copies as the prior runner. Host-only focused validation uses the actual
closed mirror and rejects altered parent, path, receipt, closure and manifest
inputs without any SSH or native execution.
