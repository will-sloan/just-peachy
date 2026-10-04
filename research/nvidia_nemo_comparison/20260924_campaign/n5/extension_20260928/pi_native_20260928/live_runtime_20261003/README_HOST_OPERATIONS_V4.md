# Strict completed host-registration correction

`host_operations_v4.py` preserves v3 native/host prechecks and adds only six exact
completed PC preparation records to a format-correction table. The inline tools
recorded actual PID/Windows FILETIME but omitted schema and/or affinity_mask.
Original evidence remains unchanged and independently copied/read back. Each
correction requires exact private path, entire original object and raw SHA256.
Unknown paths and changed values/bytes fail. The original strict FILETIME decoder
then runs; its ordinary live PID/creation-time check remains unchanged. No generic
malformed-owner exemption is added. Six dead/reused identities were independently
observed. One initial fixture used a float divisor1e7; the final exact check uses
the decoder's integer10000000, preserving the recorded FILETIME.

Inputs and outputs are identical to [README_HOST_OPERATIONS_V3.md](README_HOST_OPERATIONS_V3.md),
with v4 as the executable. A fresh reviewed action/payload and all existing guards
are still required for native dispatch. CPU14 plus durable actual registration
precede project reads. This preparation executes no native action.

PowerShell, using the qualified PY/N variables from the linked README:

```powershell
& $PY -B "$N/host_operations_v4.py" --help
```

CMD and Anaconda Prompt:

```bat
"%PY%" -B "%N%\host_operations_v4.py" --help
```

For dispatch retain the v3 documented arguments and use this filename. Output is
a fresh owner/precheck/backup/result/closure tree. Focused host verification:
six actual positives, six changed-identity refusals, one unknown malformed path
refusal, source compile and independent source readback. Original files are never
edited to satisfy the parser.
