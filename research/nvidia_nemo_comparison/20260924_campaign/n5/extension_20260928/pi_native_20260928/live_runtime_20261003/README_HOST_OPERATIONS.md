# Candidate native operations

External backup V2 uses only `launch_backup_external_action_v2.py` with the
exact `just-peachy.external-backup-common.v2` document:20,433 bytes and SHA256
`aba044705f9e4938261cd82d46264b5c4868206abcac290a31580f971a1d50ef`.
The gate verifies the decoded bytes, exactly16 MiB metadata output and the
existing separate complete-copy reservation/scope equality. V1 keeps its
separate original filename/schema/pin; mixed versions fail. The V2 scope adds
only the reviewed exact data/config directory roots. Use the existing commands
below with that precise action and its reviewed payload; no package activation
or new native authority is granted by this host gate.

The post-soak ownership decoder includes one exact historical six-field
`UNIT_OWNERSHIP.json`: `chunk52-threads2-hour-01`, runtime4530 seconds, SHA256
`3146b28d6ef3ccc9fe90fd331bded738d4c4d81c22cd882e32f605132eb59dc7`.
It also requires the observed package manifest, exact native output/unit,
mirrored extent/hash, owner/start ticks/boot and actual closed cgroup proof.
Other receipts still require their complete existing schema; this is not a
generic exemption for missing lifetime fields. The failed baseline01 and
previous runner bytes remain preserved. With the early CPU14 owner wrapper
used below, run `test_hostops_hour_binding` for the actual mirrored receipt's
acceptance and altered-root/unit/package/runtime/owner/hash/closure refusals.

`host_operations.py` runs one reviewed native action after a fresh complete
host owner/lifetime preread and the retained full Pi inspection. It preserves
v27/v28 and refuses dispatch while another project process, app or capture is
active. Inputs are a reviewed Python action and bounded JSON payload. The action
receives `PAYLOAD` and `BASELINE` and must assign `RESULT`. Outputs are immutable
source backups, independent restores, scope, admission, native source, raw SSH
streams, owner/closure records and action result in the private operation folder.

When the payload declares `maximum_output_bytes`, the dispatcher independently
checks C:50 GiB and G:75 GiB safety floors plus that complete-copy allocation
before SSH. `OUTPUT_COPY_RESERVATION.json` records actual free bytes and the
separate allocation on each drive. This does not enlarge or reuse the 16 MiB
preparation scope. A missing output allocation is zero; a malformed or larger
than512MiB allocation fails closed before dispatch, except two explicitly scoped
workflows: the1500s capture-save-replay-discard GUI action permits at most1GiB,
and `launch_full_app_soak_action.py` permits at most3GiB only with the reviewed
full-application-hour schema,3600s repeat,4680s lifetime and equal independent PC
copy allocation. Exact derived budgets remain mandatory in the native dispatcher.
See `README_FULL_APP_SOAK.md` for the full typed payload and PowerShell/CMD/Anaconda
commands. These exceptions do not change the complete-copy floor check on either
drive or the preserved historical owner decoder.

The external rc5 backup action is allowed a separate full-payload PC reservation
only as `launch_backup_external_action.py`, with exactly16MiB native metadata and
the reviewed20,362-byte common overlay SHA256
`103c24c099b946289172cf432288ef1db5abf1c744afb2f27b3f7b361d6d7aa8`.
The host decodes and hashes its explicit base64 bytes before admitting that
reservation, and still requires equality with the complete backup scope bytes.
The unchanged build08 and original native files are preserved. See the external
backup README for the exact scope, inputs, outputs and command sequence.

The helper is for installation/integration, not an unrestricted operator launcher.
It sets CPU14 and records its actual host identity before reading the project.
The native inspector records its identity before project reads, uses CPU3,
128MiB AS, 1MiB stack and a 55-second alarm. Read-only actions retain FSIZE0;
explicit `--writes` uses a finite 32MiB file ceiling. Model processes must be
launched through their separate finite systemd unit, never directly under the
inspector's memory envelope. All historical raw failures and typed closures are
preserved. The legacy timestamps are decoded with the previously reviewed exact
ISO/FILETIME exceptions, not fabricated process identities.

New `UNIT_OWNERSHIP.json` envelopes are admitted to the historical owner decoder
only from a complete independently closed job mirror. `closed_unit_owner` checks
the exact regular-file bytes/hash, supported field set, job PID/start/boot,
MainPID, unit, InvocationID and control group, finite lifetimes, and the
independent exact-owner-gone/cgroup-empty receipt. The Pi then requires the same
file SHA256 before extracting its nested process identity. Unknown envelopes
continue to fail; an ownership envelope is not a second process. Failed jobs
can be accounted for without being called successful. All prior missing-identity
gaps remain separate. This uses the existing commands below; it adds no new CLI.
The isolated source's exact `just-peachy.source-owner.v1` envelope is similarly
bound only at its known UUID session `work/source/REGISTERED_OWNER.json` path,
with CPU3/256 MiB/1 MiB bootstrap values, strict types, actual boot/PID/ticks,
and the independently closed job mirror. A failed source clock or logical Stop
is still a failed test; recording an early process identity does not upgrade it.

Use a new label for each different authorized operation. A failed operation is
preserved and must not be retried against an already-mutated target. Every
action plus its output/cleanup must fit the fresh 600-second operation scope.
No old campaign allowance, consumed policy or deadline is renewed by this tool.
The full two-session GUI qualification dispatcher alone permits an independently
reserved output-copy allowance up to1GiB when the payload names the exact
`capture-save-replay-discard` workflow and1500-second service lifetime. Other
actions retain the512MiB host admission cap. C:50GiB/G:75GiB floors still add
the complete output allocation before SSH; preparation itself remains16MiB.
The fresh600-second dispatch operation ends after launching/registering the
separately bounded service; it does not wait1500 seconds or renew old admission.

PowerShell (from this directory):

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py host_operations.py --label fresh-reviewed-operation --action native_action.py --payload private_payload.json --writes
```

Command Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" host_operations.py --label fresh-reviewed-operation --action native_action.py --payload private_payload.json --writes
```

Anaconda Prompt:

```bat
conda activate your-existing-environment
python host_operations.py --label fresh-reviewed-operation --action native_action.py --payload private_payload.json --writes
```

Omit `--writes` for read-only actions. The example filenames must refer to the
actual reviewed action/payload; they are not a suggestion to improvise native
commands. Physical tests and native performance results remain separate from
successful staging and source readback.
