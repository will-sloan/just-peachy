# Closed optional-owner continuation runner

`host_operations_v3.py` retains the guarded host dispatcher and accepts an optional child only from a complete, bounded local mirror of an actual `optional-first-NN` or `optional-followup-NN` job. It verifies the exact unit/root/parent identity, boot, package pin, full file membership digest, unique session UUID path, owner bytes/hash, and sibling CLOSURE bytes/hash. Actual child return status and whole-unit owner/cgroup closure must exist. Successful and failed execution remain distinct; recognizing a physically closed child never declares complete EOF or quality qualification.

Inputs: a fresh operation label, reviewed action Python and JSON payload, plus the existing private actual JOB/mirror receipts. Outputs: the usual independently backed operation inputs, actual host/native helper owner receipts, preflight result and bounded action output. Native identity equality and current PID/start-tick checks are unchanged. No missing-owner/schema exemption is introduced. V2 remains frozen for the already reviewed first child.

Set PY to `C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`; N to this source directory. ACTION and PAYLOAD are reviewed absolute files, LABEL is a new operation name. Use `--writes` only for a reviewed write action; omit for read-only dispatch.

PowerShell:

```powershell
& $PY -B "$N/host_operations_v3.py" --label $LABEL --action $ACTION --payload $PAYLOAD --writes
```

CMD or Anaconda Prompt (explicit interpreter):

```bat
"%PY%" -B "%N%\host_operations_v3.py" --label "%LABEL%" --action "%ACTION%" --payload "%PAYLOAD%" --writes
```

The runner pins CPU14 and publishes an actual host owner before project reads. It keeps the existing strict SSH, resource floors, independent output reservation, complete preflight and reviewed-action gates. This README is not authorization to contact the device. A future job whose owner topology or closure schema differs must be reviewed separately, not coerced into this decoder. Current parent topology requires child.parent_pid to equal the actual registered JOB owner.