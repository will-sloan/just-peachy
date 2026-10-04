# Current Start-failure inspection

`inspect_start_failure_action.py` reads the actual Just Peachy Desktop command,
its selected data root and the most recent twelve launch records. It preserves
the worker's original error rather than treating `SOURCE_NOT_STARTED`, which is
a cleanup classification, as a cause. It does not start capture or alter Pi data.

Input: `{}` through the existing guarded host dispatcher. Output: exact shortcut
text and SHA256 plus bounded recent request, owner, closure and worker log bytes
in the dispatcher's private `action_result`. Original evidence stays untouched.

From the parent `live_runtime_20261003` directory, define the existing private
evidence directory as `$Q` (PowerShell) or `%Q%` (Command/Anaconda Prompt). Save
`{}` as a new private `ui-diagnostic-payload.json`, then use a fresh label:

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B host_operations_v6.py --label ui-start-diagnostic-01 --action ui_restore_20261004/inspect_start_failure_action.py --payload "$Q/ui-diagnostic-payload.json"
```

Command Prompt / Anaconda Prompt (the existing qualified environment):

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B host_operations_v6.py --label ui-start-diagnostic-01 --action ui_restore_20261004/inspect_start_failure_action.py --payload "%Q%\ui-diagnostic-payload.json"
```

The dispatcher registers CPU14 before project reads, backs up and independently
restores its source, prereads all existing owners/lifetimes, and uses a bounded
read-only native helper. Its original ownership/resource guards remain active.
If the guarded inspection refuses an active application, preserve the result;
do not infer its session failure from that refusal or force-close the app.

`read_current_diagnostic.py` uses the same dispatcher but emits the bounded
read-only result **before** historical native admission checks. This lets us
read a user's newly created failure records when an older historical decoder
does not yet recognize their envelopes. The original verifier still runs and
may reject; an early diagnostic is never dispatch authorization. It refuses
`--writes`. Use the same arguments above, replacing `host_operations_v6.py`
with `ui_restore_20261004/read_current_diagnostic.py` and a new label. Read the
`CURRENT_DIAGNOSTIC=` line in the preserved private `dispatch/STDOUT.bin`.

The selected diagnostic is now `inspect_start_failure_action_v2.py`, which
resolves the actual Desktop `--data-root` under the user's home; version1's
campaign-directory assumption failed before reading launch records. Version2
does not change or retry any mutation. `read_current_diagnostic_v2.py` adds the
offending path/fields to an unchanged historical nested-owner refusal.

`host_repair_operations.py` uses the existing dispatch CLI and all its guards.
It adds one strict decoder for the actual production-idle-01 archived unit
envelopes under their exact readback path: full eight-field schema, real nested
PID/start/boot, matching MainPID, unit/cgroup/invocation, finite7200/300 lifetimes,
and a different current boot. It records their process identities, not a new
logical-cleanup claim. Unknown paths/fields still fail closed. CPU14 and its
early host registration precede importing the project driver. Use its path in
place of `host_operations_v6.py`, with fresh labels and unchanged CLI arguments;
`--writes` is only for reviewed actions with verified backups/admissions.

The selected repair coordinator is now `host_repair_operations_v4.py`; it keeps
v3's two independently mirrored nested supervisor bindings (see
`README_HOST_REPAIR_OPERATIONS_V3.md`). Version4 also binds one exact completed
build17 host registration by path and SHA: its kernel FILETIME, numeric creation
time and CPU14 affinity are retained, and only the missing decoder schema tag is
supplied in memory. The original owner bytes are never edited. No other format
is exempted. Use the same PowerShell/CMD/Anaconda arguments above with the v4
filename and a fresh label. The first build17 stage failed before SSH on this
format mismatch; that failed operation is preserved and no native root existed.
