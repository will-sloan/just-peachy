# Exact host format correction V3

Purpose: retain the complete native-action dispatcher and its strict historical
owner preread while binding three actual completed CPU14 registrations that
omitted only their schema label. Their original bytes stay immutable. Each
correction requires its exact path, SHA256, document, PID and kernel FILETIME;
unknown formats still fail before SSH. V3 registers its own early owner with the
full schema, CPU, affinity mask and FILETIME. V2 and failed stage25-01 remain
preserved. The first field_runtime_host_precheck decoder receives this same
exact correction map before it is compiled; no separate permissive decoder is
introduced.

New bound historical paths below `live-runtime-20261003/audit-preparation`:

- `stabilization-v5-source-1c0d89648d9a40369f513fb637c8f3fe/REGISTERED_OWNER.json`
- `stabilization-v5-source-corrected-01/REGISTERED_OWNER.json`
- `speech19-independent-restore-82def6dd72ec44f58a86713a36075d6a/REGISTERED_OWNER.json`

Inputs: a fresh operation label, a reviewed action at most128KiB, its JSON
payload at most2MiB, and `--writes` for an authorized write. Outputs: the same
immutable operation directory, backed/restored inputs, full compact preread,
actual process identities, native output and independent closure or preserved
failure. The 600-second operation, 300-second full preread, CPU/resource/floor,
SSH, unknown-owner and no-existing-target checks are unchanged. This is an
operator utility, not the field application.

PowerShell, from this directory after the current baseline preread is allowed:

```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
& $py -B './host_stabilization_operations_v3.py' --label stabilization-stage25-02 --action 'ACTUAL_FRESH_PREPARATION/ACTION.py' --payload 'ACTUAL_FRESH_PREPARATION/PAYLOAD.json' --writes
```

CMD / Anaconda Prompt use the same pinned interpreter and actual paths:

```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B host_stabilization_operations_v3.py --label stabilization-stage25-02 --action "ACTUAL_FRESH_PREPARATION/ACTION.py" --payload "ACTUAL_FRESH_PREPARATION/PAYLOAD.json" --writes
```

The label is one-use. Build25 archive/action/installer bytes are unchanged;
staging is separate from native qualification and activation. This correction
neither stages nor activates anything by itself.

Focused host-only verification: `check_host_format_corrections_v3.py` backs and
independently restores its inputs before extracting the actual V3 correction
function and original first decoder. It verifies the three real registrations,
unknown-path/changed-document rejection and the narrow function AST difference.
No wrapper top-level, native action, SSH, models or GUI run in this check.

```powershell
& $py -B './check_host_format_corrections_v3.py'
```

```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B check_host_format_corrections_v3.py
```

The check writes a bounded private preparation with SOURCE_CLOSED/RESULT;
natural exit and exact host absence must be separately verified afterward.
