# First Start microphone repair

Purpose: inspect the actual shared XVF failure in build26, then document the versioned repair. Inputs are the exact build26 package manifest and current closed session receipts. The read-only action returns bounded private source/worker/launch diagnostics and hashes; it opens no capture and sends no device command. Use only the guarded dispatcher after a fresh source freeze and independent restore/readback. It creates a unique private output and checks current boot, owners, leases and resources.

PowerShell:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$source/host_stabilization_operations_v5.py" --label first-start-diagnostics-01 --action "$source/inspect_first_start_failure.py" --payload "$prepared/PAYLOAD.json"
```

CMD / Anaconda Prompt (set SOURCE and PREPARED to the source and fresh frozen-input directories):
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%SOURCE%/host_stabilization_operations_v5.py" --label first-start-diagnostics-01 --action "%SOURCE%/inspect_first_start_failure.py" --payload "%PREPARED%/PAYLOAD.json"
```

Labels are one-use. Failed or completed outputs remain immutable. Do not send a reset based on a photo or an inactive-stream read. A repair requires actual zero-sample AEC255 failure and exact physical closure.

For version replacement, `normal_current_gui_exit.py` invokes only the freshly inspected Settings / Exit to desktop control in the exact current Tk PID. Inputs additionally pin actual GUI/supervisor PID/start ticks/boot, unit and its ownership file. It requires closed capture and no other project process, waits for natural exact owner absence and never forcibly terminates the app. Run with `host_current_gui_exit.py`, `--action normal_current_gui_exit.py`, a fresh `--label first-start-normal-exit-01` and the independently restored payload. Omit `--writes`: no hardware/config/recording mutation occurs; normal GUI closure writes its ordinary existing receipts. The same PowerShell/CMD/Anaconda Python invocation above applies with these script/argument names.

If the field application is still open and idle, use `host_first_start_diagnostics.py` in place of `host_stabilization_operations_v5.py`. This derivative permits only the exact SHA-bound read-only inspector and forbids `--writes`. It reports active GUI identities without stopping them, retaining all owner/lifetime reads, closed-capture/lease/resource guards and natural inspector closure. The original diagnostics01 safely rejected an active GUI before its action; that output remains preserved. First run `prepare_first_start_inspection.py` with the same Python command to freeze the new sources and obtain PREPARED. Then use fresh label `first-start-diagnostics-02`.
