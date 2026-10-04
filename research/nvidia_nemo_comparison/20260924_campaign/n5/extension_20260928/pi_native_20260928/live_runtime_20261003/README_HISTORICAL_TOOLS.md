# Historical inspection and recovery preparation tools

These executables are retained source history. They are not the selected current dispatch path. Their commands document the original interface; they do not authorize device access or renewal of old admissions. Use the final handoff's pinned `host_operations_v3.py` and selected external action for new reviewed work. Both tools register host CPU14 ownership before project reads.

`inspect_candidate_baseline.py` derives an exact legacy timestamp decoder and calls the historical read-only device inspection runner. Input: a fresh simple `--label`, the exact retained inspector/precheck files and existing private ownership evidence. Outputs: a new private `inspection-preparation-LABEL` directory with actual owner, decoder/runner backups, derivation receipt and the inspection runner's outputs. It does contact the configured Pi when run; it must not overlap active compute/capture. It does not change model assets or the desktop. The fixed historical caller path and reviewed decoder boundary must still exist exactly; do not adapt them silently.

`prepare_xvf_recovery.py` performs local-only backup/readback and prepares a finite recovery payload from an actual closed source fault and fresh baseline. Inputs: `--baseline` JSON, `--fault-mirror` complete closed monitor directory, fresh `--output` directory and `--label`. It requires the exact active-stream AEC255 fault, matching boot, pinned previously exercised utility and full config/display/install bytes. Outputs: before/restore copies, `PAYLOAD.json`, copied source-close receipt, source backups and `HOST_BACKUP_VERIFIED.json`. It sends no SSH/device command. Its original V1 payload is historical; the later reviewed recovery action has a separate README and pins. A failed eligibility check is not permission to reset hardware.

Set `PY` to `C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`, `N` to this source directory and all input/output variables to reviewed absolute paths. Use a new label/output; preserve failed bytes.

Original interfaces in PowerShell:

```powershell
& $PY -B "$N/inspect_candidate_baseline.py" --label $LABEL
& $PY -B "$N/prepare_xvf_recovery.py" --baseline $BASELINE --fault-mirror $FAULT_MIRROR --output $FRESH_PRIVATE_OUTPUT --label $LABEL
```

CMD or Anaconda Prompt:

```bat
"%PY%" -B "%N%\inspect_candidate_baseline.py" --label "%LABEL%"
"%PY%" -B "%N%\prepare_xvf_recovery.py" --baseline "%BASELINE%" --fault-mirror "%FAULT_MIRROR%" --output "%FRESH_PRIVATE_OUTPUT%" --label "%LABEL%"
```

The exact closed fault, fresh resource/owner inspection, complete independent backups and explicit selected action remain separate prerequisites. Documentation is not a blanket recovery or native-run authorization.
