# S6D read-only preflight

Purpose: enumerate XVF endpoints, acquire the existing recorder hardware lock for read-only control queries, record the current firmware/linear-array identity and full exposed settings, and check RAM/disk reserves. It opens no audio stream, sets no device parameter, and changes no Windows audio routing. This receipt never authorizes packed playback.

Inputs: the existing measurement_app/core.py, installed xvf_host.exe and sounddevice environment; a fresh directory below simulation/reports/S6D. The existing hardware.lock must be available. Existing recorder services or hardware processes block access. The unrelated H2 storage maintainer is observed and preserved.

Outputs: PREFLIGHT.json, initial_params_dump.txt if available, and exact original command stdout/stderr/JSONL receipts. Blocked or missing-device status is retained with explicit errors; it is not a capture failure or PASS. Use a new preflight suffix after reconnect; preserve the previous observation.

PowerShell:
```powershell
$s6dSim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
& 'C:\Users\amiri\anaconda3\python.exe' "$s6dSim\scripts\s6d_preflight_v2.py" --report "$s6dSim\reports\S6D\20260913T195357Z\preflight_v2"
```

Anaconda Prompt / CMD:
```bat
set "S6D_SIM=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\anaconda3\python.exe" "%S6D_SIM%\scripts\s6d_preflight_v2.py" --report "%S6D_SIM%\reports\S6D\20260913T195357Z\preflight_v2"
```

An occupied report path is rejected rather than overwritten. A successful read-only preflight must still be followed by fresh analog-output safety confirmation, exact routing qualification and the source-bound S6D capture gates. Dynamic Windows volumes may require Win32 logical-disk associations to identify their SSD; a volume label alone is not physical-drive proof.


The recorder vendor dependencies are CPython 3.12 binaries; use the established Anaconda 3.12 capture interpreter above. The separate edge-speech environment remains the model interpreter. An initial S6D preflight invocation with edge-speech Python 3.11 failed during import, before any report directory, audio stream, control query or hardware lock was opened; no device or dependency was changed.

V2 replaces only the legacy psutil5.9 disk_usage call with standard-library shutil.disk_usage and records exception traces. The V1 Anaconda attempt stopped during the C-drive resource query before any hardware access; its blocked PREFLIGHT.json remains unchanged. No dependency installation or source data change was required.
