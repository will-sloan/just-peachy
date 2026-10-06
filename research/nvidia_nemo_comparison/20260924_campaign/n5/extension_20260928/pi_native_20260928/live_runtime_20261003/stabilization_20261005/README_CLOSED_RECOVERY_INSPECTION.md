# Read one preserved microphone recovery tree

`inspect_closed_recovery.py` resolves whether the exact first-Start source fault
already has a preserved recovery attempt. It reads only
`data/runtime-v29/recovery/01beda380170956338c66b1489689e7c725cb0f74a6014b6793a96eb389f133a`.
It does not execute an XVF command, create a native file, clear a recovery fence,
start audio/models or retry a repair. This is a prerequisite inspection for the
shared startup fix, not a generic campaign.
It also records current `jp-*` user service inventory and MainPID/state/result/
cgroup/invocation/lifetime properties using read-only systemctl calls. This
reports a stale or still-active service without stopping it or relaxing staging.

Inputs are the exact fixed-path payload and fresh wrapper baseline. The action
reads at most256 regular single-link files/64 directories,256KiB per file and
512KiB total, with stable source identity and membership. Output reports absence
or the complete hash/membership census; original request/recovery/owner/closure
JSON; bounded stdout/stderr prefixes; exact recorded process-owner status; and
the presence of any restart intent or `TEST_CORE_BURN` command reference.
`no_send_intent_observed` describes these bytes, not permission to reuse or
overwrite them. The operator interprets exact helper return/closure before any
separate changed runtime action.

`prepare_closed_recovery_inspection.py` sets CPU14 and registers its host owner
before source reads. It creates one unique private directory under
`live-runtime-20261003/audit-preparation`, with sources, independent backups and
restores, `SOURCE_CLOSED.json` and `PAYLOAD.json`, bounded to2MiB/30seconds.
Compilation follows source closure. It performs no SSH/native operation.

PowerShell preparation:

```powershell
$inspectionSource = 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$inspectionSource\prepare_closed_recovery_inspection.py"
```

For CMD or Anaconda Prompt, use the existing interpreter; install nothing:

```bat
set "INSPECTION_SOURCE=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003\stabilization_20261005"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%INSPECTION_SOURCE%\prepare_closed_recovery_inspection.py"
```

After normal application Exit and current owner/unit preread, dispatch through
`host_closed_recovery_diagnostics.py`, with a fresh unique name. This derivative
of the retained read-only diagnostic wrapper allows only this exact action SHA,
and reports existing service inventory instead of failing on active units. The
mutating staging wrapper remains unchanged.
Set `INSPECTION_FROZEN` to the preparation directory printed above:

```powershell
$inspectionFrozen = 'G:\...\audit-preparation\closed-recovery-inspect-<UUID>'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B "$inspectionSource\host_closed_recovery_diagnostics.py" --name closed-recovery-inspect-01 --action "$inspectionFrozen\inspect_closed_recovery.py" --payload "$inspectionFrozen\PAYLOAD.json"
```

```bat
set "INSPECTION_FROZEN=G:\...\audit-preparation\closed-recovery-inspect-<UUID>"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%INSPECTION_SOURCE%\host_closed_recovery_diagnostics.py" --name closed-recovery-inspect-01 --action "%INSPECTION_FROZEN%\inspect_closed_recovery.py" --payload "%INSPECTION_FROZEN%\PAYLOAD.json"
```

Do not pass `--writes`. This wrapper keeps existing complete owner/lifetime,
resource, baseline, strict SSH and exact native utility-closure checks. A blocked
preread is not a native pass; preserve its result and interpret the failure.
