# SSH mirror: recorded full unit names

Purpose: test the changed service-identity check in a fresh read-only export.
V1 failed at its active-unit listing assertion before its owner receipt, source
plan or any payload. The failing listing was not retained, so truncation or any
other specific cause remains unproven. V1 code, admission, raw stderr and results
are immutable. The systemd result recorded natural exit1 and MainPID0, but V1
did not record the exporter /proc start ticks; do not invent an exact identity.

V2 requests `--plain --full --no-pager --no-legend`, records the actual listing
and exporter identity/properties before its assertion, then requires the exact
single unit name. ACK still precedes source enumeration and copying. All source,
resource, lease, manifest, copy, destination and closure checks remain retained.
V2 uses a new service name and a new output/admission. The unchanged receiver
is `field_ssh_mirror_v1.py`; V1's coordinator/exporter are not rerun.

Read [README_FIELD_SSH_MIRROR_V1.md](README_FIELD_SSH_MIRROR_V1.md) for complete
inputs, outputs, resource ceilings, failure preservation and scope limitations.
No model, GUI or audio source is started. The same closed V100 evidence is used
to qualify the changed transport, not to repeat any healthy model/UI test.

Inputs: fresh immutable V2 admission/code pins, exact V100 source manifest and
never-used private host output. Output: bounded host metadata/failure/closure,
and the `-mirror` tree. Only BACKUP.json after process closure and exact readback
certifies success. Private payloads must not enter Git or be displayed.

## PowerShell

```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& $py -B "$p\verify_field_ssh_mirror_v2.py" --admission '<fresh-v2-admission.json>' --output '<fresh-private-v2-host-path>'
```

## CMD and Anaconda Prompt

Use the existing absolute interpreter in either prompt; no activation or download.

```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "P=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"%PY%" -B "%P%\verify_field_ssh_mirror_v2.py" --admission "<fresh-v2-admission.json>" --output "<fresh-private-v2-host-path>"
```

Refresh exact owners, lifetime records, Pi units/leases and target-inclusive
census before dispatch. Never reuse either closed admission or failed output.
